export const VIEWER_URL = 'https://georgefejer91.github.io/respyra-2.0/';
export const OBSERVE_SCOPE = 'experiment.observe';
export const SETUP_SCOPE = 'experiment.setup';
export const RUN_SCOPE = 'experiment.run';
export const SCOPES = Object.freeze([OBSERVE_SCOPE, SETUP_SCOPE, RUN_SCOPE]);
export const PANEL = Object.freeze({ id:'respyra-2', name:'Respyra 2.0', url:new URL('remote.html', VIEWER_URL).href });

export function invitationUrl({ room, secret }) {
  if (!/^brsp_[a-f0-9]{64}$/u.test(room) || !/^[a-f0-9]{64}$/u.test(secret)) throw new Error('Invalid Respyra invitation.');
  return VIEWER_URL + '#room=' + room + '&secret=' + secret;
}

export function parseInvitation(value) {
  try {
    const url = new URL(value);
    const base = new URL(VIEWER_URL);
    if (url.origin !== base.origin || ![base.pathname, new URL('remote.html', base).pathname].includes(url.pathname) || url.search) return null;
    const fields = new URLSearchParams(url.hash.slice(1));
    if ([...fields.keys()].length !== 2 || !fields.has('room') || !fields.has('secret')) return null;
    const invitation = { room:fields.get('room'), secret:fields.get('secret') };
    invitationUrl(invitation);
    return invitation;
  } catch { return null; }
}

export function scopeForAction(action) {
  if (['field_key','field_edit','option','scan','select','use','cancel'].includes(action)) return SETUP_SCOPE;
  if (['start','abort','close','prompt_control'].includes(action)) return RUN_SCOPE;
  return null;
}

export function validCommand(command) {
  if (!command || typeof command !== 'object' || Array.isArray(command)) return false;
  if (command.scope === OBSERVE_SCOPE) return command.expectedRevision === null && (
    (command.action === 'renew' && exact(command.args, [])) ||
    (command.action === 'introduce' && exact(command.args, ['name']) && validViewerName(command.args.name)));
  if (scopeForAction(command.action) !== command.scope || !Number.isSafeInteger(command.expectedRevision) || command.expectedRevision < 0) return false;
  if (command.action === 'close') return exact(command.args, []);
  const keys = ['ui_seq','ui_time_ms'];
  if (command.action === 'field_key') keys.push('field','key');
  if (command.action === 'field_edit') keys.push('field','value');
  if (command.action === 'select') keys.push('row');
  if (command.action === 'option') keys.push('field','enabled');
  if (command.action === 'prompt_control') keys.push('prompt_id','control');
  const args = command.args;
  if (!exact(args, keys) || !integer(args.ui_seq, 1) || !Number.isFinite(args.ui_time_ms) || args.ui_time_ms < 0) return false;
  if (keys.includes('field') && !(command.action === 'option' ? ['save_csv'] : ['participant','session','marker_name','variables']).includes(args.field)) return false;
  if (keys.includes('enabled') && typeof args.enabled !== 'boolean') return false;
  if (keys.includes('key') && !text(args.key,128)) return false;
  if (keys.includes('value') && !text(args.value,args.field === 'variables' ? 2048 : 128)) return false;
  if (command.action === 'prompt_control' && (!promptId(args.prompt_id) || !['continue','retry'].includes(args.control))) return false;
  return !keys.includes('row') || integer(args.row);
}

export function validViewerName(value) {
  return typeof value === 'string' && value.length > 0 && value.length <= 64 &&
    value.trim() === value && !/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/u.test(value);
}

