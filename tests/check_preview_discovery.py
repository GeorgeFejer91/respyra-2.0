"""Real LSL discovery for the standalone preview, isolated from lab streams."""

import math
import os
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
local = root / ".for-ai-local"
local.mkdir(exist_ok=True)
config = local / f"preview-lsl-{uuid4().hex}.cfg"
config.write_text(f"[lab]\nSessionID = respyra-preview-{uuid4().hex}\n", encoding="utf-8")
os.environ["LSLAPICFG"] = str(config)
sys.path.insert(0, str(root / "scripts"))

from pylsl import StreamInfo, StreamOutlet, cf_float32, local_clock  # noqa: E402
from preview_lsl_ui import Discovery  # noqa: E402

identity = "polar-stream-vernier-raw-preview-" + uuid4().hex
info = StreamInfo("Preview check raw Force", "VernierRaw", 1, 20, cf_float32, identity)
desc = info.desc()
for key, value in {"manufacturer": "Vernier", "model": "GDX-RB", "stream_role": "raw_measurement_recording"}.items():
    desc.append_child_value(key, value)
channel = desc.append_child("channels").append_child("channel")
for key, value in {"label": "Force", "unit": "N", "sensor_number": "1", "type": "RawMeasurement"}.items():
    channel.append_child_value(key, value)
outlet = StreamOutlet(info)
stop = threading.Event()


def push():
    while not stop.wait(.05):
        outlet.push_sample([5 + math.sin(local_clock())], local_clock())


thread = threading.Thread(target=push, daemon=True)
thread.start()
discovery = Discovery()
try:
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        rows = [row for row in discovery.snapshot()["streams"] if row["source_id"] == identity]
        if rows and rows[0]["compatible"] and rows[0]["signal"] == "live" and isinstance(rows[0]["channels"][0]["value"], float):
            break
        time.sleep(.1)
    else:
        raise AssertionError(f"Valid live Force outlet was not discovered: {rows}")
    assert rows[0]["channels"][0]["unit"] == "N"
    print("Preview bridge discovered and validated an isolated live Force (N) outlet.")
finally:
    discovery.close()
    stop.set()
    thread.join(timeout=2)
    config.unlink(missing_ok=True)
