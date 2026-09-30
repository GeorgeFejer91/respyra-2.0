"""Optional input hooks have a real Windows lifecycle and one marker owner."""
import os

import pytest

from mpi.input_capture import InputCapture
from mpi.event_markers import CATALOG


@pytest.mark.skipif(os.name != "nt", reason="Windows input hooks")
@pytest.mark.parametrize("keyboard,mouse", [(True, False), (False, True), (True, True)])
def test_optional_hooks_initialize_and_stop(keyboard, mouse):
    capture = InputCapture(keyboard, mouse)
    try:
        assert capture.thread.is_alive() and capture.error is None
        events = []
        class Markers:
            def emit(self, name, **fields):
                assert set(CATALOG["events"][name]["fields"]) <= fields.keys()
                events.append((name, fields))
        # Publication runs on the study owner, retaining callback time separately.
        fields = dict(input_action="down", event_lsl_time=123.5, scope="respyra_windows",
                      vk_code=65, scan_code=30, flags=0)
        capture.events.put(("input.keyboard_event", fields))
        capture.poll(Markers())
        assert ("input.keyboard_event", fields) in events
    finally:
        capture.close()
    assert not capture.thread.is_alive()
