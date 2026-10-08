// Three parts: study inputs, all-stream preview, and the experiment action.
import { traceGeometry } from './lsl-monitor.js';
import { EVENT_MARKERS } from './marker-catalog.js';
const main = document.querySelector('main');
const notice = document.querySelector('#viewport-notice');
const dialogs = [];
let fitPending = false;
let channelPageSize = 4, streamPageSize = 3, markerPageSize = 4;
function checkViewport() {
  if (fitPending) return;
  fitPending = true;
  requestAnimationFrame(() => {
    fitPending = false;
    main.hidden = false;
    while (main.getBoundingClientRect().bottom > innerHeight + 1 && (channelPageSize > 1 || streamPageSize > 1 || markerPageSize > 1)) {
      channelPageSize = Math.max(1, channelPageSize - 1);
      streamPageSize = Math.max(1, streamPageSize - 1);
      markerPageSize = Math.max(1, markerPageSize - 1);
      paginate('channel-stack', 'Channels', channelPageSize);
      paginate('available-streams', 'Streams', streamPageSize);
      paginate('marker-list', 'Markers', markerPageSize);
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
  channelPageSize = 4; streamPageSize = 3; markerPageSize = 4;
  paginate('channel-stack', 'Channels', channelPageSize);
  paginate('available-streams', 'Streams', streamPageSize);
  paginate('marker-list', 'Markers', markerPageSize);
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
  settings.append(settingsTitle, document.querySelector('#controls > section[aria-label="Breathing input"]'));
  const observation = document.querySelector('#observation');
  settings.append(observation.querySelector('.diagnostics'));
  const actions = document.createElement('div'); actions.className = 'actions';
  actions.append(...document.querySelector('.final-actions').children, ...document.querySelector('#run-controls .actions').children);
  actions.querySelector('#start').setAttribute('form', 'setup');
  document.querySelector('.final-actions').remove();
  document.querySelector('#run-controls').remove();
  const footer = document.createElement('footer'); footer.id = 'action-bar';
  footer.append(document.querySelector('#recording-panel'), observation, actions);
  root.append(footer);
  document.querySelector('#lsl-monitor').hidden = true;
  const overview = document.createElement('section'); overview.id = 'stream-overview';
  overview.setAttribute('aria-label', 'All available LSL streams and channels');
  overview.innerHTML = `<div class="stream-heading"><h2 data-measure>Recording preview</h2><span data-measure>Records all streams, including new ones</span></div>
    <div class="readiness" aria-label="Automatic checks"><span id="raw-check" data-measure>Breathing: waiting</span><span id="markers-check" data-measure>Markers: starting</span><span id="calibration-check" data-measure>Calibration: waiting</span></div>
    <p id="viewer-error" role="status" data-measure></p>
    <div class="stream-tabs" role="tablist" aria-label="Recording information">
      <button type="button" role="tab" id="tab-all" data-preview="all" aria-controls="plot-panel" aria-selected="true" data-measure>All channels</button>
      <div id="available-streams" role="presentation"></div>
      <button type="button" role="tab" id="tab-markers" data-preview="markers" aria-controls="marker-panel" aria-selected="false" data-measure>Event markers</button>
    </div>
    <div id="plot-panel" role="tabpanel" aria-labelledby="tab-all">
      <div class="plot-frame"><div id="channel-stack" aria-label="Live channel previews"></div>
        <svg id="marker-overlay" viewBox="0 0 600 100" preserveAspectRatio="none" role="img" aria-label="Event markers crossing the visible channels"></svg></div>
      <p id="preview-note" class="preview-note" data-measure>Last 10 seconds · live preview</p>
    </div>
    <div id="marker-panel" role="tabpanel" aria-labelledby="tab-markers" hidden>
      <label class="marker-search"><span data-measure>Find event marker</span><input id="marker-filter" type="search" autocomplete="off" spellcheck="false"></label>
      <div id="marker-list" aria-label="Program event markers"></div>
    </div>`;
  root.append(overview);
  overview.addEventListener('click', event => {
    const tab = event.target.closest('[role=tab]');
    if (tab) selectPreview(tab.dataset.preview);
  });
  overview.addEventListener('keydown', event => {
    if (event.target.getAttribute('role') !== 'tab') return;
    const tabs = [...overview.querySelectorAll('[role=tab]')].filter(tab => !tab.hidden);
    const index = tabs.indexOf(event.target);
    const next = ({ArrowRight: index + 1, ArrowDown: index + 1, ArrowLeft: index - 1,
      ArrowUp: index - 1, Home: 0, End: tabs.length - 1})[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const tab = tabs[(next + tabs.length) % tabs.length];
    selectPreview(tab.dataset.preview); tab.focus();
  });
  overview.querySelector('#marker-filter').addEventListener('input', renderCatalog);
  renderCatalog();
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
    bar.append(previous, count, next);
    if (id === 'channel-stack' || id === 'available-streams') list.parentElement.after(bar); else list.after(bar);
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
  const turnPage = step => {
    pager.index += step; update();
    if (id === 'available-streams' && activePreview.startsWith('stream:') &&
        ![...list.children].some(tab => tab.dataset.preview === activePreview && !tab.hidden)) selectPreview('all');
  };
  pager.previous.onclick = () => turnPage(-1);
  pager.next.onclick = () => turnPage(1);
  update();
}

const traces = new Map(), externalMarkerTimes = new Map();
const externalMarkers = [];
let activePreview = 'all', currentProgress = {};
const markerColors = {calibration:'#9a6700', trial:'#8250df', recording:'#b42332', input:'#176534', other:'#57606a'};
function markerGroup(event) {
  if (event.startsWith('calibration.')) return 'calibration';
  if (/^(trial|baseline|tracking|feedback|assessment|countdown)\./.test(event)) return 'trial';
  if (/^(recording|run|display)\./.test(event)) return 'recording';
  if (/^(input|participant|ui|source)\./.test(event)) return 'input';
  return 'other';
}
function renderCatalog() {
  const list = document.getElementById('marker-list');
  const query = document.getElementById('marker-filter').value.trim().toLowerCase();
  markerPageSize = 4;
  list.replaceChildren(...EVENT_MARKERS.filter(({name, when}) =>
    `${name} ${when || ''}`.toLowerCase().includes(query)).map(({name, when}) => {
    const row = document.createElement('div'); row.className = 'marker-definition';
    row.style.borderLeftColor = markerColors[markerGroup(name)];
    const title = document.createElement('strong'); title.dataset.measure = ''; title.textContent = name;
    const description = document.createElement('span'); description.dataset.measure = ''; description.textContent = when || '';
    row.append(title, description); return row;
  }));
  if (!list.childElementCount) {
    const empty = document.createElement('p'); empty.dataset.measure = ''; empty.textContent = 'No matching event markers.'; list.append(empty);
  }
  if (pagers.has('marker-list')) pagers.get('marker-list').index = 0;
  paginate('marker-list', 'Markers', markerPageSize);
  checkViewport();
}
function selectPreview(key) {
  activePreview = key;
  channelPageSize = 4; streamPageSize = 3; markerPageSize = 4;
  if (pagers.has('channel-stack')) pagers.get('channel-stack').index = 0;
  renderStreams(currentProgress);
  checkViewport();
}
function markerStream(row) { return /marker|event/i.test(row.type || '') && !row.numeric; }
function markerName(value) {
  try {
    const event = JSON.parse(value).event;
    return typeof event === 'string' && event ? event : String(value);
  } catch { return String(value); }
}
function renderStreams(progress) {
  currentProgress = progress;
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
  const all = progress.streams || [], rows = all.filter(row => !markerStream(row));
  const end = Math.max(...rows.map(row => Number.isFinite(row.lsl_time) ? row.lsl_time : -Infinity)) + .2;
  for (const row of all) {
    if (!markerStream(row)) continue;
    for (const channel of row.channels) {
      const key = `${row.uid}:${channel.index}`, time = row.lsl_time;
      if (!Number.isFinite(time) || !channel.value || time <= (externalMarkerTimes.get(key) ?? -Infinity)) continue;
      externalMarkerTimes.set(key, time);
      externalMarkers.push({event: markerName(channel.value), lsl_time: time});
    }
  }
  while (externalMarkers.length > 100 || (Number.isFinite(end) && externalMarkers[0]?.lsl_time < end - 10)) externalMarkers.shift();
  const keys = new Set();
  for (const row of rows) for (const channel of row.channels) {
    const key = `${row.uid}:${channel.index}`; keys.add(key);
    if (!row.numeric) continue;
    const points = traces.get(key) || [];
    if (Number.isFinite(channel.value) && Number.isFinite(row.lsl_time) && row.lsl_time > (points.at(-1)?.[0] ?? -Infinity)) points.push([row.lsl_time, channel.value]);
    while (points.length && (points.length > 100 || (Number.isFinite(end) && points[0][0] < end - 10))) points.shift();
    traces.set(key, points);
  }
  for (const key of traces.keys()) if (!keys.has(key)) traces.delete(key);

  const tabs = document.getElementById('available-streams');
  const tabSignature = JSON.stringify(rows.map(row => [row.uid, row.name]));
  if (tabs.dataset.rows !== tabSignature) {
    tabs.dataset.rows = tabSignature;
    tabs.replaceChildren(...rows.map(row => {
      const tab = document.createElement('button'); tab.type = 'button'; tab.setAttribute('role', 'tab');
      tab.dataset.preview = `stream:${row.uid}`; tab.dataset.uid = row.uid; tab.dataset.measure = '';
      tab.id = `tab-stream-${rows.indexOf(row)}`;
      tab.setAttribute('aria-controls', 'plot-panel'); tab.textContent = row.name;
      tab.title = `${row.type}\n${row.source_id || 'No source ID'}`;
      return tab;
    }));
  }
  if (activePreview.startsWith('stream:') && !rows.some(row => `stream:${row.uid}` === activePreview)) activePreview = 'all';
  for (const tab of document.querySelectorAll('.stream-tabs [role=tab]')) {
    tab.setAttribute('aria-selected', String(tab.dataset.preview === activePreview));
    tab.tabIndex = tab.dataset.preview === activePreview ? 0 : -1;
    if (tab.dataset.uid) tab.dataset.live = String(rows.find(row => row.uid === tab.dataset.uid)?.signal === 'live');
  }
  const markerPanel = document.getElementById('marker-panel'), plotPanel = document.getElementById('plot-panel');
  markerPanel.hidden = activePreview !== 'markers'; plotPanel.hidden = activePreview === 'markers';
  plotPanel.setAttribute('aria-labelledby', activePreview === 'all' || activePreview === 'markers' ? 'tab-all' :
    document.querySelector('.stream-tabs [aria-selected=true]')?.id || 'tab-all');

  const selected = activePreview === 'all' ? rows : rows.filter(row => `stream:${row.uid}` === activePreview);
  const stack = document.getElementById('channel-stack');
  const signature = JSON.stringify(selected.map(row => [row.uid, row.name, row.numeric, row.channels.map(c => [c.index,c.label,c.unit])]));
  if (stack.dataset.rows !== signature) {
    stack.dataset.rows = signature;
    if (pagers.has('channel-stack')) pagers.get('channel-stack').index = 0;
    stack.replaceChildren(...selected.flatMap(row => row.channels.map(channel => {
      const trace = document.createElement('div'); trace.className = 'channel-trace'; trace.dataset.key = `${row.uid}:${channel.index}`;
      const heading = document.createElement('div'); heading.className = 'channel-heading';
      const name = document.createElement('span'); name.dataset.measure = ''; name.textContent = `${row.name} · ${channel.label}${channel.unit ? ' (' + channel.unit + ')' : ''}`;
      const value = document.createElement('span'); value.className = 'channel-value'; value.dataset.measure = '';
      heading.append(name, value); trace.append(heading);
      if (row.numeric) {
        const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
        svg.setAttribute('viewBox','0 0 600 140'); svg.setAttribute('preserveAspectRatio','none');
        svg.setAttribute('role','img'); svg.setAttribute('aria-label', `${channel.label} live preview`);
        for (const className of ['trace-grid','trace-line']) {
          const path = document.createElementNS(svg.namespaceURI,'path'); path.setAttribute('class',className);
          if (className === 'trace-grid') path.setAttribute('d','M0 70H600'); svg.append(path);
        }
        trace.append(svg);
      } else {
        const text = document.createElement('p'); text.className = 'channel-event'; text.dataset.measure = ''; trace.append(text);
      }
      return trace;
    })));
    if (!stack.childElementCount) {
      const empty = document.createElement('p'); empty.dataset.measure = ''; empty.textContent = 'Finding LSL channels…'; stack.append(empty);
    }
  }
  for (const row of selected) for (const channel of row.channels) {
    const element = [...stack.children].find(child => child.dataset.key === `${row.uid}:${channel.index}`);
    element.querySelector('.channel-value').textContent = row.signal === 'live' ?
      row.numeric ? Number.isFinite(channel.value) ? channel.value.toFixed(3) : 'waiting' : 'text' : row.signal;
    if (row.numeric) element.querySelector('.trace-line').setAttribute('d', traceGeometry(traces.get(element.dataset.key) || [], end).path);
    else element.querySelector('.channel-event').textContent = channel.value || 'Waiting for data';
  }
  const overlay = document.getElementById('marker-overlay');
  const visibleMarkers = Number.isFinite(end) ? [...(progress.recent || []), ...externalMarkers]
    .filter(item => Number.isFinite(item.lsl_time) && item.lsl_time >= end - 10 && item.lsl_time <= end)
    .sort((a, b) => a.lsl_time - b.lsl_time) : [];
  overlay.replaceChildren(...visibleMarkers.map(item => {
    const line = document.createElementNS(overlay.namespaceURI, 'line');
    const x = ((item.lsl_time - (end - 10)) * 60).toFixed(2);
    line.setAttribute('x1', x); line.setAttribute('x2', x); line.setAttribute('y1', '0'); line.setAttribute('y2', '100');
    line.setAttribute('stroke', markerColors[markerGroup(item.event)]);
    line.setAttribute('stroke-width', '2'); line.setAttribute('vector-effect', 'non-scaling-stroke');
    const title = document.createElementNS(overlay.namespaceURI, 'title'); title.textContent = item.event; line.append(title);
    return line;
  }));
  document.getElementById('preview-note').textContent = visibleMarkers.length ?
    `Last 10 seconds · live preview · latest marker: ${visibleMarkers.at(-1).event}` : 'Last 10 seconds · live preview';
  paginate('available-streams', 'Streams', streamPageSize);
  paginate('channel-stack', 'Channels', channelPageSize);
}
new MutationObserver(() => {
  paginate('streams', 'Stream');
  paginate('recent-markers', 'Event');
  checkViewport();
}).observe(document.querySelector('#controller'), { childList: true, subtree: true, characterData: true });
document.fonts.ready.then(checkViewport);
