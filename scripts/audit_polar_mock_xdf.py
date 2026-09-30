"""Audit a full Polar Mini mock study against its independently replayed ACC reference."""

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pyxdf

from mpi.recording import inspect_xdf


REFERENCE = Path(__file__).resolve().parents[1] / ".for-ai-local/polar-reference-30000.csv"
METRICS = {
    "adr_pca_waveform": "adrPcaWaveform",
    "adr_axis_mean_difference": "adrAxisMeanDifference",
    "adr_pca_valid": "adrPcaValid",
    "adr_axis_difference_valid": "adrAxisDifferenceValid",
    "adr_pca_quality": "adrPcaQuality",
}
CONTRACTS = {"pca": ("adr_pca_waveform", "respyra-polar-pca/1"),
             "phan": ("adr_axis_mean_difference", "respyra-polar-phan-signed/1")}


def _round_rust(values):
    return np.copysign(np.floor(np.abs(values) + .5), values)


def _mock_acc(count):
    index = np.arange(count, dtype=np.float64)
    phase = index * (2 * math.pi * .22 / 200)
    return np.column_stack((_round_rust(26 * np.sin(phase)),
                            _round_rust(18 * np.sin(phase + .8)),
                            _round_rust(1000 + 42 * np.sin(phase))))


def _reference(path):
    rows = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.setdefault(row["metric_id"], {})[int(row["tick"])] = float(row["value"])
    assert set(rows) == set(METRICS), f"Reference is missing metrics: {set(METRICS) - set(rows)}"
    return rows


def _nearest(source, query):
    following = np.searchsorted(source, query).clip(0, len(source) - 1)
    previous = np.maximum(following - 1, 0)
    return np.where(np.abs(source[previous] - query) <
                    np.abs(source[following] - query), previous, following)


