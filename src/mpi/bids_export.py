"""Export the selected breathing streams and event markers as behavioral BIDS files."""

from __future__ import annotations

import csv
import gzip
import json
import math
import os
import re
import statistics
import tempfile
from pathlib import Path

import pyxdf


def _stream(streams, identity):
    matches = [stream for stream in streams if stream["info"]["source_id"][0] == identity]
    if len(matches) != 1 or not len(matches[0]["time_stamps"]):
        raise ValueError(f"BIDS export is missing required XDF stream {identity}")
    return matches[0]


def _frequency(stamps):
    if len(stamps) < 2:
        raise ValueError("BIDS physiology needs at least two samples")
    intervals = [float(b - a) for a, b in zip(stamps[:-1], stamps[1:]) if b > a]
    if not intervals:
        raise ValueError("BIDS physiology needs increasing sample timestamps")
    return round(1 / statistics.median(intervals), 6)


def _physio(stream, destination, origin, label):
    stamps = stream["time_stamps"]
    series = stream["time_series"]
    columns = ["timestamp", *[f"channel{index + 1}" for index in range(len(series[0]))]]
    metadata = {
        "SamplingFrequency": _frequency(stamps),
        "StartTime": round(float(stamps[0]) - origin, 6),
        "Columns": columns,
        "PhysioType": "generic",
        "Description": f"{label} LSL samples. The timestamp column preserves each sample's actual recorded time; SamplingFrequency is the median observed rate.",
        "timestamp": {"Description": "Seconds relative to the first selected raw breathing sample", "Units": "s"},
    }
    desc = (stream["info"].get("desc") or [{}])[0] or {}
    channels = ((desc.get("channels") or [{}])[0] or {}).get("channel", [])
    for index, name in enumerate(columns[1:]):
        channel = channels[index] if index < len(channels) else {}
        title = channel.get("label", [name])[0]
        unit = channel.get("unit", [""])[0]
        metadata[name] = {"Description": f"{label}: {title}"}
        if unit:
            metadata[name]["Units"] = unit
    with gzip.open(str(destination) + ".tsv.gz", "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        for stamp, row in zip(stamps, series):
            values = []
            for value in row:
                number = float(value)
                values.append(format(number, ".9g") if math.isfinite(number) else "n/a")
            writer.writerow([format(float(stamp) - origin, ".9f"), *values])
    destination.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def export_bids(xdf_path: Path, output: Path, required: tuple[str, ...], participant: str, session: str):
    """Write a small BIDS behavioral dataset after a verified XDF closes."""
    if len(required) < 3:
        raise ValueError("BIDS export needs raw, marker, and calibrated stream identities")
    subject = participant.removeprefix("P")
    if not re.fullmatch(r"\d{3}", subject) or not re.fullmatch(r"[A-Za-z0-9]+", session):
        raise ValueError("Participant or session cannot be used in a BIDS filename")
    streams, _ = pyxdf.load_xdf(str(xdf_path), select_streams=[{"source_id": identity} for identity in required[:3]],
                                dejitter_timestamps=False)
    raw, markers, calibrated = (_stream(streams, identity) for identity in required[:3])
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
        readme.write_text("Respyra behavioral breathing tracking. Events and selected breathing streams are exported from the verified XDF. Exact LSL samples, timestamps, additional streams, and the original CSV files remain in the parent recording folder. Physiology files retain actual sample times in their timestamp column; SamplingFrequency is the median observed rate.\n", encoding="utf-8")
    directory = root / f"sub-{subject}" / f"ses-{session}" / "beh"
    prefix = f"sub-{subject}_ses-{session}_task-respyra"
    runs = [int(match.group(1)) for path in directory.glob(f"{prefix}_run-*_events.tsv")
            if (match := re.fullmatch(re.escape(prefix) + r"_run-(\d+)_events\.tsv", path.name))]
    stem = f"{prefix}_run-{max(runs, default=0) + 1:02d}"
    with tempfile.TemporaryDirectory(prefix=".bids-export-", dir=output) as temporary:
        staging = Path(temporary)
        events = staging / f"{stem}_events.tsv"
        with events.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(["onset", "duration", "trial_type", "trial", "condition", "phase", "screen"])
            rows = []
            for stamp, sample in zip(markers["time_stamps"], markers["time_series"]):
                event = json.loads(sample[0])
                if not isinstance(event, dict) or not isinstance(event.get("event"), str):
                    raise ValueError("XDF contains an invalid Respyra marker")
                rows.append((float(stamp) - origin, event))
            for onset, event in sorted(rows, key=lambda row: row[0]):
                writer.writerow([format(onset, ".9f"), 0, event["event"],
                                 *[(str(event.get(key)) if event.get(key) is not None else "n/a")
                                   for key in ("trial", "condition", "phase", "screen")]])
        events.with_suffix(".json").write_text(json.dumps({
            "onset": {"Description": "Seconds relative to the first selected raw breathing sample"},
            "duration": {"Description": "Point event duration in seconds"},
            "trial_type": {"Description": "Respyra event catalog name"},
            "trial": {"Description": "Trial number, when applicable"},
            "condition": {"Description": "Study condition, when applicable"},
            "phase": {"Description": "Study phase, when applicable"},
            "screen": {"Description": "Study screen, when applicable"},
        }, indent=2) + "\n", encoding="utf-8")
        _physio(raw, staging / f"{stem}_recording-raw_physio", origin, "Selected raw breathing")
        _physio(calibrated, staging / f"{stem}_recording-calibrated_physio", origin, "Respyra calibrated breathing")
        directory.mkdir(parents=True, exist_ok=True)
        for path in staging.iterdir():
            os.replace(path, directory / path.name)
    return directory
