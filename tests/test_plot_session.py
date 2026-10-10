"""The XDF adapter feeds the same statistics/figure as equivalent CSV samples."""

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from scripts.plot_session import compute_baseline_cal, compute_trial_stats, load_session, plot_session
from mpi.session_summary import save_xdf_summary


def recording(unit="N"):
    scale = 0.01 if unit == "g" else 1
    polarity = -1 if unit == "g" else 1
    stamps = np.array([1.05, 1.3, 2.1, 2.4, 2.8, 3.125, 3.25, 3.875, 4.125, 4.625, 4.875, 6.0])
    signal = (5 + np.sin(stamps)) * scale
    channel = {"unit": [unit], "sensor_number": ["1"], "type": ["RawMeasurement"]}
    raw = {"info": {"name": ["arbitrary name"], "source_id": ["selected"],
                    "desc": [{"channels": [{"channel": [{"unit": ["bpm"]}, channel]}]}]},
           "time_stamps": np.insert(stamps, 7, 3.4),
           "time_series": np.column_stack([np.zeros(len(stamps) + 1),
                                            np.insert(signal * polarity, 7, 999)])}
    derived = {"info": {"source_id": ["respyra-breathing-test"],
                        "desc": [{"raw_source_id": ["selected"], "role": ["feedback"],
                                  "input_contract": ["respyra-polar-pca/1" if unit == "g" else ""]}]},
               "time_stamps": stamps + 0.00001, "time_series": np.zeros((len(stamps), 1))}
    events = []

    def event(t, name, **fields):
        events.append((t, {"event": name, "run_id": "test", "trial": 1, "condition": "deep", **fields}))

    event(1, "calibration.attempt.started", trial=None, condition=None)
    event(1.5, "calibration.attempt.ended")
    event(1.6, "calibration.completed", input_polarity=polarity)
    event(2, "baseline.started")
    event(2.5, "baseline.ended")
    event(2.7, "countdown.started")
    event(2.9, "countdown.ended")
    event(3, "tracking.started", target_center_value=5 * scale, target_amplitude_value=2 * scale,
          feedback_gain=0.5, segments=[{"freq_hz": 1, "n_cycles": 1}, {"freq_hz": 2, "n_cycles": 1}])
    event(5, "tracking.ended")
    marker = {"info": {"name": ["renamed markers"], "desc": [{"schema": ["respyra-event-markers-v1"]}]},
              "time_stamps": [t for t, _ in events], "time_series": [[json.dumps(e)] for _, e in events]}
    # Unselected, large-valued candidate and empty metadata must not affect selection.
    comparison = {"info": {"source_id": ["respyra-comparison-test"],
                           "desc": [{"raw_source_id": ["other"], "role": ["comparison"]}]}}
    empty = {"info": {"desc": [None]}}
    return [comparison, empty, raw, marker, derived], signal[:-1]


@pytest.mark.parametrize("unit,contract", [("N", ""), ("g", "respyra-polar-pca/1"),
                                          ("g", "respyra-polar-phan-signed/1")])
