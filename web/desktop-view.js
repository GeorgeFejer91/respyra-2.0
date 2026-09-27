// Three parts: study inputs, all-stream preview, and the experiment action.
import { traceGeometry } from './lsl-monitor.js';
const main = document.querySelector('main');
const notice = document.querySelector('#viewport-notice');
const dialogs = [];
let fitPending = false;
let channelPageSize = 4, streamPageSize = 6;
function checkViewport() {
  if (fitPending) return;
  fitPending = true;
  requestAnimationFrame(() => {
    fitPending = false;
    main.hidden = false;
    while (main.getBoundingClientRect().bottom > innerHeight + 1 && (channelPageSize > 1 || streamPageSize > 1)) {
      channelPageSize = Math.max(1, channelPageSize - 1);
      streamPageSize = Math.max(1, streamPageSize - 1);
      paginate('channel-stack', 'Channels', channelPageSize);
      paginate('available-streams', 'Streams', streamPageSize);
    }
    const fits = main.getBoundingClientRect().bottom <= innerHeight + 1 && main.scrollWidth <= innerWidth + 1;
    main.hidden = !fits;
    notice.hidden = fits;
    for (const { dialog, content, message } of dialogs) {
      if (!dialog.open) continue;
      content.hidden = false;
      message.hidden = true;
      const bounds = dialog.getBoundingClientRect();
      const fits = bounds.height <= innerHeight - 24 && bounds.width <= innerWidth - 24;
      content.hidden = !fits;
      message.hidden = fits;
    }
  });
}
window.addEventListener('resize', () => {
  channelPageSize = 4; streamPageSize = 6;
  paginate('channel-stack', 'Channels', channelPageSize);
  paginate('available-streams', 'Streams', streamPageSize);
  checkViewport();
});
export function mountDesktop() {
  const root = document.querySelector('#controller');
  document.querySelector('#input-details').open = true;
  const settings = document.createElement('details');
  settings.id = 'input-settings';
  const settingsTitle = document.createElement('summary');
  settingsTitle.dataset.measure = ''; settingsTitle.textContent = 'Settings';
  document.querySelector('#controls').append(settings);
  settings.append(settingsTitle, document.querySelector('#controls > section'), document.querySelector('#save_csv').closest('label'));
  const observation = document.querySelector('#observation');
  settings.append(observation.querySelector('.diagnostics'));
  const actions = document.createElement('div'); actions.className = 'actions';
  actions.append(...document.querySelector('.final-actions').children, ...observation.querySelector('.actions').children);
  actions.querySelector('#start').setAttribute('form', 'setup');
  document.querySelector('.final-actions').remove();
  observation.querySelector('.actions').remove();
  const footer = document.createElement('footer'); footer.id = 'action-bar';
  footer.append(document.querySelector('#recording-panel'), observation, actions);
  root.append(footer);
  document.querySelector('#lsl-monitor').hidden = true;
  const overview = document.createElement('section'); overview.id = 'stream-overview';
  overview.setAttribute('aria-label', 'All available LSL streams and channels');
  overview.innerHTML = `<div class="stream-heading"><h2 data-measure>All LSL streams</h2><span data-measure>Record all · includes new streams</span></div>
    <div class="readiness" aria-label="Automatic checks"><span id="raw-check" data-measure>Breathing: waiting</span><span id="markers-check" data-measure>Markers: starting</span><span id="calibration-check" data-measure>Calibration: waiting</span></div>
    <p id="viewer-error" role="status" data-measure></p>
    <div class="stream-display"><div><div id="available-streams" aria-label="Streams included automatically"></div></div>
    <div><div id="channel-stack" aria-label="Live channel previews"></div></div></div>
    <p class="preview-note" data-measure>Last 10 seconds · live preview</p>`;
  root.append(overview);
  document.querySelector('header').append(document.querySelector('.viewer-setup'));
  for (const details of [settings, ...document.querySelectorAll('#recording-details, .diagnostics')]) {
    const summary = details.querySelector('summary');
    const dialog = document.createElement('dialog');
    dialog.setAttribute('aria-label', summary.textContent);
    const content = document.createElement('div');
    const message = document.createElement('p');
    message.dataset.measure = '';
    message.textContent = 'These details need more room. Enlarge the window.';
    message.hidden = true;
    const close = document.createElement('button');
    close.type = 'button'; close.textContent = 'Done'; close.dataset.measure = '';
    close.onclick = () => dialog.close();
    content.append(...[...details.children].filter(child => child !== summary));
    dialog.append(message, content, close);
    root.append(dialog);
    summary.onclick = event => { event.preventDefault(); dialog.showModal(); window.dispatchEvent(new Event('resize')); };
    dialog.addEventListener('close', () => window.dispatchEvent(new Event('resize')));
    dialogs.push({ dialog, content, message });
    new MutationObserver(records => {
      if (records.some(record => record.target !== content)) checkViewport();
    }).observe(content, { childList:true, subtree:true, characterData:true, attributes:true, attributeFilter:['hidden'] });
  }
  const remoteDialog = document.querySelector('#viewer-dialog');
  // The remote popup keeps a usable close button when a window is too small.
  const remoteContent = document.createElement('div');
  remoteContent.append(...remoteDialog.querySelectorAll(':scope > h2, :scope > section'));
  const message = document.createElement('p'); message.hidden = true; message.dataset.measure = '';
  message.textContent = 'Remote controls need more room. Enlarge the window.';
  remoteDialog.prepend(message, remoteContent);
  dialogs.push({ dialog:remoteDialog, content:remoteContent, message });
  new MutationObserver(checkViewport).observe(remoteContent, { childList:true, subtree:true, characterData:true, attributes:true, attributeFilter:['hidden'] });
  remoteDialog.addEventListener('close', () => window.dispatchEvent(new Event('resize')));
  checkViewport();
}

