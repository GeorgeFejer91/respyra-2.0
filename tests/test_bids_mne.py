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
