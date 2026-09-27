"""Native setup + real LSL, isolated identity settings; no physical belt."""
import json
import math
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
# Configure before importing liblsl; keep test streams out of live lab sessions.
config = root / '.for-ai-local' / ('native-lsl-' + uuid.uuid4().hex + '.cfg')
config.parent.mkdir(exist_ok=True)
config.write_text('[lab]\nSessionID = respyra-native-' + uuid.uuid4().hex + '\n', encoding='utf-8')
os.environ['LSLAPICFG'] = str(config)
from pylsl import StreamInfo, StreamOutlet, StreamInlet, cf_float32, local_clock, resolve_byprop
from pylsl.util import LostError

identity = 'polar-stream-vernier-raw-native-' + uuid.uuid4().hex
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
        outlet.push_sample([12,5+math.sin(local_clock())],local_clock())
        derived.push_sample([.5],local_clock())
thread=threading.Thread(target=push);thread.start()
env=os.environ.copy()
env.pop('RESPYRA_LSL_SOURCE_ID',None)
env['LOCALAPPDATA']=str(root/'.for-ai-local'/('native-settings-'+uuid.uuid4().hex))
env['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS']='--remote-debugging-port=9227'
env['RESPYRA_UI_TEST_READY_PATH']=str(root/'.for-ai-local'/('instructions-'+uuid.uuid4().hex))
exe=root/'src-tauri/target/debug/respyra-desktop.exe'
results=[]
try:
    for mode in ['select','memory','remote']:
        Path(env['RESPYRA_UI_TEST_READY_PATH']).unlink(missing_ok=True)
        stderr=open(root/f'.for-ai-local/native-{mode}.log','w',encoding='utf-8')
        process=subprocess.Popen([str(exe)],cwd=root,env=env,stdout=stderr,stderr=stderr)
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
            for expected in ['participant.dialog.shown','participant.field.edited','participant.field.key','source.connected','source.connection.accepted','source.disconnected','run.aborted']:assert expected in names,(expected,names)
            assert [m['seq'] for m in markers]==list(range(markers[0]['seq'],markers[0]['seq']+len(markers)))
            if mode=='select':
                assert 'source.memory.saved' in names and 'source.scan.completed' in names
                assert 'participant.dialog.rejected' in names
            else:
                assert 'source.memory.loaded' in names and 'source.memory.saved' not in names
                assert 'source.scan.started' not in names
                assert 'participant.dialog.accepted' in names and 'display.opened' in names
                assert 'ui.instructions.shown' in names and 'ui.wrapper.closed' in names
                assert 'display.closed' in names
                assert 'ui.experiment.stop.requested' in names
                stopped=next(m for m in markers if m['event']=='ui.experiment.stop.requested')
                assert stopped['ui_origin']==('remote' if mode=='remote' else 'local')
                assert next(m for m in markers if m['event']=='run.aborted')['reason']=='experimenter_stop'
            (root/f'.for-ai-local/native-{mode}-markers.json').write_text(json.dumps(markers,indent=2),encoding='utf-8')
            print(out.strip(),flush=True)
            results.append({'mode':mode,'markers':len(markers),'first':names[0],'last':names[-1]})
        finally:
            if process.poll() is None: process.kill();process.wait()
            if inlet: inlet.close_stream()
            stderr.close()
        time.sleep(2)
    print(json.dumps({'result':'passed','runs':results}),flush=True)
finally:
    stop.set();thread.join()
    config.unlink()
