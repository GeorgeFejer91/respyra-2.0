"""Exact Polar contracts, live validity and calibrated sample projection."""

import sys
import types
from unittest.mock import patch

import pytest

from mpi.lsl_force import LSLForceError
from mpi.lsl_polar import LSLPolarSource, open_polar_source, validate_polar_info


def candidate(metric, contract, suffix, flags, unit="g"):
    name = "StudyPolar_" + suffix
    companions = ",".join("StudyPolar_" + flag for flag in flags)
    xml = ("<info><desc><manufacturer>Polar</manufacturer><model>H10</model>"
           "<schema>adr-waveform/1</schema><stream_role>respiration_candidate</stream_role>"
           f"<metric_id>{metric}</metric_id><raw_source_metric_id>raw_acc</raw_source_metric_id>"
           f"<respyra_input_contract>{contract}</respyra_input_contract>"
           "<respyra_signal_role>signed_breathing_level</respyra_signal_role>"
           f"<companion_streams>{companions}</companion_streams>"
           f"<channels><channel><unit>{unit}</unit></channel></channels></desc></info>")
    return Info(name, "Respiration", xml)


class Info:
    def __init__(self, name, kind, xml):
        self.label, self.kind, self.xml = name, kind, xml
    def name(self): return self.label
    def type(self): return self.kind
    def source_id(self): return "polar-h10-" + self.label
    def channel_count(self): return 1
    def channel_format(self): return 1
    def nominal_srate(self): return 0
    def uid(self): return "uid-" + self.label
    def as_xml(self): return self.xml


@pytest.mark.parametrize("metric,contract,suffix,flags", [
    ("adr_pca_waveform", "respyra-polar-pca/1", "adrPcaWaveform", ("adrPcaValid",)),
    ("adr_axis_mean_difference", "respyra-polar-phan-signed/1", "adrAxisMeanDifference",
     ("adrPcaValid", "adrAxisDifferenceValid")),
])
def test_exact_contracts_connect_with_live_validity(metric, contract, suffix, flags):
    primary = candidate(metric, contract, suffix, flags)
    companions = [Info("StudyPolar_" + flag, "SignalQuality",
                       "<info><desc><channels><channel><unit>0/1</unit></channel></channels></desc></info>")
                  for flag in flags]
    inlets = []

    class Inlet:
        def __init__(self, info, **kwargs):
            assert kwargs["recover"] is False
            self.stream = info
            self.closed = False
            inlets.append(self)
        def info(self, **_kwargs): return self.stream
        def pull_chunk(self, **_kwargs):
            return ([[0.02]], [100.0]) if self.stream is primary else ([[1.0]], [100.0])
        def close_stream(self): self.closed = True

    module = types.SimpleNamespace(StreamInlet=Inlet, resolve_streams=lambda **_kwargs: [primary, *companions],
                                   cf_float32=1, proc_clocksync=1)
    with patch.dict(sys.modules, {"pylsl": module}):
        source = open_polar_source(primary, timeout=1.0)
        assert source.contract_id == contract and source.get_all() == [(100.0, 0.02)]
        source.polarity = -1
        source.center, source.amplitude = -0.01, 0.01
        samples = []
        source.calibrated_outlet = types.SimpleNamespace(push_sample=lambda row, timestamp: samples.append((row, timestamp)))
        assert source.get_all() == [(100.0, -0.02)]
        assert samples == [([-1.0], 100.0)]
        source.stop()
    assert all(inlet.closed for inlet in inlets)


def test_polar_contract_rejects_wrong_unit_and_wrong_method():
    from pylsl import cf_float32
    assert cf_float32 == 1
    info = candidate("adr_pca_waveform", "respyra-polar-pca/1", "adrPcaWaveform", ("adrPcaValid",))
    assert validate_polar_info(info)[0] == "respyra-polar-pca/1"
    for wrong in (
        candidate("adr_pca_waveform", "respyra-polar-pca/1", "adrPcaWaveform", ("adrPcaValid",), "N"),
        candidate("adr_pca_waveform", "respyra-polar-phan-signed/1", "adrPcaWaveform", ("adrPcaValid",)),
        candidate("adr_axis_difference_magnitude", "respyra-polar-pca/1", "adrAxisDifferenceMagnitude", ("adrPcaValid",)),
    ):
        with pytest.raises(LSLForceError):
            validate_polar_info(wrong)


def test_validity_is_matched_to_each_waveform_timestamp():
    class Inlet:
        def __init__(self, rows, times):
            self.rows, self.times = rows, times
        def pull_chunk(self, **_kwargs):
            rows, times = self.rows, self.times
            self.rows, self.times = [], []
            return rows, times
        def close_stream(self): pass

    source = LSLPolarSource(
        Inlet([[0.01], [0.02]], [100.0, 100.1]), "polar-h10-test", "test",
        "respyra-polar-pca/1", {"valid": Inlet([[0.0], [1.0]], [100.0, 100.1])},
    )
    assert source.get_all() == [(100.1, 0.02)]
    source.stop()
