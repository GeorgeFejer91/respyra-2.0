import matplotlib.pyplot as plt
import numpy as np

from mpi.signal import stitch_signals, rise_sine, fall_sine


def main():
    def only_one(t):
        return 1
    segments = [
        (2.5, rise_sine(2.5)),
        (2.0, only_one),
        (1.0, fall_sine(1.0)),
        (0.5, lambda t: -1),
    ]
    signal = stitch_signals(segments)
    t = np.linspace(0, 12.0, 1000)
    y = signal(t)

    ax = plt.subplot()
    shade_segments(ax, segments, float(t.min()), float(t.max()))
    ax.plot(t, y)
    plt.show()


def shade_segments(ax, segments, t_min, t_max):
    total = sum(d for d, _ in segments)
    boundaries = np.cumsum([0.0] + [d for d, _ in segments])
    for i, (d, _) in enumerate(segments):
        for t0 in np.arange(t_min, t_max, total):
            start = max(t0 + boundaries[i], t_min)
            end = min(t0 + boundaries[i + 1], t_max)
            if end > start:
                ax.axvspan(start, end, alpha=0.12, color=f"C{i}")


if __name__ == "__main__":
    main()
