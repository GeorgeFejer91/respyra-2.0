"""Regression: real PsychoPy import, private pipes and real LSL subscription."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid

from mpi.desktop_bridge import PREFIX


def test_importing_launcher_does_not_load_study_or_psychopy():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-c", (
        "import runpy, sys; runpy.run_path('scripts/run_experiment.py'); "
        "assert not {'psychopy', 'respyra', 'numpy'} & sys.modules.keys()"
    )], cwd=root, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_engine_enables_form_and_keeps_markers_alive_through_close(tmp_path):
    # Load liblsl in a fresh process with a private logical session so an
    # already-running recorder cannot subscribe before this test's inlet.
    config = tmp_path / "lsl_api.cfg"
    config.write_text(f"[lab]\nSessionID = respyra-test-{uuid.uuid4().hex}\n", encoding="utf-8")
    result = subprocess.run([sys.executable, __file__, str(tmp_path)],
                            env={**os.environ, "LSLAPICFG": str(config)},
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr


def check_engine_lifecycle(tmp_path):
    from pylsl import StreamInlet, cf_string, resolve_byprop
    from pylsl.util import LostError

    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "LOCALAPPDATA": str(tmp_path)}
    env.pop("RESPYRA_LSL_SOURCE_ID", None)
    states = queue.Queue()
    with (tmp_path / "engine-stderr.txt").open("w", encoding="utf-8") as stderr:
        child = subprocess.Popen([sys.executable, "-u", "scripts/run_experiment.py", "--desktop"],
                                 cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=stderr, text=True, encoding="utf-8")
        def read():
            for line in child.stdout:
                if line.startswith(PREFIX): states.put(json.loads(line[len(PREFIX):]))
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        inlet = None
        try:
            waiting = states.get(timeout=10)
            assert waiting["phase"] == "waiting_recorder"
            streams = resolve_byprop("source_id", "respyra-events-" + waiting["run_id"], timeout=5)
            assert len(streams) == 1
            info = streams[0]
            assert (info.name(), info.type(), info.channel_count(), info.nominal_srate()) == (
                "Respyra-Events", "Markers", 1, 0.0,
            )
            assert info.channel_format() == cf_string
            # The recorder may be opened after the old 30-second startup deadline.
            # No belt outlet or marker inlet exists yet: discovery is independent.
            time.sleep(31)
            assert child.poll() is None and states.empty(), list(states.queue)
            rediscovered = resolve_byprop("source_id", info.source_id(), timeout=5)
            assert len(rediscovered) == 1 and rediscovered[0].uid() == info.uid()
            inlet = StreamInlet(streams[0], recover=False)
            inlet.open_stream(timeout=5)
            setup = states.get(timeout=8)
            assert setup["phase"] == "setup" and not setup["can_start"]
            for seq, action in enumerate([
                {"action": "shown"},
                {"action": "field_key", "field": "participant", "key": "A"},
                {"action": "field_edit", "field": "participant", "value": "synthetic"},
                {"action": "cancel"},
            ], 1):
                child.stdin.write(json.dumps({**action, "ui_seq": seq, "ui_time_ms": float(seq)}) + "\n")
                child.stdin.flush()
            while states.get(timeout=5)["phase"] != "finished": pass
            assert child.poll() is None  # outlet survives the completed setup
            payloads = []
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                sample, _ = inlet.pull_sample(timeout=0.1)
                if sample:
                    payloads.append(json.loads(sample[0]))
                    if payloads[-1]["event"] == "run.aborted": break
            names = [p["event"] for p in payloads]
            assert names[0] == "run.recorder_connected" and "run.aborted" in names
            assert "participant.field.key" in names and "participant.dialog.hidden" in names
            child.stdin.write('{"action":"shutdown","reason":"close_button"}\n')
            child.stdin.flush()
            # Read until the final named button event, then permit publisher exit.
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                try: sample, _ = inlet.pull_sample(timeout=0.1)
                except LostError: break
                if sample: payloads.append(json.loads(sample[0]))
                if payloads[-1]["event"] == "ui.wrapper.closed": break
            assert payloads[-2]["event"] == "ui.wrapper.close_button.clicked"
            assert payloads[-1]["event"] == "ui.wrapper.closed"
            assert [p["seq"] for p in payloads] == list(range(1, len(payloads) + 1))
            child.wait(timeout=5)
            assert child.returncode == 0
            assert not list(tmp_path.rglob("*.csv"))
        finally:
            if child.poll() is None:
                child.stdin.close()
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired: child.kill(); child.wait()
            if inlet is not None: inlet.close_stream()
            reader.join(timeout=1)
            child.stdout.close()


if __name__ == "__main__":
    check_engine_lifecycle(Path(sys.argv[1]))