def test_xdf_and_csv_produce_same_statistics_and_six_panels(tmp_path, monkeypatch, unit, contract):
    streams, signal = recording(unit)
    streams[-1]["info"]["desc"][0]["input_contract"] = [contract]

    def read(*args, **kwargs):
        assert kwargs == {"synchronize_clocks": True, "dejitter_timestamps": False}
        return streams, {}

    monkeypatch.setattr("pyxdf.load_xdf", read)
    xdf = load_session(tmp_path / "only.XDF")
    np.testing.assert_allclose(xdf.force_n, signal)
    assert list(xdf.phase) == ["range_cal"] * 2 + ["baseline"] * 2 + ["countdown"] + ["tracking"] * 6
    assert xdf.session_time.is_monotonic_increasing
    tracking = xdf[xdf.phase == "tracking"]
    t = tracking.timestamp.to_numpy() % 1.5
    expected_target = (5 + 2 * np.where(t < 1, np.sin(2 * np.pi * t), np.sin(4 * np.pi * (t - 1))))
    expected_target *= 0.01 if unit == "g" else 1
    np.testing.assert_allclose(tracking.target_force, expected_target)
    np.testing.assert_allclose(tracking.error, expected_target - tracking.force_n)
    center = 0.05 if unit == "g" else 5
    np.testing.assert_allclose(tracking.compensated_error, expected_target - (center + 0.5 * (tracking.force_n - center)))

    csv = xdf.drop(columns="session_time")
    if unit == "g":
        csv = csv.rename(columns={"force_n": "signal_g", "target_force": "target_signal_g",
                                  "error": "error_g", "compensated_error": "compensated_error_g"})
    csv_path = tmp_path / "session.csv"
    csv.to_csv(csv_path, index=False)
    csv = load_session(csv_path)
    pd.testing.assert_frame_equal(compute_trial_stats(xdf), compute_trial_stats(csv))
    pd.testing.assert_frame_equal(compute_baseline_cal(xdf), compute_baseline_cal(csv))
    fig = plot_session(xdf, "only.xdf")
    assert len(fig.axes) == 6 and fig.axes[0].get_ylabel().endswith(f"({unit})")
    fig.savefig(tmp_path / "summary.png")
    assert (tmp_path / "summary.png").stat().st_size > 10000
    plt.close(fig)
    assert save_xdf_summary(tmp_path / "only.XDF") == tmp_path / "only_summary.png"
    assert not plt.get_fignums()


def test_stopped_phase_and_missing_or_ambiguous_input(tmp_path, monkeypatch):
    streams, _ = recording()
    markers = streams[3]
    markers["time_series"][-1] = [json.dumps({"event": "run.aborted", "run_id": "test"})]
    markers["time_stamps"][-1] = 4
    monkeypatch.setattr("pyxdf.load_xdf", lambda *args, **kwargs: (streams, {}))
    assert len(load_session(tmp_path / "stopped.xdf").query("phase == 'tracking'")) == 3
    markers["time_stamps"].append(2.6)
    markers["time_series"].append([json.dumps({"event": "baseline.calculated", "run_id": "test",
                                              "trial": 1, "condition": "deep",
                                              "center_value": 5.5, "amplitude_value": 0.7})])
    cal = compute_baseline_cal(load_session(tmp_path / "stopped.xdf"))
    assert cal.center.tolist() == [5.5] and cal.amplitude.tolist() == [0.7]
    streams[2]["time_stamps"] += 100
    with pytest.raises(ValueError, match="Cannot pair"):
        load_session(tmp_path / "unpaired.xdf")
    streams[2]["time_stamps"] -= 100
    streams.append(streams[2])
    with pytest.raises(ValueError, match="ambiguous"):
        load_session(tmp_path / "ambiguous.xdf")
    streams.pop()
    streams.pop(3)
    with pytest.raises(ValueError, match="marker stream"):
        load_session(tmp_path / "no-markers.xdf")


def test_assessment_csv_fails_clearly(tmp_path):
    path = tmp_path / "assessment.csv"
    path.write_text("trial_num,accuracy\n1,4\n", encoding="utf-8")
    with pytest.raises(ValueError, match="self-assessment"):
        load_session(path)


def test_pre_study_stop_has_no_summary(tmp_path, monkeypatch):
    streams, _ = recording()
    marker = streams[3]
    marker["time_series"] = [[json.dumps({"event": "recording.started", "run_id": "test"})]]
    marker["time_stamps"] = [0.5]
    monkeypatch.setattr("pyxdf.load_xdf", lambda *args, **kwargs: (streams, {}))
    assert save_xdf_summary(tmp_path / "stopped.xdf") is None
    assert not list(tmp_path.glob("*.png"))
