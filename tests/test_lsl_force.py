import sys
import types
from unittest.mock import patch

import pytest

from mpi.lsl_force import (
    LSLForceError, connect_force_source, force_channel_index, scan_force_streams,
    load_force_selection, save_force_selection,
)


XML = """<info><desc>
<manufacturer>Vernier</manufacturer><model>GDX-RB</model>
<stream_role>raw_measurement_recording</stream_role>
<channels>
  <channel><label>Respiration Rate</label><unit>breaths/min</unit>
    <type>RawMeasurement</type><sensor_number>2</sensor_number></channel>
  <channel><label>Force</label><unit>N</unit>
    <type>RawMeasurement</type><sensor_number>1</sensor_number></channel>
</channels></desc></info>"""


def test_force_channel_requires_raw_newtons_metadata():
    assert force_channel_index(XML, 2) == 1
    assert force_channel_index(XML.replace("<label>Force</label>", "<label>Belt tension</label>"), 2) == 1
    assert force_channel_index(XML.replace("<model>GDX-RB</model>", "<model>GDX-RB-MOCK</model>"), 2) == 1
    with pytest.raises(LSLForceError):
        force_channel_index(XML.replace("<model>GDX-RB</model>", "<model>OTHER</model>"), 2)
    with pytest.raises(LSLForceError):
        force_channel_index(XML.replace("<unit>N</unit>", "<unit>0-1</unit>"), 2)
    with pytest.raises(LSLForceError):
        force_channel_index(XML, 3)


def test_discovery_reads_only_finite_force_and_fails_on_stall():
    class Info:
        def name(self):
            return "Vernier-GDX-Mini_rawVernier"

        def type(self):
            return "VernierRaw"

        def source_id(self):
            return "polar-stream-vernier-raw-Vernier-GDX-Mini_rawVernier"

        def uid(self):
            return "synthetic-force-uid"

        def as_xml(self):
            return XML

        def channel_count(self):
            return 2

        def channel_format(self):
            return 1

    class Inlet:
        def __init__(self, *_args, **_kwargs):
            assert _kwargs["recover"] is False
            assert _kwargs["processing_flags"] == 1
            assert _kwargs["max_buflen"] >= 60
            self.chunks = [
                ([[float("nan"), 10.0]], [1.0]),
                ([[3.0, float("nan")], [4.0, 11.0]], [2.0, 3.0]),
            ]
            self.closed = False

        def info(self, **_kwargs):
            return Info()

        def pull_chunk(self, **_kwargs):
            return self.chunks.pop(0) if self.chunks else ([], [])

        def close_stream(self):
            self.closed = True

    module = types.SimpleNamespace(
        resolve_streams=lambda **_kwargs: [Info()], StreamInlet=Inlet,
        proc_clocksync=1, cf_float32=1, cf_double64=2,
    )
    with patch.dict(sys.modules, {"pylsl": module}):
        source = connect_force_source()
    assert source.get_all() == [(3.0, 11.0)]
    assert [c['value'] for c in source.health_snapshot()['preview']['channels']] == [4.0, 11.0]
    assert source.health_snapshot()['preview']['channels'][1]['unit'] == 'N'
    source.last_force_at -= 4.0
    with pytest.raises(LSLForceError, match="no Force samples"):
        source.get_all()
    source.stop()
    assert source.inlet.closed

    module.resolve_streams = lambda **_kwargs: [Info(), Info()]
    with patch.dict(sys.modules, {"pylsl": module}):
        with pytest.raises(LSLForceError, match="found 2"):
            connect_force_source()

    with patch.dict(sys.modules, {"pylsl": module}):
        with pytest.raises(LSLForceError, match="found 0"):
            connect_force_source(source_id="polar-stream-vernier-raw-missing")


