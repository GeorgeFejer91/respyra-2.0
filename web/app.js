import { actionQueue } from './action-queue.js';
import { measureTextRegions } from './text-fit.js';
import { mountRemoteViewer } from './remote-host.js';

const byId = id => document.getElementById(id);
const controls = byId('controls');
const status = byId('status');
let ready = false, leaving = false, operationSeq = 0, streamSignature = '';
const native = window.__TAURI__;

function fail(error) {
  leaving = true;
  controls.disabled = true;
  status.textContent = `Setup stopped: ${String(error)}`;
  byId('close').hidden = false;
  // Stop the engine immediately if reliable event delivery has failed.
  native?.core.invoke('close_app', { reason: 'protocol_failure' }).catch(() => {});
}

const send = actionQueue((command, args) => native.core.invoke(command, args), fail);

function render(snapshot) {
  if (leaving && snapshot.phase === 'setup') return;
  if (snapshot.phase === 'finished' || snapshot.phase === 'error') leaving = false;
  status.textContent = snapshot.message;
  const setup = snapshot.phase === 'setup';
  controls.disabled = !setup;
  byId('close').hidden = !['error', 'finished'].includes(snapshot.phase);
  if (!setup) return;
  byId('study').textContent = snapshot.study_name;
  if (!ready) {
    ready = true;
    for (const field of ['participant', 'session']) byId(field).value = snapshot.values[field];
    send('shown');
    byId('participant').focus();
  }
  const awaitingOperation = snapshot.ui_seq < operationSeq;
  byId('scan').disabled = snapshot.busy || awaitingOperation;
  byId('use').disabled = !snapshot.can_use || awaitingOperation;
  byId('start').disabled = !snapshot.can_start || awaitingOperation;
  byId('accepted').textContent = snapshot.source ? `Accepted: ${snapshot.source.stream_name}\n${snapshot.source.source_id}` : 'No input accepted.';
  const signature = JSON.stringify(snapshot.streams);
  if (signature !== streamSignature) {
    streamSignature = signature;
    byId('streams').replaceChildren(...snapshot.streams.map((stream, row) => {
      const label = document.createElement('label');
      label.className = 'stream';
      const radio = document.createElement('input');
      radio.type = 'radio'; radio.name = 'source'; radio.value = String(row);
      radio.addEventListener('change', () => send('select', { row }));
      const details = document.createElement('span'); details.className = 'details';
      for (const [className, text] of [
        ['name', stream.stream_name], ['identity', `${stream.stream_type} · ${stream.source_id}`],
        ['compatibility', stream.compatible ? `${stream.reason} · channel ${stream.force_channel_index + 1}` : stream.reason],
      ]) {
        const line = document.createElement('span');
        line.className = className; line.dataset.measure = ''; line.textContent = text;
        details.append(line);
      }
      label.append(radio, details);
      return label;
    }));
  }
  for (const radio of byId('streams').querySelectorAll('input')) {
    radio.disabled = snapshot.busy || awaitingOperation;
    // The backend may still be acknowledging an earlier action; keep local focus/selection.
    if (snapshot.ui_seq >= send.sequence) radio.checked = Number(radio.value) === snapshot.selected_row;
  }
}

for (const field of ['participant', 'session']) {
  const input = byId(field);
  input.addEventListener('keydown', event => send('field_key', { field, key: event.key }));
  input.addEventListener('input', () => send('field_edit', { field, value: input.value }));
}
function sourceAction(action) {
  byId('scan').disabled = true; byId('use').disabled = true; byId('start').disabled = true;
  for (const radio of byId('streams').querySelectorAll('input')) radio.disabled = true;
  send(action); operationSeq = send.sequence;
}
byId('scan').addEventListener('click', () => sourceAction('scan'));
byId('use').addEventListener('click', () => sourceAction('use'));
byId('setup').addEventListener('submit', event => {
  event.preventDefault();
  if (byId('start').disabled) return;
  leaving = true; controls.disabled = true;
  status.textContent = 'Starting PsychoPy…';
  send('start');
});
function cancel() {
  if (!ready || leaving) return;
  leaving = true; controls.disabled = true;
  status.textContent = 'Cancelling setup…';
  send('cancel');
}
byId('cancel').addEventListener('click', cancel);
document.addEventListener('keydown', event => { if (event.key === 'Escape' && ready && !controls.disabled) cancel(); });
byId('close').addEventListener('click', () => native.core.invoke('close_app', { reason: 'close_button' }).catch(fail));

measureTextRegions().catch(() => { document.documentElement.dataset.pretextFit = 'unavailable'; });
if (native) {
  mountRemoteViewer((command, args) => native.core.invoke(command, args));
  // Subscribe before starting the engine: no readiness/state event can be missed.
  await native.event.listen('setup-state', event => render(event.payload));
  await native.core.invoke('launch_backend').then(render).catch(fail);
} else {
  status.textContent = 'Open Respyra through the desktop launcher to connect to the experiment engine.';
}