function exact(value, keys) {
  return !!value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value,key));
}
const integer = (v,min=0) => Number.isSafeInteger(v) && v >= min;
const text = (v,max=4096) => typeof v === 'string' && v.length <= max;
const promptId = v => typeof v === 'string' && /^[A-Za-z0-9:-]{1,96}$/u.test(v);
export function validateControllerState(value) {
  if (!exact(value, ['profile','revision','monitorRevision','phase','message','setup','progress'])
    || value.profile !== 'respyra.controller/1' || !integer(value.revision) || !integer(value.monitorRevision)
    || !['starting','setup','experiment','finished','error'].includes(value.phase)
    || !text(value.message) || new TextEncoder().encode(JSON.stringify(value)).length > 8192) return false;
  if (value.setup !== null) {
    const s = value.setup;
    if (value.phase !== 'setup' || !exact(s,['phase','ui_seq','study_name','values','recorded_participants','variables','message','busy','can_start','can_use','selected_row','streams','source','omitted_streams','marker_name','save_csv','compare_inputs'])
      || s.phase !== 'setup' || !integer(s.ui_seq) || !text(s.study_name) || !text(s.message)
      || !exact(s.values,['participant','session']) || !text(s.values.participant,128) || !text(s.values.session,128)
      || (s.recorded_participants !== null && (!Array.isArray(s.recorded_participants) || s.recorded_participants.length > 101 || s.recorded_participants.some(n => !integer(n) || n > 100)))
      || !Array.isArray(s.variables) || s.variables.length > 6 || s.variables.some(row =>
        !exact(row,['label','value']) || !text(row.label,128) || !text(row.value,128))
      || !text(s.marker_name,128) || ['busy','can_start','can_use','save_csv','compare_inputs'].some(key=>typeof s[key] !== 'boolean')
      || (s.selected_row !== null && !integer(s.selected_row)) || !integer(s.omitted_streams)
      || !Array.isArray(s.streams)) return false;
    if (s.source !== null && (!exact(s.source,['source_id','stream_name']) || !text(s.source.source_id) || !text(s.source.stream_name))) return false;
    for (const row of s.streams) if (!exact(row,['source_id','stream_name','stream_type','compatible','reason','force_channel_index','row'])
      || !integer(row.row) || ['source_id','stream_name','stream_type','reason'].some(key=>!text(row[key]))
      || typeof row.compatible !== 'boolean' || (row.force_channel_index !== null && !integer(row.force_channel_index))) return false;
  }
  if (value.progress !== null) {
    const p = value.progress, keys = ['phase','event','seq','lsl_time','trial','condition','screen','experiment_phase','health','markers','recent','recording','prompt'];
    if (typeof p !== 'object' || Array.isArray(p) || p.phase !== 'progress' || Object.keys(p).some(key=>!keys.includes(key))) return false;
    for (const key of ['event','condition','screen','experiment_phase']) if (p[key] != null && !text(p[key],80)) return false;
    for (const key of ['seq','trial']) if (p[key] != null && !integer(p[key])) return false;
    if (p.lsl_time != null && (!Number.isFinite(p.lsl_time) || p.lsl_time < 0)) return false;
    if (p.prompt != null && (!exact(p.prompt,['id','screen','controls']) || !promptId(p.prompt.id)
      || !['instructions','calibration_ready','calibration_result','trial_ready','trial_feedback','end'].includes(p.prompt.screen)
      || !Array.isArray(p.prompt.controls) || !p.prompt.controls.length || p.prompt.controls.length > 2
      || new Set(p.prompt.controls).size !== p.prompt.controls.length
      || p.prompt.controls.some(control => !['continue','retry'].includes(control))
      || (p.prompt.controls.includes('retry') && p.prompt.screen !== 'calibration_result'))) return false;
    if (p.markers != null && (!exact(p.markers,['name','source_id','online','emitted'])
      || !text(p.markers.name,128) || !text(p.markers.source_id,128)
      || typeof p.markers.online !== 'boolean' || !integer(p.markers.emitted))) return false;
    if (p.recent != null && (!Array.isArray(p.recent) || p.recent.length > 12 || p.recent.some(row =>
      !exact(row,['event','seq','lsl_time']) || !text(row.event,80) || !integer(row.seq,1) || !Number.isFinite(row.lsl_time) || row.lsl_time < 0))) return false;
    if (p.recording != null && (!exact(p.recording,['phase','error','bytes_written'])
      || !['idle','preparing','recording','finalizing','complete','error'].includes(p.recording.phase)
      || (p.recording.error !== null && !text(p.recording.error)) || !integer(p.recording.bytes_written))) return false;
    if (p.health != null && (!exact(p.health,['signal','sample_age_ms','battery_percent',
      ...(Object.hasOwn(p.health,'preview') ? ['preview'] : [])])
      || !['not_selected','live','stale','lost','disconnected'].includes(p.health.signal)
      || (p.health.sample_age_ms !== null && !integer(p.health.sample_age_ms))
      || (p.health.battery_percent !== null && (!Number.isFinite(p.health.battery_percent) || p.health.battery_percent < 0 || p.health.battery_percent > 100)))) return false;
    const preview = p.health?.preview;
    if (preview != null && (!exact(preview,['source_id','name','lsl_time','force_index','channels'])
      || !text(preview.source_id) || !text(preview.name) || !Number.isFinite(preview.lsl_time) || preview.lsl_time < 0
      || !integer(preview.force_index) || !Array.isArray(preview.channels) || preview.channels.length > 32
      || preview.channels.some(channel => !exact(channel,['index','label','unit','value']) || !integer(channel.index)
        || !text(channel.label) || !text(channel.unit) || (channel.value !== null && !Number.isFinite(channel.value))))) return false;
  }
  return true;
}
