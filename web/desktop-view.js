// Secondary controls use the same screen space as setup, never a scrolling stack.
const picker = document.querySelector('#view');
const main = document.querySelector('main');
const notice = document.querySelector('#viewport-notice');
let fitPending = false;
function checkViewport() {
  if (fitPending) return;
  fitPending = true;
  requestAnimationFrame(() => {
    fitPending = false;
    main.hidden = false;
    main.querySelector('header').after(picker.closest('label'));
    const fits = main.getBoundingClientRect().bottom <= innerHeight + 1 && main.scrollWidth <= innerWidth + 1;
    const focusWasInMain = main.contains(document.activeElement);
    // A no-fit state is explicit; never hide a scrollbar or shrink enlarged text.
    main.hidden = !fits;
    notice.hidden = fits;
    if (!fits) {
      notice.prepend(picker.closest('label'));
      if (focusWasInMain) picker.focus();
    }
  });
}
window.addEventListener('resize', checkViewport);
document.addEventListener('toggle', checkViewport, true);
function show(view) {
  picker.value = view;
  document.body.dataset.view = view;
  const input = document.querySelector('#input-details');
  if (input) input.open = ['input', 'markers'].includes(view);
  window.dispatchEvent(new Event('resize'));
}
picker.addEventListener('change', () => show(picker.value));

const pagers = new Map();
export function renderRecording(recording = {}) {
  const phase = {idle:'Ready to record', preparing:'Preparing recording', recording:'Recording',
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
  if (event.target.id === 'use') show('setup');
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
let lastPhase;
new MutationObserver(() => {
  paginate('streams', 'Stream');
  paginate('recent-markers', 'Event');
  const phase = document.querySelector('#phase')?.textContent;
  if (phase && phase !== lastPhase) {
    lastPhase = phase;
    if (['Running', 'Finished', 'Needs attention'].includes(phase)) show('status');
  }
  checkViewport();
}).observe(document.querySelector('#controller'), { childList: true, subtree: true, characterData: true });
new MutationObserver(checkViewport).observe(document.querySelector('.viewer-setup'), { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ['hidden'] });
document.fonts.ready.then(checkViewport);
