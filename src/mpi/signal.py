import numpy as np


def stitch_signals(segments):
    """
    Given a sequence signal functions s_i with durations d_i, [[d_0, s_0],
    [d_1, s_1], ...], return a signal function that returns the first signal
    for duration d0, then second signal for d1 and so on. Each signal function
    is evaluated from [0, d_i).
    """
    segments = [(d, s) for d, s in segments if d > 0]
    total_duration = sum(d for d, _ in segments)

    def signal(t):
        # periodic signal, wrap around
        ti = np.mod(np.asarray(t), total_duration)
        scalar = np.ndim(t) == 0

        out = np.empty(ti.shape)
        start = 0.0
        for d, s in segments:
            end = start + d
            mask = np.logical_and(start <= ti, ti < end)
            out[mask] = s(ti[mask] - start)
            start = end
        return float(out) if scalar else out

    return signal


def rise_sine(duration):
    """
    Return a signal function that starts at -1 for t = 0 and will reach 1 at
    t = duration following a sine curve.
    """
    return lambda t: np.sin(np.pi * (t / duration - 1 / 2))


def fall_sine(duration):
    """
    Return a signal function that starts at 1 for t = 0 and will reach -1 at
    t = duration following a sine curve.
    """
    return lambda t: np.cos(np.pi * t / duration)
