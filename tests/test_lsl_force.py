import sys
import types
from unittest.mock import patch

import pytest

from mpi.lsl_force import LSLForceError, connect_force_source, force_channel_index


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

        def as_xml(self):
            return XML

        def channel_count(self):
            return 2

    class Inlet:
        def __init__(self, *_args, **_kwargs):
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
        resolve_byprop=lambda *_args, **_kwargs: [Info()], StreamInlet=Inlet,
        proc_clocksync=1,
    )
    with patch.dict(sys.modules, {"pylsl": module}):
        source = connect_force_source()
    assert source.get_all() == [(3.0, 11.0)]
    source.last_force_at -= 4.0
    with pytest.raises(LSLForceError, match="no Force samples"):
        source.get_all()
    source.stop()
    assert source.inlet.closed

    module.resolve_byprop = lambda *_args, **_kwargs: [Info(), Info()]
    with patch.dict(sys.modules, {"pylsl": module}):
        with pytest.raises(LSLForceError, match="found 2"):
            connect_force_source()
