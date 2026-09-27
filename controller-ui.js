// Shared presentation and intents. Python decides whether an action is valid.
import { MONITOR_HTML, mountLslMonitor } from './lsl-monitor.js';
export const CONTROL_HTML = `
  <p id="status" role="status" aria-live="polite" data-measure>Waiting for the experiment engine…</p>
  <p id="command-status" role="status" aria-live="polite" data-measure></p>
  ${MONITOR_HTML}
  <form id="setup" autocomplete="off">
    <fieldset id="controls" disabled>
      <legend class="sr-only">Experiment setup</legend>
      <div class="fields">
        <label><span data-measure>Participant</span><input id="participant" name="participant" maxlength="128" required spellcheck="false"></label>
        <label><span data-measure>Session</span><input id="session" name="session" maxlength="128" required spellcheck="false"></label>
      </div>
      <section aria-label="Breathing input">
        <h2 data-measure>Breathing input</h2>
        <p id="accepted" data-measure>No input accepted.</p>
        <details id="input-details"><summary data-measure>LSL input / marker name</summary>
          <p id="source-identity" data-measure>Select VernierRaw with raw Force in newtons.</p>
          <div class="actions">
            <button id="scan" type="button" data-measure>Scan streams</button>
            <button id="use" type="button" disabled data-measure>Use stream</button>
          </div>
          <div id="streams" role="radiogroup" aria-label="Available LSL streams"></div>
          <p id="omitted-streams" hidden data-measure></p>
          <div class="marker-options">
            <label><span data-measure>Marker LSL name (before recording)</span><input id="marker_name" maxlength="128" spellcheck="false"></label>
            <button id="rename" type="button" data-measure>Apply name</button>
          </div>
        </details>
      </section>
      <label class="check-option"><input id="save_csv" type="checkbox"><span data-measure>Save original CSV files locally</span></label>
      <p class="recording-note" data-measure>Start automatically records all LSL streams to XDF before calibration, including streams that appear later.</p>
      <div class="actions final-actions">
        <button id="start" type="submit" disabled data-measure>Start Experiment</button>
        <button id="cancel" type="button" data-measure>Cancel</button>
      </div>
    </fieldset>
  </form>
  <section id="observation" aria-label="Experiment monitoring">
    <h2 data-measure>Experiment status</h2>
    <dl class="progress">
      <dt data-measure>XDF recording</dt><dd id="xdf-state" data-measure>Ready</dd>
      <dt data-measure>Progress</dt><dd><span id="phase" data-measure>Starting</span> <span id="trial-summary" data-measure></span><span id="phase-summary" data-measure></span></dd>
      <dt data-measure>Force signal</dt><dd id="signal-state" data-measure>Not selected</dd>
      <dt data-measure>Markers</dt><dd id="marker-state" data-measure>Starting</dd>
      <dt data-measure>Events sent</dt><dd id="sequence" data-measure>0</dd>
      <dt data-measure>Latest event</dt><dd id="event" data-measure>—</dd>
    </dl>
    <div class="actions">
      <button id="abort" type="button" hidden data-measure>Stop experiment</button>
      <button id="close" type="button" hidden data-measure>Close</button>
    </div>
    <details class="diagnostics"><summary data-measure>Recent markers and details</summary>
      <dl class="progress">
        <dt data-measure>Marker stream</dt><dd id="marker-identity" data-measure>—</dd>
        <dt data-measure>Marker LSL time</dt><dd id="lsl-time" data-measure>—</dd>
        <dt data-measure>Last Force sample</dt><dd id="sample-age" data-measure>—</dd>
        <dt data-measure>Belt battery</dt><dd id="battery" data-measure>Not reported</dd>
      </dl>
      <ol id="recent-markers"></ol>
      <p data-measure>Last 12 events only. Sent events and a live outlet do not prove recording. Force status reflects sample reception; battery is not provided by this stream.</p>
    </details>
  </section>`;

