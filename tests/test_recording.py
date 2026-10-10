"""Recording failures must never masquerade as a started/saved experiment."""
import json
from pathlib import Path
import struct
import subprocess
from types import SimpleNamespace

import pytest

from mpi.recording import NativeRecording, RecordingError, inspect_xdf, participant_number, recorded_participant_numbers, recording_stem
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
    markers = SimpleNamespace(name='Events', run_id='test-run', emit=lambda name, **_: events.append(name))
    recorder = SimpleNamespace(start=lambda *a: (_ for _ in ()).throw(RecordingError('disk unavailable')))
    setup = SourceSetup(SimpleNamespace(name='Study'), markers, recorder)
    setup.source = SimpleNamespace(get_all=lambda: [], start_derived=lambda _: None,
                                   source_id='raw-test', stream_name='Force')
    setup.values['participant'] = '2'
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


def test_filename_uses_number_and_custom_fields():
    values = {'participant':'2', 'session':'001', 'variables':[
        {'label':'Age', 'value':'28'}, {'label':'Study group', 'value':'Control'}]}
    assert recording_stem(values) == 'P002_Session-001_Age-28_Study-group-Control'


def test_participant_number_and_verified_history(tmp_path):
    assert [participant_number(value) for value in ('0', 'P001', '100', '101', 'other')] == [0, 1, 100, None, None]
    assert recorded_participant_numbers(tmp_path) == []
    (tmp_path / 'participant-list.jsonl').write_text('\n'.join(json.dumps(row) for row in [
        {'participant_number':'P000'}, {'participant_number':'P100'}, {'participant_number':'P001'},
        {'participant_number':'P001'}, {'participant_number':'synthetic'}]) + '\n', encoding='utf-8')
    assert recorded_participant_numbers(tmp_path) == [0, 1, 100]
    (tmp_path / 'participant-list.jsonl').write_text('{bad json\n', encoding='utf-8')
    with pytest.raises(RecordingError, match='history'):
        recorded_participant_numbers(tmp_path)


def test_participant_list_appends_only_after_verified_xdf(tmp_path):
    recorder = NativeRecording(tmp_path, tmp_path)
    recorder.path = tmp_path / 'P002_Session-001_Age-28_test.xdf.partial'
    recorder.path.write_bytes(fixture_xdf())
    recorder.required = ('raw-test',)
    recorder.participant_record = {'xdf_file':recorder.path.name.removesuffix('.partial'),
        'participant_number':'P002', 'session':'001', 'variables':[{'label':'Age','value':'28'}]}
    recorder.process = SimpleNamespace(poll=lambda: 0, wait=lambda **_: 0,
        stdin=SimpleNamespace(closed=True), stderr=SimpleNamespace(close=lambda: None))
    recorder.stop()
    assert recorder.phase == 'complete' and recorder.path.suffix == '.xdf'
    assert json.loads((tmp_path / 'participant-list.jsonl').read_text(encoding='utf-8').strip()) == recorder.participant_record
    assert not (tmp_path / 'P002_Session-001_Age-28_test.xdf.partial').exists()


def test_list_failure_keeps_verified_xdf_and_reports_it(tmp_path):
    recorder = NativeRecording(tmp_path, tmp_path)
    recorder.path = tmp_path / 'P002_test.xdf.partial'
    recorder.path.write_bytes(fixture_xdf())
    recorder.required = ('raw-test',)
    recorder.participant_record = {'xdf_file':'P002_test.xdf', 'participant_number':'P002',
                                   'session':'001', 'variables':[]}
    (tmp_path / 'participant-list.jsonl').mkdir()
    recorder.process = SimpleNamespace(poll=lambda: 0, wait=lambda **_: 0,
        stdin=SimpleNamespace(closed=True), stderr=SimpleNamespace(close=lambda: None))
    with pytest.raises(RecordingError, match='XDF saved, but participant list'):
        recorder.stop()
    assert recorder.path == tmp_path / 'P002_test.xdf' and recorder.path.exists()
    assert recorder.phase == 'error' and 'Partial recording preserved' not in recorder.error


def test_bids_failure_keeps_verified_xdf_and_participant_history(monkeypatch, tmp_path):
    from mpi import bids_export
    monkeypatch.setattr(bids_export, 'export_bids', lambda *args: (_ for _ in ()).throw(OSError('disk full')))
    recorder = NativeRecording(tmp_path, tmp_path)
    recorder.path = tmp_path / 'P002_test.xdf.partial'
    recorder.path.write_bytes(fixture_xdf())
    recorder.required = ('raw-test', 'raw-test', 'raw-test')
    recorder.participant_record = {'xdf_file':'P002_test.xdf', 'participant_number':'P002',
                                   'session':'001', 'variables':[]}
    recorder.process = SimpleNamespace(poll=lambda: 0, wait=lambda **_: 0,
        stdin=SimpleNamespace(closed=True), stderr=SimpleNamespace(close=lambda: None))
    with pytest.raises(RecordingError, match='XDF saved, but BIDS export failed'):
        recorder.stop()
    assert recorder.path.suffix == '.xdf' and recorder.path.exists()
    assert recorded_participant_numbers(tmp_path) == [2]


def test_missing_native_bundle_reports_failure_without_starting(tmp_path):
    recorder = NativeRecording(tmp_path, tmp_path)
    with pytest.raises(RecordingError, match='Native recorder is missing'):
        recorder.start({'participant':'synthetic', 'session':'001'}, None, None)
    assert recorder.phase == 'error' and recorder.process is None and recorder.path is None


@pytest.mark.parametrize('fails', [False, True])
def test_summary_runs_after_promotion_and_keeps_xdf_on_plot_failure(monkeypatch, tmp_path, fails):
    from mpi import bids_export, session_summary
    monkeypatch.setattr(bids_export, 'export_bids', lambda *args: None)
    recorder = NativeRecording(tmp_path, tmp_path)
    recorder.path = tmp_path / 'P002_test.xdf.partial'
    recorder.path.write_bytes(fixture_xdf())
    recorder.required = ('raw-test', 'raw-test', 'raw-test')
    recorder.participant_record = {'xdf_file':'P002_test.xdf', 'participant_number':'P002',
                                   'session':'001', 'variables':[]}
    recorder.process = SimpleNamespace(poll=lambda: 0, wait=lambda **_: 0,
        stdin=SimpleNamespace(closed=True), stderr=SimpleNamespace(close=lambda: None))

    def render(path):
        assert path.suffix == '.xdf' and path.is_file()
        assert recorded_participant_numbers(tmp_path) == [2]
        if fails:
            raise OSError('PNG destination unavailable')
        return path.with_name(path.stem + '_summary.png')

    monkeypatch.setattr(session_summary, 'save_xdf_summary', render)
    if fails:
        with pytest.raises(RecordingError, match='XDF saved, but session summary failed'):
            recorder.stop()
    else:
        recorder.stop()
        assert recorder.summary_plot == tmp_path / 'P002_test_summary.png'
        assert recorder.phase == 'complete'
    assert recorder.path.is_file() and recorder.process is None


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
    assert not (tmp_path / 'participant-list.jsonl').exists()
