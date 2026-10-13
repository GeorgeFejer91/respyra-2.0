"""Exact Polar contracts, live validity and calibrated sample projection."""

import sys
import types
import math
from xml.etree import ElementTree as ET
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
           f"<validity_streams>{companions}</validity_streams>"
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
    ("adr_pca_waveform", "respyra-polar-pca/1", "ChestMotion", ("PCA-Valid",)),
    ("adr_axis_mean_difference", "respyra-polar-phan-signed/1", "ChestMotion-DT",
     ("PCA-Valid", "Phan-Valid")),
    ("adr_pca_waveform", "respyra-polar-pca/1", "PCA-Breathing", ("PCA-Valid",)),
    ("adr_axis_mean_difference", "respyra-polar-phan-signed/1", "Phan-Breathing",
     ("PCA-Valid", "Phan-Valid")),
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
                                   cf_float32=1, cf_double64=2, proc_clocksync=1)
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


def test_polar_contract_rejects_wrong_format_and_discrete_classification():
    from pylsl import cf_float32
    assert cf_float32 == 1
    info = candidate("adr_pca_waveform", "respyra-polar-pca/1", "adrPcaWaveform", ("adrPcaValid",))
    assert validate_polar_info(info)[0] == "respyra-polar-pca/1"
    for wrong in (
        candidate("adr_pca_waveform", "respyra-polar-pca/1", "adrPcaWaveform", ("adrPcaValid",), "N"),
        candidate("adr_pca_waveform", "unsupported/1", "adrPcaWaveform", ("adrPcaValid",)),
        candidate("adr_axis_difference_magnitude", "", "adrAxisDifferenceMagnitude", ("adrPcaValid",)),
        candidate("adr_moving_average_phase", "", "Flowborne", (), "class"),
        candidate("adr_pca_waveform", "respyra-polar-pca/1", "Anything", ()),
    ):
        with pytest.raises(LSLForceError):
            validate_polar_info(wrong)


def test_waveform_eligibility_ignores_names_and_accepts_double_precision():
    info = candidate("custom_projection", "respyra-polar-pca/1", "Operator-label", ("my-readiness",))
    info.label = "Chest movement session A"
    info.kind = "Custom sensor waveform"
    info.source_id = lambda: "stable-device-7"
    info.channel_format = lambda: 2
    info.nominal_srate = lambda: 25.0
    assert validate_polar_info(info) == ("respyra-polar-pca/1", ("StudyPolar_my-readiness",))
    info.channel_format = lambda: 3
    with pytest.raises(LSLForceError, match="floating-point"):
        validate_polar_info(info)


def test_earlier_mini_metadata_identifies_flags_without_a_name_pattern():
    info = candidate("adr_pca_waveform", "respyra-polar-pca/1", "adrPcaWaveform", ("adrPcaValid",))
    info.xml = info.xml.replace("<validity_streams>StudyPolar_adrPcaValid</validity_streams>",
        "<processing><companion_metric_ids>adr_pca_valid</companion_metric_ids></processing>")
    info.label = "Renamed legacy breathing"
    assert validate_polar_info(info)[1] == ("StudyPolar_adrPcaValid",)


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


def bundled_candidate(contract, reordered=False):
    metric = "adr_pca_waveform" if contract == "respyra-polar-pca/1" else "adr_axis_mean_difference"
    info = candidate(metric, contract, "Chest movement", ())
    root = ET.fromstring(info.xml)
    desc = root.find("desc")
    desc.find("schema").text = "adr-waveform/2"
    desc.remove(desc.find("channels"))
    flags = ["adr_pca_valid"] + (["adr_axis_difference_valid"] if "phan" in contract else [])
    ET.SubElement(desc, "waveform_channel").text = metric
    ET.SubElement(desc, "validity_channels").text = ",".join(flags)
    definitions = [(metric, "g", "waveform"), ("adr_pca_quality", "0–1", "quality")]
    definitions += [(flag, "0/1", "validity") for flag in flags]
    if reordered:
        definitions.reverse()
    channels = ET.SubElement(desc, "channels")
    for metric_id, unit, role in definitions:
        channel = ET.SubElement(channels, "channel")
        for key, value in dict(metric_id=metric_id, label="Operator label", unit=unit, role=role).items():
            ET.SubElement(channel, key).text = value
    info.xml = ET.tostring(root, encoding="unicode")
    info.channel_count = lambda: len(definitions)
    return info, definitions


@pytest.mark.parametrize("contract,reordered", [("respyra-polar-pca/1", False),
    ("respyra-polar-phan-signed/1", False), ("respyra-polar-phan-signed/1", True)])
def test_bundled_waveform_gates_each_row_and_retains_calibrated_diagnostics(contract, reordered):
    info, definitions = bundled_candidate(contract, reordered)
    assert validate_polar_info(info) == (contract, ())
    waveform_index = next(i for i, (_, _, role) in enumerate(definitions) if role == "waveform")
    valid_row = [0.02 if role == "waveform" else 0.7 if role == "quality" else 1.0
                 for _, _, role in definitions]
    invalid_row = valid_row.copy()
    invalid_row[next(i for i, (_, _, role) in enumerate(definitions) if role == "validity")] = 0
    closed = []

    class Inlet:
        def __init__(self, *_args, **_kwargs): pass
        def info(self, **_kwargs): return info
        def pull_chunk(self, **_kwargs): return [invalid_row, valid_row], [100.0, 100.1]
        def close_stream(self): closed.append(True)

    def no_companion_resolution(**_kwargs):
        raise AssertionError("Bundled streams must not resolve separate validity outlets")

    module = types.SimpleNamespace(StreamInlet=Inlet, resolve_streams=no_companion_resolution,
        cf_float32=1, cf_double64=2, proc_clocksync=1)
    with patch.dict(sys.modules, {"pylsl": module}):
        source = open_polar_source(info, timeout=1)
        assert source.force_index == waveform_index and source.valid_inlets == {}
        projected = []
        source.calibrated_outlet = types.SimpleNamespace(push_sample=lambda row, timestamp: projected.append((row, timestamp)))
        assert source.get_all() == [(100.1, 0.02)]
        assert len(projected) == 1 and all(math.isnan(value) for value in projected[0][0])
        source.center, source.amplitude, source.polarity = -0.01, 0.01, -1
        assert source.get_all() == [(100.1, -0.02)]
        assert projected[-1] == ([-1.0, *[value for i, value in enumerate(valid_row) if i != waveform_index]], 100.1)
        source.stop()
    assert closed == [True]


@pytest.mark.parametrize("fault", ["missing", "duplicate", "wrong_unit", "wrong_role", "wrong_count", "wrong_flags"])
def test_bundled_channel_contract_rejects_ambiguous_or_missing_readiness(fault):
    info, _ = bundled_candidate("respyra-polar-phan-signed/1")
    root = ET.fromstring(info.xml)
    channels = root.find("desc/channels")
    if fault == "missing":
        channels.remove(channels[-1])
    elif fault == "duplicate":
        channels[-1].find("metric_id").text = "adr_pca_valid"
    elif fault == "wrong_unit":
        channels[-1].find("unit").text = "g"
    elif fault == "wrong_role":
        channels[-1].find("role").text = "waveform"
    elif fault == "wrong_count":
        info.channel_count = lambda: 9
    else:
        root.find("desc/validity_channels").text = "adr_pca_valid"
    info.xml = ET.tostring(root, encoding="unicode")
    with pytest.raises(LSLForceError):
        validate_polar_info(info)
