import gzip
import json

import numpy as np
import pytest

pytest.importorskip("mne")

from mpi.bids_mne import read_bids_signal


def test_mne_reader_keeps_regular_values_and_requires_explicit_irregular_rate(tmp_path):
    source = {"Name": "Polar ECG", "ChannelFormat": "float32", "SourceID": "ecg"}
    fixed = tmp_path / "sub-001_task-respyra_recording-ecg_physio.tsv.gz"
    with gzip.open(fixed, "wt", encoding="utf-8") as handle:
        handle.write("0.000000000\t1\n0.010000000\t2\n0.020000000\t3\n")
    fixed.with_suffix("").with_suffix(".json").write_text(json.dumps({
        "Columns": ["timestamp", "channel1"], "SamplingFrequency": 100,
        "channel1": {"LongName": "Raw ECG", "Units": "µV"}, "LSLSource": source,
    }), encoding="utf-8")
    raw, stamps = read_bids_signal(fixed)
    assert raw.info["sfreq"] == 100
    assert raw.ch_names == ["Raw ECG"]
    np.testing.assert_array_equal(raw.get_data(), [[1, 2, 3]])
    np.testing.assert_allclose(stamps, [0, 0.01, 0.02])

    irregular = tmp_path / "sub-001_task-respyra_acq-waveform_beh.tsv"
    irregular.write_text("timestamp\tchannel1\n0.00\t1\n0.10\t2\n0.20\tn/a\n0.30\t4\n", encoding="utf-8")
    irregular.with_suffix(".json").write_text(json.dumps({
        "channel1": {"LongName": "Breathing", "Units": "g"},
        "LSLSource": {"Name": "Polar waveform", "ChannelFormat": "float32", "SourceID": "breath"},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="explicit positive sfreq"):
        read_bids_signal(irregular)
    waveform, original = read_bids_signal(irregular, sfreq=20)
    assert waveform.info["sfreq"] == 20
    np.testing.assert_allclose(original, [0, 0.1, 0.2, 0.3])
    np.testing.assert_allclose(waveform.get_data()[0, :3], [1, 1.5, 2])
    assert np.isnan(waveform.get_data()[0, 3:6]).all()
    assert waveform.get_data()[0, 6] == 4

    single = tmp_path / "sub-001_task-respyra_acq-counter_beh.tsv"
    single.write_text("timestamp\tchannel1\n0.30\t7\n", encoding="utf-8")
    single.with_suffix(".json").write_text(json.dumps({
        "channel1": {"LongName": "Counter"},
        "LSLSource": {"Name": "Counter", "ChannelFormat": "int64", "SourceID": "count"},
    }), encoding="utf-8")
    one, one_stamp = read_bids_signal(single, sfreq=20)
    assert one.n_times == 1 and one.get_data()[0, 0] == 7
    np.testing.assert_array_equal(one_stamp, [0.3])


def test_protocol_mne_selects_variables_scales_ecg_and_masks_invalid_waveforms(tmp_path):
    data = tmp_path / "sub-001_task-respyra_recording-polar_physio.tsv.gz"
    support = tmp_path / "sub-001_task-respyra_recording-polarsupport_physio.tsv.gz"
    common = {"StreamProtocol": "respyra-stream/1", "SamplingFrequency": 10,
              "LSLSource": {"Name": "Polar", "ChannelFormat": "float32", "SourceID": "polar"}}
    with gzip.open(data, "wt") as handle:
        handle.write("0.0\t100\t0.01\n0.1\t200\t0.02\n0.2\t300\t0.03\n")
    with gzip.open(support, "wt") as handle:
        handle.write("0.0\t0.0\t0\n0.1\t0.8\t1\n0.2\t0.0\t0\n")
    data.with_suffix("").with_suffix(".json").write_text(json.dumps({**common,
        "Columns": ["timestamp", "channel1", "channel2"], "SupportTable": support.name,
        "channel1": {"LongName": "ECG", "Units": "uV", "ChannelRole": "measurement", "MNEType": "ecg", "MNEValueScale": 1e-6},
        "channel2": {"LongName": "ChestPCA", "Units": "g", "ChannelRole": "waveform", "MNEType": "misc", "ValidityColumns": ["channel4"]},
    }))
    support.with_suffix("").with_suffix(".json").write_text(json.dumps({**common,
        "Columns": ["timestamp", "channel3", "channel4"],
        "channel3": {"LongName": "PCAQuality", "ChannelRole": "quality"},
        "channel4": {"LongName": "PCAValid", "ChannelRole": "validity"},
    }))
    raw, stamps = read_bids_signal(data)
    assert raw.ch_names == ["Polar:ECG", "Polar:ChestPCA"]
    assert raw.get_channel_types() == ["ecg", "misc"]
    np.testing.assert_allclose(raw.get_data()[0], [100e-6, 200e-6, 300e-6])
    np.testing.assert_allclose(raw.get_data()[1], [np.nan, 0.02, np.nan], equal_nan=True)
    np.testing.assert_allclose(stamps, [0.0, 0.1, 0.2])
    with pytest.raises(ValueError, match="No experimental data channels"):
        read_bids_signal(support)
    diagnostic, _ = read_bids_signal(support, include_support=True)
    np.testing.assert_allclose(diagnostic.get_data(), [[0, 0.8, 0], [0, 1, 0]])
    combined, _ = read_bids_signal(data, include_support=True)
    assert combined.ch_names == ["Polar:ECG", "Polar:ChestPCA", "Polar:PCAQuality", "Polar:PCAValid"]


def test_protocol_resampling_keeps_phase_codes_and_does_not_bridge_acquisition_gaps(tmp_path):
    path = tmp_path / "sub-001_task-respyra_acq-phase_beh.tsv"
    path.write_text("timestamp\tchannel1\n0.0\t1\n0.1\t-1\n0.2\t0\n1.0\t1\n1.1\t-1\n")
    path.with_suffix(".json").write_text(json.dumps({"StreamProtocol": "respyra-stream/1",
        "LSLSource": {"Name": "Polar_BreathPhase", "ChannelFormat": "float32"},
        "channel1": {"LongName": "Phase", "Units": "class", "ChannelRole": "measurement", "Interpolation": "previous"}}))
    raw, _ = read_bids_signal(path, sfreq=20)
    np.testing.assert_array_equal(raw.get_data()[0, :5], [1, 1, -1, -1, 0])
    assert np.isnan(raw.get_data()[0, 5:20]).all()
    assert raw.get_data()[0, 20] == 1
