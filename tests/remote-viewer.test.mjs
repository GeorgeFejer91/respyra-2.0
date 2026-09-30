import assert from 'node:assert/strict';
import { test } from 'node:test';
import { invitationUrl, parseInvitation, PANEL, OBSERVE_SCOPE, SCOPES, RUN_SCOPE, validCommand, validateControllerState } from '../web/remote-profile.js';
import { BRSPConnection } from '../vendor/remote/brsp.js';

const invite = { room:'brsp_' + 'a'.repeat(64), secret:'b'.repeat(64) };
const snapshot = { profile:'respyra.controller/1', revision:2, monitorRevision:10, phase:'experiment',
  message:'Experiment running in PsychoPy.', setup:null, progress:{ phase:'progress',
    event:'tracking.started', seq:12, lsl_time:123.5, trial:2, condition:'normal', experiment_phase:'tracking', screen:null } };
test('invitation, state and commands have closed bounded contracts', () => {
  const url = invitationUrl(invite);
  assert.deepEqual(parseInvitation(url), invite);
  assert.equal(new URL(PANEL.url).hash, '');
  for (const bad of [url.replace('https:','http:'), url.replace('georgefejer91.github.io','evil.example'),
    url + '&extra=x', url.replace('#','?'), url.replace(invite.secret,'short')]) assert.equal(parseInvitation(bad),null);
  assert.equal(validateControllerState(snapshot),true);
  assert.equal(validateControllerState({ ...snapshot,participant:'private' }),false);
  assert.equal(validateControllerState({ ...snapshot,progress:{ ...snapshot.progress,lsl_time:NaN } }),false);
  assert.equal(validateControllerState({ ...snapshot,message:'x'.repeat(8192) }),false);
  const monitoring = {...snapshot,progress:{...snapshot.progress,
    recording:{phase:'recording',error:null,bytes_written:1024},
    health:{signal:'live',sample_age_ms:25,battery_percent:null,
      preview:{name:'Raw Force',source_id:'synthetic',lsl_time:123.5,force_index:0,
        channels:[{index:0,label:'Force',unit:'N',value:5}]}}}};
  assert(validateControllerState(monitoring));
  assert(!validateControllerState({...monitoring,progress:{...monitoring.progress,
    recording:{...monitoring.progress.recording,output_file:'C:/private/test.xdf'}}}));
  assert(!validateControllerState({...monitoring,progress:{...monitoring.progress,
    health:{...monitoring.progress.health,preview:{...monitoring.progress.health.preview,
      channels:[{index:0,label:'Force',unit:'N',value:NaN}]}}}}));
  const start = { scope:RUN_SCOPE, action:'start', args:{ ui_seq:1,ui_time_ms:1 }, expectedRevision:2 };
  assert(validCommand(start));
  const csv = {scope:SCOPES[1],action:'option',args:{ui_seq:2,ui_time_ms:2,field:'save_csv',enabled:true},expectedRevision:2};
  assert(validCommand(csv));
  const variables = {scope:SCOPES[1],action:'field_edit',args:{ui_seq:3,ui_time_ms:3,field:'variables',value:'[{"label":"Age","value":"28"}]'},expectedRevision:2};
  assert(validCommand(variables));
  assert(validCommand({scope:OBSERVE_SCOPE,action:'introduce',args:{name:'Ada'},expectedRevision:null}));
  for (const name of ['', ' Ada', 'Ada\nX', '\u202eAda', 'x'.repeat(65)])
    assert(!validCommand({scope:OBSERVE_SCOPE,action:'introduce',args:{name},expectedRevision:null}));
  assert(!validCommand({...variables,args:{...variables.args,value:'x'.repeat(2049)}}));
  assert(!validCommand({...csv,args:{...csv.args,enabled:'true'}}));
  assert(!validCommand({...csv,args:{...csv.args,field:'recording'}}));
  for (const command of [{ ...start,scope:OBSERVE_SCOPE }, { ...start,action:'shell' },
    { ...start,args:{ ...start.args,path:'x' } }, { ...start,expectedRevision:null }]) assert(!validCommand(command));
});

class Lane extends EventTarget {
  sendControl(peerKey,data) { queueMicrotask(() => this.other.dispatchEvent(event('controlmessage',{peerKey,data}))); return true; }
  sendState(peerKey,data) { queueMicrotask(() => this.other.dispatchEvent(event('statemessage',{peerKey,data}))); return true; }
  async stop() {}
}
function event(type,detail) { const value = new Event(type); Object.defineProperty(value,'detail',{value:detail}); return value; }
function once(source,type) { return new Promise(resolve => source.addEventListener(type,event => resolve(event.detail),{once:true})); }
test('mutual BRSP proof gates state and reliable mutation acknowledgments', { timeout:3000 }, async () => {
  for (const scopes of [SCOPES,[]]) {
    const a=new Lane(), b=new Lane(); a.other=b; b.other=a;
    let target, effects=0;
    target=new BRSPConnection({ transport:a,role:'target',sessionId:invite.room,sharedSecret:invite.secret,
      grantedScopes:SCOPES, getState:() => target.acceptedScopes.includes(OBSERVE_SCOPE) ? snapshot : undefined,
      applyCommand:async command => {
        if (!validCommand(command)) return { ok:false,revision:2,error:'unsupported_command' };
        await new Promise(resolve=>setTimeout(resolve,10));
        effects++;
        return { ok:true,revision:3 };
      } });
    const controller=new BRSPConnection({ transport:b,role:'controller',sessionId:invite.room,
      sharedSecret:invite.secret,requestedScopes:scopes });
    let states=0;
    controller.addEventListener('state',()=>states++);
    const ready=once(controller,'ready'), received=scopes.length ? once(controller,'snapshot') : null;
    a.dispatchEvent(event('peeropen',{peerKey:'fixture'})); b.dispatchEvent(event('peeropen',{peerKey:'fixture'}));
    await ready;
    if (received) {
      assert.deepEqual((await received).state,snapshot);
      const applied=once(controller,'commandapplied');
      controller.sendCommand(RUN_SCOPE,'start',{ui_seq:1,ui_time_ms:1},{expectedRevision:2});
      assert.equal(effects,0,'Sending is not an application acknowledgment');
      assert.equal((await applied).ok,true);
      assert.equal(effects,1);
      const rejected=once(controller,'commandapplied');
      controller.sendCommand(RUN_SCOPE,'shell',{}, {expectedRevision:3});
      assert.equal((await rejected).ok,false);
      assert.equal(effects,1);
    } else assert.throws(()=>controller.sendCommand(RUN_SCOPE,'start',{}),/not granted/u);
    await new Promise(done=>setTimeout(done,10));
    if (!scopes.length) assert.equal(states,0);
    await controller.close(); await target.close();
  }
});
