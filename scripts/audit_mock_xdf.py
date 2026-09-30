"""Independently audit a full Vernier Mini mock study XDF."""

import argparse
import json
import math
from collections import Counter
from collections import deque
from pathlib import Path

import numpy as np
import pyxdf

from mpi.recording import inspect_xdf


def mock_breathing(last_sequence: int) -> np.ndarray:
    """Replay Vernier Stream Mini's versioned 30-second force normalization."""
    history = deque()
    values = np.empty(last_sequence + 1, dtype=np.float32)
    elapsed = 0.0
    lower = upper = 0.0
    since_bounds = 0
    for index in range(last_sequence + 1):
        force = 12 + 2.4 * math.sin(index * 2 * math.pi * .22 / 20)
        history.append((elapsed, force))
        since_bounds += 1
        while history and history[0][0] < elapsed - 30:
            history.popleft()
        if len(history) <= 5 or since_bounds >= 5:
            ordered = sorted(value for _, value in history)
            if len(ordered) < 20:
                lower, upper = ordered[0], ordered[-1]
            else:
                def quantile(part):
                    position = (len(ordered) - 1) * part
                    low, high = math.floor(position), math.ceil(position)
                    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)
                lower, upper = quantile(.05), quantile(.95)
            since_bounds = 0
        values[index] = .5 if upper - lower < 1e-9 else min(1, max(0, (force - lower) / (upper - lower)))
        elapsed += .05
    return values


