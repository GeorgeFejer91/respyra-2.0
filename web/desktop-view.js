// One experiment control center; optional configuration uses native HTML dialogs.
const main = document.querySelector('main');
const notice = document.querySelector('#viewport-notice');
const dialogs = [];
let fitPending = false;
function checkViewport() {
  if (fitPending) return;
  fitPending = true;
  requestAnimationFrame(() => {
    fitPending = false;
    main.hidden = false;
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
window.addEventListener('resize', checkViewport);
export function mountDesktop() {
  const root = document.querySelector('#controller');
  document.querySelector('#input-details').open = true;
  const options = document.querySelector('.marker-options');
  const settings = document.createElement('details');
  settings.id = 'input-settings';
  const settingsTitle = document.createElement('summary');
  settingsTitle.dataset.measure = ''; settingsTitle.textContent = 'Input and marker details';
  options.before(settings);
  settings.append(settingsTitle, document.querySelector('#source-identity'), options);
  const observation = document.querySelector('#observation');
  const actions = document.createElement('div'); actions.className = 'actions';
  actions.append(...document.querySelector('.final-actions').children, ...observation.querySelector('.actions').children);
  actions.querySelector('#start').setAttribute('form', 'setup');
  document.querySelector('.final-actions').remove();
  observation.querySelector('.actions').remove();
  const footer = document.createElement('footer'); footer.id = 'action-bar';
  footer.append(document.querySelector('#recording-panel'), actions);
  root.append(footer);
  document.querySelector('#lsl-monitor').append(observation);
  document.querySelector('header').append(document.querySelector('.viewer-setup'));
  for (const details of [settings, ...document.querySelectorAll('#recording-details, .diagnostics, .viewer-setup')]) {
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
  checkViewport();
}

const pagers = new Map();
export function renderRecording(recording = {}) {
  const phase = {idle:'XDF ready · Start records before calibration', preparing:'Preparing recording', recording:'Recording',
    finalizing:'Finalizing XDF', complete:'XDF saved', error:'Recording failed'}[recording.phase || 'idle'];
  document.querySelector('#recording-status').textContent = recording.error || `${phase} · ${recording.bytes_written || 0} bytes`;
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
  checkViewport();
}
document.querySelector('#controller').addEventListener('click', event => {
  if (event.target.id === 'scan' && pagers.has('streams')) pagers.get('streams').index = 0;
}, true);
function paginate(id, label) {
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
    previous.onclick = () => { pager.index--; update(); };
    next.onclick = () => { pager.index++; update(); };
  }
  function update() {
    const rows = [...list.children];
    pager.index = Math.max(0, Math.min(pager.index, rows.length - 1));
    rows.forEach((row, index) => { row.hidden = index !== pager.index; });
    pager.bar.hidden = rows.length < 2;
    pager.previous.disabled = pager.index === 0;
    pager.next.disabled = pager.index === rows.length - 1;
    const text = `${label} ${pager.index + 1} / ${rows.length}`;
    if (pager.count.textContent !== text) pager.count.textContent = text;
    checkViewport();
  }
  update();
}
new MutationObserver(() => {
  paginate('streams', 'Stream');
  paginate('recent-markers', 'Event');
  checkViewport();
}).observe(document.querySelector('#controller'), { childList: true, subtree: true, characterData: true });
document.fonts.ready.then(checkViewport);
