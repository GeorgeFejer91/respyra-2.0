import csv

import numpy as np

from scripts.xdf_to_csv import export


def test_export_numeric_markers_and_empty_stream(tmp_path, monkeypatch):
    def stream(name, label, unit, times, values):
        return {"info": {"name": [name], "channel_count": ["1"],
                         "desc": [{"channels": [{"channel": [{"label": [label], "unit": [unit]}]}]}]},
                "time_stamps": times, "time_series": values}

    streams = [
        stream("Mock Force", "Force", "N", [1.0, 1.02], np.array([[5.0], [6.0]])),
        stream("Mock Markers", "Event", "", [1.01], [["{\"event\":\"trial.started\"}"]]),
        stream("Mock Empty", "Status", "0/1", [], np.empty((0, 1))),
    ]
    monkeypatch.setattr("pyxdf.load_xdf", lambda *args, **kwargs: (streams, {}))
    output = export(tmp_path / "example.xdf")

    with (output / "01_Mock_Force.csv").open(newline="", encoding="utf-8") as file:
        assert list(csv.reader(file)) == [["lsl_time_s", "ch1_Force [N]"], ["1.0", "5.0"], ["1.02", "6.0"]]
    with (output / "02_Mock_Markers.csv").open(newline="", encoding="utf-8") as file:
        assert list(csv.reader(file))[1] == ["1.01", '{"event":"trial.started"}']
    with (output / "03_Mock_Empty.csv").open(newline="", encoding="utf-8") as file:
        assert list(csv.reader(file)) == [["lsl_time_s", "ch1_Status [0/1]"]]
