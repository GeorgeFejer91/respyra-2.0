"""Configuration for the validation study (48 trials in four blocks).

Extends the base breath_tracking config with:
- 4 breath cycles per trial (40 s at 0.1 Hz)
- 12 trials per block, with feedback and no-feedback conditions
- Counterbalanced block order across odd/even participant numbers

To use: change the import in breath_tracking_task.py from
    from respyra.configs.breath_tracking import ...
to
    from respyra.configs.validation_study import ...

The selected participant number determines the block order. Odd participants
start with a feedback block; even participants (including 0) start without feedback.
"""

# ------------------------------------------------------------------ #
#  Inherit all defaults from the base config                          #
# ------------------------------------------------------------------ #
from respyra.configs.breath_tracking import (  # noqa: F401, E402
    BASELINE_DURATION_SEC,
    BG_COLOR,
    COUNTDOWN_DURATION_SEC,
    DATA_COLUMNS,
    DOT_COLOR_BAD,
    DOT_COLOR_GOOD,
    DOT_COLOR_MID,
    DOT_FEEDBACK_MODE,
    DOT_GRADED_MAX_ERROR_N,
    DOT_RADIUS,
    DOT_X_OFFSET,
    ERROR_THRESHOLD_MID_N,
    ERROR_THRESHOLD_N,
    ESCAPE_KEY,
    FORCE_SATURATION_HI,
    FORCE_SATURATION_LO,
    MONITOR_DISTANCE_CM,
    MONITOR_NAME,
    MONITOR_WIDTH_CM,
    RANGE_CAL_DURATION_SEC,
    RANGE_CAL_PERCENTILE_HI,
    RANGE_CAL_PERCENTILE_LO,
    RANGE_CAL_SCALE,
    TRACE_BORDER_COLOR,
    TRACE_BUFFER_SIZE,
    TRACE_COLOR,
    TRACE_RECT,
    TRACE_Y_RANGE,
    UNITS,
)
from respyra.core.target_generator import SegmentDef
from mpi.condition import ConditionDef
from mpi.recording import participant_number

# ------------------------------------------------------------------ #
#  Display override                                                    #
# ------------------------------------------------------------------ #
FULLSCR = True
MONITOR_SIZE_PIX = (1470, 956)

# ------------------------------------------------------------------ #
#  Conditions — 4 cycles per trial (40 s at 0.1 Hz)                  #
# ------------------------------------------------------------------ #
SLOW_STEADY = ConditionDef("normal", [SegmentDef(0.1, 4)])
PERTURBED_DEEP = ConditionDef("deep", [SegmentDef(0.1, 4)], feedback_gain=0.5)
PERTURBED_SHALLOW = ConditionDef("shallow", [SegmentDef(0.1, 4)], feedback_gain=1.5)

SLOW_STEADY_NO_FEEDBACK = ConditionDef("normal_no_feedback", [SegmentDef(0.1, 4)], feedback=False)
PERTURBED_SHALLOW_NO_FEEDBACK = ConditionDef(
    "shallow_no_feedback", [SegmentDef(0.1, 4)], feedback=False
)
PERTURBED_DEEP_NO_FEEDBACK = ConditionDef(
    "deep_no_feedback", [SegmentDef(0.1, 4)], feedback=False
)

# ------------------------------------------------------------------ #
#  Block size                                                          #
# ------------------------------------------------------------------ #
BLOCK_SIZE = 1
BLOCK_SIZE_HALF = 1

# ------------------------------------------------------------------ #
#  Trials                                                              #
# ------------------------------------------------------------------ #
N_REPS = 1  # trial list is fully expanded by build_conditions()
TRIAL_METHOD = "sequential"

# ------------------------------------------------------------------ #
#  Tracking duration — matches 4 cycles at 0.1 Hz                    #
# ------------------------------------------------------------------ #
TRACKING_DURATION_SEC = 40.0

# ------------------------------------------------------------------ #
#  Data output                                                         #
# ------------------------------------------------------------------ #
OUTPUT_DIR = "data/"


def build_conditions(participant: str) -> list[ConditionDef]:
    veridical_fb = SLOW_STEADY
    veridical_no_fb = SLOW_STEADY_NO_FEEDBACK
    deep_fb = PERTURBED_DEEP
    deep_no_fb = PERTURBED_DEEP_NO_FEEDBACK
    shallow_fb = PERTURBED_SHALLOW
    shallow_no_fb = PERTURBED_SHALLOW_NO_FEEDBACK

    number = participant_number(participant)
    if number is None:
        raise ValueError("Choose a participant number from 0 to 100")
    if number % 2 == 1:
        return (
            # block 1
            [veridical_fb] * 4
            + [shallow_fb] * 4
            + [deep_fb] * 4
            # block 2
            + [veridical_no_fb] * 4
            + [deep_no_fb] * 4
             + [shallow_no_fb] * 4
            # block 3
            + [shallow_fb] * 4
            + [deep_fb] * 4
            + [veridical_fb] * 4
            # block 4
            + [deep_no_fb] * 4
            + [shallow_no_fb] * 4
            + [veridical_no_fb] * 4
        )
    else:
        return (
            # block 1
            [veridical_no_fb] * 4
            + [shallow_no_fb] * 4
            + [deep_no_fb] * 4
            # block 2
            + [veridical_fb] * 4
            + [deep_fb] * 4
            + [shallow_fb] * 4
            # block 3
            + [shallow_no_fb] * 4
            + [deep_no_fb] * 4
            + [veridical_no_fb] * 4
            # block 4
            + [deep_fb] * 4
            + [shallow_fb] * 4
            + [veridical_fb] * 4
        )


# ------------------------------------------------------------------ #
#  Structured config (for use with respyra.core.runner)                #
# ------------------------------------------------------------------ #
from dataclasses import replace as _replace  # noqa: E402

from respyra.configs.breath_tracking import CONFIG as _BASE  # noqa: E402
from respyra.configs.experiment_config import TrialConfig as _TrialConfig  # noqa: E402

CONFIG = _replace(
    _BASE,
    name="Validation Study 1.0",
    display=_replace(_BASE.display, fullscr=FULLSCR, monitor_size_pix=MONITOR_SIZE_PIX),
    timing=_replace(_BASE.timing, tracking_duration_sec=TRACKING_DURATION_SEC),
    trial=_TrialConfig(
        n_reps=N_REPS,
        method=TRIAL_METHOD,
        build_conditions=build_conditions,
    ),
)
