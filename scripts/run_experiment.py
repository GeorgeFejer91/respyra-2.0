from __future__ import annotations

from collections import deque
from contextlib import ExitStack
from typing import Any

from mpi.event_markers import MarkerOutlet, NullSampleLogger
from mpi.lsl_force import LSLForceError, connect_force_source
from respyra.configs.experiment_config import ExperimentConfig
from respyra.core.target_generator import TargetGenerator, calibrate_from_baseline
from respyra.core.runner import (
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
)


def main():
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
            visual_force = s.range_center + feedback_gain * (force - s.range_center)
            compensated_error = target_force - visual_force
            trial_errors.append(abs(compensated_error))

        dot_y = _force_to_dot_y(target_force, s.y_min, s.y_max, trace_bottom, trace_top)
        target_dot.pos = (trace_right + cfg.dot.x_offset, dot_y)

        if latest_force is not None:
            visual_f = s.range_center + feedback_gain * (latest_force - s.range_center)
            current_error = abs(target_force - visual_f)

            if getattr(condition_def, "feedback", True):
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

    Composes all phases in order: LSL force discovery, display setup,
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

    markers = MarkerOutlet()
    markers.wait_for_recorder()
    markers.emit("run.recorder_connected")
    belt = None
    win = None
    state = None
    hooks = ExitStack()
    abort_reason = None
    completed_trials = 0
    error_occurred = False

    try:
        belt = connect_force_source()
        markers.emit("source.connected", source_id=belt.source_id,
                     stream_name=belt.stream_name, force_channel_index=belt.force_index)

        from psychopy import core, data

        markers.emit("participant.dialog.opened")
        exp_info = run_participant_dialog(cfg)
        if exp_info is None:
            markers.emit("participant.dialog.cancelled")
            abort_reason = "participant_dialog_cancelled"
            return

        participant = exp_info["participant"]
        session = exp_info["session"]
        markers.emit("participant.dialog.submitted", participant=participant, session=session)

        win, stimuli = setup_display(cfg)
        markers.emit("display.opened")

        markers.emit(
            "run.configured", study_name=cfg.name,
            range_cal_s=cfg.timing.range_cal_duration_sec,
            baseline_s=cfg.timing.baseline_duration_sec,
            countdown_s=cfg.timing.countdown_duration_sec,
            tracking_s=cfg.timing.tracking_duration_sec,
            dot_feedback_mode=cfg.dot.feedback_mode,
            range_percentiles=[cfg.range_cal.percentile_lo, cfg.range_cal.percentile_hi],
            range_scale=cfg.range_cal.scale,
        )
        exp_clock = core.Clock()
        buffer = deque(maxlen=cfg.trace_buffer_size)

        state = ExperimentState(
            belt=belt,
            win=win,
            logger=NullSampleLogger(),
            clock=exp_clock,
            buffer=buffer,
            stimuli=stimuli,
            y_min=cfg.trace.y_range[0],
            y_max=cfg.trace.y_range[1],
        )
        markers.state = state
        show_text_and_wait = hooks.enter_context(markers.observe_inputs_and_screens())

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
            abort_reason = "instructions_escape"
            return

        markers.emit("run.started", participant=participant, session=session)

        markers.phase = "calibration"
        try:
            calibrated = run_range_calibration(state, cfg)
        except Exception:
            markers.end_calibration_attempt("error")
            raise
        else:
            used_defaults = calibrated and markers.calibration_attempt_open
            markers.end_calibration_attempt(
                "no_data_fallback" if used_defaults else "escaped"
            )
        finally:
            markers.phase = None
        if not calibrated:
            abort_reason = "calibration_escape"
            return  # finally handles cleanup
        if used_defaults:
            raise LSLForceError("Range calibration received no Force samples")
        markers.emit(
            "calibration.completed", center_n=state.range_center,
            amplitude_n=state.global_amplitude,
            y_min_n=state.y_min, y_max_n=state.y_max,
        )

        # 8. Build trial order
        conditions = (cfg.trial.build_conditions(session)
                      if cfg.trial.build_conditions is not None
                      else cfg.trial.conditions)

        if not conditions:
            raise ValueError("No conditions defined -- nothing to run")

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
        markers.emit("trial.order", conditions=[c.name for c in conditions],
                     total_trials=trials.nTotal, method=cfg.trial.method)

        # 9. Trial loop
        for trial in trials:
            condition_name = trial["condition"]
            condition_def = condition_map[condition_name]
            trial_num = trials.thisN + 1
            total_trials = trials.nTotal
            markers.trial_num = trial_num
            markers.condition = condition_name
            markers.emit(
                "trial.condition.selected", feedback_gain=condition_def.feedback_gain,
                feedback_enabled=getattr(condition_def, "feedback", True),
                segments=[{"freq_hz": seg.freq_hz, "n_cycles": seg.n_cycles}
                          for seg in condition_def.segments],
            )

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
                markers.emit("trial.aborted", reason="ready_escape")
                abort_reason = "ready_escape"
                break
            markers.emit("trial.started")

            # Fresh buffer per trial
            state.buffer.clear()
            state.frame_count = 0

            # a) Baseline
            with markers.phase_scope("baseline", win):
                baseline_forces, escaped = run_baseline(
                    state, cfg, condition_name, trial_num, total_trials
                )
            if escaped:
                markers.emit("trial.aborted", reason="baseline_escape")
                abort_reason = "baseline_escape"
                break

            # b) Calibrate from baseline (center logged for diagnostics only;
            #    target generation uses the global range calibration values)
            baseline_center, baseline_amp = calibrate_from_baseline(baseline_forces)
            markers.emit("baseline.calculated", center_n=baseline_center,
                         amplitude_n=baseline_amp)
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
            with markers.phase_scope("countdown", win):
                with markers.countdown_ticks(win, state.stimuli["countdown_text"]):
                    escaped = run_countdown(
                        state, cfg, condition_def, condition_name, trial_num, total_trials
                    )
            if escaped:
                markers.emit("trial.aborted", reason="countdown_escape")
                abort_reason = "countdown_escape"
                break

            # d) Tracking
            markers.phase = "tracking"
            win.callOnFlip(state.clock.reset)
            win.callOnFlip(
                markers.emit, "tracking.started",
                target_center_n=state.range_center,
                target_amplitude_n=state.global_amplitude,
                segments=[{"freq_hz": seg.freq_hz, "n_cycles": seg.n_cycles}
                          for seg in condition_def.segments],
                feedback_gain=condition_def.feedback_gain,
                feedback_enabled=getattr(condition_def, "feedback", True),
            )
            try:
                trial_errors, escaped = run_tracking(
                    state, cfg, condition_def, target_gen, condition_name,
                    trial_num, total_trials,
                )
            except Exception:
                markers.emit("tracking.ended", sample_count=None,
                             escaped=None, outcome="error")
                raise
            else:
                markers.emit("tracking.ended", sample_count=len(trial_errors),
                             escaped=escaped,
                             outcome="escaped" if escaped else "completed")
            finally:
                markers.phase = None
            if escaped:
                markers.emit("trial.aborted", reason="tracking_escape")
                abort_reason = "tracking_escape"
                break
            self_accuracy = show_text_and_wait(
                 win,
                text=(
                    "On a scale of 1 (very inaccurate) to 5 (very accurate) \n\n"
                    "how would you rate your performance in the last trial? \n\n"
                    "Please press the corresponding key."
                ),
                key_list=[cfg.escape_key, "1", "2", "3", "4", "5"],
            )
            if self_accuracy == cfg.escape_key:
                markers.emit("trial.aborted", reason="accuracy_escape")
                abort_reason = "accuracy_escape"
                break
            markers.emit("assessment.accuracy", value=self_accuracy)

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
            if self_condition == cfg.escape_key:
                markers.emit("trial.aborted", reason="breathing_judgment_escape")
                abort_reason = "breathing_judgment_escape"
                break
            markers.emit("assessment.breathing_judgment", value=self_condition)
            confidence = show_text_and_wait(
                win,
                text=(
                    "On a scale of 1 (completely unsure) \n"
                    "to 5 ( sure), how confident are you about this assessment?"
                ),
                key_list=[cfg.escape_key, "1", "2", "3", "4", "5"],
            )
            if confidence == cfg.escape_key:
                markers.emit("trial.aborted", reason="confidence_escape")
                abort_reason = "confidence_escape"
                break
            markers.emit("assessment.confidence", value=confidence)

            markers.emit(
                "assessment.completed", accuracy=self_accuracy,
                breathing_judgment=self_condition, confidence=confidence,
            )

            # e) Feedback
            if show_trial_feedback(state, cfg, trial_errors, trial_num):
                print("Escape pressed at feedback.")
                markers.emit("trial.aborted", reason="feedback_escape")
                abort_reason = "feedback_escape"
                break
            markers.emit(
                "trial.ended",
                mean_abs_compensated_error_n=(
                    sum(trial_errors) / len(trial_errors) if trial_errors else None
                ),
            )
            completed_trials += 1

        else:
            # All trials completed normally
            overall = (
                sum(state.all_trial_errors) / len(state.all_trial_errors)
                if state.all_trial_errors else None
            )
            mean_text = f"{overall:.2f} N" if overall is not None else "unavailable"
            show_text_and_wait(
                win,
                text=(
                    "Experiment complete!\n\n"
                    f"Overall mean tracking error: {mean_text}\n\n"
                    "The LSL recorder manages the breathing and event recording.\n\n"
                    "Press SPACE to exit."
                ),
                key_list=["space", cfg.escape_key],
            )
            markers.emit("run.completed", trials_completed=completed_trials)

    except Exception as exc:
        error_occurred = True
        if isinstance(exc, LSLForceError) and belt is not None:
            markers.emit("source.lost", message=str(exc))
        markers.emit("run.failed", error_type=type(exc).__name__, message=str(exc))
        raise

    finally:
        cleanup_error = None

        def cleanup(action):
            nonlocal cleanup_error
            try:
                action()
            except Exception as exc:
                if cleanup_error is None:
                    cleanup_error = exc

        cleanup(hooks.close)
        if abort_reason is not None:
            cleanup(lambda: markers.emit("run.aborted", reason=abort_reason,
                                         trials_completed=completed_trials))
        if belt is not None:
            cleanup(belt.stop)
            cleanup(lambda: markers.emit("source.disconnected"))
        if state is not None:
            print(f"Trials completed: {completed_trials}")
            if state.all_trial_errors:
                overall = sum(state.all_trial_errors) / len(state.all_trial_errors)
                print(f"Overall mean error: {overall:.2f} N")

        if win is not None:
            cleanup(win.close)
            cleanup(lambda: markers.emit("display.closed"))
        if cleanup_error is not None and not error_occurred:
            raise cleanup_error
        if not error_occurred and win is not None:
            core.quit()


if __name__ == "__main__":
    main()
