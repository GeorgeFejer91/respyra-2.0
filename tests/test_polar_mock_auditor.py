"""A plateau must not conceal a shifted or altered mock recording."""
import numpy as np
import pytest
from scripts.audit_polar_mock_xdf import _metric_source_id, _mock_acc, _mock_sequence_start, _recorded_metric


@pytest.mark.parametrize("suffix,identity_suffix", [
    ("ChestMotion", "PCA-Breathing"),
    ("ChestMotion-DT", "Phan-Breathing"),
    ("ChestPCA", "PCA-Breathing"),
    ("ChestDT", "Phan-Breathing"),
    ("PCAQuality", "PCA-Quality"),
    ("PCAValid", "PCA-Valid"),
    ("DTValid", "Phan-Valid"),
    ("ACC", "Accelerometer"),
    ("rawACC", "Accelerometer"),
    ("rawECG", "ECG"),
    ("PCA-Breathing", "PCA-Breathing"),
    ("Phan-Breathing", "Phan-Breathing"),
    ("Accelerometer", "Accelerometer"),
    ("adrPcaWaveform", "adrPcaWaveform"),
])
def test_renamed_and_legacy_outlets_retain_saved_identity(suffix, identity_suffix):
    assert _metric_source_id("Custom_Polar", suffix) == "polar-h10-Custom_Polar_" + identity_suffix


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


def test_auditor_finds_readiness_inside_the_waveform_without_a_scalar_copy():
    bundle = {"info": {"desc": [{"channels": [{"channel": [
        {"metric_id": ["adr_pca_waveform"]}, {"metric_id": ["adr_pca_quality"]},
        {"metric_id": ["adr_pca_valid"]}]}]}]}, "time_series": np.array([[0.02, 0.8, 1]])}
    stream, index = _recorded_metric({"Polar_ChestPCA": bundle}, "Polar", "adr_pca_valid", "PCAValid")
    assert stream is bundle and stream["time_series"][0, index] == 1
