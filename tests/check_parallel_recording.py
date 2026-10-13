"""Headless three-input XDF round trip, including comparison signal loss."""

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
from mpi.lsl_force import open_force_source, calibrated_stream_name  # noqa: E402
from mpi.parallel_inputs import ParallelInputs  # noqa: E402
from mpi.recording import NativeRecording, inspect_xdf  # noqa: E402
from mpi.time_reference import TimeReference  # noqa: E402

base = "Parallel" + uuid4().hex[:8]
force_id = "device-force-" + base
force_info = StreamInfo("Vernier_rawForce", "VernierRaw", 1, 0, cf_float32, force_id)
desc = force_info.desc()
for key, value in dict(manufacturer="Vernier", model="GDX-RB-MOCK",
                       stream_role="raw_measurement_recording").items():
    desc.append_child_value(key, value)
channel = desc.append_child("channels").append_child("channel")
for key, value in dict(label="Belt tension", unit="N", sensor_number="1", type="RawMeasurement").items():
    channel.append_child_value(key, value)
force = StreamOutlet(force_info)

waveforms = {}
links = []
for device in ("Polar", "Vernier"):
    info = StreamInfo(f"{device}_Link", "Markers", 1, 0, cf_float32,
                      f"{device.lower()}-mini-{base}-signal-status")
    info.desc().append_child_value("manufacturer", device)
    info.desc().append_child_value("stream_role", "signal_continuity_markers")
    channel = info.desc().append_child("channels").append_child("channel")
    for key, value in dict(label="signal_state", unit="code", type="Marker", role="event").items():
        channel.append_child_value(key, value)
    links.append(StreamOutlet(info))
for metric, suffix, contract, companions in (
    ("adr_pca_waveform", "adrPcaWaveform", "respyra-polar-pca/1", ("adrPcaValid",)),
    ("adr_axis_mean_difference", "adrAxisMeanDifference", "respyra-polar-phan-signed/1",
     ("adrPcaValid", "adrAxisDifferenceValid")),
):
    name = "Polar_" + ("ChestPCA" if metric == "adr_pca_waveform" else "ChestDT")
    info = StreamInfo(name, "Custom waveform", 2 + len(companions), 0, cf_float32, "device-waveform-" + metric + base)
    desc = info.desc()
    flag_ids = ["adr_pca_valid"] + (["adr_axis_difference_valid"] if len(companions) == 2 else [])
    for key, value in dict(manufacturer="Polar", model="H10", schema="adr-waveform/2",
                           stream_role="respiration_candidate", metric_id=metric,
                           raw_source_metric_id="raw_acc", respyra_input_contract=contract,
                           respyra_signal_role="signed_breathing_level",
                           waveform_channel=metric, validity_channels=",".join(flag_ids)).items():
        desc.append_child_value(key, value)
    channels = desc.append_child("channels")
    for channel_metric, unit, role in [(metric, "g", "waveform"), ("adr_pca_quality", "0–1", "quality"),
                                      *[(flag, "0/1", "validity") for flag in flag_ids]]:
        channel = channels.append_child("channel")
        for key, value in dict(label=channel_metric, metric_id=channel_metric, unit=unit, role=role).items():
            channel.append_child_value(key, value)
    waveforms[suffix] = StreamOutlet(info)

stop = threading.Event()
lose_phan = threading.Event()
lose_pca = threading.Event()


def produce():
    index = 0
    while not stop.wait(0.05):
        timestamp = local_clock()
        value = math.sin(index * 0.16)
        force.push_sample([5 + value], timestamp)
        if not lose_pca.is_set():
            waveforms["adrPcaWaveform"].push_sample([0.02 * value, 0.8, 1.0], timestamp)
        waveforms["adrAxisMeanDifference"].push_sample([0.01 * value, 0.8, 1.0, float(not lose_phan.is_set())], timestamp)
        index += 1


