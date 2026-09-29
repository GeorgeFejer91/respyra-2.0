"""Headless XDF proof for each exact Polar breathing-input contract."""

import json
import math
import os
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
output = root / ".for-ai-local" / ("polar-recording-" + uuid4().hex)
output.mkdir(parents=True)
config = output / "lsl.cfg"
config.write_text("[lab]\nSessionID = respyra-polar-" + uuid4().hex + "\n", encoding="utf-8")
os.environ["LSLAPICFG"] = str(config)

import pyxdf  # noqa: E402
from pylsl import StreamInfo, StreamOutlet, cf_float32, local_clock, resolve_byprop  # noqa: E402
from mpi.event_markers import MarkerOutlet  # noqa: E402
from mpi.lsl_force import open_force_source  # noqa: E402
from mpi.recording import NativeRecording, inspect_xdf  # noqa: E402


def run(metric, suffix, contract, flags):
    base = "SyntheticPolar" + uuid4().hex[:8]
    name = base + "_" + suffix
    identity = "polar-h10-" + name
    info = StreamInfo(name, "Respiration", 1, 0, cf_float32, identity)
    desc = info.desc()
    for key, value in {
        "manufacturer": "Polar", "model": "H10", "schema": "adr-waveform/1",
        "stream_role": "respiration_candidate", "metric_id": metric,
        "raw_source_metric_id": "raw_acc", "respyra_input_contract": contract,
        "respyra_signal_role": "signed_breathing_level",
        "companion_streams": ",".join(base + "_" + flag for flag in flags),
    }.items():
        desc.append_child_value(key, value)
    desc.append_child("channels").append_child("channel").append_child_value("unit", "g")
    waveform = StreamOutlet(info)
    validity = []
    for flag in flags:
        flag_name = base + "_" + flag
        flag_info = StreamInfo(flag_name, "SignalQuality", 1, 0, cf_float32,
                               "polar-h10-" + flag_name)
        flag_info.desc().append_child("channels").append_child("channel").append_child_value("unit", "0/1")
        validity.append(StreamOutlet(flag_info))
    stop = threading.Event()

    def produce():
        index = 0
        while not stop.wait(0.05):
            timestamp = local_clock()
            for outlet in validity:
                outlet.push_sample([1.0], timestamp)
            waveform.push_sample([0.02 * math.sin(index * 0.2)], timestamp)
            index += 1

    thread = threading.Thread(target=produce)
    thread.start()
    source = recorder = None
    try:
        resolved = resolve_byprop("source_id", identity, timeout=5)
        assert len(resolved) == 1
        source = open_force_source(resolved[0])
        source.polarity = -1
        markers = MarkerOutlet()
        source.start_derived(markers.run_id)
        recorder = NativeRecording(root / ".for-ai-local/recorder/runtime", output)
        recorder.start({"participant": "polar-check", "session": "001"}, source, markers)
        source.calibrate(0.0, 0.02, markers.run_id)
        markers.emit("calibration.completed", center_n=None, amplitude_n=None,
                     y_min_n=None, y_max_n=None, center_value=0.0,
                     amplitude_value=0.02, y_min_value=-0.02, y_max_value=0.02,
                     signal_unit="g", input_polarity=-1)
        recorder.wait_for_finite_data(source.calibrated_id, source.get_all)
        until = time.monotonic() + 0.5
        while time.monotonic() < until:
            source.get_all()
            time.sleep(0.025)
        markers.emit("recording.finalizing")
        recorder.stop()
        ids = [identity, source.calibrated_id, markers.health_snapshot()["source_id"],
               *("polar-h10-" + base + "_" + flag for flag in flags)]
        summary = inspect_xdf(recorder.path, ids)
        streams, _ = pyxdf.load_xdf(str(recorder.path), synchronize_clocks=False,
                                    dejitter_timestamps=False)
        by_id = {stream["info"]["source_id"][0]: stream for stream in streams}
        derived = [row[0] for row in by_id[source.calibrated_id]["time_series"]]
        assert any(math.isnan(value) for value in derived)
        assert any(math.isfinite(value) for value in derived)
        assert all(item["sample_count"] > 0 for item in summary)
        raw = list(zip(by_id[identity]["time_stamps"], by_id[identity]["time_series"]))
        for timestamp, sample in zip(by_id[source.calibrated_id]["time_stamps"],
                                     by_id[source.calibrated_id]["time_series"]):
            if not math.isfinite(sample[0]):
                continue
            raw_time, raw_sample = min(raw, key=lambda item: abs(item[0] - timestamp))
            assert abs(raw_time - timestamp) < 0.01
            assert abs(sample[0] + raw_sample[0] / 0.02) < 1e-5
        assert by_id[source.calibrated_id]["info"]["desc"][0]["input_contract"][0] == contract
        events = [json.loads(sample[0]) for sample in
                  by_id[markers.health_snapshot()["source_id"]]["time_series"]]
        calibration = next(event for event in events if event["event"] == "calibration.completed")
        assert calibration["input_polarity"] == -1 and calibration["signal_unit"] == "g"
        return {"contract": contract, "file": str(recorder.path), "streams": summary}
    finally:
        if recorder is not None and recorder.process is not None:
            recorder.stop()
        if source is not None:
            source.stop()
        stop.set()
        thread.join()


results = [
    run("adr_pca_waveform", "adrPcaWaveform", "respyra-polar-pca/1", ("adrPcaValid",)),
    run("adr_axis_mean_difference", "adrAxisMeanDifference", "respyra-polar-phan-signed/1",
        ("adrPcaValid", "adrAxisDifferenceValid")),
]
print(json.dumps({"result": "passed", "contracts": results}))
