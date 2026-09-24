import numpy as np
import pytest

from mpi.signal import stitch_signals, rise_sine, fall_sine

def test_stitch_signals():
    signal = stitch_signals(
        [[1.0, lambda t: t], [2.0, lambda t: t + 1.0], [0.5, lambda t: -t]]
    )

    t = np.array([0.25, 1.0, 2.5, 3.0, 3.25, 4.0])
    expected = np.array([0.25, 1.0, 2.5, 0.0, -0.25, 0.5])
    np.testing.assert_allclose(signal(t), expected, atol=1e-12)

    np.testing.assert_allclose(signal(3.5), signal(0.0), atol=1e-12)


def test_stitch_signals_scalar():
    signal = stitch_signals([[1.0, lambda t: t], [2.0, lambda t: t]])

    value = signal(0.5)
    assert isinstance(value, float)
    assert value == pytest.approx(0.5)


def test_stitch_signals_constant_segments():
    signal = stitch_signals(
        [
            [2.5, rise_sine(2.5)],
            [2.0, lambda t: 1.0],
            [1.0, fall_sine(1.0)],
            [0.5, lambda t: -1.0],
        ]
    )

    t = np.array([0.0, 1.25, 3.0, 4.5, 5.0, 5.5, 5.75, 6.0])
    expected = np.array([-1.0, 0.0, 1.0, 1.0, 0.0, -1.0, -1.0, -1.0])
    np.testing.assert_allclose(signal(t), expected, atol=1e-12)


def test_stitch_signals_ignores_zero_duration():
    signal = stitch_signals(
        [[1.0, lambda t: t], [0.0, lambda t: t * 1000], [1.0, lambda t: t]]
    )

    t = np.array([0.5, 1.5, 2.0])
    np.testing.assert_allclose(signal(t), [0.5, 0.5, 0.0], atol=1e-12)


def test_rise_sine():
    s1 = rise_sine(1.0)
    t1 = np.array([0.0, 0.5, 1.0])
    np.testing.assert_allclose(s1(t1), np.array([-1.0, 0.0, 1.0]), atol=1e-12)

    s2 = rise_sine(2.0)
    t2 = np.array([0.0, 1.0, 2.0])
    np.testing.assert_allclose(s2(t2), np.array([-1.0, 0.0, 1.0]), atol=1e-12)


def test_fall_sine():
    s1 = fall_sine(1.0)
    t1 = np.array([0.0, 0.5, 1.0])
    np.testing.assert_allclose(s1(t1), np.array([1.0, 0.0, -1.0]), atol=1e-12)

    s2 = fall_sine(2.0)
    t2 = np.array([0.0, 1.0, 2.0])
    np.testing.assert_allclose(s2(t2), np.array([1.0, 0.0, -1.0]), atol=1e-12)