thread = threading.Thread(target=produce)
thread.start()
source = recorder = None
try:
    selected = os.environ.get("RESPYRA_PARALLEL_INPUT", "force")
    selected_id = (force_id if selected == "force" else
                   waveforms["adrPcaWaveform" if selected == "pca" else "adrAxisMeanDifference"].get_info().source_id())
    source = open_force_source(resolve_byprop("source_id", selected_id, timeout=5)[0])
    markers = MarkerOutlet()
    markers.clock_reference = TimeReference()
    markers.clock_reference.start()
    source.start_derived(markers.run_id)
    source.comparisons = ParallelInputs.discover(source, markers)
    assert len(source.comparisons.sources) == 2, [s.source_id for s in source.comparisons.sources]
    recorder = NativeRecording(os.environ.get("RESPYRA_RECORDER_RUNTIME", root / ".for-ai-local/recorder/runtime"), output)
    recorder.start({"participant": "17", "session": "001"}, source, markers)
    assert len(recorder.required) == 7, recorder.required
    deadline = time.monotonic() + 5
    while not all(link.get_info().source_id() in recorder.data_sources or
                  link.get_info().source_id() in recorder.streams for link in links):
        assert time.monotonic() < deadline, "Both Link streams must be subscribed directly"
        recorder.check_health()
        time.sleep(.02)
    for code in (1.0, 2.0):
        for link in links:
            link.push_sample([code], local_clock())
    if selected == "force":
        from mpi.lsl_viewer import LSLViewer
        viewer = LSLViewer(markers.health_snapshot()["source_id"])
        try:
            deadline = time.monotonic() + 5
            while True:
                viewed = viewer.snapshot()
                if {"Polar_Link", "Vernier_Link"}.issubset({row["name"] for row in viewed}):
                    break
                assert time.monotonic() < deadline, "Both Link streams must be visible"
                time.sleep(.02)
        finally:
            viewer.close()
    source.comparisons.begin_range()
    until = time.monotonic() + 1.2
    while time.monotonic() < until:
        source.get_all()
        time.sleep(0.02)
    source.comparisons.end_range()
    source.comparisons.activate(SimpleNamespace(percentile_lo=5, percentile_hi=95, scale=1.0))
    source.calibrate(5.0 if selected == "force" else 0.0,
                     {"force": 1.0, "pca": 0.02, "phan": 0.01}[selected], markers.run_id)
    for identity in (source.calibrated_id, *(s.calibrated_id for s in source.comparisons.sources)):
        recorder.wait_for_finite_data(identity, source.get_all)
    until = time.monotonic() + 0.5
    while time.monotonic() < until:
        source.get_all()
        time.sleep(0.02)
    # An optional candidate can lose validity while the feedback input stays live.
    lost_source = next((s for s in source.comparisons.sources
                       if getattr(s, "contract_id", None) == "respyra-polar-phan-signed/1"), None)
    if lost_source is None:
        # With DT selected, stop optional PCA samples while its shared flags stay live.
        lost_source = next(s for s in source.comparisons.sources if hasattr(s, "contract_id"))
        lose_pca.set()
    else:
        lose_phan.set()
    deadline = time.monotonic() + 6
    while lost_source in source.comparisons.active:
        assert time.monotonic() < deadline, "Invalid comparison did not report signal loss"
        source.get_all()
        time.sleep(0.02)
    assert lost_source.stopped and len(source.comparisons.active) == 1
    until = time.monotonic() + 0.3
    while time.monotonic() < until:
        source.get_all()
        time.sleep(0.02)
    markers.emit("recording.finalizing")
    recorder.stop()
    summary = inspect_xdf(recorder.path, recorder.required)
    streams, _ = pyxdf.load_xdf(str(recorder.path), synchronize_clocks=False,
                                dejitter_timestamps=False)
    by_id = {item["info"]["source_id"][0]: item for item in streams}
    assert len(streams) == 9, "Three raw, three calibrated, events and two Link streams"
    assert len([item for item in streams if item["info"]["source_id"][0] in recorder.required]) == 7
    assert not any(item["info"]["name"][0] == "Respyra_Housekeeping" for item in streams)
    for link in links:
        recorded_link = by_id[link.get_info().source_id()]
        assert recorded_link["info"]["name"][0] == link.get_info().name()
        assert list(recorded_link["time_series"][:, 0]) == [1.0, 2.0]
        assert recorded_link["time_stamps"][1] > recorded_link["time_stamps"][0]
        assert recorded_link["info"]["desc"][0]["channels"][0]["channel"][0]["role"] == ["event"]
    calibrated = [source, *source.comparisons.sources]
    for item in calibrated:
        raw = by_id[item.source_id]
        derived = by_id[item.calibrated_id]
        assert derived["info"]["name"][0] == calibrated_stream_name(item.stream_name)
        assert derived["info"]["desc"][0]["raw_source_name"][0] == item.stream_name
        raw_samples = list(zip(raw["time_stamps"], raw["time_series"]))
        if hasattr(item, "contract_id"):
            expected_channels = 3 if item.contract_id == "respyra-polar-pca/1" else 4
            assert int(raw["info"]["channel_count"][0]) == expected_channels
            assert int(derived["info"]["channel_count"][0]) == expected_channels
            assert all(all(math.isnan(v) for v in row) for row in derived["time_series"] if math.isnan(row[0]))
        finite = [(timestamp, sample[0]) for timestamp, sample in
                  zip(derived["time_stamps"], derived["time_series"])
                  if math.isfinite(sample[0])]
        assert finite and any(math.isnan(sample[0]) for sample in derived["time_series"])
        for timestamp, value in finite:
            raw_time, raw_row = min(raw_samples, key=lambda sample: abs(sample[0] - timestamp))
            assert abs(raw_time - timestamp) < 0.01
            expected = (raw_row[0] - item.center) / item.amplitude
            assert abs(value - expected) < 1e-5
        if hasattr(item, "contract_id"):
            for timestamp, row in zip(derived["time_stamps"], derived["time_series"]):
                if not math.isfinite(row[0]):
                    continue
                raw_time, raw_row = min(raw_samples, key=lambda sample: abs(sample[0] - timestamp))
                assert abs(raw_time - timestamp) < 0.01
                assert list(row[1:]) == list(raw_row[1:]) and all(v == 1 for v in row[2:])
        role = derived["info"]["desc"][0]["role"][0]
        assert role == ("feedback" if item is source else "comparison")
    assert all(item["sample_count"] > 0 for item in summary if item["source_id"] in recorder.required)
    events = [json.loads(row[0]) for row in by_id[recorder.required[1]]["time_series"]]
    losses = [event for event in events if event["event"] == "source.comparison.lost"]
    assert len(losses) == 1 and losses[0]["source_id"] == lost_source.source_id
    for item in (source, *source.comparisons.active):
        assert any(timestamp > losses[0]["lsl_time"] and math.isfinite(row[0])
                   for timestamp, row in zip(by_id[item.calibrated_id]["time_stamps"],
                                             by_id[item.calibrated_id]["time_series"]))
    print(json.dumps({"result": "passed", "selected": selected, "xdf": str(recorder.path),
                      "required": list(recorder.required), "streams": len(summary),
                      "lost_comparison": lost_source.source_id}))
finally:
    if recorder is not None and recorder.process is not None:
        recorder.stop()
    if source is not None:
        source.stop()
    stop.set()
    thread.join()
