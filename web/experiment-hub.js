import { measureTextRegions } from './text-fit.js';
import { actionQueue } from './action-queue.js';

    import { prepareWithSegments, measureLineStats, measureNaturalWidth, setLocale } from './vendor/pretext/layout.js';



    const $ = id => document.getElementById(id);
    const native = window.__TAURI__;
    if (native) {
      document.querySelector('.preview-note').hidden = true;
      const { mountRemoteViewer } = await import('./remote-host.js');
      mountRemoteViewer((command, args) => native.core.invoke(command, args));
    } else $('viewer-open').addEventListener('click', () => $('remote-preview-dialog').showModal());
    $('remote-preview-close').addEventListener('click', () => $('remote-preview-dialog').close());
    $('settings-open').addEventListener('click', () => $('settings-dialog').showModal());
    $('settings-done').addEventListener('click', () => $('settings-dialog').close());
    $('marker-name').addEventListener('input', () => { if (native) void request('field_edit', { field:'marker_name', value:$('marker-name').value }); });
    $('save-csv').addEventListener('change', () => { if (native) void request('option', { field:'save_csv', enabled:$('save-csv').checked }); });
    let saved;
    if (!native) try { saved = JSON.parse(localStorage.getItem('respyra-preview-fields') || 'null'); } catch { saved = null; }
    let variables = native ? [] : Array.isArray(saved?.variables) ? saved.variables : [{ label: 'Age', value: '' }, { label: 'Study group', value: '' }];
    $('participant').value = typeof saved?.participant === 'string' ? saved.participant : '';
    const fail = error => {
      $('stream-status').textContent = 'Experiment control failed: ' + String(error);
      native?.core.invoke('close_app', { reason:'protocol_failure' }).catch(() => {});
    };
    const send = native ? actionQueue((command, args) => native.core.invoke(command, args), fail) : null;
    let nativeState = { phase:'starting' }, nativeProgress = {}, operation = 0, shownSent = false;
    async function request(action, fields = {}) {
      if (!send) return;
      const discrete = !['shown', 'field_key', 'field_edit'].includes(action);
      if (discrete) { operation++; updateNativeControls(); }
      try {
        const result = await send(action, fields);
        if (result?.ok === false) $('stream-status').textContent = result.message || 'Action rejected.';
        return result;
      } finally {
        if (discrete) { operation--; updateNativeControls(); }
      }
    }
    const saveFields = () => native
      ? void request('field_edit', { field:'variables', value:JSON.stringify(variables) })
      : localStorage.setItem('respyra-preview-fields', JSON.stringify({ participant: $('participant').value, variables }));
    $('participant').addEventListener('input', () => {
      if (native) void request('field_edit', { field:'participant', value:$('participant').value });
      else saveFields();
    });
    $('participant').addEventListener('keydown', event => { if (native) void request('field_key', { field:'participant', key:event.key }); });
    let streams = [], selectedSource = '', sourceAssigned = false, discoverySignature = '', discoveryError = '';
    let nativeCandidates = [], nativeSelectedId = '', nativeExcluded = new Set();
    const choices = new Map(), histories = new Map();
    let inputMarkers = [], lastInputSequence = 0;
    const palette = ['#84bfe0', '#e95e60', '#4ed482', '#acb2bb', '#e9a86c'];
    let variablePage = 0, streamPage = 0, channelPage = 0, variableSize = 4, streamSize = 6, channelSize = 4, fitting = false, resetForFit = false, pretextReady = false;
    const prepared = new Map();
    let savedLayout;
    try { savedLayout = JSON.parse(localStorage.getItem('respyra-preview-layout') || 'null'); } catch { savedLayout = null; }
    let hubShare = Number.isFinite(savedLayout?.hub) ? savedLayout.hub : .32;
    let selectionShare = Number.isFinite(savedLayout?.selection) ? savedLayout.selection : .30;
    let preferredSelectionShare = selectionShare;
    let scheduleTextMeasurement = () => {};
    const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));
    const saveLayout = () => { preferredSelectionShare = selectionShare; localStorage.setItem('respyra-preview-layout', JSON.stringify({ hub: hubShare, selection: selectionShare })); };

    function updateNativeControls() {
      if (!native) return;
      const setup = nativeState.phase === 'setup', running = nativeState.phase === 'experiment';
      $('start').hidden = !setup;
      $('start').disabled = !setup || !nativeState.can_start || operation > 0;
      $('stop').hidden = !running;
      $('stop').disabled = !running || operation > 0 || nativeProgress.recording?.phase === 'finalizing';
      $('close').hidden = !['finished', 'error'].includes(nativeState.phase);
      $('close').disabled = operation > 0 || ['preparing', 'recording', 'finalizing'].includes(nativeProgress.recording?.phase);
      $('participant').disabled = !setup || operation > 0;
      $('add-field').disabled = !setup || operation > 0 || variables.length >= 6;
      $('refresh').disabled = !setup || !!nativeState.busy || operation > 0;
      for (const [id, type] of [['vernier-source', 'VernierRaw'], ['polar-source', 'Respiration']])
        $(id).disabled = !setup || !!nativeState.busy || operation > 0 || !nativeCandidates.some(row => row.compatible && row.stream_type === type);
      $('polar-direction').disabled = !setup || operation > 0 || !nativeState.source?.contract_id?.startsWith('respyra-polar-');
      $('marker-name').disabled = !setup || operation > 0;
      $('save-csv').disabled = !setup || operation > 0;
      for (const input of $('variable-list').querySelectorAll('input, button')) input.disabled = !setup || operation > 0;
      for (const kind of ['keyboard', 'mouse']) $(`include-${kind}-markers`).disabled = !setup || operation > 0;
      for (const input of $('stream-list').querySelectorAll('input[data-record]'))
        input.disabled = !setup || operation > 0 || input.dataset.required === 'true';
    }

    function applyLayout(commit = false) {
      const content = document.querySelector('.content'), body = $('stream-body');
      const css = getComputedStyle(content);
      const width = content.clientWidth - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight);
      if (width > 0 && getComputedStyle($('hub-divider')).display !== 'none') {
        const maxHubWidth = Math.max(250, width - 408);
        const hubWidth = clamp(hubShare * width, 250, maxHubWidth);
        if (commit) hubShare = hubWidth / width;
        content.style.setProperty('--hub-size', `${hubWidth}px`);
        $('hub-divider').setAttribute('aria-valuemin', String(Math.round(250 / width * 100)));
        $('hub-divider').setAttribute('aria-valuemax', String(Math.round(maxHubWidth / width * 100)));
        $('hub-divider').setAttribute('aria-valuenow', String(Math.round(hubWidth / width * 100)));
        $('hub-divider').setAttribute('aria-valuetext', `Experiment hub ${Math.round(hubWidth)} pixels wide`);
      }
      if (body.clientHeight > 0) {
        const height = body.clientHeight;
        const maxSelectionHeight = Math.max(150, height - 148);
        const selectionHeight = clamp(selectionShare * height, 150, maxSelectionHeight);
        if (commit) selectionShare = selectionHeight / height;
        body.style.setProperty('--selection-size', `${selectionHeight}px`);
        $('selection-divider').setAttribute('aria-valuemin', String(Math.round(150 / height * 100)));
        $('selection-divider').setAttribute('aria-valuemax', String(Math.round(maxSelectionHeight / height * 100)));
        $('selection-divider').setAttribute('aria-valuenow', String(Math.round(selectionHeight / height * 100)));
        $('selection-divider').setAttribute('aria-valuetext', `Stream selection ${Math.round(selectionHeight)} pixels high`);
      }
    }

    function wireDivider(id, axis) {
      const divider = $(id);
      const change = coordinate => {
        if (axis === 'x') {
          const content = document.querySelector('.content'), css = getComputedStyle(content);
          const width = content.clientWidth - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight);
          hubShare = (coordinate - content.getBoundingClientRect().left - parseFloat(css.paddingLeft)) / width;
        } else {
          const body = $('stream-body');
          selectionShare = (coordinate - body.getBoundingClientRect().top) / body.clientHeight;
        }
        applyLayout(true); fit();
      };
      divider.addEventListener('pointerdown', event => {
        if (event.button !== 0) return;
        divider.setPointerCapture(event.pointerId);
        change(axis === 'x' ? event.clientX : event.clientY);
      });
      divider.addEventListener('pointermove', event => {
        if (divider.hasPointerCapture(event.pointerId)) change(axis === 'x' ? event.clientX : event.clientY);
      });
      divider.addEventListener('pointerup', saveLayout);
      divider.addEventListener('keydown', event => {
        const key = event.key;
        const direction = axis === 'x' ? { ArrowLeft: -1, ArrowRight: 1 }[key] : { ArrowUp: -1, ArrowDown: 1 }[key];
        if (direction === undefined && key !== 'Home' && key !== 'End') return;
        event.preventDefault();
        const length = axis === 'x' ? document.querySelector('.content').clientWidth : $('stream-body').clientHeight;
        const current = axis === 'x' ? hubShare : selectionShare;
        const target = key === 'Home' ? 0 : key === 'End' ? 1 : current + direction * (event.shiftKey ? 64 : 24) / length;
        if (axis === 'x') hubShare = target; else selectionShare = target;
        applyLayout(true); fit(); saveLayout();
      });
    }
    wireDivider('hub-divider', 'x');
    wireDivider('selection-divider', 'y');



    function textHeight(element, availableWidth) {
      if (!element.getClientRects().length) return 0;
      const css = getComputedStyle(element);
      const boxWidth = availableWidth || (css.display === 'inline' ? element.parentElement.clientWidth : element.clientWidth);
      const width = Math.max(1, boxWidth - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight) - 2);

      const font = `${css.fontStyle} ${css.fontWeight} ${css.fontSize} ${css.fontFamily}`;

      const spacing = parseFloat(css.letterSpacing) || 0;

      const key = JSON.stringify([element.textContent, font, spacing, css.whiteSpace]);

      let item = prepared.get(key);

      if (!item) {

        item = prepareWithSegments(element.textContent, font, { letterSpacing: spacing, whiteSpace: css.whiteSpace === 'pre-wrap' ? 'pre-wrap' : 'normal' });

        if (prepared.size >= 128) prepared.clear();

        prepared.set(key, item);

      }

      const stats = measureLineStats(item, width);

      return Math.ceil(Math.max(1, stats.lineCount) * parseFloat(css.lineHeight));

    }



    function sizeStreamRows() {

      if (!pretextReady) return;

      for (const row of document.querySelectorAll('.stream-row')) {
        const name = row.querySelector('.stream-name');
        const identity = row.querySelector('.stream-identity');
        const height = Math.max(22, textHeight(name, identity.clientWidth) + 4);
        row.style.minHeight = `${height}px`;

        row.dataset.pretextRowHeight = String(height);

      }

    }



    function actionFits(button) {

      if (!button.getClientRects().length) return true;

      const css = getComputedStyle(button);

      const font = `${css.fontStyle} ${css.fontWeight} ${css.fontSize} ${css.fontFamily}`;

      const spacing = parseFloat(css.letterSpacing) || 0;

      const label = prepareWithSegments(button.textContent, font, { letterSpacing: spacing });

      const trackWidth = button.id === 'start' ? button.clientWidth : button.parentElement.clientWidth;

      const width = trackWidth - parseFloat(css.paddingLeft) - parseFloat(css.paddingRight) - 2;

      const height = button.clientHeight - parseFloat(css.paddingTop) - parseFloat(css.paddingBottom);

      return width > 0 && measureLineStats(label, width).lineCount === 1 &&

        measureNaturalWidth(label) <= width + 1 && parseFloat(css.lineHeight) <= height + 1;

    }



    function chooseType() {

      const shell = $('shell');

      const userSize = parseFloat(getComputedStyle(document.documentElement).fontSize);

      const width = Math.min($('hub').clientWidth, $('streams').clientWidth);

      const height = $('streams').clientHeight;
      const preferred = userSize > 14 ? userSize : Math.max(14, Math.min(18, Math.floor(Math.min(width / 20, height / 38))));
      for (let size = preferred; size >= (userSize > 14 ? preferred : 14); size--) {

        shell.style.setProperty('--ui-type', `${size}px`);

        const failures = ['start', 'refresh', 'variable-prev', 'variable-next', 'stream-prev', 'stream-next', 'channel-prev', 'channel-next'].filter(id => !actionFits($(id)));

        if (!failures.length) {

          shell.dataset.typeFit = 'fit'; return;

        }

      }

      shell.dataset.typeFit = 'no-fit';

    }



    function panelFits() {

      const regions = [$('shell'), document.querySelector('.content'), $('hub'), $('streams'), $('hub-body'), $('stream-body'), $('stream-selection'), document.querySelector('.stream-section'), $('stream-list'), $('plot-section')];

      return regions.every(region => region.scrollWidth <= region.clientWidth + 1 && region.scrollHeight <= region.clientHeight + 1) &&

        document.documentElement.scrollWidth <= innerWidth + 1 && document.documentElement.scrollHeight <= innerHeight + 1;

    }



    function renderVariables() {

      const list = $('variable-list'); list.replaceChildren();

      const first = variablePage * variableSize;

      for (let index = first; index < Math.min(first + variableSize, variables.length); index++) {

        const variable = variables[index], row = document.createElement('div'); row.className = 'variable-row';

        const labelWrap = document.createElement('label'); labelWrap.className = 'label-wrap';

        const labelTitle = document.createElement('span'); labelTitle.className = 'field-label'; labelTitle.dataset.measure = ''; labelTitle.textContent = 'Variable label';

        const label = document.createElement('input'); label.className = 'text-input'; label.type = 'text'; label.maxLength = 128; label.value = variable.label; label.placeholder = 'e.g. Age'; label.setAttribute('aria-label', `Variable ${index + 1} label`);

        label.addEventListener('input', () => { variable.label = label.value; saveFields(); });
        label.addEventListener('keydown', event => { if (native) void request('field_key', { field:'variables', key:event.key }); });

        labelWrap.append(labelTitle, label);

        const valueWrap = document.createElement('label'); valueWrap.className = 'value-wrap';

        const valueTitle = document.createElement('span'); valueTitle.className = 'field-label'; valueTitle.dataset.measure = ''; valueTitle.textContent = 'Entry for this participant';

        const value = document.createElement('input'); value.className = 'text-input'; value.type = 'text'; value.maxLength = 128; value.value = variable.value; value.placeholder = 'Enter value'; value.setAttribute('aria-label', `Entry for ${variable.label || 'variable ' + (index + 1)}`);

        value.addEventListener('input', () => { variable.value = value.value; saveFields(); });
        value.addEventListener('keydown', event => { if (native) void request('field_key', { field:'variables', key:event.key }); });

        valueWrap.append(valueTitle, value);

        const remove = document.createElement('button'); remove.className = 'remove'; remove.type = 'button'; remove.textContent = '×'; remove.title = 'Remove variable'; remove.setAttribute('aria-label', `Remove variable ${index + 1}`);

        remove.addEventListener('click', () => { variables.splice(index, 1); variablePage = Math.min(variablePage, Math.max(0, Math.ceil(variables.length / variableSize) - 1)); saveFields(); renderVariables(); fit(); });

        row.append(labelWrap, valueWrap, remove); list.append(row);

      }

      if (!variables.length) { const empty = document.createElement('p'); empty.className = 'variable-empty'; empty.dataset.measure = ''; empty.textContent = 'No custom variables yet. Use + to add one.'; list.append(empty); }

      const pages = Math.max(1, Math.ceil(variables.length / variableSize));

      $('variable-pager').hidden = pages === 1;

      $('variable-count').textContent = `${variablePage + 1} / ${pages}`;

      $('variable-prev').disabled = variablePage === 0; $('variable-next').disabled = variablePage >= pages - 1;
      updateNativeControls();

    }

    $('add-field').addEventListener('click', () => {
      if (native && variables.length >= 6) return;

      variables.push({ label: '', value: '' }); variablePage = Math.floor((variables.length - 1) / variableSize);

      saveFields(); renderVariables(); fit();

      document.querySelector('#variable-list .variable-row:last-child .label-wrap input')?.focus();

    });

    $('variable-prev').addEventListener('click', () => { variablePage--; renderVariables(); fit(); });

    $('variable-next').addEventListener('click', () => { variablePage++; renderVariables(); fit(); });

    $('start').addEventListener('click', () => {
      if (native) void request('start');
      else { $('stream-status').textContent = 'Preview only'; fit(); }
    });
    $('stop').addEventListener('click', () => { void request('abort'); });
    $('close').addEventListener('click', () => { void native?.core.invoke('close_app', { reason:'close_button' }); });



    let latestRows = [];
    function applyDiscovery(payload) {
      const now = performance.now() / 1000;
      latestRows = Array.isArray(payload.streams) ? payload.streams : [];
      const families = new Map();
      for (const row of latestRows) {
        const parts = row.name.split(/[-_]/).filter(Boolean);
        if (!families.has(parts[0])) families.set(parts[0], []);
        families.get(parts[0]).push(parts);
      }
      const commonPrefixes = new Map();
      for (const [family, names] of families) {
        const prefix = [...names[0]];
        for (const parts of names.slice(1)) while (prefix.length && !prefix.every((word, index) => parts[index] === word)) prefix.pop();
        commonPrefixes.set(family, names.length > 1 ? prefix.length : 0);
      }
      const shortNames = latestRows.map(row => {
        const parts = row.name.split(/[-_]/).filter(Boolean);
        const prefixLength = commonPrefixes.get(parts[0]);
        if (!prefixLength) return row.name;
        return (parts.slice(prefixLength).length ? parts.slice(prefixLength) : parts.slice(1, 3)).join(' ') || row.name;
      });
      const shortNameCounts = new Map();
      for (const name of shortNames) shortNameCounts.set(name, (shortNameCounts.get(name) || 0) + 1);
      const shortNameIndex = new Map();
      discoveryError = payload.error || '';
      const eligible = latestRows.filter(row => row.compatible);
      if (selectedSource && !eligible.some(row => row.uid === selectedSource)) selectedSource = '';
      if (nativeSelectedId) selectedSource = eligible.find(row => row.source_id === nativeSelectedId)?.uid || selectedSource;
      if (!native && !selectedSource && !sourceAssigned && eligible.length === 1) selectedSource = eligible[0].uid;
      if (selectedSource) sourceAssigned = true;
      const actualProcessed = latestRows.some(row => row.name === 'Respyra-Calibrated-Breathing' && row.source_id?.startsWith('respyra-breathing-'));

      streams = latestRows.map((row, index) => {
        const id = row.uid, processed = row.name === 'Respyra-Calibrated-Breathing' && row.source_id?.startsWith('respyra-breathing-');
        const baseName = shortNames[index];
        const nextIndex = (shortNameIndex.get(baseName) || 0) + 1;
        shortNameIndex.set(baseName, nextIndex);
        const shortName = processed ? 'Respyra breathing' : shortNameCounts.get(baseName) > 1 ? `${baseName} ${nextIndex}` : baseName;
        const required = id === selectedSource || (processed && !!selectedSource);
        const choice = choices.get(id) || {};
        const channels = row.numeric ? row.channels.map(channel => {
          const key = `${id}:${channel.index}`;
          const history = histories.get(key) || { last: null, points: [] };
          history.points = history.points.filter(point => point.t >= now - 10);
          if (row.signal === 'live' && Number.isFinite(channel.value) && Number.isFinite(row.lsl_time) && row.lsl_time !== history.last) {
            history.last = row.lsl_time;
            history.points.push({ t: now, y: channel.value });
          }
          histories.set(key, history);
          return { name: channel.label, plotLabel: `${channel.label}${channel.unit ? ` (${channel.unit})` : ''}`, points: history.points };
        }) : [];
        const markerKey = `marker:${id}`;
        const markerHistory = histories.get(markerKey) || { last: null, points: [] };
        markerHistory.points = markerHistory.points.filter(t => t >= now - 10);
        if (!row.numeric && row.signal === 'live' && Number.isFinite(row.lsl_time) && row.lsl_time !== markerHistory.last) {
          markerHistory.last = row.lsl_time; markerHistory.points.push(now);
        }
        histories.set(markerKey, markerHistory);
        return { id, name: row.name, shortName, detail: `${row.type} · ${row.signal} · ${row.reason} · ${row.channels.length} channels`,
          compatible: row.compatible, signal: row.signal,
          record: required || (native ? !nativeExcluded.has(id) : !!choice.record),
          display: choice.display ?? required, required, channels, numeric: row.numeric,
          markers: markerHistory.points, color: colorFor(id, processed) };
      });
      if (selectedSource && !actualProcessed) streams.push({ id: 'pending-calibrated', name: 'Respyra-Calibrated-Breathing', shortName: 'Respyra breathing',
        detail: 'Prepared at Start; calibrated values begin after calibration', record: true, display: false, required: true,
        pending: true, channels: [], markers: [], color: '#4ed482' });
      streams.sort((a, b) => Number(b.id === selectedSource) - Number(a.id === selectedSource) ||
        Number(b.id === 'pending-calibrated' || b.name === 'Respyra-Calibrated-Breathing') - Number(a.id === 'pending-calibrated' || a.name === 'Respyra-Calibrated-Breathing'));

      const signature = JSON.stringify([selectedSource, discoveryError, eligible.map(row => [row.uid, row.type]), streams.map(({ id, name, shortName, signal, required, pending, record }) => [id, name, shortName, signal, required, pending, record])]);
      if (signature !== discoverySignature) {
        discoverySignature = signature;
        renderSourceOptions(eligible);
        renderStreams();
        fit();
      }
      $('stream-status').textContent = discoveryError ? 'LSL discovery unavailable.' : latestRows.length ? '' : 'No LSL streams found.';
      renderPlots();
    }

    function renderSourceOptions(eligible) {
      for (const [id, type, label] of [['vernier-source', 'VernierRaw', 'Vernier'], ['polar-source', 'Respiration', 'Polar']]) {
        const options = eligible.filter(row => row.type === type);
        const select = $(id); select.replaceChildren();
        const placeholder = document.createElement('option'); placeholder.value = '';
        placeholder.textContent = options.length ? `Choose ${label} stream` : `No ${label} stream found`;
        select.append(placeholder);
        for (const row of options) {
          const option = document.createElement('option'); option.value = row.uid; option.textContent = row.name;
          select.append(option);
        }
        select.value = options.some(row => row.uid === selectedSource) ? selectedSource : '';
        select.disabled = !options.length;
      }
      const source = streams.find(stream => stream.id === selectedSource);
      const live = native ? !!nativeState.source && nativeProgress.health?.signal === 'live' : source?.signal === 'live';
      const polar = !!nativeState.source?.contract_id?.startsWith('respyra-polar-');
      $('polar-direction-field').hidden = !native || !polar;
      $('input-readiness').dataset.state = discoveryError ? 'error' : live ? 'live' : 'waiting';
      $('input-readiness').textContent = discoveryError ? 'LSL discovery unavailable' : !source ? '' : polar && !nativeState.polar_direction_set ? 'Choose Polar inhale direction' : live ? 'Receiving samples' : 'Waiting for samples';
      $('hub-input-status').textContent = source ? `Breathing input: ${source.name} · ${source.signal}` : 'No breathing input selected';
      if (native) updateNativeControls(); else $('start').disabled = !live;
    }

    function renderStreams() {
      const list = $('stream-list'); list.replaceChildren();
      if (!streams.length) {
        const empty = document.createElement('p'); empty.className = 'muted'; empty.dataset.measure = '';
        empty.textContent = discoveryError ? 'Discovery unavailable.' : 'No streams found.';
        list.append(empty);
      }
      const first = streamPage * streamSize;
      for (const stream of streams.slice(first, first + streamSize)) {
        const row = document.createElement('div'); row.className = 'stream-row'; row.style.setProperty('--stream-color', stream.color);
        const recordWrap = document.createElement('label'); recordWrap.className = 'check'; recordWrap.title = stream.required ? 'Required recording' : 'Record this stream';
        const record = document.createElement('input'); record.type = 'checkbox'; record.checked = stream.record; record.disabled = !!stream.required || (native && (nativeState.phase !== 'setup' || operation > 0));
        record.dataset.record = ''; record.dataset.required = String(!!stream.required);
        record.setAttribute('aria-label', `Record ${stream.name}`);
        record.addEventListener('change', () => {
          const current = streams.find(row => row.id === stream.id);
          if (!current) return;
          current.record = record.checked;
          if (record.checked) { current.display = true; display.checked = true; }
          choices.set(stream.id, { ...choices.get(stream.id), record: current.record, display: current.display });
          if (native) void request('record_stream', { uid:stream.id, enabled:record.checked });
          renderPlots(); fit();
        });
        const recordLetter = document.createElement('span'); recordLetter.dataset.measure = ''; recordLetter.textContent = 'R';
        recordWrap.append(record, recordLetter);
        const displayWrap = document.createElement('label'); displayWrap.className = 'check'; displayWrap.title = 'Display this stream';
        const display = document.createElement('input'); display.type = 'checkbox'; display.checked = stream.display; display.disabled = !!stream.pending;
        display.setAttribute('aria-label', `Display ${stream.name}`);
        display.addEventListener('change', () => {
          const current = streams.find(row => row.id === stream.id);
          if (!current) return;
          current.display = display.checked;
          choices.set(stream.id, { ...choices.get(stream.id), display: display.checked });
          channelPage = 0; renderPlots(); fit();
        });
        const displayLetter = document.createElement('span'); displayLetter.dataset.measure = ''; displayLetter.textContent = 'V';
        displayWrap.append(display, displayLetter);
        const identity = document.createElement('div'); identity.className = 'stream-identity'; identity.innerHTML = `<span class="stream-name" data-measure></span>`;
        identity.children[0].textContent = stream.shortName || stream.name;
        identity.title = `${stream.name} · ${stream.detail}${stream.required ? ' · required recording' : ''}`;
        row.append(recordWrap, displayWrap, identity); list.append(row);
      }

      const pages = Math.max(1, Math.ceil(streams.length / streamSize));

      $('stream-pager').hidden = pages === 1;

      $('stream-page-count').textContent = `${streamPage + 1} / ${pages}`;

      $('stream-prev').disabled = streamPage === 0; $('stream-next').disabled = streamPage >= pages - 1;

    }
    function displayedChannels() {
      return streams.filter(stream => stream.display).flatMap(stream => (stream.channels || []).map(channel => ({ stream, channel })));
    }
    const colors = new Map();
    function colorFor(id, processed) {
      if (processed) return '#4ed482';
      if (!colors.has(id)) colors.set(id, palette[colors.size % palette.length]);
      return colors.get(id);
    }
    function boundsFor(channel) {
      const values = channel.points.map(point => point.y);
      return values.length ? { min: Math.min(...values), max: Math.max(...values) } : null;
    }
    function visibleChannels() { return displayedChannels().slice(channelPage * channelSize, (channelPage + 1) * channelSize); }
    function renderPlots() {
      const channels = displayedChannels();
      const pages = Math.max(1, Math.ceil(channels.length / channelSize));
      channelPage = Math.min(channelPage, pages - 1);
      $('plot-section').classList.toggle('paged', pages > 1);
      $('channel-pager').hidden = pages === 1;
      $('channel-page-count').textContent = `${channelPage + 1} / ${pages}`;
      $('channel-prev').disabled = channelPage === 0; $('channel-next').disabled = channelPage >= pages - 1;
      $('plot-count').textContent = channels.length ? `${channels.length} ${channels.length === 1 ? 'channel' : 'channels'}` : '';
      const legend = $('plot-legend'); legend.replaceChildren();
      const visible = visibleChannels();
      const labelCounts = new Map();
      for (const { channel } of visible) labelCounts.set(channel.plotLabel, (labelCounts.get(channel.plotLabel) || 0) + 1);
      for (const [index, { stream, channel }] of visible.entries()) {
        const bounds = boundsFor(channel);
        const key = document.createElement('span'); key.className = 'plot-key'; key.style.setProperty('--trace-color', stream.color);
        const number = document.createElement('span'); number.className = 'plot-index'; number.dataset.measure = ''; number.textContent = String(index + 1);
        const label = document.createElement('strong'); label.dataset.measure = ''; label.textContent = labelCounts.get(channel.plotLabel) > 1 ? `${stream.shortName || stream.name} · ${channel.plotLabel}` : channel.plotLabel;
        key.title = `${stream.name} · ${channel.plotLabel}`;
        key.append(number, label);
        if (bounds) { const range = document.createElement('span'); range.className = 'range'; range.dataset.measure = ''; range.textContent = `${formatBound(bounds.min)}–${formatBound(bounds.max)}`; key.append(range); }
        legend.append(key);
      }
      requestAnimationFrame(drawPlots);
    }
    const svgNS = 'http://www.w3.org/2000/svg';
    function svgElement(tag, attributes = {}, value = '') {
      const element = document.createElementNS(svgNS, tag);
      for (const [key, item] of Object.entries(attributes)) element.setAttribute(key, String(item));
      if (value) element.textContent = value;
      return element;
    }
    function formatBound(value) { return Math.abs(value) >= 10 ? value.toFixed(1) : value.toFixed(2); }
    const plotFontSize = () => Math.max(10, Math.round(parseFloat(getComputedStyle($('shell')).fontSize) * .72));
    function lanesFit() {
      const count = visibleChannels().length;
      return !count || ($('plot-canvas').clientHeight - plotFontSize() * 2.4) / count >= plotFontSize() * 1.7 + 4;
    }
    function drawPlots() {
      const svg = $('plot-canvas'), channels = visibleChannels();
      const width = Math.max(1, Math.round(svg.clientWidth)), height = Math.max(1, Math.round(svg.clientHeight));
      if (width < 100 || height < 44) return;
      const fontSize = plotFontSize();
      const left = fontSize * 3.1, right = width - 8, top = fontSize * .8, bottom = height - fontSize * 1.6;
      const now = performance.now() / 1000;
      const x = t => left + (t - (now - 10)) / 10 * (right - left);
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`); svg.replaceChildren();
      const enabledMarkers = ['keyboard', 'mouse'].filter(kind => $(`include-${kind}-markers`).checked);
      svg.setAttribute('aria-label', (channels.length ? `Ten-second plot with stacked channel lanes on one time axis: ${channels.map(({ stream, channel }) => `${stream.name} ${channel.name}`).join(', ')}` : 'No numeric channels selected for display') +
        (enabledMarkers.length ? `; ${enabledMarkers.join(' and ')} input markers enabled` : ''));
      svg.append(svgElement('line', { x1: left, y1: bottom, x2: right, y2: bottom, class: 'plot-axis' }));
      svg.append(svgElement('line', { x1: left, y1: top, x2: left, y2: bottom, class: 'plot-axis' }));
      const laneHeight = (bottom - top) / Math.max(1, channels.length);
      for (const [index, { stream, channel }] of channels.entries()) {
        const laneCenter = top + (index + .5) * laneHeight;
        const padding = Math.min(8, laneHeight * .14);
        const laneTop = top + index * laneHeight + padding;
        const laneBottom = top + (index + 1) * laneHeight - padding;
        svg.append(svgElement('line', { x1: left - 16, y1: laneCenter, x2: left - 4, y2: laneCenter, stroke: stream.color, class: 'plot-anchor', 'data-lane': index + 1 }));
        svg.append(svgElement('text', { x: left - 20, y: laneCenter + fontSize * .35, 'text-anchor': 'end', 'font-size': fontSize, class: 'plot-anchor-label' }, String(index + 1)));
        const bounds = boundsFor(channel);
        if (!bounds || channel.points.length < 2) continue;
        const { min, max } = bounds, span = max - min;
        const y = value => span ? laneBottom - (value - min) / span * (laneBottom - laneTop) : laneCenter;
        const path = channel.points.map((point, i) => `${i ? 'L' : 'M'}${x(point.t).toFixed(2)} ${y(point.y).toFixed(2)}`).join(' ');
        svg.append(svgElement('path', { d: path, class: 'plot-trace', stroke: stream.color, 'data-stream': stream.id, 'data-channel': channel.name, 'data-min': min, 'data-max': max, 'data-lane-top': laneTop, 'data-lane-bottom': laneBottom }));
      }
      for (const stream of streams.filter(stream => stream.display && !stream.numeric))
        for (const t of stream.markers) svg.append(svgElement('line', { x1: x(t), y1: top, x2: x(t), y2: bottom, class: 'plot-event', stroke: stream.color }));
      inputMarkers = inputMarkers.filter(marker => marker.t >= now - 10);
      for (const marker of inputMarkers) svg.append(svgElement('line', { x1: x(marker.t), y1: top, x2: x(marker.t), y2: bottom,
        class: 'plot-event plot-input-event', stroke: marker.kind === 'keyboard' ? '#e9a86c' : '#acb2bb', 'data-kind': marker.kind }));
      svg.append(svgElement('text', { x: left, y: height - 3, 'font-size': fontSize }, '−10 s'));
      svg.append(svgElement('text', { x: right, y: height - 3, 'text-anchor': 'end', 'font-size': fontSize }, 'now'));
      if ((!channels.length && !svg.querySelector('.plot-event')) || (channels.length && channels.every(({ channel }) => channel.points.length < 2)))
        svg.append(svgElement('text', { x: (left + right) / 2, y: (top + bottom) / 2, 'text-anchor': 'middle', 'font-size': fontSize }, channels.length ? 'Waiting for live samples' : 'Select View on a numeric stream'));
    }
    function markInput(kind) { inputMarkers.push({ kind, t: performance.now() / 1000 }); drawPlots(); }
    window.addEventListener('keydown', () => { if (!native && $('include-keyboard-markers').checked) markInput('keyboard'); }, true);
    window.addEventListener('mousedown', () => { if (!native && $('include-mouse-markers').checked) markInput('mouse'); }, true);
    for (const kind of ['keyboard', 'mouse']) $(`include-${kind}-markers`).addEventListener('change', () => {
      if (!$(`include-${kind}-markers`).checked) inputMarkers = inputMarkers.filter(marker => marker.kind !== kind);
      if (native) void request('option', { field:kind === 'keyboard' ? 'record_keyboard' : 'record_mouse', enabled:$(`include-${kind}-markers`).checked });
      drawPlots();
    });
    function chooseSource(event) {
      const requestedSource = event.currentTarget.value;
      if (!requestedSource) return;
      $(event.currentTarget.id === 'vernier-source' ? 'polar-source' : 'vernier-source').value = '';
      selectedSource = requestedSource; sourceAssigned = true; channelPage = 0;
      if (native && requestedSource) {
        const sourceId = latestRows.find(row => row.uid === requestedSource)?.source_id;
        const row = nativeCandidates.findIndex(candidate => candidate.source_id === sourceId && candidate.compatible);
        if (row >= 0) void request('select', { row }).then(result => { if (result?.ok) void request('use'); });
      } else applyDiscovery({ streams: latestRows, error: discoveryError });
    }
    for (const id of ['vernier-source', 'polar-source']) $(id).addEventListener('change', chooseSource);
    $('polar-direction').addEventListener('change', () => {
      if (native && $('polar-direction').value)
        void request('option', { field:'polar_inverted', enabled:$('polar-direction').value === 'decreasing' });
    });
    $('refresh').addEventListener('click', async () => {
      if (native) { void request('scan'); return; }
      $('stream-status').textContent = 'Refreshing LSL discovery…';
      try { await fetch('/api/refresh', { cache: 'no-store' }); } catch { /* The regular poll reports the bridge error. */ }
      setTimeout(pollOnce, 400);
    });

    $('stream-prev').addEventListener('click', () => { streamPage--; renderStreams(); fit(); });

    $('stream-next').addEventListener('click', () => { streamPage++; renderStreams(); fit(); });
    $('channel-prev').addEventListener('click', () => { channelPage--; renderPlots(); fit(); });
    $('channel-next').addEventListener('click', () => { channelPage++; renderPlots(); fit(); });

    let requestPending = false;
    function applyNativeState(snapshot) {
      nativeState = snapshot;
      nativeProgress = snapshot.progress || nativeProgress;
      if (snapshot.phase === 'setup') {
        nativeCandidates = snapshot.streams || [];
        nativeSelectedId = snapshot.source?.source_id || '';
        $('polar-direction').value = snapshot.polar_direction_set ? (snapshot.polar_inverted ? 'decreasing' : 'increasing') : '';
        nativeExcluded = new Set(snapshot.excluded_streams || []);
        if (document.activeElement !== $('participant') && snapshot.values)
          $('participant').value = snapshot.values.participant || '';
        if (!document.activeElement?.closest?.('#variable-list') && JSON.stringify(variables) !== JSON.stringify(snapshot.variables || [])) {
          variables = (snapshot.variables || []).map(row => ({ ...row }));
          renderVariables();
        }
        $('include-keyboard-markers').checked = !!snapshot.record_keyboard;
        $('include-mouse-markers').checked = !!snapshot.record_mouse;
        if (document.activeElement !== $('marker-name')) $('marker-name').value = snapshot.marker_name || '';
        $('save-csv').checked = !!snapshot.save_csv;
        if (!shownSent) { shownSent = true; void request('shown'); }
      }
      const candidates = new Map(nativeCandidates.map(row => [row.source_id, row]));
      const rows = (nativeProgress.streams || []).map(row => ({ ...row,
        compatible: !!candidates.get(row.source_id)?.compatible ||
          (row.source_id === nativeSelectedId && ['VernierRaw', 'Respiration'].includes(row.type)),
        reason: candidates.get(row.source_id)?.reason ||
          (row.source_id === nativeSelectedId ? 'Connected breathing input' : '') }));
      const markers = nativeProgress.markers;
      if (markers?.source_id) rows.push({ uid:`marker:${markers.source_id}`, source_id:markers.source_id,
        name:markers.name, type:'Markers', numeric:false, signal:markers.online ? 'live' : 'waiting',
        lsl_time:nativeProgress.lsl_time, channels:[{ index:0, label:'Event', unit:'', value:nativeProgress.event || null }],
        compatible:false, reason:'Experiment events' });
      for (const marker of nativeProgress.recent || []) {
        if (marker.seq > lastInputSequence) {
          if (marker.event === 'input.keyboard_event') inputMarkers.push({ kind:'keyboard', t:performance.now() / 1000 });
          if (marker.event === 'input.mouse_event') inputMarkers.push({ kind:'mouse', t:performance.now() / 1000 });
          lastInputSequence = marker.seq;
        }
      }
      applyDiscovery({ streams:rows, error:nativeProgress.viewer_error });
      const recording = nativeProgress.recording;
      const recordingStatus = recording?.phase === 'recording' ? `XDF recording · ${recording.streams?.length || 0} streams` :
        recording?.phase === 'complete' ? 'XDF saved' : '';
      $('stream-status').textContent = [snapshot.message, recordingStatus].filter(Boolean).join(' · ');
      updateNativeControls();
      fit();
    }
    async function pollOnce() {
      if (requestPending) return;
      requestPending = true;
      try {
        const response = await fetch('/api/streams', { cache: 'no-store' });
        if (!response.ok) throw new Error(`Discovery response ${response.status}`);
        applyDiscovery(await response.json());
      } catch {
        applyDiscovery({ streams: [], error: 'Live LSL preview server unavailable' });
      } finally { requestPending = false; }
    }
    async function pollingLoop() { await pollOnce(); setTimeout(pollingLoop, 750); }


    function fit(resetPages = false) {

      if (resetPages) selectionShare = preferredSelectionShare;

      resetForFit ||= resetPages;

      if (fitting) return;

      fitting = true;

      requestAnimationFrame(() => {

        fitting = false;

        $('shell').hidden = false; $('no-fit').hidden = true;

        document.documentElement.classList.toggle('large-text', parseFloat(getComputedStyle(document.documentElement).fontSize) > 20);

        applyLayout();
        if (resetForFit) {
          resetForFit = false;
          variableSize = 4; streamSize = 6; channelSize = 4;
          variablePage = Math.min(variablePage, Math.max(0, Math.ceil(variables.length / variableSize) - 1));
          streamPage = Math.min(streamPage, Math.max(0, Math.ceil(streams.length / streamSize) - 1));
          renderVariables(); renderStreams();
        }
        chooseType();
        applyLayout();

        sizeStreamRows();
        while ((!panelFits() || !lanesFit()) && (variableSize > 1 || streamSize > 1 || channelSize > 1 || $('stream-list').scrollHeight > $('stream-list').clientHeight + 1)) {
          if (!lanesFit() && channelSize > 1) { channelSize--; channelPage = 0; renderPlots(); continue; }
          const body = $('stream-body');
          const shortage = Math.max(0, $('stream-list').scrollHeight - $('stream-list').clientHeight,
            document.querySelector('.stream-section').scrollHeight - document.querySelector('.stream-section').clientHeight);
          const current = parseFloat(body.style.getPropertyValue('--selection-size')) || 0;
          const next = Math.min(body.clientHeight - 148, current + shortage + 2);
          if (shortage > 1 && next > current + 1) {
            selectionShare = next / body.clientHeight;
            applyLayout();
            sizeStreamRows();
            continue;
          }
          if (streamSize > 1) { streamSize--; streamPage = 0; renderStreams(); }
          if (variableSize > 1) { variableSize--; variablePage = 0; renderVariables(); }
          if (channelSize > 1) { channelSize--; channelPage = 0; renderPlots(); }
          sizeStreamRows();
          if (streamSize === 1 && variableSize === 1 && channelSize === 1) break;
        }
        const okay = panelFits() && lanesFit() && $('shell').dataset.typeFit === 'fit';
        $('shell').hidden = !okay; $('no-fit').hidden = okay;
        if (okay) { requestAnimationFrame(drawPlots); scheduleTextMeasurement(); }
      });
    }
    window.addEventListener('resize', () => { variablePage = 0; streamPage = 0; channelPage = 0; renderPlots(); fit(true); });
    renderVariables(); renderStreams(); renderPlots();
    $('start').disabled = true;
    await document.fonts.load('400 16px "Noto Sans"');

    await document.fonts.load('600 16px "Noto Sans"');

    await document.fonts.ready;

    setLocale(document.documentElement.lang);

    pretextReady = true;

    fit();

    scheduleTextMeasurement = await measureTextRegions(document) || (() => {});
    if (native) {
      await native.event.listen('setup-state', event => applyNativeState(event.payload));
      await native.core.invoke('launch_backend').then(applyNativeState).catch(fail);
    } else void pollingLoop();
