"""Observe installed error windows using sample loss and a terminated engine.

Run through a private Win32 desktop launcher; never the active user desktop.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from uuid import uuid4

import psutil

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "tests"))
from check_native_keyboard import require_private_desktop
require_private_desktop()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("exe", type=Path)
args = parser.parse_args()
evidence = root / ".for-ai-local" / ("diagnostics-native-" + uuid4().hex)
evidence.mkdir(parents=True)
log = (evidence / "check.log").open("w", encoding="utf-8", buffering=1)
sys.stdout = sys.stderr = log
config = evidence / "lsl.cfg"
config.write_text("[lab]\nSessionID = respyra-diagnostics-" + uuid4().hex + "\n")
os.environ["LSLAPICFG"] = str(config)
from pylsl import StreamInfo, StreamOutlet, cf_float32, local_clock

info = StreamInfo("Diagnostic synthetic Force", "VernierRaw", 1, 20, cf_float32,
                  "polar-stream-vernier-raw-diagnostic-" + uuid4().hex)
desc = info.desc()
for key, value in {"manufacturer":"Vernier", "model":"GDX-RB", "stream_role":"raw_measurement_recording"}.items():
    desc.append_child_value(key, value)
channel = desc.append_child("channels").append_child("channel")
for key, value in {"label":"Force", "unit":"N", "sensor_number":"1", "type":"RawMeasurement"}.items():
    channel.append_child_value(key, value)
outlet = StreamOutlet(info)
stop, paused = threading.Event(), threading.Event()
def push():
    while not stop.wait(.05):
        if not paused.is_set():
            outlet.push_sample([5 + math.sin(local_clock())], local_clock())
thread = threading.Thread(target=push)
thread.start()
env = os.environ.copy()
env.update(LOCALAPPDATA=str(evidence / "settings"),
           WEBVIEW2_USER_DATA_FOLDER=str(evidence / "webview"),
           WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--remote-debugging-port=9227",
           RESPYRA_DIAGNOSTIC_DROP_FILE=str(evidence / "drop"),
           RESPYRA_DIAGNOSTIC_EVIDENCE=str(evidence))
results = []
try:
    for mode in ("on", "off", "remember", "native-exit"):
        paused.clear()
        Path(env["RESPYRA_DIAGNOSTIC_DROP_FILE"]).unlink(missing_ok=True)
        process = subprocess.Popen([str(args.exe.resolve())], cwd=evidence, env=env,
                                   stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        ui = subprocess.Popen(["node", str(root / "tests/check_native_diagnostics.cjs"), mode],
                              cwd=root, env=env, stdout=log, stderr=log,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        dropped = False
        try:
            deadline = time.monotonic() + 130
            while process.poll() is None and time.monotonic() < deadline:
                if Path(env["RESPYRA_DIAGNOSTIC_DROP_FILE"]).exists() and not dropped:
                    dropped = True
                    if mode == "native-exit":
                        children = [child for child in psutil.Process(process.pid).children()
                                    if child.name().lower() == "python.exe"]
                        assert len(children) == 1
                        children[0].kill()
                    else:
                        paused.set()
                if ui.poll() not in (None, 0):
                    raise AssertionError(f"Native diagnostics UI failed: {ui.returncode}")
                time.sleep(.1)
            assert process.wait(timeout=5) == 0
            assert ui.wait(timeout=5) == 0
            assert dropped == (mode != "remember")
            results.append({"mode":mode, "result":"passed"})
        finally:
            for child in (ui, process):
                if child.poll() is None:
                    for descendant in psutil.Process(child.pid).children(recursive=True):
                        try: descendant.kill()
                        except psutil.NoSuchProcess: pass
                    child.kill()
                child.wait()
    (evidence / "result.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results), flush=True)
finally:
    stop.set()
    thread.join()
