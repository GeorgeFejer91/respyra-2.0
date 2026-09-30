"""Opt-in fast PsychoPy responses for an isolated native full-study check."""

import os
import sys

if (os.environ.get("RESPYRA_FULL_MOCK_STUDY") == "1"
        and sys.argv[0].endswith("run_experiment.py")
        and "--desktop" in sys.argv):
    import copy

    from mpi import event_markers, validation_study_jenny
    from psychopy import core, event

    config = copy.deepcopy(validation_study_jenny.CONFIG)
    config.display.fullscr = False
    config.display.monitor_size_pix = (800, 600)
    config.timing.range_cal_duration_sec = 1.5
    config.timing.baseline_duration_sec = .15
    config.timing.countdown_duration_sec = .1
    config.timing.tracking_duration_sec = float(os.environ.get("RESPYRA_TEST_TRACKING_SECONDS", ".15"))
    validation_study_jenny.CONFIG = config

    current = {}
    original_init = event_markers.MarkerOutlet.__init__

    def marker_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        current["markers"] = self

    def wait_keys(*args, **kwargs):
        screen = getattr(current.get("markers"), "screen", None)
        return ["1" if screen in {"accuracy", "confidence"}
                else "n" if screen == "breathing_judgment" else "space"]

    event_markers.MarkerOutlet.__init__ = marker_init
    event.getKeys = lambda **kwargs: []
    event.waitKeys = wait_keys
    core.quit = lambda: None
