import csv
import gzip
import json

import pytest

from mpi.bids_export import export_bids


def test_bids_export_writes_events_and_timed_breathing(monkeypatch, tmp_path):
    def stream(identity, stamps, rows):
        return {"info": {"source_id": [identity]}, "time_stamps": stamps, "time_series": rows}

    raw = stream("raw", [10.0, 10.1, 10.22], [[1.0], [2.0], [3.0]])
    raw["info"]["desc"] = [None]
    markers = stream("markers", [10.05, 10.2], [
        [json.dumps({"event": "trial.started", "trial": 1, "condition": "normal"})],
        [json.dumps({"event": "trial.ended", "trial": 1})],
    ])
    calibrated = stream("calibrated", [10.0, 10.1, 10.22], [[float("nan")], [0.5], [0.75]])
    monkeypatch.setattr("pyxdf.load_xdf", lambda *args, **kwargs: ([raw, markers, calibrated], {}))

    for run in (1, 2):
        directory = export_bids(tmp_path / "recording.xdf", tmp_path, ("raw", "markers", "calibrated"), "P002", "001")
        stem = f"sub-002_ses-001_task-respyra_run-{run:02d}"
        with (directory / f"{stem}_events.tsv").open(encoding="utf-8", newline="") as handle:
            events = list(csv.DictReader(handle, delimiter="\t"))
        assert [row["trial_type"] for row in events] == ["trial.started", "trial.ended"]
        assert events[0]["onset"] == "0.050000000"
        with gzip.open(directory / f"{stem}_recording-calibrated_physio.tsv.gz", "rt", encoding="utf-8") as handle:
            assert list(csv.reader(handle, delimiter="\t")) == [
                ["0.000000000", "n/a"], ["0.100000000", "0.5"], ["0.220000000", "0.75"]]
        sidecar = json.loads((directory / f"{stem}_recording-raw_physio.json").read_text(encoding="utf-8"))
        assert sidecar["Columns"] == ["timestamp", "channel1"]
        assert sidecar["SamplingFrequency"] > 0
    assert json.loads((tmp_path / "bids/dataset_description.json").read_text())["BIDSVersion"] == "1.11.2"
    markers["time_series"][0] = ["invalid json"]
    with pytest.raises(json.JSONDecodeError):
        export_bids(tmp_path / "recording.xdf", tmp_path, ("raw", "markers", "calibrated"), "P002", "001")
    assert not list(directory.glob("*_run-03_*"))
