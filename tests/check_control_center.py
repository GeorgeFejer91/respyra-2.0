"""Independent XDF and all-channel preview proof, in a private LSL session."""
import json
import math
import os
import sys
from pathlib import Path
import threading
import time
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
output = root / ".for-ai-local" / ("control-center-" + uuid4().hex)
output.mkdir(parents=True)
config = output / "lsl.cfg"
config.write_text("[lab]\nSessionID = respyra-control-" + uuid4().hex + "\n", encoding="utf-8")
os.environ["LSLAPICFG"] = str(config)
from pylsl import StreamInfo, StreamOutlet, cf_float32, cf_string, local_clock, resolve_byprop
import pyxdf
from mpi.event_markers import MarkerOutlet
from mpi.lsl_force import open_force_source
from mpi.lsl_viewer import LSLViewer
from mpi.recording import NativeRecording, inspect_xdf

identity = "polar-stream-vernier-raw-check-" + uuid4().hex
raw = StreamInfo("Control check raw", "VernierRaw", 2, 20, cf_float32, identity)
desc = raw.desc()
for key, value in dict(manufacturer="Vernier", model="GDX-RB", stream_role="raw_measurement_recording").items():
    desc.append_child_value(key, value)
channels = desc.append_child("channels")
for label, unit, number in [("Respiration Rate", "breaths/min", "2"), ("Force", "N", "1")]:
    ch = channels.append_child("channel")
    for key, value in dict(label=label, unit=unit, sensor_number=number, type="RawMeasurement").items():
        ch.append_child_value(key, value)
outlet = StreamOutlet(raw)
markers = MarkerOutlet()
viewer = LSLViewer(markers.health_snapshot()["source_id"])
stop = threading.Event()
late = None

def push():
    while not stop.wait(.05):
        outlet.push_sample([12, 5 + math.sin(local_clock())], local_clock())
        if late is not None:
            late.push_sample(["late.marker"], local_clock())

