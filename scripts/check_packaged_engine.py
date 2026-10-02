"""Real embedded imports and native synthetic XDF round trip; no study display."""
import hashlib
import importlib
import importlib.util
import importlib.metadata as metadata
import json
import math
from pathlib import Path
import os
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

# Isolate synthetic streams from live lab recordings before importing liblsl.
proof = tempfile.TemporaryDirectory(prefix="respyra-package-check-")
config = Path(proof.name) / "lsl.cfg"
config.write_text("[lab]\nSessionID = respyra-package-check-" + uuid4().hex + "\n")
os.environ["LSLAPICFG"] = str(config)

engine = Path(__file__).resolve().parents[1]
runtime = engine / "python"
assert Path(sys.executable).resolve() == runtime / "python.exe"
assert sys.flags.isolated and sys.flags.no_user_site and sys.flags.dont_write_bytecode and sys.flags.utf8_mode
assert sys.stdout.encoding.lower() == "utf-8"
assert all(Path(path).resolve().is_relative_to(runtime) for path in sys.path), sys.path
for name in ("numpy", "scipy", "pandas", "matplotlib", "pylsl", "psychopy.core", "psychopy.visual",
             "psychopy.data", "psychopy.event", "pythoncom", "pywintypes",
             "mpi.lsl_force", "mpi.event_markers", "mpi.recording", "mpi.validation_study_jenny", "respyra.core.runner"):
    module = importlib.import_module(name)
    assert Path(module.__file__).resolve().is_relative_to(runtime), (name, module.__file__)
assert importlib.util.find_spec("ffpyplayer") is None
assert importlib.util.find_spec("imageio_ffmpeg") is None
assert importlib.util.find_spec("jupyterlab") is None
assert importlib.util.find_spec("ipympl") is None
assert importlib.util.find_spec("psycopg") is None
assert importlib.util.find_spec("PyQt6") is None
assert importlib.util.find_spec("cv2") is None
assert importlib.util.find_spec("pyarrow") is None
assert importlib.util.find_spec("soundfile") is None
assert importlib.util.find_spec("vlc") is None
assert importlib.util.find_spec("questplus") is None
assert importlib.util.find_spec("meshpy") is None
assert importlib.util.find_spec("tables") is None
assert importlib.util.find_spec("blosc2") is None
assert not (runtime / "share/ffpyplayer").exists()
assert not list(runtime.rglob("*ffmpeg*.exe"))
assert not list(runtime.rglob("*ffmpeg*.dll"))
assert not list(runtime.rglob("avcodec-*.dll"))
assert not list(runtime.rglob("avformat-*.dll"))
assert not list(runtime.rglob("avutil-*.dll"))
assert not list(runtime.rglob("swresample-*.dll"))
assert not list(runtime.rglob("swscale-*.dll"))
from mpi.event_markers import MarkerOutlet
import psutil
support = [Path(m.path) for m in psutil.Process().memory_maps()
           if "msvcp140" in m.path.lower() or "vcruntime140" in m.path.lower()]
for path in support:
    # NTFS may report an original name for an immutable build hardlink. Installed
    # copies must load their own files, never another environment/system CRT.
    assert path.is_relative_to(runtime) or any(path.samefile(candidate) for candidate in runtime.rglob(path.name)), path
markers = MarkerOutlet()
assert markers.health_snapshot()["online"]
catalog = runtime / "Lib/site-packages/mpi/event_markers/catalog.json"
assert catalog.is_file()
bundle = engine / "recorder"
manifest = json.loads((bundle / "manifest.json").read_text())
for name, expected in manifest["files"].items():
    assert Path(name).name == name
    assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == expected, name
from pylsl import StreamInfo, StreamOutlet, cf_float32, local_clock
from mpi.recording import NativeRecording
identity = "package-proof-" + uuid4().hex
derived_id = "respyra-breathing-" + uuid4().hex
raw = StreamOutlet(StreamInfo("Packaged recorder proof", "VernierRaw", 1, 50, cf_float32, identity))
derived = StreamOutlet(StreamInfo("Respyra-Calibrated-Breathing", "Respiration", 1, 50, cf_float32, derived_id))
stop = threading.Event()
def push():
    while not stop.wait(.02):
        raw.push_sample([5.0], local_clock())
        derived.push_sample([math.nan], local_clock())
worker = threading.Thread(target=push)
worker.start()
recorder = NativeRecording(bundle, proof.name)
try:
    recorder.start({"participant": "P001", "session": "001"},
                   SimpleNamespace(source_id=identity, calibrated_id=derived_id,
                                   get_all=lambda: []), markers)
    markers.emit("recording.finalizing")
    recorder.stop()
    assert recorder.phase == "complete" and recorder.path.suffix == ".xdf"
    assert len(recorder.summary) == 3 and all(s["sample_count"] > 0 for s in recorder.summary)
finally:
    try:
        if recorder.process is not None:
            recorder.stop()
    finally:
        stop.set()
        worker.join()
        proof.cleanup()
print(json.dumps({"result": "passed", "isolated": bool(sys.flags.isolated),
                  "python": sys.version.split()[0], "psychopy": metadata.version("psychopy"),
                  "respyra": metadata.version("respyra"), "pylsl": metadata.version("pylsl"),
                  "marker_outlet": markers.health_snapshot()["online"], "app_local_msvc": True,
                  "native_xdf_round_trip": True, "recorded_streams": recorder.summary}))