const pagers = new Map();
export function renderRecording(recording = {}, progress = {}) {
  const phase = {idle:'Ready to record all streams', preparing:'Checking streams and recorder…', recording:'Recording',
    finalizing:'Finalizing XDF', complete:'XDF saved', error:'Recording failed'}[recording.phase || 'idle'];
  document.querySelector('#recording-status').textContent = recording.error || `${phase}${recording.bytes_written ? ' · ' + recording.bytes_written + ' bytes' : ''}`;
  document.querySelector('#recording-file').textContent = recording.output_file || 'Start records all visible LSL streams, including streams that appear later.';
  const list = document.querySelector('#recorded-streams');
  const rows = recording.streams || [];
  const signature = JSON.stringify(rows);
  if (list.dataset.rows !== signature) {
    list.dataset.rows = signature;
    list.replaceChildren(...rows.map(stream => {
      const row = document.createElement('li'); row.dataset.measure = '';
      row.textContent = `${stream.name}\n${stream.source_id}`; return row;
    }));
  }
  paginate('recorded-streams', 'Stream');
  renderStreams(progress);
  checkViewport();
}
document.querySelector('#controller').addEventListener('click', event => {
  if (event.target.id === 'scan' && pagers.has('streams')) pagers.get('streams').index = 0;
}, true);
function paginate(id, label, size = 1) {
  const list = document.getElementById(id);
  if (!list) return;
  let pager = pagers.get(id);
  if (!pager) {
    const bar = document.createElement('div'); bar.className = 'actions page-actions';
    const previous = document.createElement('button'); previous.type = 'button'; previous.textContent = 'Previous'; previous.dataset.measure = '';
    const count = document.createElement('span'); count.dataset.measure = ''; count.setAttribute('aria-live', 'polite');
    const next = document.createElement('button'); next.type = 'button'; next.textContent = 'Next'; next.dataset.measure = '';
    bar.append(previous, count, next); list.after(bar);
    pager = { index: 0, bar, previous, count, next }; pagers.set(id, pager);
  }
  function update() {
    const rows = [...list.children];
    const pages = Math.ceil(rows.length / size);
    pager.index = Math.max(0, Math.min(pager.index, pages - 1));
    rows.forEach((row, index) => { row.hidden = Math.floor(index / size) !== pager.index; });
    pager.bar.hidden = pages < 2;
    pager.previous.disabled = pager.index === 0;
    pager.next.disabled = pager.index >= pages - 1;
    const text = size === 1 ? `${label} ${pager.index + 1} / ${rows.length}` : `${label} ${pager.index * size + 1}–${Math.min((pager.index + 1) * size, rows.length)} / ${rows.length}`;
    if (pager.count.textContent !== text) pager.count.textContent = text;
    checkViewport();
  }
  pager.previous.onclick = () => { pager.index--; update(); };
  pager.next.onclick = () => { pager.index++; update(); };
  update();
}

