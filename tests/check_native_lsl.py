"""Native setup + real LSL, isolated identity settings; no physical belt."""
import json
import argparse
import csv
import math
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('modes', nargs='*', metavar='{select,memory,remote}')
modes=parser.parse_args().modes or ['select','memory','remote']
if any(mode not in {'select','memory','remote'} for mode in modes):
    parser.error('modes must be select, memory or remote')
# Configure before importing liblsl; keep test streams out of live lab sessions.
external = os.environ.get('RESPYRA_TEST_SOURCE_ID')
full_mock = os.environ.get('RESPYRA_FULL_MOCK_STUDY') == '1'
config = None
if not external:
    config = root / '.for-ai-local' / ('native-lsl-' + uuid.uuid4().hex + '.cfg')
    config.parent.mkdir(exist_ok=True)
    config.write_text('[lab]\nSessionID = respyra-native-' + uuid.uuid4().hex + '\n', encoding='utf-8')
    os.environ['LSLAPICFG'] = str(config)
from pylsl import StreamInfo, StreamOutlet, StreamInlet, cf_float32, local_clock, resolve_byprop
from pylsl.util import LostError

identity = external or 'polar-stream-vernier-raw-native-' + uuid.uuid4().hex
if external:
    raw = resolve_byprop('source_id', identity, timeout=10)[0]
    outlet = derived = None
else:
    raw = StreamInfo('Synthetic raw Force', 'VernierRaw', 2, 20, cf_float32, identity)
    desc = raw.desc()
    for key,value in {'manufacturer':'Vernier','model':'GDX-RB','stream_role':'raw_measurement_recording'}.items(): desc.append_child_value(key,value)
    channels = desc.append_child('channels')
    for label,unit,number in [('Respiration Rate','breaths/min','2'),('Force','N','1')]:
        ch=channels.append_child('channel')
        for key,value in {'label':label,'unit':unit,'sensor_number':number,'type':'RawMeasurement'}.items(): ch.append_child_value(key,value)
    outlet=StreamOutlet(raw)
    derived=StreamOutlet(StreamInfo('Synthetic normalized','Respiration',1,20,cf_float32,'native-derived-'+uuid.uuid4().hex))
stop=threading.Event()
def push():
    while not stop.wait(.05):
        if outlet is not None:
            outlet.push_sample([12,5+math.sin(local_clock())],local_clock())
            derived.push_sample([.5],local_clock())
thread=threading.Thread(target=push);thread.start()
env=os.environ.copy()
env.pop('RESPYRA_LSL_SOURCE_ID',None)
env['LOCALAPPDATA']=str(root/'.for-ai-local'/('native-settings-'+uuid.uuid4().hex))
env['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS']='--remote-debugging-port=9227'
env['WEBVIEW2_USER_DATA_FOLDER']=str(root/'.for-ai-local'/('native-webview-'+uuid.uuid4().hex))
env['RESPYRA_UI_TEST_READY_PATH']=str(root/'.for-ai-local'/('instructions-'+uuid.uuid4().hex))
exe=(Path(os.environ['RESPIRA_INSTALLED_EXE']) if os.environ.get('RESPIRA_INSTALLED_EXE') else
     Path(os.environ['RESPYRA_DEBUG_EXE']) if os.environ.get('RESPYRA_DEBUG_EXE') else
     root/'src-tauri/target/debug/respyra-desktop.exe')
work=root/'.for-ai-local/packaging/run elsewhere' if os.environ.get('RESPIRA_INSTALLED_EXE') else root
work.mkdir(parents=True,exist_ok=True)
if os.environ.get('RESPIRA_INSTALLED_EXE'):
    env['RESPIRA_TEST_PARTICIPANT']='packaging-test-'+uuid.uuid4().hex[:12]
else:
    env['RESPIRA_DATA_DIR']=str(root/'.for-ai-local'/('native-recordings-'+uuid.uuid4().hex))
results=[]
if modes[0] != 'select':
    # A focused reconnect/remote run owns its own saved-source fixture.
    from types import SimpleNamespace
    from mpi.lsl_force import save_force_selection
    save_force_selection(SimpleNamespace(source_id=identity, stream_name=raw.name()),
                         Path(env['LOCALAPPDATA'])/'Respyra/lsl-source.json')
