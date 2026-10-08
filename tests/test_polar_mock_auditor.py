"""A plateau must not conceal a shifted or altered mock recording."""
import numpy as np
import pytest
from scripts.audit_polar_mock_xdf import _mock_acc, _mock_sequence_start


def test_complete_sequence_resolves_ambiguous_flat_prefix():
    reference = _mock_acc(12000)
    recorded = reference[6050:8468].copy()
    assert np.array_equal(reference[6054:6086], recorded[:32])
    assert _mock_sequence_start(recorded, reference, 6053.88) == 6050


def test_altered_sample_after_prefix_is_rejected():
    reference = _mock_acc(12000)
    recorded = reference[6050:8468].copy()
    recorded[100, 0] += 1
    with pytest.raises(AssertionError, match="Lost, duplicated or altered ACC"):
        _mock_sequence_start(recorded, reference, 6053.88)


def test_complete_match_still_requires_consistent_stream_age():
    reference = _mock_acc(12000)
    with pytest.raises(AssertionError, match="inconsistent with stream age"):
        _mock_sequence_start(reference[6050:8468], reference, 1000)
