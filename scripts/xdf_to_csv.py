"""Export each XDF stream to a timestamped CSV in <recording>_csv/.

Run in the Respyra project/runtime environment (mpi and PyXDF required).
Usage: python scripts/xdf_to_csv.py recording.xdf
"""

import argparse
import csv
import re
from pathlib import Path

import pyxdf
from mpi.time_reference import TIME_COLUMNS, recorded_reference, timestamp_fields


def export(path: Path) -> Path:
    streams, _ = pyxdf.load_xdf(str(path), dejitter_timestamps=False)
    marker_streams = [stream for stream in streams
                      if (stream["info"].get("source_id") or [""])[0].startswith("respyra-events-")]
    reference = recorded_reference(marker_streams[0]) if len(marker_streams) == 1 else None
    output = path.with_name(f"{path.stem}_csv")
    output.mkdir()  # Do not overwrite an earlier export.

    for number, stream in enumerate(streams, 1):
        info = stream["info"]
        name = info["name"][0]
        count = int(info["channel_count"][0])
        channels = info.get("desc", [{}])[0].get("channels", [{}])[0].get("channel", [])
        headers = []
        for index in range(count):
            channel = channels[index] if index < len(channels) else {}
            label = channel.get("label", [f"value_{index + 1}"])[0]
            unit = channel.get("unit", [""])[0]
            headers.append(f"ch{index + 1}_{label}" + (f" [{unit}]" if unit else ""))

        safe_name = re.sub(r"\W+", "_", name).strip("_")[:60] or "stream"
        csv_path = output / f"{number:02d}_{safe_name}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            time_columns = TIME_COLUMNS[1:] if reference else []
            writer.writerow(["lsl_time_s", *headers, *time_columns])
            for timestamp, sample in zip(stream["time_stamps"], stream["time_series"], strict=True):
                if len(sample) != count:
                    raise ValueError(f"{name}: expected {count} channels, got {len(sample)}")
                times = timestamp_fields(reference, timestamp) if reference else {}
                writer.writerow([timestamp, *sample, *[times[key] for key in time_columns]])
        if reference:
            import json
            csv_path.with_suffix(".json").write_text(json.dumps({"ClockReference": reference}, indent=2) + "\n", encoding="utf-8")
        print(f"{csv_path}: {len(stream['time_stamps'])} samples")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xdf", type=Path, help="recording.xdf")
    args = parser.parse_args()
    if not args.xdf.is_file():
        parser.error(f"XDF file not found: {args.xdf}")
    export(args.xdf)
