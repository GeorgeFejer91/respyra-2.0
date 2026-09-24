from __future__ import annotations

import colorsys
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from respyra.configs.experiment_config import ExperimentConfig
from respyra.core.breath_belt import BreathBelt, BreathBeltError
from respyra.core.data_logger import DataLogger, create_session_file
from respyra.core.target_generator import TargetGenerator, calibrate_from_baseline
from respyra.core.runner import (
    connect_belt,
    setup_display,
    run_participant_dialog,
    apply_gain,
    _compute_dot_color,
    _force_to_dot_y,
    run_countdown,
    run_baseline,
    run_range_calibration,
    #  run_tracking,
    ExperimentState,
    show_trial_feedback,
    show_end_screen,
)


def main():
    from respyra.configs.breath_tracking import CONFIG as _default_cfg
    from mpi.validation_study_jenny import CONFIG as _cfg

    cfg = _cfg
    # cfg.display.fullscr = True
    run_experiment(cfg)


def run_tracking(
    state: ExperimentState,
    cfg: ExperimentConfig,
    condition_def,
    target_gen: TargetGenerator,
    condition_name: str,
    trial_num: int,
    total_trials: int,
) -> tuple[list[float], bool]:
    """Run the active tracking phase for one trial.

    Returns
    -------
    trial_errors : list[float]
        Absolute compensated errors for each sample.
    escaped : bool
    """
    from respyra.core.events import check_keys

    s = state
    escape = cfg.escape_key
    feedback_gain = condition_def.feedback_gain
    trace_left, trace_bottom, trace_right, trace_top = cfg.trace.rect
    target_dot = s.stimuli["target_dot"]
    trial_errors: list[float] = []

    target_dot.lineColor = "#aaaaaa"
    target_dot.fillColor = "#aaaaaa"

    s.stimuli["phase_title"].text = f"TRACKING -- Trial {trial_num}/{total_trials}"
    s.clock.reset()

    while s.clock.getTime() < cfg.timing.tracking_duration_sec:
        s.frame_count += 1
        tracking_t = s.clock.getTime()

        target_force = target_gen.get_target(tracking_t)

        latest_force = None
        new_samples = s.belt.get_all()
        for _ts, force in new_samples:
            s.buffer.append(force)
            latest_force = force
            error = target_force - force
            visual_force = s.range_center + feedback_gain * (force - s.range_center)
            compensated_error = target_force - visual_force
            trial_errors.append(abs(compensated_error))
            s.logger.log_row(
                timestamp=round(tracking_t, 4),
                frame=s.frame_count,
                force_n=round(force, 4),
                target_force=round(target_force, 4),
                error=round(error, 4),
                compensated_error=round(compensated_error, 4),
                phase="tracking",
                condition=condition_name,
                trial_num=trial_num,
                feedback_gain=feedback_gain,
            )

        dot_y = _force_to_dot_y(target_force, s.y_min, s.y_max, trace_bottom, trace_top)
        target_dot.pos = (trace_right + cfg.dot.x_offset, dot_y)

        if latest_force is not None:
            visual_f = s.range_center + feedback_gain * (latest_force - s.range_center)
            current_error = abs(target_force - visual_f)

            if condition_def.feedback:
                color = _compute_dot_color(current_error, cfg)

                target_dot.fillColor = color
                target_dot.lineColor = color

        remaining = max(0, cfg.timing.tracking_duration_sec - tracking_t)
        s.stimuli["status_text"].text = f"Follow the dot -- {remaining:.0f}s remaining"

        s.stimuli["trace_border"].draw()

        s.stimuli["trace"].draw(apply_gain(s.buffer, feedback_gain, s.range_center))

        target_dot.draw()
        s.stimuli["phase_title"].draw()
        s.stimuli["status_text"].draw()
        s.win.flip()

        keys = check_keys([escape])
        if keys:
            print("Escape pressed during tracking.")
            return trial_errors, True

    return trial_errors, False