const traces = new Map();
function renderStreams(progress) {
  const recording = progress.recording || {}, received = new Set(recording.data_sources || []);
  const health = progress.health || {}, marker = progress.markers;
  const recorded = identity => received.has(identity);
  const receiptStatus = recording.phase === 'complete' ? 'saved' : recording.phase === 'error' ? 'received' : 'recording';
  const checks = [
    ['raw-check', 'Breathing', health.signal === 'live' ? 'live' : 'waiting', health.signal === 'live'],
    ['markers-check', 'Markers', recorded(marker?.source_id) ? receiptStatus : marker?.online ? 'ready' : 'starting', !!marker?.online],
    ['calibration-check', 'Calibration', recorded(health.calibrated?.source_id) ? receiptStatus : health.calibrated?.active ? 'checking' : 'waiting', recorded(health.calibrated?.source_id)]
  ];
  for (const [id, label, status, live] of checks) {
    const element = document.getElementById(id);
    element.textContent = `${label}: ${status}`; element.dataset.live = String(live);
  }
  document.getElementById('viewer-error').textContent = progress.viewer_error || '';
  const rows = [...(progress.streams || [])];
  if (marker) rows.push({uid: marker.source_id || marker.name, source_id: marker.source_id, name: marker.name, type:'Markers',
    numeric:false, signal:marker.online ? 'live' : 'lost', lsl_time:progress.lsl_time,
    channels:[{index:0,label:'Events',unit:'',value:progress.event || 'Waiting for events'}]});
  const checklist = document.getElementById('available-streams'), stack = document.getElementById('channel-stack');
  const signature = JSON.stringify(rows.map(row => [row.uid,row.name,row.channels.map(c=>[c.index,c.label,c.unit])]));
  if (checklist.dataset.rows !== signature) {
    checklist.dataset.rows = signature;
    checklist.replaceChildren(); stack.replaceChildren();
    const keys = new Set();
    for (const row of rows) {
      const label = document.createElement('label'); label.className = 'included-stream'; label.dataset.uid = row.uid;
      const check = document.createElement('input'); check.type = 'checkbox'; check.checked = true; check.disabled = true;
      check.setAttribute('aria-label', `${row.name} included automatically`);
      const name = document.createElement('span'); name.dataset.measure = ''; name.textContent = row.name;
      label.title = `${row.type}\n${row.source_id || 'No source ID'}\n${row.uid}`;
      label.append(check,name); checklist.append(label);
      for (const channel of row.channels) {
        const key = `${row.uid}:${channel.index}`; keys.add(key);
        const trace = document.createElement('section'); trace.className = 'channel-trace'; trace.dataset.key = key;
        const heading = document.createElement('div'); heading.className = 'channel-heading';
        const name = document.createElement('span'); name.dataset.measure = ''; name.textContent = `${row.name} · ${channel.label}${channel.unit ? ' (' + channel.unit + ')' : ''}`;
        const value = document.createElement('span'); value.className = 'channel-value'; value.dataset.measure = '';
        heading.append(name,value); trace.append(heading);
        if (row.numeric) {
          const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
          svg.setAttribute('viewBox','0 0 600 140'); svg.setAttribute('preserveAspectRatio','none'); svg.setAttribute('role','img'); svg.setAttribute('aria-label', `${channel.label} live preview`);
          for (const className of ['trace-grid','trace-markers','trace-line']) {
            const path = document.createElementNS(svg.namespaceURI,'path'); path.setAttribute('class',className);
            if (className === 'trace-grid') path.setAttribute('d','M0 70H600'); svg.append(path);
          }
          trace.append(svg);
        } else {
          const text = document.createElement('p'); text.className = 'channel-event'; text.dataset.measure = ''; trace.append(text);
        }
        stack.append(trace);
      }
    }
    for (const key of traces.keys()) if (!keys.has(key)) traces.delete(key);
  }
  const streamElements = [...checklist.children], channelElements = [...stack.children];
  for (const row of rows) {
    const label = streamElements.find(element => element.dataset.uid === row.uid);
    label.dataset.live = String(row.signal === 'live');
    for (const channel of row.channels) {
      const key = `${row.uid}:${channel.index}`, element = channelElements.find(element => element.dataset.key === key);
      const points = traces.get(key) || [];
      if (row.numeric && Number.isFinite(channel.value) && Number.isFinite(row.lsl_time) && row.lsl_time > (points.at(-1)?.[0] ?? -Infinity)) points.push([row.lsl_time,channel.value]);
      while (points.length && (points[0][0] < row.lsl_time - 10 || points.length > 100)) points.shift();
      traces.set(key,points);
      element.querySelector('.channel-value').textContent = row.signal === 'live' ? row.numeric ? Number.isFinite(channel.value) ? channel.value.toFixed(3) : 'waiting' : 'events' : row.signal;
      if (row.numeric) {
        const geometry = traceGeometry(points);
        element.querySelector('.trace-line').setAttribute('d',geometry.path);
        element.querySelector('.trace-markers').setAttribute('d',(progress.recent || []).filter(marker=>marker.lsl_time >= geometry.start && marker.lsl_time <= geometry.end)
          .map(marker=>`M${((marker.lsl_time-geometry.start)*60).toFixed(2)},0V140`).join(' '));
      } else {
        let text = channel.value || 'Waiting for events';
        try { text = JSON.parse(text).event || text; } catch { /* Ordinary marker strings are valid. */ }
        element.querySelector('.channel-event').textContent = text;
      }
    }
  }
  if (!rows.length) {
    const empty = document.createElement('p'); empty.dataset.measure = ''; empty.textContent = 'Finding LSL streams…'; checklist.replaceChildren(empty);
  }
  paginate('available-streams','Streams',streamPageSize);
  paginate('channel-stack','Channels',channelPageSize);
}
new MutationObserver(() => {
  paginate('streams', 'Stream');
  paginate('recent-markers', 'Event');
  checkViewport();
}).observe(document.querySelector('#controller'), { childList: true, subtree: true, characterData: true });
document.fonts.ready.then(checkViewport);
