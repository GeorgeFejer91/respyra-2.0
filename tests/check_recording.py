"""Real native XDF proof: pre-calibration raw/markers and a late numeric stream."""
import json
import ctypes
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
    identity = "recording-proof-force-" + uuid4().hex
    raw = StreamOutlet(StreamInfo("Recorder proof Force", "VernierRaw", 1, 50, cf_float32, identity))
    markers = MarkerOutlet()
    stop = threading.Event()
    later = []
    def push():
        while not stop.wait(.02):
            raw.push_sample([5.0], local_clock())
            for outlet, value in later:
                if isinstance(value, int):
                    assert push_int64(outlet.obj, (ctypes.c_int64 * 1)(value), local_clock(), 1) == 0
                else:
                    outlet.push_sample([value], local_clock())
    worker = threading.Thread(target=push)
    worker.start()
    recorder = NativeRecording(ROOT / ".for-ai-local/recorder/runtime", OUTPUT)
    try:
        recorder.start({"participant": "native test", "session": "001"},
                       SimpleNamespace(source_id=identity), markers)
        start = local_clock()
        markers.emit("run.started", participant="native test", session="001")
        markers.phase = "calibration"
        markers.emit("calibration.attempt.started")
        time.sleep(.5)
        markers.emit("calibration.completed", center_n=5.0, amplitude_n=2.0, y_min_n=3.0, y_max_n=7.0)
        late_id = "recording-proof-late-" + uuid4().hex
        later.append((StreamOutlet(StreamInfo("Late processed breathing", "Respiration", 1, 50, cf_float32, late_id)), .25))
        later.append((StreamOutlet(StreamInfo("Late anonymous stream", "Counters", 1, 50, cf_int64, "")), 2**53+1))
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
        summaries = inspect_xdf(recorder.path, [identity, late_id, markers.health_snapshot()["source_id"]])
        streams, _ = pyxdf.load_xdf(str(recorder.path))
        by_id = {s["info"]["source_id"][0] or "": s for s in streams}
        assert by_id[identity]["time_stamps"][0] < start, "Raw recording must precede calibration/run markers"
        events = [json.loads(row[0]) for row in by_id[markers.health_snapshot()["source_id"]]["time_series"]]
        names = [e["event"] for e in events]
        for name in ["recording.started", "run.started", "calibration.attempt.started", "calibration.completed", "run.aborted", "display.closed", "recording.finalizing"]:
            assert name in names, (name, names)
        assert names.index("recording.started") < names.index("calibration.completed") < names.index("display.closed")
        assert [e["seq"] for e in events] == list(range(events[0]["seq"], events[-1]["seq"] + 1))
        assert by_id[late_id]["time_stamps"][0] > start
        assert len(streams) == 4 and len(by_id[""]["time_stamps"]) > 0
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