def test_monitoring_uses_received_sample_freshness_and_never_invents_battery():
    from mpi.lsl_force import LSLForceSource
    inlet = types.SimpleNamespace(pull_chunk=lambda **_kwargs: ([[5.0]], [1.0]),
                                  close_stream=lambda: None)
    with patch("mpi.lsl_force.time.monotonic", return_value=10.0):
        source = LSLForceSource(inlet, 0)
        source.get_all()
    for now, expected in [(10.1, "live"), (12, "stale"), (14, "lost")]:
        with patch("mpi.lsl_force.time.monotonic", return_value=now):
            health = source.health_snapshot()
            assert health['signal'] == expected and health['sample_age_ms'] == round((now-10)*1000)
            assert health['battery_percent'] is None
            assert health['preview']['lsl_time'] == 1.0 and health['preview']['channels'][0]['value'] == 5.0
    source.stop()
    assert source.health_snapshot()["signal"] == "disconnected"


def test_scan_displays_rejected_units_and_rejects_duplicate_identities():
    class Info:
        def __init__(self, name, xml=XML, kind="VernierRaw", identity=None, fmt=1):
            self.label, self.xml, self.kind, self.fmt = name, xml, kind, fmt
            self.identity = identity or "polar-stream-vernier-raw-" + name

        def name(self): return self.label
        def type(self): return self.kind
        def source_id(self): return self.identity
        def as_xml(self): return self.xml
        def channel_count(self): return 2
        def channel_format(self): return self.fmt

    closed = []

    class Inlet:
        def __init__(self, info, **_kwargs):
            assert _kwargs["recover"] is False
            self.stream = info
        def info(self, **_kwargs):
            return types.SimpleNamespace(source_id=self.stream.source_id, type=self.stream.type,
                                         as_xml=self.stream.as_xml, channel_count=self.stream.channel_count,
                                         channel_format=self.stream.channel_format)
        def close_stream(self): closed.append(self.stream.name())

    streams = [
        Info("good"), Info("wrong units", XML.replace("<unit>N</unit>", "<unit>0-1</unit>")),
        Info("processed", kind="Respiration"), Info("strings", fmt=3),
        Info("duplicate1", identity="polar-stream-vernier-raw-duplicate"),
        Info("duplicate2", identity="polar-stream-vernier-raw-duplicate"),
        Info("unstable", identity=""),
    ]
    streams[-1].identity = ""
    module = types.SimpleNamespace(resolve_streams=lambda **_kwargs: streams,
                                   StreamInlet=Inlet, cf_float32=1, cf_double64=2)
    with patch.dict(sys.modules, {"pylsl": module}):
        candidates = {item.info.name(): item for item in scan_force_streams()}
    assert len(candidates) == len(streams)
    assert candidates["good"].info is streams[0]  # full inlet metadata is not resolver connection info
    assert candidates["good"].force_index == 1
    assert all(item.force_index is None for name, item in candidates.items() if name != "good")
    assert "Duplicate" in candidates["duplicate1"].reason
    assert len(closed) == 7  # Respiration streams need metadata validation for Polar contracts


def test_selection_memory_contains_identity_only_and_rejects_corruption(tmp_path):
    path = tmp_path / "settings" / "lsl-source.json"
    assert load_force_selection(path) is None
    source = types.SimpleNamespace(source_id="polar-stream-vernier-raw-test", stream_name="Test")
    save_force_selection(source, path)
    assert load_force_selection(path) == {
        "version": 1, "source_id": source.source_id, "stream_name": "Test",
    }
    assert list(path.parent.iterdir()) == [path]
    for invalid in ('{broken', '[]', '{"version": 2}',
                    '{"version":1,"source_id":"","stream_name":"Test"}'):
        path.write_text(invalid, encoding="utf-8")
        with pytest.raises(LSLForceError, match="choose a stream again"):
            load_force_selection(path)
    source = types.SimpleNamespace(source_id="stable-device-7", stream_name="Chest movement", contract_id="respyra-polar-pca/1")
    save_force_selection(source, path)
    assert load_force_selection(path)["source_id"] == "stable-device-7"