def run_experiment(cfg: ExperimentConfig | None = None) -> None:
    """Run the standard breath tracking experiment.

    Composes all phases in order: belt connection, display setup,
    participant dialog, range calibration, then the trial loop
    (baseline -> countdown -> tracking -> feedback per trial).

    Power users can call the individual phase functions above to
    build custom experiment flows.

    Parameters
    ----------
    cfg : ExperimentConfig or None
        Experiment configuration.  If ``None``, uses a default
        :class:`ExperimentConfig`.
    """
    if cfg is None:
        from respyra.configs.breath_tracking import CONFIG as _default_cfg

        cfg = _default_cfg

    # 1. Connect belt BEFORE PsychoPy (Windows BLE/COM constraint)
    belt = connect_belt(cfg)

    # 2. Import PsychoPy (safe now)
    from psychopy import core, data

    from respyra.core.display import show_text_and_wait

    # 4. Participant dialog
    exp_info = run_participant_dialog(cfg)
    if exp_info is None:
        belt.stop()
        return

    # 3. Setup display and stimuli
    win, stimuli = setup_display(cfg)

    filepath = None
    logger = None
    state = None
    error_occurred = False

    try:
        participant = exp_info["participant"]
        session = exp_info["session"]

        # 5. Create session file and logger
        filepath = create_session_file(
            participant_id=participant,
            session=session,
            output_dir=cfg.output_dir,
        )
        print(f"Data will be saved to: {filepath}")

        logger = DataLogger(filepath, columns=cfg.data_columns)
        self_assessment_logger = DataLogger(
            f"{filepath}-self-assessment.csv",
            columns=["trial_num", "condition", "self_condition", "confidence", "self_accuracy"],
        )
        exp_clock = core.Clock()
        buffer = deque(maxlen=cfg.trace_buffer_size)

        state = ExperimentState(
            belt=belt,
            win=win,
            logger=logger,
            clock=exp_clock,
            buffer=buffer,
            stimuli=stimuli,
            y_min=cfg.trace.y_range[0],
            y_max=cfg.trace.y_range[1],
        )

        # 6. Instructions
        baseline_dur = int(cfg.timing.baseline_duration_sec)
        countdown_dur = int(cfg.timing.countdown_duration_sec)
        tracking_dur = int(cfg.timing.tracking_duration_sec)
        key = show_text_and_wait(
            win,
            text=(
                f"{cfg.name}\n\n"
                "You will see your live breathing signal on screen.\n"
                "A target dot will appear at the right edge of the trace.\n\n"
                "Your goal: breathe so your signal follows the dot.\n\n"
                "First, we will calibrate your breathing range.\n"
                "Then, each trial has three phases:\n"
                f"  1. Baseline -- breathe naturally ({baseline_dur} s)\n"
                f"  2. Countdown -- get ready ({countdown_dur} s)\n"
                f"  3. Tracking -- follow the dot ({tracking_dur} s)\n\n"
                "Press SPACE to begin."
            ),
            key_list=["space", cfg.escape_key],
        )
        if key == cfg.escape_key:
            print("Escape pressed -- ending experiment.")
            return

        # 7. Range calibration
        if not run_range_calibration(state, cfg):
            return  # finally handles cleanup

        # 8. Build trial order
        if cfg.trial.build_conditions is not None:
            conditions = cfg.trial.build_conditions(session)

        if not conditions:
            print("[error] No conditions defined -- nothing to run.")
            return

        # Map condition names to defs; warn on duplicates with differing params
        condition_map: dict[str, Any] = {}
        for c in conditions:
            if c.name in condition_map and c is not condition_map[c.name]:
                existing = condition_map[c.name]
                if (
                    c.feedback_gain != existing.feedback_gain
                    or c.segments != existing.segments
                ):
                    raise ValueError(
                        f"Duplicate condition name '{c.name}' with different parameters. "
                        f"Give each condition a unique name."
                    )
            condition_map[c.name] = c
        trial_list = [{"condition": c.name} for c in conditions]
        trials = data.TrialHandler(
            trialList=trial_list,
            nReps=cfg.trial.n_reps,
            method=cfg.trial.method,
        )

        # 9. Trial loop
        for trial in trials:
            condition_name = trial["condition"]
            condition_def = condition_map[condition_name]
            trial_num = trials.thisN + 1
            total_trials = trials.nTotal

            # Trial info screen
            key = show_text_and_wait(
                win,
                text=(
                    f"Trial {trial_num} of {total_trials}\n\n"
                   # f"Condition: {condition_name}\n\n"
                    "Press SPACE when ready."
                ),
                key_list=["space", cfg.escape_key],
            )
            if key == cfg.escape_key:
                print("Escape pressed -- ending experiment.")
                break

            # Fresh buffer per trial
            state.buffer.clear()
            state.frame_count = 0

            # a) Baseline
            baseline_forces, escaped = run_baseline(
                state, cfg, condition_name, trial_num, total_trials
            )
            if escaped:
                break

            # b) Calibrate from baseline (center logged for diagnostics only;
            #    target generation uses the global range calibration values)
            baseline_center, _baseline_amp = calibrate_from_baseline(baseline_forces)
            target_gen = TargetGenerator(
                condition_def, state.range_center, state.global_amplitude
            )
            print(
                f"Trial {trial_num}: target center={state.range_center:.2f} N, "
                f"amplitude={state.global_amplitude:.2f} N, "
                f"baseline center={baseline_center:.2f} N, "
                f"feedback_gain={condition_def.feedback_gain}"
            )

            # c) Countdown
            escaped = run_countdown(
                state, cfg, condition_def, condition_name, trial_num, total_trials
            )
            if escaped:
                break

            # d) Tracking
            trial_errors, escaped = run_tracking(
                state,
                cfg,
                condition_def,
                target_gen,
                condition_name,
                trial_num,
                total_trials,
            )
            self_accuracy = show_text_and_wait(
                 win,
                text=(
                    "On a scale of 1 (very inaccurate) to 5 (very accurate) \n\n"
                    "how would you rate your performance in the last trial? \n\n"
                    "Please press the corresponding key."
                ),
                key_list=[cfg.escape_key, "1", "2", "3", "4", "5"],
            )

            self_condition = show_text_and_wait(
                win,
                text=(
                    "Did you feel like you had to breathe \n\n"
                    "normally (n), deeper (d), or more shallow (s) than normal \n\n"
                    "to stay on target in the last trial? \n\n"
                    "Please press the corresponding key."
                ),
                key_list=[cfg.escape_key, "n", "d", "s"],
            )
            confidence = show_text_and_wait(
                win,
                text=(
                    "On a scale of 1 (completely unsure) \n"
                    "to 5 ( sure), how confident are you about this assessment?"
                ),
                key_list=[cfg.escape_key, "1", "2", "3", "4", "5"],
            )

            self_assessment_logger.log_row(
                trial_num=trial_num,
                condition=condition_name,
                self_condition=self_condition,
                confidence=confidence,
                self_accuracy=self_accuracy,
            )

            if escaped:
                break

            # e) Feedback
            if show_trial_feedback(state, cfg, trial_errors, trial_num):
                print("Escape pressed at feedback.")
                break

        else:
            # All trials completed normally
            show_end_screen(state, cfg, filepath)

    except Exception:
        error_occurred = True
        import traceback

        traceback.print_exc()

    finally:
        belt.stop()
        if logger is not None:
            logger.close()
        if self_assessment_logger is not None:
            self_assessment_logger.close()

        if filepath is not None:
            print(f"Data saved to: {filepath}")
        if state is not None:
            print(f"Trials completed: {len(state.all_trial_errors)}")
            if state.all_trial_errors:
                overall = sum(state.all_trial_errors) / len(state.all_trial_errors)
                print(f"Overall mean error: {overall:.2f} N")

        win.close()
        if not error_occurred:
            core.quit()


if __name__ == "__main__":
    main()