try:
    for mode in modes:
        Path(env['RESPYRA_UI_TEST_READY_PATH']).unlink(missing_ok=True)
        stderr=open(root/f'.for-ai-local/native-{mode}.log','w',encoding='utf-8')
        process=subprocess.Popen([str(exe)],cwd=work,env=env,stdout=stderr,stderr=stderr)
        inlet=None
        try:
            streams=resolve_byprop('name','Respyra-Events',timeout=20)
            assert len(streams)==1, 'Expected unique synthetic-run marker outlet'
            inlet=StreamInlet(streams[0],recover=False)
            inlet.open_stream(timeout=5)
            ui=subprocess.Popen(['node',str(root/'tests/check_native_ui.cjs'),mode],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            markers=[]
            deadline=time.monotonic()+120
            while process.poll() is None and time.monotonic()<deadline:
                try: sample,ts=inlet.pull_sample(timeout=.1)
                except LostError: sample=None;time.sleep(.05)
                if sample:
                    markers.append(json.loads(sample[0]))
                    if markers[-1]['event']=='ui.instructions.shown':Path(env['RESPYRA_UI_TEST_READY_PATH']).write_text('ready')
                if ui.poll() not in (None,0):
                    out,err=ui.communicate();raise AssertionError(out+err)
            assert process.poll()==0,'Native app did not close cleanly'
            out,err=ui.communicate(timeout=5)
            assert ui.returncode==0,out+err
            while True:
                try: sample,ts=inlet.pull_sample(timeout=0)
                except LostError: break
                if not sample:break
                markers.append(json.loads(sample[0]))
            names=[m['event'] for m in markers]
            (root/f'.for-ai-local/native-{mode}-markers.json').write_text(json.dumps(markers,indent=2),encoding='utf-8')
            assert 'run.failed' not in names,names
            for expected in ['participant.dialog.shown','participant.field.edited','participant.field.key','source.connected','source.connection.accepted','source.disconnected',
                             'run.completed' if full_mock else 'run.aborted']:assert expected in names,(expected,names)
            assert [m['seq'] for m in markers]==list(range(markers[0]['seq'],markers[0]['seq']+len(markers)))
            if mode=='select':
                assert 'source.memory.saved' in names and 'source.scan.completed' in names
                assert 'participant.dialog.rejected' in names
            else:
                assert 'source.memory.saved' not in names
                if not external:
                    assert 'source.memory.loaded' in names
                assert 'source.scan.started' not in names
                assert 'participant.dialog.accepted' in names and 'display.opened' in names
                assert 'ui.instructions.shown' in names and 'ui.wrapper.closed' in names
                assert 'display.closed' in names
                if full_mock:
                    assert mode == 'remote' and 'run.aborted' not in names
                    assert sum(m['event']=='trial.ended' for m in markers) == 48
                else:
                    assert 'ui.experiment.stop.requested' in names
                    stopped=next(m for m in markers if m['event']=='ui.experiment.stop.requested')
                    assert stopped['ui_origin']==('remote' if mode=='remote' else 'local')
                    assert next(m for m in markers if m['event']=='run.aborted')['reason']=='experimenter_stop'
                from mpi.recording import inspect_xdf
                import pyxdf
                file=Path(json.loads((root/f'.for-ai-local/native-{mode}-xdf.json').read_text())['file'])
                recorded,_=pyxdf.load_xdf(str(file))
                by_id={s['info']['source_id'][0]:s for s in recorded}
                marker_id=streams[0].source_id()
                derived_id='respyra-breathing-'+markers[0]['run_id']
                summaries=inspect_xdf(file,[identity,marker_id,derived_id])
                recorded_events=[json.loads(row[0]) for row in by_id[marker_id]['time_series']]
                recorded_names=[m['event'] for m in recorded_events]
                for expected in ['recording.started','participant.dialog.accepted','display.opened',
                                 'ui.instructions.shown','run.completed' if full_mock else 'run.aborted',
                                 'source.disconnected','display.closed','recording.finalizing']:
                    assert expected in recorded_names,(expected,recorded_names)
                assert by_id[identity]['time_stamps'][0] < next(m['lsl_time'] for m in recorded_events if m['event']=='display.opened')
                assert recorded_names.index('display.closed') < recorded_names.index('recording.finalizing')
                assert [m['seq'] for m in recorded_events]==list(range(recorded_events[0]['seq'],recorded_events[-1]['seq']+1))
                assert (len(recorded)>=3 if external else len(recorded)==4)
                assert all(s['sample_count'] for s in summaries if s['source_id'] in {identity, marker_id, derived_id})
                import math
                if full_mock:
                    assert any(math.isfinite(float(row[0])) for row in by_id[derived_id]['time_series'])
                    from scripts.audit_mock_xdf import audit
                    print(json.dumps(audit(file)),flush=True)
                else:
                    assert all(math.isnan(float(row[0])) for row in by_id[derived_id]['time_series'])
                print(json.dumps({'native_xdf':'passed','mode':mode,'file':str(file),'streams':summaries}),flush=True)
            (root/f'.for-ai-local/native-{mode}-markers.json').write_text(json.dumps(markers,indent=2),encoding='utf-8')
            print(out.strip(),flush=True)
            results.append({'mode':mode,'markers':len(markers),'first':names[0],'last':names[-1]})
        finally:
            if process.poll() is None: process.kill();process.wait()
            if inlet: inlet.close_stream()
            stderr.close()
        time.sleep(2)
    if os.environ.get('RESPIRA_INSTALLED_EXE') and 'memory' in modes:
        # Rust uses Windows' known local-data folder, not the isolated Python
        # identity-memory override. Only inspect/remove this test's unique IDs.
        output=Path(os.environ['LOCALAPPDATA'])/'Respira/data'
        files=sorted(output.glob('*'+env['RESPIRA_TEST_PARTICIPANT']+'*.csv'))
        assert len(files)==2,files  # one CSV-on run; the other two create none
        from mpi.validation_study_jenny import CONFIG
        for file in files:
            with file.open(newline='',encoding='utf-8') as handle:
                header=next(csv.reader(handle))
            expected=(['trial_num','condition','self_condition','confidence','self_accuracy']
                      if file.name.endswith('-self-assessment.csv') else list(CONFIG.data_columns))
            assert header==expected,(file.name,header,expected)
            evidence=root/'.for-ai-local/packaging/csv'
            evidence.mkdir(parents=True,exist_ok=True)
            (evidence/file.name).write_bytes(file.read_bytes())
            file.unlink()  # proves logger handles are closed; never touch other IDs
        print(json.dumps({'installed_csv':'passed','files':2,'original_headers':True}),flush=True)
    print(json.dumps({'result':'passed','runs':results}),flush=True)
finally:
    stop.set();thread.join()
    if config is not None: config.unlink()