def audit(path: Path, reference: Path = REFERENCE, expect_abort: bool = False,
          expect_disconnect: bool = False) -> dict:
    path = Path(path)
    streams, _ = pyxdf.load_xdf(str(path), synchronize_clocks=False, dejitter_timestamps=False)
    by_name = {stream["info"]["name"][0]: stream for stream in streams}
    assert len(by_name) == len(streams), "Duplicate stream names in XDF"
    raw = next(stream for stream in streams if stream["info"]["type"][0] == "Accelerometer"
               and "-Mock-" in stream["info"]["name"][0])
    base = raw["info"]["name"][0].removesuffix("_rawACC")
    assert raw["info"]["name"] == [base + "_rawACC"]
    assert raw["info"]["channel_format"] == ["float32"]
    channels = raw["info"]["desc"][0]["channels"][0]["channel"]
    assert [(item["label"][0], item["unit"][0]) for item in channels] == [
        ("X", "mg"), ("Y", "mg"), ("Z", "mg")]
    acc, acc_time = raw["time_series"], raw["time_stamps"]
    assert len(acc) > 100 and len(acc) % 2 == 0
    assert np.all(np.diff(acc_time) > 0)
    assert np.max(np.abs(np.diff(acc_time) - .005)) < 1e-4

    replay = _reference(reference)
    max_samples = 2 * (max(replay["adr_pca_valid"]) + 1)
    expected_acc = _mock_acc(max_samples)
    prefix = min(32, len(acc))
    starts = np.flatnonzero(np.all(expected_acc[:max_samples-prefix+1] == acc[0], axis=1))
    starts = [int(start) for start in starts
              if np.array_equal(expected_acc[start:start+prefix], acc[:prefix])]
    assert starts, "Raw ACC has no matching mock sequence"
    age_samples = (acc_time[0] - float(raw["info"]["created_at"][0])) * 200
    start = min(starts, key=lambda value: abs(value - age_samples))
    assert abs(start - age_samples) < 400, "Mock sequence is inconsistent with stream age"
    assert start % 2 == 0 and start + len(acc) <= max_samples
    assert np.array_equal(acc, expected_acc[start:start + len(acc)]), "Lost, duplicated or altered ACC samples"

    tick_times = acc_time[1::2]
    metric_streams = {}
    metric_errors = {}
    for metric, suffix in METRICS.items():
        stream = by_name[base + "_" + suffix]
        info, description = stream["info"], stream["info"]["desc"][0]
        assert info["source_id"] == ["polar-h10-" + info["name"][0]]
        assert info["channel_format"] == ["float32"] and int(info["channel_count"][0]) == 1
        assert float(info["nominal_srate"][0]) == 0
        if metric in {"adr_pca_waveform", "adr_axis_mean_difference"}:
            assert info["type"] == ["Respiration"]
            assert description["schema"] == ["adr-waveform/1"]
            assert description["metric_id"] == [metric]
            assert description["stream_role"] == ["respiration_candidate"]
            assert description["raw_source_metric_id"] == ["raw_acc"]
            assert description["respyra_signal_role"] == ["signed_breathing_level"]
            assert description["channels"][0]["channel"][0]["unit"] == ["g"]
        else:
            assert info["type"] == ["SignalQuality"]
            if metric.endswith("valid"):
                assert description["channels"][0]["channel"][0]["unit"] == ["0/1"]
        values = stream["time_series"][:, 0]
        stamps = stream["time_stamps"]
        assert len(values) > 100 and np.all(np.diff(stamps) > 0)
        assert np.max(np.abs(np.diff(stamps) - .01)) < .003, f"Lost or duplicated {metric} timestamps"
        first_tick = start // 2 + round((stamps[0] - tick_times[0]) / .01)
        ticks = first_tick + np.arange(len(stamps))
        in_raw = (ticks >= start // 2) & (ticks < start // 2 + len(tick_times))
        assert np.count_nonzero(~in_raw) <= 2, f"{metric} extends beyond recorded ACC boundary"
        raw_positions = ticks[in_raw] - start // 2
        assert np.max(np.abs(tick_times[raw_positions] - stamps[in_raw])) < .005
        expected = np.array([replay[metric].get(int(tick), np.nan) for tick in ticks])
        assert np.all(np.isfinite(expected)), f"Reference lacks {metric} at a recorded tick"
        error = float(np.max(np.abs(values - expected)))
        assert error < 2e-6, f"{metric} differs from deterministic reference by {error}"
        if metric.endswith("valid"):
            assert set(np.unique(values)) <= {0, 1}
        if metric == "adr_pca_quality":
            assert np.all((values >= 0) & (values <= 1))
        metric_streams[metric] = stream
        metric_errors[metric] = error

    for mode, (metric, contract) in CONTRACTS.items():
        description = metric_streams[metric]["info"]["desc"][0]
        assert description["respyra_input_contract"] == [contract]
        companions = set(description["companion_streams"][0].split(","))
        required = {base + "_adrPcaValid"}
        if mode == "phan":
            required.add(base + "_adrAxisDifferenceValid")
        assert required <= companions and base + "_adrPcaQuality" in companions
    signed = metric_streams["adr_axis_mean_difference"]["time_series"][:, 0]
    assert np.min(signed) < 0 < np.max(signed), "Phan candidate lost its sign"

    markers = by_name["Respyra-Events"]
    recorded = [json.loads(row[0]) for row in markers["time_series"]]
    assert recorded and recorded[0]["event"] == "recording.started"
    earlier = recorded[0]["pre_recording_events"]
    events = earlier + recorded
    assert [item["seq"] for item in events] == list(range(1, events[-1]["seq"] + 1))
    assert len({item["run_id"] for item in events}) == 1
    assert all(abs(item["lsl_time"] - stamp) < 1e-4
               for item, stamp in zip(recorded, markers["time_stamps"]))
    assert all(events[index]["lsl_time"] <= events[index+1]["lsl_time"]
               for index in range(len(events)-1))
    counts = Counter(item["event"] for item in events)
    if expect_disconnect:
        assert counts["source.lost"] == counts["run.failed"] == counts["recording.finalizing"] == 1
        assert counts["run.completed"] == 0
        failed = next(item for item in events if item["event"] == "run.failed")
        assert failed["error_type"] == "LSLForceError" and "lost" in failed["message"]
        derived = by_name["Respyra-Calibrated-Breathing"]
        assert np.all(np.isnan(derived["time_series"][:, 0]))
        inspect_xdf(path, [markers["info"]["source_id"][0], derived["info"]["source_id"][0]])
        return {"result": "passed", "xdf": str(path), "outcome": "source_lost",
                "raw_acc_samples": len(acc), "candidate_samples": len(metric_streams["adr_pca_waveform"]["time_stamps"]),
                "metric_max_errors": metric_errors, "xdf_marker_samples": len(recorded),
                "embedded_setup_markers": len(earlier), "reconstructed_markers": len(events)}
    if expect_abort:
        assert counts["run.aborted"] == counts["recording.finalizing"] == 1
        assert counts["run.completed"] == counts["run.failed"] == 0
        derived = by_name["Respyra-Calibrated-Breathing"]
        assert np.all(np.isnan(derived["time_series"][:, 0]))
        saved = [json.loads(line) for line in (path.parent / "participant-list.jsonl").read_text(encoding="utf-8").splitlines()]
        assert sum(item["xdf_file"] == path.name for item in saved) == 1
        inspect_xdf(path, [markers["info"]["source_id"][0], derived["info"]["source_id"][0]])
        return {"result": "passed", "xdf": str(path), "outcome": "aborted",
                "raw_acc_samples": len(acc), "candidate_samples": len(metric_streams["adr_pca_waveform"]["time_stamps"]),
                "metric_max_errors": metric_errors, "xdf_marker_samples": len(recorded),
                "embedded_setup_markers": len(earlier), "reconstructed_markers": len(events)}
    assert counts["source.polarity.set"] == counts["calibration.completed"] == 1
    assert counts["run.completed"] == counts["recording.finalizing"] == 1
    assert counts["run.failed"] == counts["run.aborted"] == 0
    order = next(item for item in events if item["event"] == "trial.order")
    assert order["total_trials"] == len(order["conditions"]) == 48
    required_events = ("trial.condition.selected", "trial.started", "baseline.started",
                       "baseline.ended", "baseline.calculated", "countdown.started",
                       "countdown.ended", "tracking.started", "tracking.ended",
                       "assessment.accuracy", "assessment.breathing_judgment",
                       "assessment.confidence", "assessment.completed", "trial.ended")
    assert all(counts[name] == 48 for name in required_events)
    assert next(item for item in events if item["event"] == "run.completed")["trials_completed"] == 48
    for number, condition in enumerate(order["conditions"], 1):
        trial = [item for item in events if item.get("trial") == number]
        positions = [next(index for index, item in enumerate(trial) if item["event"] == name)
                     for name in ("trial.condition.selected", "trial.started", "baseline.started",
                                  "baseline.ended", "countdown.started", "countdown.ended",
                                  "tracking.started", "tracking.ended", "assessment.completed",
                                  "trial.ended")]
        assert positions == sorted(positions)
        chosen = next(item for item in trial if item["event"] == "trial.condition.selected")
        baseline = next(item for item in trial if item["event"] == "baseline.calculated")
        tracking = next(item for item in trial if item["event"] == "tracking.started")
        tracking_end = next(item for item in trial if item["event"] == "tracking.ended")
        assert chosen["condition"] == tracking["condition"] == condition
        assert chosen["segments"] == tracking["segments"]
        assert chosen["feedback_gain"] == tracking["feedback_gain"]
        assert chosen["feedback_enabled"] == tracking["feedback_enabled"]
        assert all(math.isfinite(item["freq_hz"]) and item["freq_hz"] > 0
                   and item["n_cycles"] > 0 for item in tracking["segments"])
        assert baseline["signal_unit"] == tracking["signal_unit"] == "g"
        assert all(math.isfinite(item[key]) for item, key in (
            (baseline, "center_value"), (baseline, "amplitude_value"),
            (tracking, "target_center_value"), (tracking, "target_amplitude_value")))
        assert baseline["amplitude_value"] > 0 and tracking["target_amplitude_value"] > 0
        assert tracking_end["outcome"] == "completed" and not tracking_end["escaped"]
        for assessment in ("assessment.accuracy", "assessment.breathing_judgment",
                           "assessment.confidence"):
            assert next(item for item in trial if item["event"] == assessment)["value"]

    configured = next(item for item in events if item["event"] == "run.configured")
    selected_metric, contract = next((metric, contract) for metric, contract in CONTRACTS.values()
                                     if contract == configured["input_contract"])
    assert configured["signal_unit"] == "g"
    selected = metric_streams[selected_metric]
    assert recorded[0]["source_ids"][0] == selected["info"]["source_id"][0]
    calibration = next(item for item in events if item["event"] == "calibration.completed")
    assert calibration["signal_unit"] == "g" and calibration["input_polarity"] in (-1, 1)
    center, amplitude = calibration["center_value"], calibration["amplitude_value"]
    assert math.isfinite(center) and math.isfinite(amplitude) and amplitude > 0
    direction = next(item for item in earlier if item["event"] == "source.polarity.set")
    assert calibration["input_polarity"] == (-1 if direction["enabled"] else 1)
    derived = by_name["Respyra-Calibrated-Breathing"]
    derived_desc = derived["info"]["desc"][0]
    assert derived_desc["input_contract"] == [contract]
    assert derived_desc["raw_source_id"] == selected["info"]["source_id"]
    derived_times, derived_values = derived["time_stamps"], derived["time_series"][:, 0]
    assert np.all(np.diff(derived_times) > 0)
    finite = np.isfinite(derived_values)
    assert np.any(finite) and np.any(~finite)
    assert np.all(~finite[derived_times < calibration["lsl_time"] - .01])
    selected_times, selected_values = selected["time_stamps"], selected["time_series"][:, 0]
    match = _nearest(selected_times, derived_times[finite])
    assert np.max(np.abs(selected_times[match] - derived_times[finite])) < .002
    assert np.all(np.diff(match) == 1), "Lost or duplicated calibrated samples"
    transformed = (calibration["input_polarity"] * selected_values[match] - center) / amplitude
    derived_error = float(np.max(np.abs(derived_values[finite] - transformed)))
    assert derived_error < 2e-5

    participant_file = path.parent / "participant-list.jsonl"
    saved = [json.loads(line) for line in participant_file.read_text(encoding="utf-8").splitlines()]
    assert sum(item["xdf_file"] == path.name for item in saved) == 1
    participant = next(item for item in saved if item["xdf_file"] == path.name)
    started = next(item for item in events if item["event"] == "run.started")
    assert participant["participant_number"] == started["participant"]
    assert participant["session"] == started["session"]
    inspect_xdf(path, [selected["info"]["source_id"][0], markers["info"]["source_id"][0],
                       derived["info"]["source_id"][0]])
    return {"result": "passed", "xdf": str(path), "contract": contract,
            "raw_acc_samples": len(acc), "raw_acc_first_index": start,
            "candidate_samples": len(selected_times), "metric_max_errors": metric_errors,
            "derived_samples": len(derived_times), "derived_finite": int(finite.sum()),
            "derived_max_error": derived_error, "xdf_marker_samples": len(recorded),
            "embedded_setup_markers": len(earlier), "reconstructed_markers": len(events),
            "trials_reconstructed": 48, "conditions": dict(Counter(order["conditions"])),
            "participant_record_matched": True, "protocol_and_breathing_reconstructable": True,
            "exact_rendered_frames_recorded": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xdf", type=Path)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--expect-abort", action="store_true")
    parser.add_argument("--expect-disconnect", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(audit(arguments.xdf, arguments.reference, arguments.expect_abort,
                           arguments.expect_disconnect), indent=2))
