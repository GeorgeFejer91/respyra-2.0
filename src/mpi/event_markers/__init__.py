"""Named LSL markers for discrete Respyra experiment events."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


CATALOG = json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))


def prompt_name(text: str) -> str:
    """Fail if a new screen lacks an explicit marker identity."""
    if text.startswith("Breathing Range Calibration"):
        return "calibration_ready"
    if text.startswith("Calibration Complete"):
        return "calibration_result"
    if text.startswith("Trial ") and " complete." in text:
        return "trial_feedback"
    if text.startswith("Trial ") and " of " in text:
        return "trial_ready"
    if text.startswith("On a scale of 1 (very inaccurate)"):
        return "accuracy"
    if text.startswith("Did you feel like you had to breathe"):
        return "breathing_judgment"
    if text.startswith("On a scale of 1 (completely unsure)"):
        return "confidence"
    if text.startswith("Experiment complete!"):
        return "end"
    if text.endswith("Press SPACE to begin."):
        return "instructions"
    raise ValueError("Undocumented experiment screen; add its event markers to catalog.json")


class MarkerOutlet:
    """Publish catalogued JSON events on one LSL string marker channel."""

    def __init__(self) -> None:
        from pylsl import StreamInfo, StreamOutlet, cf_string, local_clock

        self._clock = local_clock
        self.run_id = str(uuid4())
        self.sequence = 0
        self.trial_num: int | None = None
        self.condition: str | None = None
        self.phase: str | None = None
        self.screen: str | None = None
        self.state = None
        self.observer = None
        self.calibration_attempt_open = False
        info = StreamInfo(
            "Respyra-Events", "Markers", 1, 0.0, cf_string,
            f"respyra-events-{self.run_id}",
        )
        desc = info.desc()
        desc.append_child_value("schema", CATALOG["schema"])
        desc.append_child_value("payload_format", "json")
        desc.append_child_value("application", "Respyra 2.0")
        self._outlet = StreamOutlet(info)

    def wait_for_recorder(self, timeout: float | None = 30.0, cancel_check=None) -> None:
        """Keep the advertised outlet alive; None waits until subscription or cancellation."""
        if cancel_check is None and timeout is not None:
            connected = self._outlet.wait_for_consumers(timeout)
        else:
            deadline = float("inf") if timeout is None else time.monotonic() + timeout
            connected = False
            while time.monotonic() < deadline:
                if cancel_check is not None:
                    cancel_check()
                if self._outlet.wait_for_consumers(min(0.1, deadline - time.monotonic())):
                    connected = True
                    break
        if not connected:
            raise RuntimeError("No LSL recorder subscribed to Respyra-Events")

    def start_calibration_attempt(self) -> None:
        self.emit("calibration.attempt.started")
        self.calibration_attempt_open = True

    def end_calibration_attempt(self, outcome: str) -> None:
        if self.calibration_attempt_open and self.state is not None:
            self.emit("calibration.attempt.ended", outcome=outcome,
                      center_n=self.state.range_center,
                      amplitude_n=self.state.global_amplitude,
                      y_min_n=self.state.y_min, y_max_n=self.state.y_max)
            self.calibration_attempt_open = False

    def emit(self, name: str, **fields) -> None:
        if name not in CATALOG["events"]:
            raise ValueError(f"Undocumented LSL marker: {name}")
        missing = set(CATALOG["events"][name]["fields"]) - fields.keys()
        if missing:
            raise ValueError(f"{name} is missing marker fields: {sorted(missing)}")
        if not self._outlet.have_consumers():
            raise RuntimeError("Respyra-Events has no LSL recorder subscriber")
        self.sequence += 1
        timestamp = self._clock()
        payload = {
            "schema": CATALOG["schema"], "event": name,
            "run_id": self.run_id, "seq": self.sequence,
            "lsl_time": timestamp, "trial": self.trial_num,
            "condition": self.condition, "phase": self.phase,
            "screen": self.screen, **fields,
        }
        self._outlet.push_sample(
            [json.dumps(payload, separators=(",", ":"), allow_nan=False)],
            timestamp=timestamp,
        )
        if self.observer is not None:
            self.observer(payload)

    @contextmanager
    def observe_inputs_and_screens(self, cancel_check=None):
        """Mark accepted/rejected keys and every known respyra text screen."""
        from psychopy import event
        from respyra.core import display, events

        original_wait = event.waitKeys
        original_clear = event.clearEvents
        original_get = event.getKeys
        original_check = events.check_keys
        original_show = display.show_text_and_wait

        def mark_key(key, accepted: bool, source: str, psychopy_time=None):
            self.emit("input.key", key=key, accepted=accepted, source=source,
                      psychopy_time=psychopy_time)
            if key == "escape":
                self.emit("input.escape", source=source)

        def observed_wait(*args, **kwargs):
            allowed = kwargs.pop("keyList", None)
            deadline = time.monotonic() + kwargs.get("maxWait", float("inf"))
            while True:
                if cancel_check is not None:
                    cancel_check()
                    kwargs["maxWait"] = min(0.1, max(0, deadline - time.monotonic()))
                keys = original_wait(*args, keyList=None, **kwargs)
                if cancel_check is not None:
                    kwargs["clearEvents"] = False
                if keys is None:
                    if cancel_check is not None and time.monotonic() < deadline:
                        continue
                    return None
                accepted = []
                for item in keys:
                    key = item[0] if isinstance(item, (list, tuple)) else item
                    key_time = item[1] if isinstance(item, (list, tuple)) and len(item) > 1 else None
                    mark_key(key, allowed is None or key in allowed, "waitKeys", key_time)
                    if allowed is None or key in allowed:
                        accepted.append(item)
                if accepted:
                    return accepted

        def observed_check(key_list=None, clock=None):
            if cancel_check is not None:
                cancel_check()
            keys = original_check(None, clock)
            for key, timestamp in keys:
                mark_key(key, key_list is None or key in key_list,
                         "check_keys", timestamp)
            return [(key, timestamp) for key, timestamp in keys
                    if key_list is None or key in key_list]

        def observed_clear(*args, **kwargs):
            if cancel_check is not None:
                cancel_check()
            event_type = args[0] if args else kwargs.get("eventType")
            if event_type in (None, "keyboard"):
                for key, timestamp in original_get(keyList=None, timeStamped=True):
                    mark_key(key, False, "clearEvents", timestamp)
            return original_clear(*args, **kwargs)

        def observed_show(win, text, key_list=None, **kwargs):
            screen = prompt_name(text)
            previous_screen = self.screen
            self.screen = screen
            if screen == "calibration_result" and self.state is not None:
                self.end_calibration_attempt("result")
                if "WARNING: Sensor saturation detected" in text:
                    self.emit("calibration.saturation")
            win.callOnFlip(self.emit, f"ui.{screen}.shown")
            try:
                result = original_show(win, text, key_list=key_list, **kwargs)
                key = result[0] if isinstance(result, tuple) else result
                self.emit(f"ui.{screen}.dismissed", key=key)
                if screen == "calibration_ready" and key == "space":
                    if self.state is not None:
                        self.state.belt.get_all()  # discard samples from the ready screen
                    win.callOnFlip(self.start_calibration_attempt)
                if screen == "trial_ready" and key == "space" and self.state is not None:
                    self.state.belt.get_all()  # baseline starts with fresh samples
                if screen == "calibration_result":
                    if key == "r":
                        self.emit("calibration.retry")
                    elif key == "space":
                        self.emit("calibration.accepted")
                return result
            finally:
                self.screen = previous_screen

        event.waitKeys = observed_wait
        event.clearEvents = observed_clear
        events.check_keys = observed_check
        display.show_text_and_wait = observed_show
        try:
            yield observed_show
        finally:
            event.waitKeys = original_wait
            event.clearEvents = original_clear
            events.check_keys = original_check
            display.show_text_and_wait = original_show

    @contextmanager
    def phase_scope(self, name: str, win, **fields):
        previous_phase = self.phase
        self.phase = name
        win.callOnFlip(self.emit, f"{name}.started", **fields)
        try:
            yield
        finally:
            self.emit(f"{name}.ended")
            self.phase = previous_phase

    @contextmanager
    def countdown_ticks(self, win, stimulus):
        original_flip = win.flip
        last = None

        def observed_flip(*args, **kwargs):
            nonlocal last
            value = stimulus.text
            if value != last:
                win.callOnFlip(self.emit, "countdown.tick", number=int(value))
            result = original_flip(*args, **kwargs)
            if value != last:
                last = value
            return result

        win.flip = observed_flip
        try:
            yield
        finally:
            win.flip = original_flip


class NullSampleLogger:
    """Satisfy respyra's phase API without writing a local data file."""

    def log_row(self, **_fields) -> None:
        pass

    def flush(self, *_args, **_kwargs) -> None:
        pass
