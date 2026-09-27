// Shared presentation and intents. Python decides whether an action is valid.
export const CONTROL_HTML = `
  <p id="status" role="status" aria-live="polite" data-measure>Waiting for the experiment engine…</p>
  <p id="command-status" role="status" aria-live="polite" data-measure></p>
  <form id="setup" autocomplete="off">
    <fieldset id="controls" disabled>
      <legend class="sr-only">Experiment setup</legend>
      <div class="fields">
        <label><span data-measure>Participant</span><input id="participant" name="participant" maxlength="128" required spellcheck="false"></label>
        <label><span data-measure>Session</span><input id="session" name="session" maxlength="128" required spellcheck="false"></label>
      </div>
      <section aria-label="Breathing input">
        <h2 data-measure>Breathing input</h2>
        <p data-measure>Select a VernierRaw stream with the raw Force channel in newtons.</p>
        <p id="accepted" data-measure>No input accepted.</p>
        <div class="actions">
          <button id="scan" type="button" data-measure>Add LSL Stream</button>
          <button id="use" type="button" disabled data-measure>Use Selected Stream</button>
        </div>
        <div id="streams" role="radiogroup" aria-label="Available LSL streams"></div>
        <p id="omitted-streams" hidden data-measure></p>
      </section>
      <p class="recording-note" data-measure>The LSL recorder records the breathing signal and Respyra events. Keep it recording through the final Close.</p>
      <div class="actions final-actions">
        <button id="start" type="submit" disabled data-measure>Start Experiment</button>
        <button id="cancel" type="button" data-measure>Cancel</button>
      </div>
    </fieldset>
  </form>
  <section id="observation" aria-label="Experiment monitoring">
    <h2 data-measure>Experiment monitor</h2>
    <dl class="progress">
      <dt data-measure>Status</dt><dd id="phase" data-measure>Starting</dd>
      <dt data-measure>Trial</dt><dd id="trial-summary" data-measure>—</dd>
      <dt data-measure>Phase / screen</dt><dd id="phase-summary" data-measure>—</dd>
      <dt data-measure>Force signal</dt><dd id="signal-state" data-measure>Not selected</dd>
      <dt data-measure>Last sample</dt><dd id="sample-age" data-measure>—</dd>
      <dt data-measure>Belt battery</dt><dd id="battery" data-measure>Not reported</dd>
    </dl>
    <p data-measure>Signal status reflects received LSL Force samples. Battery telemetry is unavailable from the current raw Force stream.</p>
    <div class="actions">
      <button id="abort" type="button" hidden data-measure>Stop experiment</button>
      <button id="close" type="button" hidden data-measure>Close</button>
    </div>
    <details class="diagnostics"><summary data-measure>Event details</summary>
      <dl class="progress">
        <dt data-measure>Latest event</dt><dd id="event" data-measure>—</dd>
        <dt data-measure>Marker sequence</dt><dd id="sequence" data-measure>—</dd>
        <dt data-measure>Marker LSL time</dt><dd id="lsl-time" data-measure>—</dd>
      </dl>
    </details>
  </section>`;

const phases = { starting: 'Starting', waiting_recorder: 'Waiting for recorder', setup: 'Setup',
  experiment: 'Running', finished: 'Finished', error: 'Needs attention' };

export function mountController(root, send, onReady) {
  root.innerHTML = CONTROL_HTML;
  const byId = id => root.querySelector('#' + id);
  let state = { phase: 'starting' }, progress = {}, enabled = true, ready = false;
  let operation = 0, streamSignature = '';
  const edits = new Map();

  function availability() {
    const setup = state.phase === 'setup';
    byId('setup').hidden = !setup;
    byId('controls').disabled = !enabled || !setup || operation > 0;
    byId('scan').disabled = !!state.busy;
    byId('use').disabled = !state.can_use;
    byId('start').disabled = !state.can_start;
    byId('abort').hidden = state.phase !== 'experiment';
    byId('abort').disabled = !enabled || operation > 0;
    byId('close').hidden = !['finished', 'error'].includes(state.phase);
    byId('close').disabled = !enabled || operation > 0;
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
      } else if (discrete && result?.ok === true) byId('command-status').textContent = 'Command accepted by the experiment engine.';
    } finally {
      if (discrete) operation -= 1;
      if (action === 'field_edit' && edits.get(fields.field) === fields.value) edits.delete(fields.field);
      render(state);
    }
  }

  function render(snapshot) {
    state = snapshot;
    progress = snapshot.progress || progress;
    byId('status').textContent = snapshot.message || '';
    byId('phase').textContent = phases[snapshot.phase] || 'Needs attention';
    byId('trial-summary').textContent = [progress.trial, progress.condition].filter(v => v !== null && v !== undefined).join(' · ') || '—';
    byId('phase-summary').textContent = [progress.experiment_phase, progress.screen].filter(Boolean).join(' · ') || '—';
    const health = progress.health;
    byId('signal-state').textContent = { not_selected:'Not selected', live:'Live', stale:'Waiting for samples',
      lost:'Signal lost', disconnected:'Disconnected' }[health?.signal] || 'Not reported';
    byId('sample-age').textContent = health?.sample_age_ms == null ? '—' : (health.sample_age_ms / 1000).toFixed(1) + ' s ago';
    byId('battery').textContent = health?.battery_percent == null ? 'Not reported' : health.battery_percent + '%';
    for (const [id,key] of [['event','event'],['sequence','seq'],['lsl-time','lsl_time']]) byId(id).textContent = progress[key] == null ? '—' : String(progress[key]);
    if (snapshot.phase === 'setup' && snapshot.values) {
      for (const field of ['participant','session']) {
        if (!edits.has(field) && byId(field).value !== snapshot.values[field]) byId(field).value = snapshot.values[field];
      }
      byId('accepted').textContent = snapshot.source ? 'Accepted: ' + snapshot.source.stream_name + '\n' + snapshot.source.source_id : 'No input accepted.';
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
  byId('setup').addEventListener('submit', event => {
    event.preventDefault();
    if (!byId('start').disabled && !byId('controls').disabled) void request('start');
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !byId('controls').disabled) void request('cancel');
  });
  availability();
  return { render, setEnabled(value) { enabled = value; availability(); },
    fail(message) { enabled = false; byId('command-status').textContent = message; availability(); } };
}
