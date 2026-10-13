import pytest

from mpi.stream_protocol import waveform_validity_columns


def test_each_experimental_waveform_binds_its_own_readiness_in_a_shared_row():
    pca = {"role": ["waveform"], "metric_id": ["pca"], "validity_channels": ["pca_valid"]}
    dt = {"role": ["waveform"], "metric_id": ["dt"], "validity_channels": ["pca_valid,dt_valid"]}
    channels = [pca, dt, {"role": ["validity"], "metric_id": ["pca_valid"]},
                {"role": ["validity"], "metric_id": ["dt_valid"]}]
    assert waveform_validity_columns(pca, channels, {}) == ["channel3"]
    assert waveform_validity_columns(dt, channels, {}) == ["channel3", "channel4"]
    with pytest.raises(ValueError, match="must declare their own validity"):
        waveform_validity_columns({"role": ["waveform"]}, channels, {})
    with pytest.raises(ValueError, match="Missing or ambiguous"):
        waveform_validity_columns({"validity_channels": ["missing"]}, channels, {})
