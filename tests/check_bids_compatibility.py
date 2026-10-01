"""Check one recorded XDF/BIDS run against BIDS, MNE-BIDS and MNE-Python."""

import argparse
import csv
import gzip
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import mne_bids
import pyxdf

from mpi.bids_mne import read_bids_signal


def read_table(path, metadata):
    with (gzip.open(path, "rt", encoding="utf-8", newline="") if path.suffix == ".gz"
          else path.open(encoding="utf-8", newline="")) as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    if path.name.endswith("_physio.tsv.gz"):
        return metadata["Columns"], rows
    return rows[0], rows[1:]


def check(xdf, events, resample_hz):
    events_path = mne_bids.get_bids_path_from_fname(events)
    assert events_path.suffix == "events" and events_path.datatype == "beh"
    assert events_path.fpath.resolve() == events.resolve()
    root = events.parents[3]
    assert (root / "dataset_description.json").exists()
    streams, _ = pyxdf.load_xdf(str(xdf), dejitter_timestamps=False)
    by_id = {str(stream["info"]["stream_id"]): stream for stream in streams}
    marker_streams = [stream for stream in streams
                      if (stream["info"]["source_id"][0] or "").startswith("respyra-events-")]
    assert len(marker_streams) == 1
    tables = []
    for path in events.parent.iterdir():
        if not (path.name.endswith("_physio.tsv.gz") or path.name.endswith("_beh.tsv")):
            continue
        bids_path = mne_bids.get_bids_path_from_fname(path)
        if all(getattr(bids_path, key) == getattr(events_path, key)
               for key in ("subject", "session", "task", "run")):
            assert bids_path.datatype == "beh" and bids_path.basename == path.name
            assert bids_path.fpath.resolve() == path.resolve()
            tables.append(path)
    sidecars = {}
    for path in tables:
        metadata = json.loads(path.with_suffix("").with_suffix(".json").read_text(encoding="utf-8"))
        source = by_id[metadata["LSLSource"]["XDFStreamID"]]
        sidecars[path] = (metadata, source)
    raw = next(source for path, (metadata, source) in sidecars.items()
               if mne_bids.get_bids_path_from_fname(path).recording == "raw"
               or mne_bids.get_bids_path_from_fname(path).acquisition == "raw")
    origin = float(raw["time_stamps"][0])
    represented = set()
    opened = 0
    samples = 0
    for path, (metadata, source) in sidecars.items():
        info = source["info"]
        stream_id = str(info["stream_id"])
        assert stream_id not in represented
        represented.add(stream_id)
        assert metadata["LSLSource"]["SourceID"] == info["source_id"][0]
        assert metadata["LSLSource"]["Name"] == info["name"][0]
        assert metadata["LSLSource"]["ChannelFormat"] == info["channel_format"][0]
        columns, rows = read_table(path, metadata)
        assert columns[0] == "timestamp" and len(rows) == len(source["time_stamps"])
        assert len(columns) - 1 == int(info["channel_count"][0])
        if path.name.endswith("_physio.tsv.gz"):
            nominal = float(info["nominal_srate"][0])
            assert nominal > 0 and metadata["SamplingFrequency"] == nominal
            assert all(abs(float(b - a) - 1 / nominal) <= 0.02 / nominal
                       for a, b in zip(source["time_stamps"][:-1], source["time_stamps"][1:]))
        else:
            assert "SamplingFrequency" not in metadata
        channels = (((info.get("desc") or [{}])[0] or {}).get("channels") or [{}])[0].get("channel", [])
        for index, column in enumerate(columns[1:]):
            channel = channels[index] if index < len(channels) else {}
            assert metadata[column]["LongName"] == (channel.get("label") or [column])[0]
            assert metadata[column].get("Units", "") == (channel.get("unit") or [""])[0]
        kind = info["channel_format"][0]
        for row, stamp, values in zip(rows, source["time_stamps"], source["time_series"]):
            assert abs(float(row[0]) - (float(stamp) - origin)) <= 1e-9
            for cell, value in zip(row[1:], values):
                if kind == "string":
                    assert cell == str(value)
                elif kind.startswith("int"):
                    assert int(cell) == int(value)
                elif cell == "n/a":
                    assert not math.isfinite(float(value))
                else:
                    assert math.isclose(float(cell), float(value), rel_tol=1e-8, abs_tol=1e-8)
        samples += len(rows)
        if kind != "string":
            result, stamps = read_bids_signal(path, sfreq=None if path.suffix == ".gz" else resample_hz)
            assert result.n_times > 0 and len(result.ch_names) == len(columns) - 1
            assert len(stamps) == len(rows)
            opened += 1
    expected = {str(stream["info"]["stream_id"]) for stream in streams
                if len(stream["time_stamps"]) and stream is not marker_streams[0]}
    assert represented == expected, {"missing": expected - represented, "extra": represented - expected}
    with events.open(encoding="utf-8", newline="") as handle:
        event_rows = list(csv.DictReader(handle, delimiter="\t"))
    assert len(event_rows) == len(marker_streams[0]["time_stamps"])
    markers = sorted(zip(marker_streams[0]["time_stamps"], marker_streams[0]["time_series"]),
                     key=lambda item: item[0])
    for row, (stamp, sample) in zip(event_rows, markers):
        assert abs(float(row["onset"]) - (float(stamp) - origin)) <= 1e-9
        assert row["trial_type"] == json.loads(sample[0])["event"]
    pnpm = shutil.which("pnpm.cmd") or shutil.which("pnpm")
    assert pnpm, "pnpm is required for the BIDS validator gate"
    validator = subprocess.run([pnpm, "dlx", "bids-validator@1.15.0", str(root), "--json"],
                               capture_output=True, text=True, check=False,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    report = json.loads(validator.stdout)
    assert validator.returncode == 0 and not report["issues"]["errors"], report["issues"]["errors"]
    print(json.dumps({"result": "passed", "xdf": str(xdf), "streams": len(represented),
                      "samples": samples, "mne_raw_opened": opened,
                      "bids_errors": 0, "bids_warnings": [item["key"] for item in report["issues"]["warnings"]]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xdf", required=True, type=Path)
    parser.add_argument("--events", required=True, type=Path, help="Events TSV for the matching BIDS run")
    parser.add_argument("--resample-hz", type=float, default=100,
                        help="Explicit MNE grid for irregular numeric streams")
    args = parser.parse_args()
    check(args.xdf, args.events, args.resample_hz)