def audit(path: Path) -> dict:
    streams, _ = pyxdf.load_xdf(str(path), synchronize_clocks=False, dejitter_timestamps=False)
    by_id = {stream["info"]["source_id"][0]: stream for stream in streams}
    raw = next(stream for stream in streams if stream["info"]["type"][0] == "VernierRaw"
               and stream["info"]["desc"][0]["model"][0] == "GDX-RB-MOCK")
    channels = raw["info"]["desc"][0]["channels"][0]["channel"]
    labels = [channel["label"][0] for channel in channels]
    force_index, sequence_index = labels.index("Force"), labels.index("sequence")
    assert channels[force_index]["unit"] == ["N"]
    assert channels[force_index]["sensor_number"] == ["1"]
    values = raw["time_series"][:, force_index]
    times = raw["time_stamps"]
    sequence = raw["time_series"][:, sequence_index].astype(np.int64)
    assert len(sequence) > 0 and np.all(np.diff(sequence) == 1), "Missing or repeated Mini rows"
    expected = 12 + 2.4 * np.sin(sequence * 2 * np.pi * .22 / 20)
    assert np.max(np.abs(values - expected)) < 1e-10, "Mock Force differs from the producer formula"
    assert np.all(np.isfinite(values))
    for diagnostic in ("dropped_rows_before", "device_drop_reports_before"):
        assert np.all(raw["time_series"][:, labels.index(diagnostic)] == 0), diagnostic

    force_copy = next((stream for stream in streams if stream["info"]["type"][0] == "RespirationForce"), None)
    if force_copy is not None:
        assert len(force_copy["time_stamps"]) == len(times)
        assert np.max(np.abs(force_copy["time_stamps"] - times)) < 1e-6
        assert np.max(np.abs(force_copy["time_series"][:, 0] - values)) < 1e-5

    producer = next(stream for stream in streams if stream["info"]["type"][0] == "Respiration"
                    and stream["info"]["desc"][0].get("stream_role") == ["derived_breathing_waveform"])
    settings = producer["info"]["desc"][0]["processing"][0]
    assert settings["algorithm"] == ["polar-stream-vernier-force-respiration"]
    assert settings["settings_schema"] == ["vernier-breathing-settings-v1"]
    assert settings["window_seconds"] == ["30"]
    assert settings["bounds_update_samples"] == ["5"]
    assert settings["lower_quantile"] == ["0.05"] and settings["upper_quantile"] == ["0.95"]
    assert len(producer["time_stamps"]) == len(times)
    producer_sequence = sequence[0] + np.rint((producer["time_stamps"] - times[0]) / .05).astype(np.int64)
    assert producer_sequence[0] >= 0 and np.all(np.diff(producer_sequence) == 1)
    assert np.max(np.abs(producer["time_stamps"] - times[0] - (producer_sequence - sequence[0]) * .05)) < .02

    replay = mock_breathing(int(producer_sequence[-1]))
    producer_error = np.max(np.abs(producer["time_series"][:, 0] - replay[producer_sequence]))
    assert producer_error < 2e-6
    combined = next((stream for stream in streams if stream["info"]["type"][0] == "VernierMini"), None)
    combined_rows = []
    combined_error = None
    if combined is not None:
        combined_labels = [channel["label"][0] for channel in combined["info"]["desc"][0]["channels"][0]["channel"]]
        combined_rows = combined["time_series"]
        assert len(combined_rows) == 2 * len(times)
        combined_force = combined_rows[::2]
        combined_breathing = combined_rows[1::2]
        combined_sequence = combined_force[:, combined_labels.index("sequence")].astype(np.int64)
        if combined_sequence[-1] >= len(replay):
            replay = mock_breathing(int(combined_sequence[-1]))
        assert np.all(np.diff(combined_sequence) == 1)
        assert np.all(np.isnan(combined_force[:, combined_labels.index("vernier_breathing_01")]))
        assert np.all(np.isnan(combined_breathing[:, combined_labels.index("sensor_1_Force")]))
        expected_force = 12 + 2.4 * np.sin(combined_sequence * 2 * np.pi * .22 / 20)
        assert np.max(np.abs(combined_force[:, combined_labels.index("sensor_1_Force")] - expected_force)) < 1e-5
        combined_error = np.max(np.abs(combined_breathing[:, combined_labels.index("vernier_breathing_01")] - replay[combined_sequence]))
        assert combined_error < 2e-6

    markers = next(stream for stream in streams if stream["info"]["name"][0] == "Respyra-Events")
    events = [json.loads(row[0]) for row in markers["time_series"]]
    assert len(events) > 0
    assert [event["seq"] for event in events] == list(range(events[0]["seq"], events[-1]["seq"] + 1))
    assert len({event["run_id"] for event in events}) == 1
    assert all(abs(event["lsl_time"] - stamp) < 1e-4 for event, stamp in zip(events, markers["time_stamps"]))
    counts = Counter(event["event"] for event in events)
    order = next(event for event in events if event["event"] == "trial.order")
    total = order["total_trials"]
    assert total == len(order["conditions"]) == 48
    assert counts["run.completed"] == 1 and counts["run.failed"] == counts["run.aborted"] == 0
    assert next(event for event in events if event["event"] == "run.completed")["trials_completed"] == total
    required = ("trial.condition.selected", "trial.started", "baseline.started", "baseline.ended",
                "baseline.calculated", "countdown.started", "countdown.ended", "tracking.started",
                "tracking.ended", "assessment.accuracy", "assessment.breathing_judgment",
                "assessment.confidence", "assessment.completed", "trial.ended")
    assert all(counts[name] == total for name in required), {name: counts[name] for name in required}
    assert counts["calibration.completed"] == counts["recording.finalizing"] == 1

    trials = []
    for number, condition in enumerate(order["conditions"], 1):
        trial = [event for event in events if event.get("trial") == number]
        selected = next(event for event in trial if event["event"] == "trial.condition.selected")
        tracking = next(event for event in trial if event["event"] == "tracking.started")
        assert selected["condition"] == tracking["condition"] == condition
        assert selected["segments"] == tracking["segments"]
        assert selected["feedback_gain"] == tracking["feedback_gain"]
        assert tracking["target_amplitude_n"] > 0 and math.isfinite(tracking["target_center_n"])
        positions = {name: next(i for i, event in enumerate(trial) if event["event"] == name)
                     for name in ("trial.started", "baseline.started", "baseline.ended",
                                  "countdown.started", "countdown.ended", "tracking.started",
                                  "tracking.ended", "assessment.completed", "trial.ended")}
        assert list(positions.values()) == sorted(positions.values()), (number, positions)
        assert next(event for event in trial if event["event"] == "tracking.ended")["outcome"] == "completed"
        trials.append({"number": number, "condition": condition,
                       "gain": tracking["feedback_gain"], "segments": tracking["segments"],
                       "target_center_n": tracking["target_center_n"],
                       "target_amplitude_n": tracking["target_amplitude_n"]})

    derived_id = "respyra-breathing-" + events[0]["run_id"]
    derived = by_id[derived_id]
    calibration = next(event for event in events if event["event"] == "calibration.completed")
    center, amplitude = calibration["center_n"], calibration["amplitude_n"]
    derived_times = derived["time_stamps"]
    derived_values = derived["time_series"][:, 0]
    assert len(derived_times) > 0 and np.all(np.diff(derived_times) > 0)
    assert np.any(np.isnan(derived_values)) and np.any(np.isfinite(derived_values))
    assert np.all(np.isnan(derived_values[derived_times < calibration["lsl_time"] - .01]))
    assert np.all(np.isfinite(derived_values[derived_times > calibration["lsl_time"] + .1]))
    assert derived_times[0] <= times[0] + .1
    # The selected inlet stops at source.disconnected. Every raw sample through
    # its last derived timestamp must have a matching derived sample.
    covered = times <= derived_times[-1] + 1e-3
    assert np.any(covered)
    indices = np.searchsorted(derived_times, times[covered])
    indices = np.minimum(indices, len(derived_times) - 1)
    previous = np.maximum(indices - 1, 0)
    distance = np.minimum(np.abs(derived_times[indices] - times[covered]),
                          np.abs(derived_times[previous] - times[covered]))
    assert np.max(distance) < .01, f"Raw Force missing from derived stream: {np.sum(distance >= .01)} rows"
    finite = np.isfinite(derived_values)
    raw_indices = np.searchsorted(times, derived_times[finite])
    raw_indices = np.minimum(raw_indices, len(times) - 1)
    prior = np.maximum(raw_indices - 1, 0)
    raw_indices = np.where(np.abs(times[prior] - derived_times[finite]) <
                           np.abs(times[raw_indices] - derived_times[finite]), prior, raw_indices)
    assert np.max(np.abs(times[raw_indices] - derived_times[finite])) < .01
    assert np.max(np.abs(derived_values[finite] - (values[raw_indices] - center) / amplitude)) < 2e-5

    required_ids = [stream["info"]["source_id"][0] for stream in
                    (raw, producer, markers, derived, force_copy, combined) if stream is not None]
    summaries = inspect_xdf(path, required_ids)
    assert all(row["sample_count"] > 0 for row in summaries if row["source_id"] in required_ids)
    return {"result": "passed", "xdf": str(path), "streams": len(streams),
            "raw_samples": len(times), "raw_sequence_first": int(sequence[0]),
            "raw_sequence_last": int(sequence[-1]), "derived_samples": len(derived_times),
            "producer_breathing_samples": len(producer_sequence),
            "producer_breathing_max_error": float(producer_error),
            "combined_rows": len(combined_rows), "combined_breathing_max_error": float(combined_error) if combined_error is not None else None,
            "derived_precalibration_nan": int(np.isnan(derived_values).sum()),
            "derived_postcalibration_finite": int(finite.sum()), "marker_count": len(events),
            "trials_reconstructed": len(trials), "conditions": dict(Counter(order["conditions"])),
            "protocol_and_breathing_reconstructable": True,
            "exact_rendered_frames_recorded": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xdf", type=Path)
    print(json.dumps(audit(parser.parse_args().xdf), indent=2))
