"""Recording failures must never masquerade as a started/saved experiment."""
from pathlib import Path
import struct
import subprocess
from types import SimpleNamespace

import pytest

from mpi.recording import NativeRecording, RecordingError, inspect_xdf
from mpi.lsl_setup import SourceSetup, SetupRejected


def fixture_xdf(footer=True, count=1):
    def chunk(tag, payload):
        body = struct.pack('<H', tag) + payload
        return b'\x04' + struct.pack('<I', len(body)) + body
    identity = struct.pack('<I', 1)
    header = b'<info><name>Force</name><source_id>raw-test</source_id></info>'
    data = identity + b'\x01\x01' + b'\x08' + struct.pack('<df', 1.0, 5.0)
    result = b'XDF:' + chunk(2, identity + header) + chunk(3, data)
    if footer:
        result += chunk(6, identity + f'<info><sample_count>{count}</sample_count></info>'.encode())
    return result


@pytest.mark.parametrize('kind', ['missing_footer', 'wrong_count', 'truncated', 'huge_chunk', 'missing_source'])
def test_completion_rejects_incomplete_or_missing_data(tmp_path, kind):
    path = tmp_path / 'test.xdf.partial'
    data = fixture_xdf(footer=kind != 'missing_footer', count=0 if kind == 'wrong_count' else 1)
    if kind == 'truncated': data = data[:-3]
    if kind == 'huge_chunk': data += b'\x08' + struct.pack('<Q', 2**63)
    path.write_bytes(data)
    with pytest.raises(RecordingError):
        inspect_xdf(path, ['other-source' if kind == 'missing_source' else 'raw-test'])
    assert path.exists(), 'A failed verification must preserve the partial file'


def test_recorder_failure_prevents_setup_acceptance():
    events = []
    markers = SimpleNamespace(name='Events', emit=lambda name, **_: events.append(name))
    recorder = SimpleNamespace(start=lambda *a: (_ for _ in ()).throw(RecordingError('disk unavailable')))
    setup = SourceSetup(SimpleNamespace(name='Study'), markers, recorder)
    setup.source = SimpleNamespace(get_all=lambda: [], source_id='raw-test', stream_name='Force')
    setup.values['participant'] = 'synthetic'
    setup.shown = True
    try:
        with pytest.raises(SetupRejected, match='disk unavailable'):
            setup.command({'action':'start', 'ui_seq':1, 'ui_time_ms':1})
        assert not setup.accepted and not setup.done
        assert 'participant.dialog.accepted' not in events
    finally:
        setup.source = None
        setup.close()


def test_hung_recorder_is_reaped_and_keeps_partial_file(tmp_path):
    recording = NativeRecording(tmp_path, tmp_path)
    recording.path = tmp_path / 'hung.xdf.partial'
    recording.path.write_bytes(fixture_xdf())
    actions = []
    def wait(timeout):
        if timeout == 10: raise subprocess.TimeoutExpired('native recorder', timeout)
        return -1
    recording.process = SimpleNamespace(poll=lambda: None, stdin=SimpleNamespace(
        write=lambda _: None, flush=lambda: None, close=lambda: None, closed=True),
        stderr=SimpleNamespace(close=lambda: None), wait=wait, kill=lambda: actions.append('killed'))
    recording._reader = SimpleNamespace(join=lambda **_: None)
    with pytest.raises(RecordingError, match='Partial recording preserved'):
        recording.stop()
    assert actions == ['killed'] and recording.process is None and recording.phase == 'error'
    assert recording.path.exists() and not recording.path.with_suffix('').exists()


def test_complete_file_has_matching_samples_and_footer(tmp_path):
    path = tmp_path / 'complete.xdf'
    path.write_bytes(fixture_xdf())
    assert inspect_xdf(path, ['raw-test'])[0]['sample_count'] == 1


def test_missing_native_bundle_reports_failure_without_starting(tmp_path):
    recorder = NativeRecording(tmp_path, tmp_path)
    with pytest.raises(RecordingError, match='Native recorder is missing'):
        recorder.start({'participant':'synthetic', 'session':'001'}, None, None)
    assert recorder.phase == 'error' and recorder.process is None and recorder.path is None


def test_failed_child_cannot_promote_a_closed_looking_file(tmp_path):
    recorder = NativeRecording(tmp_path, tmp_path)
    recorder.path = tmp_path / 'failed.xdf.partial'
    recorder.path.write_bytes(fixture_xdf())
    recorder.phase = 'recording'
    recorder.process = SimpleNamespace(poll=lambda: 1, wait=lambda **_: 1,
        stdin=SimpleNamespace(closed=True), stderr=SimpleNamespace(close=lambda: None))
    with pytest.raises(RecordingError, match='exited'):
        recorder.check_health()
    with pytest.raises(RecordingError, match='Partial recording preserved'):
        recorder.stop()
    assert recorder.phase == 'error' and recorder.process is None
    assert recorder.path.exists() and not recorder.path.with_suffix('').exists()