const phases = { starting: 'Starting', setup: 'Setup',
  experiment: 'Running', finished: 'Finished', error: 'Needs attention' };

export function mountController(root, send, onReady) {
  root.innerHTML = CONTROL_HTML;
  const byId = id => root.querySelector('#' + id);
  const monitor = mountLslMonitor(root);
  let state = { phase: 'starting' }, progress = {}, enabled = true, ready = false;
  let operation = 0, streamSignature = '', recentSignature = '';
  const edits = new Map();

  function availability() {
    const setup = state.phase === 'setup';
    byId('setup').hidden = !setup;
    byId('controls').disabled = !enabled || !setup || operation > 0;
    byId('scan').disabled = !!state.busy;
    byId('use').disabled = !state.can_use;
    byId('start').disabled = !state.can_start;
    byId('abort').hidden = state.phase !== 'experiment';
    byId('abort').disabled = !enabled || operation > 0 || progress.recording?.phase === 'finalizing';
    byId('close').hidden = !['finished', 'error'].includes(state.phase);
    byId('close').disabled = !enabled || operation > 0 || ['preparing','recording','finalizing'].includes(progress.recording?.phase);
    for (const radio of byId('streams').querySelectorAll('input')) radio.disabled = !!state.busy;
  }

  async function request(action, fields = {}) {
    const discrete = !['field_key', 'field_edit', 'shown'].includes(action);
    if (!enabled) return;
    if (discrete) operation += 1;
    if (action === 'field_edit') edits.set(fields.field, fields.value);
    byId('command-status').textContent = discrete ? 'Waiting for the experiment engine…' : '';
    availability();
    try {
      const result = await send(action, fields);
      if (result?.ok === false) {
        byId('command-status').textContent = result.message || result.error || 'Command rejected. Review the current controls.';
      } else if (discrete && result?.ok === true) byId('command-status').textContent = 'Applied by Respyra.';
    } finally {
      if (discrete) operation -= 1;
      if (action === 'field_edit' && edits.get(fields.field) === fields.value) edits.delete(fields.field);
      render(state);
    }
  }

  function render(snapshot) {
    state = snapshot;
    root.dataset.phase = snapshot.phase;
    progress = snapshot.progress || progress;
    byId('status').textContent = snapshot.message === 'Ready for this experiment.' ? '' : snapshot.message || '';
    byId('phase').textContent = phases[snapshot.phase] || 'Needs attention';
    byId('trial-summary').textContent = [progress.trial == null ? null : ' · Trial ' + progress.trial, progress.condition].filter(v => v !== null && v !== undefined).join(' · ');
    byId('phase-summary').textContent = [progress.experiment_phase, progress.screen].filter(Boolean).join(' · ') || '—';
    const health = progress.health;
    monitor.render(progress, enabled);
    byId('xdf-state').textContent = {idle:'Ready',preparing:'Preparing',recording:'Recording',finalizing:'Finalizing',complete:'Saved',error:'Failed'}[progress.recording?.phase] || 'Ready';
    byId('signal-state').textContent = { not_selected:'Not selected', live:'Live', stale:'Waiting for samples',
      lost:'Signal lost', disconnected:'Disconnected' }[health?.signal] || 'Not reported';
    byId('sample-age').textContent = health?.sample_age_ms == null ? '—' : (health.sample_age_ms / 1000).toFixed(1) + ' s ago';
    byId('battery').textContent = health?.battery_percent == null ? 'Not reported' : health.battery_percent + '%';
    byId('signal-state').dataset.live = String(health?.signal === 'live');
    byId('marker-state').textContent = progress.markers?.online ? progress.markers.name + ' · Online' : 'Starting';
    byId('marker-state').dataset.live = String(!!progress.markers?.online);
    byId('marker-identity').textContent = progress.markers ? progress.markers.name + '\n' + progress.markers.source_id : '—';
    const recent = JSON.stringify(progress.recent || []);
    if (recent !== recentSignature) {
      recentSignature = recent;
      byId('recent-markers').replaceChildren(...(progress.recent || []).map(marker => {
        const item = document.createElement('li'); item.dataset.measure = '';
        item.textContent = marker.seq + ' · ' + marker.event; return item;
      }));
    }
    for (const [id,key] of [['event','event'],['sequence','seq'],['lsl-time','lsl_time']]) byId(id).textContent = progress[key] == null ? '—' : String(progress[key]);
    byId('sequence').textContent = String(progress.markers?.emitted ?? progress.seq ?? 0);
    if (snapshot.phase === 'setup' && snapshot.values) {
      for (const field of ['participant','session']) {
        if (!edits.has(field) && byId(field).value !== snapshot.values[field]) byId(field).value = snapshot.values[field];
      }
      byId('save_csv').checked = !!snapshot.save_csv;
      if (document.activeElement !== byId('marker_name')) byId('marker_name').value = snapshot.marker_name || 'Respyra-Events';
      byId('accepted').textContent = snapshot.source ? 'Accepted: ' + snapshot.source.stream_name : 'No input accepted.';
      byId('source-identity').textContent = snapshot.source ? snapshot.source.source_id : 'Select VernierRaw with raw Force in newtons.';
      const streams = snapshot.streams || [];
      const signature = JSON.stringify(streams);
      if (signature !== streamSignature) {
        streamSignature = signature;
        byId('streams').replaceChildren(...streams.map((stream, index) => {
          const row = stream.row ?? index;
          const label = document.createElement('label'); label.className = 'stream';
          const radio = document.createElement('input');
          radio.type = 'radio'; radio.name = 'source'; radio.value = String(row);
          radio.addEventListener('change', () => { void request('select', { row }); });
          const details = document.createElement('span'); details.className = 'details';
          for (const [className, text] of [['name',stream.stream_name],
            ['identity',stream.stream_type + ' · ' + stream.source_id],
            ['compatibility',stream.compatible ? stream.reason + ' · channel ' + (stream.force_channel_index + 1) : stream.reason]]) {
            const line = document.createElement('span');
            line.className = className; line.dataset.measure = ''; line.textContent = text;
            details.append(line);
          }
          label.append(radio, details);
          return label;
        }));
      }
      for (const radio of byId('streams').querySelectorAll('input')) radio.checked = Number(radio.value) === snapshot.selected_row;
      byId('omitted-streams').hidden = !snapshot.omitted_streams;
      byId('omitted-streams').textContent = (snapshot.omitted_streams || 0) + ' additional streams exceed the phone display limit. Use the local controller to select them.';
      if (!ready) {
        ready = true;
        onReady?.();
      }
    }
    availability();
  }

  for (const field of ['participant','session']) {
    const input = byId(field);
    input.addEventListener('keydown', event => { void request('field_key', { field, key:event.key }); });
    input.addEventListener('input', () => { void request('field_edit', { field, value:input.value }); });
  }
  for (const action of ['scan','use','cancel','abort','close']) byId(action).addEventListener('click', () => { void request(action); });
  byId('use').addEventListener('click', () => { byId('input-details').open = false; });
  byId('save_csv').addEventListener('change', () => { void request('option', {field:'save_csv',enabled:byId('save_csv').checked}); });
  byId('rename').addEventListener('click', () => { void request('field_edit', {field:'marker_name',value:byId('marker_name').value}); });
  byId('setup').addEventListener('submit', event => {
    event.preventDefault();
    if (!byId('start').disabled && !byId('controls').disabled) void request('start');
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !byId('controls').disabled) void request('cancel');
  });
  availability();
  return { render, setEnabled(value) { enabled = value; monitor.render(progress, enabled); availability(); },
    clearMonitor() { monitor.clear(); },
    fail(message) { enabled = false; monitor.render(progress, false); byId('command-status').textContent = message; availability(); } };
}
