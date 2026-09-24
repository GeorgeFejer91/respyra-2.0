def to_viewport(t, s, s0, s1, tape_speed):
    """Map time/signal samples to viewport coords x in (-1,1), y in (-1,1)."""
    x = 1.0 - tape_speed * (t[-1] - t)  # x = 1 is the latest sample
    y = 2.0 * (s - s0) / (s1 - s0) - 1.0  # s0 -> -1, s1 -> +1

    return x, y
