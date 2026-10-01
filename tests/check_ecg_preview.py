"""Verify the desktop viewer forwards every 130 Hz ECG sample in ordered batches."""
import os
from pathlib import Path
import threading
import time
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
config = root / ".for-ai-local" / f"ecg-preview-{uuid4().hex}.cfg"
config.parent.mkdir(parents=True, exist_ok=True)
config.write_text(f"[lab]\nSessionID = respyra-ecg-preview-{uuid4().hex}\n", encoding="utf-8")
os.environ["LSLAPICFG"] = str(config)

from pylsl import StreamInfo, StreamOutlet, cf_float32, local_clock  # noqa: E402
from mpi.lsl_viewer import LSLViewer  # noqa: E402

identity = f"ecg-preview-{uuid4().hex}"
info = StreamInfo("Polar rawECG preview check", "ECG", 1, 130, cf_float32, identity)
channel = info.desc().append_child("channels").append_child("channel")
channel.append_child_value("label", "ECG")
channel.append_child_value("unit", "uV")
outlet = StreamOutlet(info)
viewer = LSLViewer("unused-marker-id")
try:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if any(row["source_id"] == identity for row in viewer.snapshot()) and outlet.have_consumers():
            break
        time.sleep(.05)
    else:
        raise AssertionError("ECG outlet was not discovered")

    source_time = local_clock()
    expected = [1000.0 if index in (10, 80) else float(index % 7) for index in range(130)]
    def publish():
        start = time.monotonic()
        for index, value in enumerate(expected):
            outlet.push_sample([value], source_time + index / 130)
            time.sleep(max(0, start + (index + 1) / 130 - time.monotonic()))

    sender = threading.Thread(target=publish)
    sender.start()
    received = []
    deadline = time.monotonic() + 4
    while len(received) < len(expected) and time.monotonic() < deadline:
        row = next(row for row in viewer.snapshot() if row["source_id"] == identity)
        received.extend(row["samples"])
        time.sleep(.1)
    sender.join(timeout=1)
    assert [sample[1] for sample in received] == expected, (len(received), len(expected))
    assert all(previous[0] < current[0] for previous, current in zip(received, received[1:]))
    assert not next(row for row in viewer.snapshot() if row["source_id"] == identity)["samples"]
    print(f"ECG preview passed: {len(received)} ordered samples at 130 Hz, both peaks preserved")
finally:
    viewer.close()
    del outlet
