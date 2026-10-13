"""Real native XDF proof: pre-calibration raw/markers and a late numeric stream."""
import json
import ctypes
import math
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".for-ai-local/recording-proof/Unicode café"
OUTPUT.mkdir(parents=True, exist_ok=True)
config = OUTPUT / (uuid4().hex + ".cfg")
config.write_text("[lab]\nSessionID = respyra-recorder-proof-" + uuid4().hex + "\n")
os.environ["LSLAPICFG"] = str(config)
# liblsl reads its config on first import; run this as a separate process.
from pylsl import StreamInfo, StreamOutlet, cf_float32, cf_int64, local_clock
from mpi.event_markers import MarkerOutlet
from mpi.recording import NativeRecording, inspect_xdf
import pyxdf
from pylsl.lib import lib

# pylsl disables its int64 wrapper on Windows; the pinned SDK's typed C ABI is
# available. Exercise that ABI directly in this fixture, never in product code.
push_int64 = lib.lsl_push_sample_ltp
push_int64.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64), ctypes.c_double, ctypes.c_int32]
push_int64.restype = ctypes.c_int32


def main():
    markers = MarkerOutlet()
    identity = "recording-proof-force-" + uuid4().hex
    derived_id = "respyra-breathing-" + markers.run_id
    raw_info = StreamInfo("Recorder proof Force", "VernierRaw", 1, 50, cf_float32, identity)
    for key, value in {"manufacturer": "Vernier", "model": "GDX-RB-MOCK",
                       "stream_role": "raw_measurement_recording"}.items():
        raw_info.desc().append_child_value(key, value)
    channel = raw_info.desc().append_child("channels").append_child("channel")
    for key, value in {"label": "Force", "unit": "N", "sensor_number": "1",
                       "type": "RawMeasurement", "role": "measurement"}.items():
        channel.append_child_value(key, value)
    raw = StreamOutlet(raw_info)
    derived_info = StreamInfo("Respyra_rawForce_calibrated", "Respiration", 1, 50, cf_float32, derived_id)
    derived_info.desc().append_child_value("raw_source_id", identity)
    channel = derived_info.desc().append_child("channels").append_child("channel")
    for key, value in {"label": "Calibrated breathing", "unit": "normalized", "role": "waveform"}.items():
        channel.append_child_value(key, value)
    derived = StreamOutlet(derived_info)
    omitted_id = "recording-proof-omitted-" + uuid4().hex
    omitted = StreamOutlet(StreamInfo("Unchecked stream", "Auxiliary", 1, 50, cf_float32, omitted_id))
    empty_link_id = "polar-mini-quiet-" + uuid4().hex + "-signal-status"
    empty_link_info = StreamInfo("Polar_Link", "Markers", 1, 0, cf_float32, empty_link_id)
    empty_link = StreamOutlet(empty_link_info)
    stop = threading.Event()
    calibrated = threading.Event()
    later = []
    def push():
        while not stop.wait(.02):
            raw.push_sample([5.0], local_clock())
            derived.push_sample([0.0 if calibrated.is_set() else math.nan], local_clock())
            omitted.push_sample([7.0], local_clock())
            for outlet, value in later:
                if isinstance(value, int):
                    assert push_int64(outlet.obj, (ctypes.c_int64 * 1)(value), local_clock(), 1) == 0
                else:
                    outlet.push_sample([value], local_clock())
    worker = threading.Thread(target=push)
    worker.start()
    recorder = NativeRecording(ROOT / ".for-ai-local/recorder/runtime", OUTPUT)
    try:
        recorder.start({"participant": "P002", "session": "001", "variables": [{"label": "Age", "value": "28"}]},
                       SimpleNamespace(source_id=identity, uid=raw.get_info().uid(),
                                       calibrated_id=derived_id, calibrated_uid=derived.get_info().uid(),
                                       get_all=lambda: derived.push_sample([math.nan], local_clock())), markers,
                       excluded_uids={omitted.get_info().uid(), raw.get_info().uid(),
                                      derived.get_info().uid(), markers.uid})
        start = local_clock()
        markers.emit("run.started", participant="native test", session="001")
        markers.phase = "calibration"
        markers.emit("calibration.attempt.started")
        time.sleep(.5)
        markers.emit("calibration.completed", center_n=5.0, amplitude_n=2.0, y_min_n=3.0, y_max_n=7.0,
                     center_value=5.0, amplitude_value=2.0, y_min_value=3.0, y_max_value=7.0,
                     signal_unit="N", input_polarity=None)
        calibrated.set()
        recorder.wait_for_finite_data(derived_id)
        late_id = "recording-proof-late-" + uuid4().hex
        later.append((StreamOutlet(StreamInfo("Late processed breathing", "Respiration", 1, 50, cf_float32, late_id)), .25))
        later.append((StreamOutlet(StreamInfo("Late anonymous stream", "Counters", 1, 50, cf_int64, "")), 2**53+1))
        link_id = "vernier-mini-late-" + uuid4().hex + "-signal-status"
        link_info = StreamInfo("Vernier_Link", "Markers", 1, 0, cf_float32, link_id)
        link_info.desc().append_child_value("manufacturer", "Vernier")
        link_info.desc().append_child_value("stream_role", "signal_continuity_markers")
        channel = link_info.desc().append_child("channels").append_child("channel")
        for key, value in {"label": "signal_state", "unit": "code", "type": "Marker", "role": "event"}.items():
            channel.append_child_value(key, value)
        late_link = StreamOutlet(link_info)
        deadline = time.monotonic() + 6
        while not late_link.have_consumers():
            assert time.monotonic() < deadline, "Late Link stream was not subscribed by the recorder"
            recorder.check_health()
            time.sleep(.02)
        late_link.push_sample([1.0], local_clock())
        late_link.push_sample([2.0], local_clock())
        deadline = time.monotonic() + 6
        while late_id not in [s["source_id"] for s in recorder.snapshot()["streams"]] or not any(
                s["name"] == "Late anonymous stream" for s in recorder.snapshot()["streams"]):
            assert time.monotonic() < deadline, "Late stream was not subscribed"
            recorder.check_health()
            time.sleep(.05)
        time.sleep(.5)
        markers.emit("run.aborted", reason="synthetic_proof", trials_completed=0)
        markers.emit("display.closed")
        markers.emit("recording.finalizing")
        recorder.stop()
        assert recorder.phase == "complete" and recorder.process is None
        assert recorder.path.name.startswith("P002_Session-001_Age-28_")
        participant = json.loads((OUTPUT / "participant-list.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        assert participant == {"xdf_file": recorder.path.name, "participant_number": "P002",
                               "session": "001", "variables": [{"label": "Age", "value": "28"}]}
        summaries = inspect_xdf(recorder.path, [identity, derived_id, late_id, markers.health_snapshot()["source_id"]])
        streams, _ = pyxdf.load_xdf(str(recorder.path), synchronize_clocks=False,
                                   dejitter_timestamps=False)
        by_id = {s["info"]["source_id"][0] or "": s for s in streams}
        assert omitted_id not in by_id, "Unchecked stream must stay out of XDF"
        assert by_id[identity]["time_stamps"][0] < start, "Raw recording must precede calibration/run markers"
        derived_values = [float(row[0]) for row in by_id[derived_id]["time_series"]]
        assert any(math.isnan(value) for value in derived_values)
        assert any(math.isfinite(value) for value in derived_values)
        events = [json.loads(row[0]) for row in by_id[markers.health_snapshot()["source_id"]]["time_series"]]
        names = [e["event"] for e in events]
        recording_start = next(event for event in events if event["event"] == "recording.started")
        assert (recording_start["subject"], recording_start["session"], recording_start["task"]) == ("002", "001", "respyra")
        assert recording_start["variables"] == [{"label": "Age", "value": "28"}]
        for name in ["recording.started", "run.started", "calibration.attempt.started", "calibration.completed", "run.aborted", "display.closed", "recording.finalizing"]:
            assert name in names, (name, names)
        assert names.index("recording.started") < names.index("calibration.completed") < names.index("display.closed")
        assert [e["seq"] for e in events] == list(range(events[0]["seq"], events[-1]["seq"] + 1))
        assert by_id[late_id]["time_stamps"][0] > start
        assert len(streams) == 7 and len(by_id[""]["time_stamps"]) > 0
        assert not any(s["info"]["name"][0] == "Respyra_Housekeeping" for s in streams)
        assert list(by_id[link_id]["time_series"][:, 0]) == [1.0, 2.0]
        assert len(by_id[empty_link_id]["time_stamps"]) == 0
        assert next(s for s in summaries if s["source_id"] == empty_link_id)["footer"] == 0
        assert int(by_id[""]["time_series"][0][0]) == 2**53+1
        print(json.dumps({"result": "passed", "file": str(recorder.path), "streams": summaries, "events": names}))
    finally:
        try:
            if recorder.process is not None:
                recorder.stop()
        finally:
            stop.set()
            worker.join()


if __name__ == "__main__":
    main()
