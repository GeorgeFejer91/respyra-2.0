"""Export each XDF stream to a timestamped CSV in <recording>_csv/.

Python 3.10+: python -m pip install pyxdf==1.17.5
Usage: python xdf_to_csv.py recording.xdf
"""

import argparse
import csv
import re
from pathlib import Path

import pyxdf


def export(path: Path) -> Path:
    streams, _ = pyxdf.load_xdf(str(path), dejitter_timestamps=False)
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
            writer.writerow(["lsl_time_s", *headers])
            for timestamp, sample in zip(stream["time_stamps"], stream["time_series"], strict=True):
                if len(sample) != count:
                    raise ValueError(f"{name}: expected {count} channels, got {len(sample)}")
                writer.writerow([timestamp, *sample])
        print(f"{csv_path}: {len(stream['time_stamps'])} samples")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xdf", type=Path, help="recording.xdf")
    args = parser.parse_args()
    if not args.xdf.is_file():
        parser.error(f"XDF file not found: {args.xdf}")
    export(args.xdf)
