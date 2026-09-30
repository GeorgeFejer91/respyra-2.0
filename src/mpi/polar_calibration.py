"""Range calibration for signed Polar ACC waveforms in their native g units."""

from __future__ import annotations

from mpi.lsl_force import LSLForceError


def run_polar_range_calibration(state, cfg):
    from respyra.core.display import show_text_and_wait
    from respyra.core.events import check_keys

    while True:
        key = show_text_and_wait(
            state.win,
            text=("Breathing Range Calibration\n\n"
                  "Breathe normally and comfortably through your full natural range.\n"
                  "Keep the Polar strap in the position used for the study.\n\n"
                  "Press SPACE when ready."),
            key_list=["space", cfg.escape_key],
        )
        if key == cfg.escape_key:
            return False
        samples = []
        state.buffer.clear()
        state.stimuli["phase_title"].text = "RANGE CALIBRATION"
        state.clock.reset()
        while state.clock.getTime() < cfg.timing.range_cal_duration_sec:
            state.frame_count += 1
            elapsed = state.clock.getTime()
            for _timestamp, value in state.belt.get_all():
                samples.append(value)
                state.buffer.append(value)
                state.logger.log_row(timestamp=round(elapsed, 4), frame=state.frame_count,
                                     force_n=round(value, 6), phase="range_cal",
                                     condition="", trial_num=0, feedback_gain=1.0)
            remaining = max(0, cfg.timing.range_cal_duration_sec - elapsed)
            state.stimuli["status_text"].text = f"Breathe normally -- {remaining:.0f}s remaining"
            for name in ("trace_border", "trace", "phase_title", "status_text"):
                stimulus = state.stimuli[name]
                if name == "trace":
                    stimulus.draw(list(state.buffer))
                else:
                    stimulus.draw()
            state.win.flip()
            if check_keys([cfg.escape_key]):
                return False
        if len(samples) < 6:
            raise LSLForceError("Polar range calibration received too few valid waveform samples")
        values = sorted(samples)
        n = len(values)
        lo = values[max(0, min(int(n * cfg.range_cal.percentile_lo / 100), n - 1))]
        hi = values[max(0, min(int(n * cfg.range_cal.percentile_hi / 100) - 1, n - 1))]
        half_range = (hi - lo) / 2
        if half_range <= 1e-5:
            raise LSLForceError("Polar breathing waveform has too little calibrated variation")
        state.range_center = (hi + lo) / 2
        state.global_amplitude = half_range * cfg.range_cal.scale
        padding = (hi - lo) * 0.2
        state.y_min, state.y_max = lo - padding, hi + padding
        state.stimuli["trace"].y_min = state.y_min
        state.stimuli["trace"].y_max = state.y_max
        key = show_text_and_wait(
            state.win,
            text=("Calibration Complete\n\n"
                  f"Waveform range: {lo:.4f} to {hi:.4f} g\n"
                  f"Target amplitude: {state.global_amplitude:.4f} g\n\n"
                  "Press SPACE to accept, R to recalibrate."),
            key_list=["space", "r", cfg.escape_key],
        )
        if key == cfg.escape_key:
            return False
        if key == "space":
            return True


class PolarSampleLogger:
    """Keep optional Polar CSV columns honest while reusing respyra phases."""

    def __init__(self, logger):
        self.logger = logger

    def log_row(self, **fields):
        for old, new in (("force_n", "signal_g"), ("target_force", "target_signal_g"),
                         ("error", "error_g"), ("compensated_error", "compensated_error_g")):
            if old in fields:
                fields[new] = fields.pop(old)
        self.logger.log_row(**fields)
