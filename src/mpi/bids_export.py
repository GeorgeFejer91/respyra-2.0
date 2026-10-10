"""Export recorded LSL streams to timed BIDS behavioral files."""

from __future__ import annotations

import csv
import gzip
import json
import math
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

import pyxdf
from mpi.time_reference import BERLIN, iso_time, recorded_reference, timestamp_fields


def _stream(streams, identity):
    matches = [stream for stream in streams if stream["info"]["source_id"][0] == identity]
    if len(matches) != 1 or not len(matches[0]["time_stamps"]):
        raise ValueError(f"BIDS export is missing required XDF stream {identity}")
    return matches[0]


def _field(info, key, default=""):
    value = info.get(key, default)
    return value[0] if isinstance(value, list) and value else (default if value is None else value)


def _regular_frequency(stream):
    """A nominal rate alone does not make dropped or irregular samples continuous."""
    stamps = stream["time_stamps"]
    try:
        nominal = float(_field(stream["info"], "nominal_srate", 0))
    except (TypeError, ValueError):
        return None
    if nominal <= 0 or len(stamps) < 2:
        return None
    period = 1 / nominal
    if any(not math.isfinite(float(b - a)) or abs(float(b - a) - period) > period * 0.02
           for a, b in zip(stamps[:-1], stamps[1:])):
        return None
    return nominal


def _write_signal(stream, destination, origin, label, reference=None):
    stamps = stream["time_stamps"]
    series = stream["time_series"]
    if not len(stamps):
        return
    if any(not math.isfinite(float(stamp)) for stamp in stamps) or any(b <= a for a, b in zip(stamps[:-1], stamps[1:])):
        raise ValueError("XDF stream timestamps must be finite and strictly increasing")
    count = int(_field(stream["info"], "channel_count", len(series[0])))
    if any(len(row) != count for row in series):
        raise ValueError("XDF stream channel count changed during recording")
    columns = ["timestamp", *[f"channel{index + 1}" for index in range(count)]]
    channel_format = _field(stream["info"], "channel_format")
    numeric = channel_format != "string"
    frequency = _regular_frequency(stream) if numeric else None
    info = stream["info"]
    metadata = {
        "TaskName": "Respyra breathing tracking",
        "Description": f"{label} LSL samples with source timestamps relative to the first selected raw breathing sample.",
        "timestamp": {"Description": "Seconds relative to the first selected raw breathing sample", "Units": "s"},
        "LSLSource": {"Name": _field(info, "name"), "Type": _field(info, "type"),
                      "SourceID": _field(info, "source_id"), "XDFStreamID": str(_field(info, "stream_id")),
                      "NominalSamplingFrequency": _field(info, "nominal_srate", "0"),
                      "ChannelFormat": _field(info, "channel_format"),
                      "Metadata": _field(info, "desc", {}) or {}},
    }
    desc = (stream["info"].get("desc") or [{}])[0] or {}
    channels = ((desc.get("channels") or [{}])[0] or {}).get("channel", [])
    for index, name in enumerate(columns[1:]):
        channel = channels[index] if index < len(channels) else {}
        title = channel.get("label", [name])[0]
        unit = channel.get("unit", [""])[0]
        metadata[name] = {"Description": f"{label}: LSL channel {index + 1}", "LongName": title}
        if unit:
            metadata[name]["Units"] = unit
    if reference is not None:
        columns.extend(["lsl_time_s", "utc_unix_s", "berlin_utc_offset_s"])
        metadata.update(_clock_metadata(reference, origin))
        metadata.update({
            "lsl_time_s": {"Description": "Clock-synchronized XDF sample time without dejitter", "Units": "s"},
            "utc_unix_s": {"Description": "Estimated seconds since 1970-01-01T00:00:00Z", "Units": "s"},
            "berlin_utc_offset_s": {"Description": "Europe/Berlin offset from UTC at this sample, including DST", "Units": "s"},
        })
    if frequency is not None:
        metadata.update({"SamplingFrequency": frequency, "StartTime": round(float(stamps[0]) - origin, 9),
                         "Columns": columns, "PhysioType": "generic"})
        path = Path(str(destination) + "_physio.tsv.gz")
        open_table = lambda: gzip.open(path, "wt", encoding="utf-8", newline="")
    else:
        metadata["Timing"] = "irregular or unverified; no regular sampling rate is asserted"
        path = Path(str(destination) + "_beh.tsv")
        open_table = lambda: path.open("w", encoding="utf-8", newline="")
    with open_table() as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        if frequency is None:
            writer.writerow(columns)
        for stamp, row in zip(stamps, series):
            values = []
            for value in row:
                if numeric:
                    if channel_format.startswith("int"):
                        values.append(str(int(value)))
                    else:
                        number = float(value)
                        precision = ".17g" if channel_format in ("double64", "float64") else ".9g"
                        values.append(format(number, precision) if math.isfinite(number) else "n/a")
                else:
                    values.append(str(value))
            times = []
            if reference is not None:
                unix_time = reference["unix_anchor_s"] + (float(stamp) - reference["lsl_anchor_s"])
                offset = datetime.fromtimestamp(unix_time, BERLIN).utcoffset().total_seconds()
                times = [format(float(stamp), ".17g"), format(unix_time, ".17g"), int(offset)]
            writer.writerow([format(float(stamp) - origin, ".9f"), *values, *times])
    path.with_suffix("").with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def _clock_metadata(reference, origin):
    origin_unix = reference["unix_anchor_s"] + (origin - reference["lsl_anchor_s"])
    return {"ClockReference": reference, "TimeOriginLSL": origin,
            "TimeOriginUTC": iso_time(origin_unix),
            "TimeOriginBerlin": iso_time(origin_unix, BERLIN)}