thread = threading.Thread(target=push)
thread.start()
source = None
recorder = NativeRecording(root / ".for-ai-local/recorder/runtime", output)
try:
    source = open_force_source(resolve_byprop('source_id', identity, timeout=5)[0])
    source.start_derived(markers.run_id)
    recorder.start(dict(participant="synthetic-control", session="001"), source, markers)
    assert source.calibrated_id in recorder.snapshot()["data_sources"]
    assert source.calibrated_sample is None
    if '--full-study' in sys.argv:
        # Exercise every configured trial and actual PsychoPy phase with fast timings
        # and simulated responses. This is deliberately separate from a participant run.
        import copy
        import importlib.util
        from types import SimpleNamespace
        from psychopy import core, event
        from mpi.validation_study_jenny import CONFIG
        spec = importlib.util.spec_from_file_location('checked_study', root / 'scripts/run_experiment.py')
        study = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(study)
        cfg = copy.deepcopy(CONFIG)
        cfg.display.fullscr = False
        cfg.display.monitor_size_pix = (800, 600)
        cfg.timing.range_cal_duration_sec = 1.5
        cfg.timing.baseline_duration_sec = .15
        cfg.timing.countdown_duration_sec = .1
        cfg.timing.tracking_duration_sec = .15
        bridge = SimpleNamespace(recorder=recorder, check_cancel=recorder.check_health,
                                 send=lambda _: None, finish_stop=lambda _: None)
        study.run_source_setup = lambda *args: (dict(participant='synthetic-control', session='001'), source)
        event.getKeys = lambda **kwargs: []
        event.waitKeys = lambda **kwargs: ['1' if markers.screen in {'accuracy', 'confidence'}
                                         else 'n' if markers.screen == 'breathing_judgment' else 'space']
        core.quit = lambda: None
        study.run_experiment(cfg, bridge, markers)
        assert markers.state is not None
        assert source.stopped
        calibration_center, calibration_amplitude = source.center, source.amplitude
    else:
        source.get_all()
        markers.emit("calibration.completed", center_n=5, amplitude_n=2, y_min_n=3, y_max_n=7,
                     center_value=5, amplitude_value=2, y_min_value=3, y_max_value=7,
                     signal_unit="N", input_polarity=None)
        source.calibrate(5, 2, markers.run_id)
        deadline = time.monotonic() + 8
        while source.calibrated_sample is None and time.monotonic() < deadline:
            source.get_all()
            time.sleep(.025)
        assert source.calibrated_sample is not None
        recorder.wait_for_finite_data(source.calibrated_id, source.get_all)
        calibration_center, calibration_amplitude = 5, 2
    late = StreamOutlet(StreamInfo("Late external markers", "Markers", 1, 0, cf_string, "late-control-markers"))
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not source.stopped:
            source.get_all()
        rows = {row["source_id"]: row for row in viewer.snapshot()}
        if (all(identity in rows for identity in [identity, source.calibrated_id, "late-control-markers"])
            and (source.stopped or all(row["signal"] == "live" for row in rows.values()))
            and rows['late-control-markers']['channels'][0]['value'] == 'late.marker'
            and "late-control-markers" in recorder.snapshot()["data_sources"]):
            break
        time.sleep(.025)
    else:
        raise AssertionError(viewer.snapshot())
    assert len(rows[identity]["channels"]) == 2
    assert rows[identity]["channels"][1]["unit"] == "N"
    assert rows["late-control-markers"]["channels"][0]["value"] == "late.marker"
    # Compare independent recorded streams at shared original sample timestamps.
    markers.emit("recording.finalizing")
    recorder.stop()
    summary = inspect_xdf(recorder.path, [identity, source.calibrated_id, markers.health_snapshot()["source_id"], "late-control-markers"])
    streams, _ = pyxdf.load_xdf(str(recorder.path), synchronize_clocks=False, dejitter_timestamps=False)
    by_id = {stream["info"]["source_id"][0]: stream for stream in streams}
    raw_values = [(timestamp, sample[1]) for timestamp, sample in zip(by_id[identity]["time_stamps"], by_id[identity]["time_series"])]
    derived = list(zip(by_id[source.calibrated_id]["time_stamps"], by_id[source.calibrated_id]["time_series"]))
    assert any(math.isnan(sample[0]) for _, sample in derived)
    assert any(math.isfinite(sample[0]) for _, sample in derived)
    for timestamp, sample in derived:
        if math.isnan(sample[0]):
            continue
        # The study inlet applies clock synchronization; native raw XDF retains producer timestamps.
        raw_time, raw_value = min(raw_values, key=lambda row: abs(row[0] - timestamp))
        assert abs(raw_time - timestamp) < .01
        assert abs(sample[0] - (raw_value - calibration_center) / calibration_amplitude) < 1e-5
    assert all(stream["sample_count"] > 0 for stream in summary)
    events = [json.loads(sample[0]) for sample in by_id[markers.health_snapshot()['source_id']]['time_series']]
    assert [event['seq'] for event in events] == list(range(events[0]['seq'], events[-1]['seq'] + 1))
    if '--full-study' in sys.argv:
        ended = [event for event in events if event['event'] == 'trial.ended']
        assert len(ended) == len(CONFIG.trial.build_conditions('001')) == 48
        assert any(event['event'] == 'run.completed' for event in events)
        assert not any(event['event'] in {'run.failed', 'run.aborted'} for event in events)
    print(json.dumps({"result": "passed", "full_study": '--full-study' in sys.argv, "trials": len(ended) if '--full-study' in sys.argv else 0,
                      "file": str(recorder.path), "preview_channels": sum(len(row["channels"]) for row in rows.values()), "streams": summary}))
finally:
    if recorder.process is not None:
        recorder.stop()
    viewer.close()
    if source is not None:
        source.stop()
    stop.set()
    thread.join()
