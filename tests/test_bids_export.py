import csv
import gzip
import json

import pytest

from mpi.bids_export import export_bids


def test_bids_export_writes_events_and_timed_breathing(monkeypatch, tmp_path):
    def stream(identity, stamps, rows):
        return {"info": {"source_id": [identity], "channel_format": ["float32"],
                         "channel_count": ["1"], "nominal_srate": ["10"]},
                "time_stamps": stamps, "time_series": rows}

    raw = stream("raw", [10.0, 10.1, 10.2], [[1.0], [2.0], [3.0]])
    raw["info"]["desc"] = [None]
    markers = stream("markers", [10.05, 10.2], [
        [json.dumps({"event": "trial.started", "trial": 1, "condition": "normal"})],
        [json.dumps({"event": "trial.ended", "trial": 1})],
    ])
    markers["info"]["channel_format"] = ["string"]
    calibrated = stream("calibrated", [10.0, 10.1, 10.2], [[float("nan")], [0.5], [0.75]])
    mini = stream("mini-acc", [10.02, 10.07, 10.15], [[0.1], [float("nan")], [0.3]])
    mini["info"].update({"name": ["Polar ACC"], "nominal_srate": ["0"],
                         "desc": [{"channels": [{"channel": [{"label": ["ACC X"], "unit": ["g"]}]}]}]})
    ecg = stream("mini-ecg", [10.0, 10.1, 10.2], [[1.0], [2.0], [3.0]])
    ecg["info"].update({"name": ["Polar ECG"], "desc": [{"processing": ["raw"]}]})
    status = stream("mini-status", [10.12], [["ready"]])
    status["info"]["channel_format"] = ["string"]
    counter = stream("mini-counter", [10.12], [[2**53 + 1]])
    counter["info"]["channel_format"] = ["int64"]
    double = stream("vernier-double", [10.13], [[1.2345678901234567]])
    double["info"]["channel_format"] = ["double64"]
    empty = stream("mini-empty", [], [])
    monkeypatch.setattr("pyxdf.load_xdf", lambda *args, **kwargs: ([raw, markers, calibrated, mini, ecg, status, counter, double, empty], {}))

    for run in (1, 2):
        directory = export_bids(tmp_path / "recording.xdf", tmp_path, ("raw", "markers", "calibrated"), "P002", "001")
        stem = f"sub-002_ses-001_task-respyra_run-{run:02d}"
        with (directory / f"{stem}_events.tsv").open(encoding="utf-8", newline="") as handle:
            events = list(csv.DictReader(handle, delimiter="\t"))
        assert [row["trial_type"] for row in events] == ["trial.started", "trial.ended"]
        assert events[0]["onset"] == "0.050000000"
        with gzip.open(directory / f"{stem}_recording-calibrated_physio.tsv.gz", "rt", encoding="utf-8") as handle:
            assert list(csv.reader(handle, delimiter="\t")) == [
                ["0.000000000", "n/a"], ["0.100000000", "0.5"], ["0.200000000", "0.75"]]
        sidecar = json.loads((directory / f"{stem}_recording-raw_physio.json").read_text(encoding="utf-8"))
        assert sidecar["Columns"] == ["timestamp", "channel1"]
        assert sidecar["SamplingFrequency"] == 10
        irregular = f"sub-002_ses-001_task-respyra_acq-lsl01_run-{run:02d}_beh"
        with (directory / f"{irregular}.tsv").open(encoding="utf-8", newline="") as handle:
            assert list(csv.reader(handle, delimiter="\t")) == [
                ["timestamp", "channel1"], ["0.020000000", "0.1"],
                ["0.070000000", "n/a"], ["0.150000000", "0.3"]]
        mini_sidecar = json.loads((directory / f"{irregular}.json").read_text(encoding="utf-8"))
        assert mini_sidecar["channel1"]["LongName"] == "ACC X"
        assert mini_sidecar["channel1"]["Units"] == "g"
        assert mini_sidecar["LSLSource"]["SourceID"] == "mini-acc"
        assert "SamplingFrequency" not in mini_sidecar
        assert (directory / f"{stem}_recording-lsl02_physio.tsv.gz").exists()
        assert (directory / f"sub-002_ses-001_task-respyra_acq-lsl03_run-{run:02d}_beh.tsv").exists()
        counter_path = directory / f"sub-002_ses-001_task-respyra_acq-lsl04_run-{run:02d}_beh.tsv"
        assert counter_path.read_text(encoding="utf-8").splitlines()[1].endswith(str(2**53 + 1))
        double_path = directory / f"sub-002_ses-001_task-respyra_acq-lsl05_run-{run:02d}_beh.tsv"
        assert float(double_path.read_text(encoding="utf-8").splitlines()[1].split("\t")[1]) == 1.2345678901234567
        assert not list(directory.glob(f"*lsl06*run-{run:02d}*"))
    assert json.loads((tmp_path / "bids/dataset_description.json").read_text())["BIDSVersion"] == "1.11.2"
    markers["time_series"][0] = ["invalid json"]
    with pytest.raises(json.JSONDecodeError):
        export_bids(tmp_path / "recording.xdf", tmp_path, ("raw", "markers", "calibrated"), "P002", "001")
    assert not list(directory.glob("*_run-03_*"))
