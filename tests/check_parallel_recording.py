"""Headless three-input, six-waveform native XDF round trip."""

import json
import math
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
output = root / ".for-ai-local" / ("parallel-recording-" + uuid4().hex)
output.mkdir(parents=True)
config = output / "lsl.cfg"
config.write_text("[lab]\nSessionID = respyra-parallel-" + uuid4().hex + "\n", encoding="utf-8")
os.environ["LSLAPICFG"] = str(config)

import pyxdf  # noqa: E402
from pylsl import StreamInfo, StreamOutlet, cf_float32, local_clock, resolve_byprop  # noqa: E402
from mpi.event_markers import MarkerOutlet  # noqa: E402
from mpi.lsl_force import open_force_source  # noqa: E402
from mpi.parallel_inputs import ParallelInputs  # noqa: E402
from mpi.recording import NativeRecording, inspect_xdf  # noqa: E402

base = "Parallel" + uuid4().hex[:8]
force_id = "polar-stream-vernier-raw-" + base
force_info = StreamInfo(base + "_rawVernier", "VernierRaw", 1, 0, cf_float32, force_id)
desc = force_info.desc()
for key, value in dict(manufacturer="Vernier", model="GDX-RB-MOCK",
                       stream_role="raw_measurement_recording").items():
    desc.append_child_value(key, value)
channel = desc.append_child("channels").append_child("channel")
for key, value in dict(label="Force", unit="N", sensor_number="1", type="RawMeasurement").items():
    channel.append_child_value(key, value)
force = StreamOutlet(force_info)

validity = {}
for suffix in ("adrPcaValid", "adrAxisDifferenceValid"):
    name = base + "_" + suffix
    info = StreamInfo(name, "SignalQuality", 1, 0, cf_float32, "polar-h10-" + name)
    channel = info.desc().append_child("channels").append_child("channel")
    channel.append_child_value("label", suffix)
    channel.append_child_value("unit", "0/1")
    validity[suffix] = StreamOutlet(info)

waveforms = {}
for metric, suffix, contract, companions in (
    ("adr_pca_waveform", "adrPcaWaveform", "respyra-polar-pca/1", ("adrPcaValid",)),
    ("adr_axis_mean_difference", "adrAxisMeanDifference", "respyra-polar-phan-signed/1",
     ("adrPcaValid", "adrAxisDifferenceValid")),
):
    name = base + "_" + suffix
    info = StreamInfo(name, "Respiration", 1, 0, cf_float32, "polar-h10-" + name)
    desc = info.desc()
    for key, value in dict(manufacturer="Polar", model="H10", schema="adr-waveform/1",
                           stream_role="respiration_candidate", metric_id=metric,
                           raw_source_metric_id="raw_acc", respyra_input_contract=contract,
                           respyra_signal_role="signed_breathing_level",
                           companion_streams=",".join(base + "_" + flag for flag in companions)).items():
        desc.append_child_value(key, value)
    channel = desc.append_child("channels").append_child("channel")
    channel.append_child_value("label", suffix)
    channel.append_child_value("unit", "g")
    waveforms[suffix] = StreamOutlet(info)

stop = threading.Event()


def produce():
    index = 0
    while not stop.wait(0.05):
        timestamp = local_clock()
        value = math.sin(index * 0.16)
        for outlet in validity.values():
            outlet.push_sample([1.0], timestamp)
        force.push_sample([5 + value], timestamp)
        waveforms["adrPcaWaveform"].push_sample([0.02 * value], timestamp)
        waveforms["adrAxisMeanDifference"].push_sample([0.01 * value], timestamp)
        index += 1


thread = threading.Thread(target=produce)
thread.start()
source = recorder = None
try:
    source = open_force_source(resolve_byprop("source_id", force_id, timeout=5)[0])
    markers = MarkerOutlet()
    source.start_derived(markers.run_id)
    source.comparisons = ParallelInputs.discover(source, markers)
    assert len(source.comparisons.sources) == 2, [s.source_id for s in source.comparisons.sources]
    recorder = NativeRecording(root / ".for-ai-local/recorder/runtime", output)
    recorder.start({"participant": "17", "session": "001"}, source, markers)
    assert len(recorder.required) == 7, recorder.required  # 3 raw + 3 calibrated + markers
    source.comparisons.begin_range()
    until = time.monotonic() + 1.2
    while time.monotonic() < until:
        source.get_all()
        time.sleep(0.02)
    source.comparisons.end_range()
    source.comparisons.activate(SimpleNamespace(percentile_lo=5, percentile_hi=95, scale=1.0))
    source.calibrate(5.0, 1.0, markers.run_id)
    for identity in (source.calibrated_id, *(s.calibrated_id for s in source.comparisons.sources)):
        recorder.wait_for_finite_data(identity, source.get_all)
    until = time.monotonic() + 0.5
    while time.monotonic() < until:
        source.get_all()
        time.sleep(0.02)
    markers.emit("recording.finalizing")
    recorder.stop()
    summary = inspect_xdf(recorder.path, recorder.required)
    streams, _ = pyxdf.load_xdf(str(recorder.path), synchronize_clocks=False,
                                dejitter_timestamps=False)
    by_id = {item["info"]["source_id"][0]: item for item in streams}
    assert len([item for item in streams if item["info"]["source_id"][0] in recorder.required]) == 7
    calibrated = [source, *source.comparisons.sources]
    for item in calibrated:
        raw = by_id[item.source_id]
        derived = by_id[item.calibrated_id]
        raw_samples = list(zip(raw["time_stamps"], raw["time_series"]))
        finite = [(timestamp, sample[0]) for timestamp, sample in
                  zip(derived["time_stamps"], derived["time_series"])
                  if math.isfinite(sample[0])]
        assert finite and any(math.isnan(sample[0]) for sample in derived["time_series"])
        for timestamp, value in finite:
            raw_time, raw_row = min(raw_samples, key=lambda sample: abs(sample[0] - timestamp))
            assert abs(raw_time - timestamp) < 0.01
            expected = (raw_row[0] - item.center) / item.amplitude
            assert abs(value - expected) < 1e-5
        role = derived["info"]["desc"][0]["role"][0]
        assert role == ("feedback" if item is source else "comparison")
    assert all(item["sample_count"] > 0 for item in summary if item["source_id"] in recorder.required)
    print(json.dumps({"result": "passed", "xdf": str(recorder.path),
                      "required": list(recorder.required), "streams": len(summary)}))
finally:
    if recorder is not None and recorder.process is not None:
        recorder.stop()
    if source is not None:
        source.stop()
    stop.set()
    thread.join()