def export_bids(xdf_path: Path, output: Path, required: tuple[str, ...], participant: str, session: str):
    """Write BIDS behavioral data for every nonempty stream after XDF closes."""
    if len(required) < 3:
        raise ValueError("BIDS export needs raw, marker, and calibrated stream identities")
    subject = participant.removeprefix("P")
    if not re.fullmatch(r"\d{3}", subject) or not re.fullmatch(r"[A-Za-z0-9]+", session):
        raise ValueError("Participant or session cannot be used in a BIDS filename")
    streams, _ = pyxdf.load_xdf(str(xdf_path), dejitter_timestamps=False)
    raw, markers, calibrated = (_stream(streams, identity) for identity in required[:3])
    reference = recorded_reference(markers)
    origin = float(raw["time_stamps"][0])
    root = output / "bids"
    root.mkdir(parents=True, exist_ok=True)
    description = root / "dataset_description.json"
    if description.exists():
        existing = json.loads(description.read_text(encoding="utf-8"))
        if existing.get("Name") != "Respyra breathing tracking" or existing.get("DatasetType") != "raw":
            raise ValueError("The BIDS folder contains a different dataset")
    else:
        description.write_text(json.dumps({"Name": "Respyra breathing tracking", "BIDSVersion": "1.11.2",
                                           "DatasetType": "raw", "GeneratedBy": [{"Name": "Respyra 2.0"}]}, indent=2) + "\n", encoding="utf-8")
    readme = root / "README"
    if not readme.exists():
        readme.write_text("Respyra behavioral data exported from verified XDF. Fixed-rate LSL signals are BIDS physiology; irregular or unverified-rate signals and other markers are timed behavioral tables. Sidecars retain source identity, channel units and LSL provenance. The parent XDF is the full source record, including empty outlets. MNE Raw requires regular sampling; irregular tables require explicit resampling for MNE analysis.\n", encoding="utf-8")
    directory = root / f"sub-{subject}" / f"ses-{session}" / "beh"
    prefix = f"sub-{subject}_ses-{session}_task-respyra"
    runs = [int(match.group(1)) for path in directory.glob(f"{prefix}_run-*_events.tsv")
            if (match := re.fullmatch(re.escape(prefix) + r"_run-(\d+)_events\.tsv", path.name))]
    run = max(runs, default=0) + 1
    stem = f"{prefix}_run-{run:02d}"
    with tempfile.TemporaryDirectory(prefix=".bids-export-", dir=output) as temporary:
        staging = Path(temporary)
        events = staging / f"{stem}_events.tsv"
        with events.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            time_columns = ["lsl_time_s", "utc_time", "berlin_time", "time_reference"] if reference else []
            writer.writerow(["onset", "duration", "trial_type", "trial", "condition", "phase", "screen", *time_columns])
            rows = []
            for stamp, sample in zip(markers["time_stamps"], markers["time_series"]):
                event = json.loads(sample[0])
                if not isinstance(event, dict) or not isinstance(event.get("event"), str):
                    raise ValueError("XDF contains an invalid Respyra marker")
                rows.append((float(stamp) - origin, event))
            for onset, event in sorted(rows, key=lambda row: row[0]):
                times = timestamp_fields(reference, onset + origin) if reference else {}
                writer.writerow([format(onset, ".9f"), 0, event["event"],
                                 *[(str(event.get(key)) if event.get(key) is not None else "n/a")
                                   for key in ("trial", "condition", "phase", "screen")],
                                 *[times[key] for key in time_columns]])
        events.with_suffix(".json").write_text(json.dumps({
            "onset": {"Description": "Seconds relative to the first selected raw breathing sample"},
            "duration": {"Description": "Point event duration in seconds"},
            "trial_type": {"Description": "Respyra event catalog name"},
            "trial": {"Description": "Trial number, when applicable"},
            "condition": {"Description": "Study condition, when applicable"},
            "phase": {"Description": "Study phase, when applicable"},
            "screen": {"Description": "Study screen, when applicable"},
            **(_clock_metadata(reference, origin) if reference else {}),
            **({"lsl_time_s": {"Description": "Clock-synchronized XDF event time", "Units": "s"},
                "utc_time": {"Description": "Estimated ISO 8601 UTC event time"},
                "berlin_time": {"Description": "Estimated ISO 8601 Europe/Berlin event time, with DST offset"},
                "time_reference": {"Description": "timeapi.io or offline system reference"}} if reference else {}),
        }, indent=2) + "\n", encoding="utf-8")
        for label, stream in (("raw", raw), ("calibrated", calibrated)):
            filename = (f"{stem}_recording-{label}" if _regular_frequency(stream) is not None
                        else f"{prefix}_acq-{label}_run-{run:02d}")
            _write_signal(stream, staging / filename, origin, label, reference)
        others = [stream for stream in streams if stream is not raw and stream is not markers and stream is not calibrated]
        for index, stream in enumerate(others, start=1):
            label = f"lsl{index:02d}"
            filename = (f"{stem}_recording-{label}" if _regular_frequency(stream) is not None
                        else f"{prefix}_acq-{label}_run-{run:02d}")
            _write_signal(stream, staging / filename, origin, label, reference)
        directory.mkdir(parents=True, exist_ok=True)
        promoted = []
        try:
            for path in staging.iterdir():
                destination = directory / path.name
                os.replace(path, destination)
                promoted.append(destination)
        except OSError:
            for path in promoted:
                path.unlink(missing_ok=True)
            raise
    return directory
