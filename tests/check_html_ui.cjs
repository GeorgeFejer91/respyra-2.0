const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');

(async () => {
  const web = path.resolve(__dirname, '../web');
  const server = http.createServer(async (request, response) => {
    const file = path.resolve(web, '.' + new URL(request.url, 'http://localhost').pathname);
    if (!file.startsWith(web + path.sep)) { response.writeHead(403).end(); return; }
    try {
      response.setHeader('Content-Type', { '.html':'text/html', '.js':'text/javascript', '.mjs':'text/javascript', '.css':'text/css', '.woff2':'font/woff2' }[path.extname(file)] || 'application/octet-stream');
      response.end(await fs.readFile(file));
    } catch { response.writeHead(404).end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ channel:'chrome', headless:true });
  const page = await browser.newPage({ viewport:{ width:1200, height:760 } });
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.addInitScript(() => {
    let listener;
    const rawId = 'polar-stream-vernier-raw-ui';
    const polarId = 'polar-h10-StudyPolar_adrPcaWaveform';
    const state = { phase:'setup', ui_seq:0, values:{ participant:'', session:'001' }, variables:[], marker_name:'Respyra-Events', save_csv:false,
      message:'Choose a raw Force stream', can_start:false, busy:false, record_keyboard:false, record_mouse:false,
      excluded_streams:[],
      streams:[{ source_id:rawId, stream_name:'Vernier Stream Mini', stream_type:'VernierRaw', compatible:true,
        reason:'Compatible: raw Force (N)', force_channel_index:0 },
        { source_id:polarId, stream_name:'StudyPolar_adrPcaWaveform', stream_type:'Respiration', compatible:true,
          reason:'Compatible: Polar PCA', force_channel_index:0 }], source:null, selected_row:null,
      progress:{ phase:'progress', health:{ signal:'not_selected', sample_age_ms:null },
        markers:{ name:'Respyra-Events', source_id:'respyra-events-ui', online:true, emitted:1 },
        recording:{ phase:'idle', streams:[] },
        streams:[{ uid:'raw-ui', source_id:rawId, name:'Vernier Stream Mini', type:'VernierRaw', numeric:true,
          signal:'live', lsl_time:1, channels:[{ index:0, label:'Force', unit:'N', value:5 }] },
          { uid:'polar-ui', source_id:polarId, name:'StudyPolar_adrPcaWaveform', type:'Respiration', numeric:true,
            signal:'live', lsl_time:1, channels:[{ index:0, label:'Breathing candidate', unit:'g', value:0.02 }] },
          { uid:'aux-ui', source_id:'polar-heart-ui', name:'Polar H10 heart rate', type:'HeartRate', numeric:true,
            signal:'live', lsl_time:1, channels:[{ index:0, label:'HR', unit:'BPM', value:72 }] }] } };
    window.testActions = [];
    window.testSnapshot = () => structuredClone(state);
    window.testProgress = progress => {
      state.progress = { ...state.progress, ...progress };
      listener({ payload:structuredClone(state) });
    };
    window.testCandidates = candidates => {
      state.streams = candidates;
      listener({ payload:structuredClone(state) });
    };
    window.__TAURI__ = { event:{ listen:async (_, callback) => { listener = callback; return () => {}; } },
      core:{ invoke:async (command, args) => {
        if (command === 'launch_backend') return structuredClone(state);
        if (command === 'close_app' || command === 'viewer_action') return null;
        const action = args.action;
        window.testActions.push(action);
        state.ui_seq = action.ui_seq;
        if (action.action === 'field_edit') {
          if (action.field === 'variables') state.variables = JSON.parse(action.value);
          else if (action.field === 'marker_name') state.marker_name = action.value;
          else state.values[action.field] = action.value;
        }
        if (action.action === 'option') state[action.field] = action.enabled;
        if (action.action === 'record_stream') state.excluded_streams = action.enabled ?
          state.excluded_streams.filter(uid => uid !== action.uid) : [...new Set([...state.excluded_streams, action.uid])];
        if (action.action === 'select') state.selected_row = action.row;
        if (action.action === 'use') {
          const polar = state.selected_row === 1;
          state.source = polar ? { source_id:polarId, stream_name:'StudyPolar_adrPcaWaveform', contract_id:'respyra-polar-pca/1' }
            : { source_id:rawId, stream_name:'Vernier Stream Mini', contract_id:'vernier-force/1' };
          state.polar_direction_set = false;
          state.message = 'Ready for this experiment.';
          state.progress.health.signal = 'live';
        }
        if (action.action === 'option' && action.field === 'polar_inverted') state.polar_direction_set = true;
        state.can_start = !!state.source && !!state.values.participant.trim() &&
          state.variables.every(row => row.label.trim() && row.value.trim()) &&
          (!state.source.contract_id.startsWith('respyra-polar-') || state.polar_direction_set);
        if (action.action === 'start') {
          state.phase = 'experiment'; state.message = 'Experiment running in PsychoPy.';
          state.progress.recording = { phase:'recording', streams:[{ source_id:rawId, name:'Vernier Stream Mini' },
            { source_id:'respyra-breathing-ui', name:'Respyra-Calibrated-Breathing' },
            { source_id:'respyra-events-ui', name:'Respyra-Events' }] };
        }
        if (action.action === 'abort') { state.phase = 'finished'; state.message = 'XDF saved. Experiment stopped.'; state.progress.recording.phase = 'complete'; }
        listener({ payload:structuredClone(state) });
        return { ok:true };
      } } };
  });
  try {
    await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);
    await page.locator('#vernier-source option').nth(1).waitFor({ state:'attached' });
    await page.locator('#polar-source option').nth(1).waitFor({ state:'attached' });
    assert.deepEqual(await page.locator('#vernier-source option').allTextContents(), ['Choose Vernier stream', 'Vernier Stream Mini']);
    assert.deepEqual(await page.locator('#polar-source option').allTextContents(), ['Choose Polar stream', 'StudyPolar_adrPcaWaveform']);
    assert.equal(await page.title(), 'Respyra 2.0 — Experiment control');
    assert(await page.locator('#viewer-open').isVisible());
    const catalog = JSON.parse(await fs.readFile(path.resolve(__dirname, '../src/mpi/event_markers/catalog.json'), 'utf8'));
    const planned = Object.entries(catalog.events).filter(([, event]) => event.active !== false).map(([name]) => name);
    await page.locator('#marker-inventory-open').click();
    assert(await page.locator('#marker-inventory-dialog').isVisible());
    assert.equal(await page.locator('#marker-inventory-list li').count(), planned.length);
    assert.deepEqual(await page.locator('#marker-inventory-list li strong').allTextContents(), planned);
    await page.locator('#marker-inventory-search').fill('tracking.started');
    assert.equal(await page.locator('#marker-inventory-list li').count(), 1);
    assert.match(await page.locator('#marker-inventory-list').textContent(), /First displayed tracking frame/);
    await page.locator('#marker-inventory-search').fill('no-such-marker');
    assert.match(await page.locator('#marker-inventory-list').textContent(), /No matching markers/);
    await page.locator('#marker-inventory-close').click();
    assert(await page.locator('#marker-inventory-dialog').isHidden());
    assert(await page.locator('#hub').isVisible() && await page.locator('#streams').isVisible());
    assert(await page.locator('#start').isDisabled());
    await page.locator('#participant').fill('P024');
    await page.locator('#add-field').click();
    await page.locator('#variable-list .variable-row input').first().fill('Age');
    await page.locator('#variable-list .variable-row input').nth(1).fill('28');
    await page.locator('#vernier-source').selectOption('raw-ui');
    await page.waitForFunction(() => !document.querySelector('#start').disabled);
    assert.equal(await page.locator('#polar-source').inputValue(), '');
    const rawRow = page.locator('.stream-row').filter({ hasText:'Vernier Stream Mini' });
    assert(await rawRow.getByRole('checkbox', { name:/Record/ }).isChecked());
    assert(await rawRow.getByRole('checkbox', { name:/Record/ }).isDisabled());
    const auxRow = page.locator('.stream-row').filter({ hasText:'Polar H10 heart rate' });
    await auxRow.getByRole('checkbox', { name:/Record/ }).uncheck();
    await page.waitForFunction(() => window.testSnapshot().excluded_streams.includes('aux-ui'));
    assert(await auxRow.getByRole('checkbox', { name:/Record/ }).isEnabled());
    assert(await auxRow.getByRole('checkbox', { name:/Display/ }).isEnabled());
    await page.locator('#settings-open').click();
    await page.locator('#marker-name').fill('Study Events');
    await page.locator('#save-csv').check();
    await page.keyboard.press('Escape');
    assert(await page.locator('#settings-dialog').isHidden());
    assert(await page.locator('#start').isEnabled());
    await rawRow.getByRole('checkbox', { name:/Display/ }).uncheck();
    assert.equal(await page.locator('#plot-legend .plot-key').count(), 0,
      JSON.stringify(await page.locator('#plot-legend').textContent()));
    await rawRow.getByRole('checkbox', { name:/Display/ }).check();
    for (const [width, height] of [[1200,760], [820,760], [390,844], [800,600]]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(100);
      assert(await page.locator('#shell').isVisible(), `Hub hidden at ${width}×${height}`);
      const fit = await page.evaluate(() => ({ width:document.documentElement.scrollWidth, height:document.documentElement.scrollHeight,
        clipped:[...document.querySelectorAll('[data-measure]')].filter(element => element.getClientRects().length &&
          (element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)).map(element => element.textContent) }));
      assert(fit.width <= width + 1 && fit.height <= height + 1 && !fit.clipped.length, JSON.stringify({ width, height, fit }));
      if (width === 1200 || width === 390) await page.screenshot({ path:path.resolve(__dirname, `../.for-ai-local/hub-${width}.png`) });
      if (width === 390) {
        await page.locator('#marker-inventory-open').click();
        const bounds = await page.locator('#marker-inventory-dialog').boundingBox();
        assert(bounds && bounds.x >= 0 && bounds.y >= 0 && bounds.x + bounds.width <= width + 1 && bounds.y + bounds.height <= height + 1);
        await page.screenshot({ path:path.resolve(__dirname, '../.for-ai-local/marker-inventory-390.png') });
        await page.locator('#marker-inventory-close').click();
      }
    }
    for (const [width, height, textSize] of [[320,480,16], [360,700,16], [820,760,32], [1440,900,32]]) {
      await page.setViewportSize({ width, height });
      await page.evaluate(size => { document.documentElement.style.fontSize = `${size}px`; document.documentElement.style.letterSpacing = '.08em'; }, textSize);
      await page.waitForTimeout(120);
      const fit = await page.evaluate(() => ({ width:document.documentElement.scrollWidth, height:document.documentElement.scrollHeight,
        shell:!!document.querySelector('#shell').getClientRects().length,
        notice:!!document.querySelector('#no-fit').getClientRects().length,
        clipped:[...document.querySelectorAll('[data-measure]')].filter(element => element.getClientRects().length &&
          (element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)).map(element => element.textContent) }));
      assert(fit.width <= width + 1 && fit.height <= height + 1 && (fit.shell || fit.notice), JSON.stringify({ width, height, fit }));
      if (fit.shell) assert(!fit.clipped.length, JSON.stringify({ width, height, fit }));
    }
    await page.evaluate(() => { document.documentElement.style.fontSize = ''; document.documentElement.style.letterSpacing = ''; });
    await page.setViewportSize({ width:1200, height:760 });
    await page.waitForFunction(() => document.querySelector('#shell').getClientRects().length > 0);
    await page.locator('#marker-inventory-open').click();
    await page.setViewportSize({ width:320, height:480 });
    await page.evaluate(() => { document.documentElement.style.fontSize = '32px'; document.documentElement.style.letterSpacing = '.08em'; });
    const dialogFit = await page.locator('#marker-inventory-dialog').evaluate(dialog => {
      const box = dialog.getBoundingClientRect();
      const clipped = [...dialog.querySelectorAll('[data-measure]')].filter(element =>
        element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1).map(element => element.textContent);
      return { x:box.x, y:box.y, right:box.right, bottom:box.bottom,
        horizontalOverflow:dialog.scrollWidth > dialog.clientWidth + 1,
        headerOverflow:dialog.querySelector('.inventory-head').scrollWidth > dialog.querySelector('.inventory-head').clientWidth + 1,
        clipped };
    });
    assert(dialogFit.x >= 0 && dialogFit.y >= 0 && dialogFit.right <= 321 && dialogFit.bottom <= 481 &&
      !dialogFit.horizontalOverflow && !dialogFit.headerOverflow && !dialogFit.clipped.length, JSON.stringify(dialogFit));
    await page.screenshot({ path:path.resolve(__dirname, '../.for-ai-local/marker-inventory-320-large.png') });
    await page.locator('#marker-inventory-list').evaluate(list => { list.scrollTop = list.scrollHeight; });
    assert(await page.locator('#marker-inventory-list li').last().isVisible());
    await page.locator('#marker-inventory-close').click();
    await page.evaluate(() => { document.documentElement.style.fontSize = ''; document.documentElement.style.letterSpacing = ''; });
    await page.setViewportSize({ width:1200, height:760 });
    await page.waitForFunction(() => document.querySelector('#shell').getClientRects().length > 0);
    await page.locator('#polar-source').selectOption('polar-ui');
    await page.waitForFunction(() => window.testSnapshot().source?.contract_id === 'respyra-polar-pca/1');
    assert.equal(await page.locator('#vernier-source').inputValue(), '');
    assert.equal(await page.locator('#polar-source').inputValue(), 'polar-ui');
    await page.evaluate(() => {
      const rows = window.testSnapshot().progress.streams;
      window.testCandidates([]);
      window.testProgress({ streams:rows.filter(row => row.uid !== 'polar-ui') });
      window.testProgress({ streams:rows });
    });
    assert.equal(await page.locator('#polar-source').inputValue(), 'polar-ui', 'remembered connected source stays visible without a scan list');
    assert(await page.locator('#polar-direction-field').isVisible());
    assert(await page.locator('#start').isDisabled());
    for (const [width, height] of [[820,760], [390,844], [320,480]]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(120);
      const fit = await page.evaluate(() => ({ width:document.documentElement.scrollWidth,
        height:document.documentElement.scrollHeight,
        shell:!!document.querySelector('#shell').getClientRects().length,
        notice:!!document.querySelector('#no-fit').getClientRects().length,
        clipped:[...document.querySelectorAll('[data-measure]')].filter(element => element.getClientRects().length &&
          (element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)).map(element => element.textContent) }));
      assert(fit.width <= width + 1 && fit.height <= height + 1 && (fit.shell || fit.notice), JSON.stringify({ width, height, fit }));
      if (fit.shell) assert(!fit.clipped.length, JSON.stringify({ width, height, fit }));
      if (width === 390) assert(fit.shell, 'Polar source controls should fit the compact 390 px hub');
      if (width === 820 || width === 390) await page.screenshot({ path:path.resolve(__dirname, `../.for-ai-local/polar-hub-${width}.png`) });
    }
    await page.setViewportSize({ width:1200, height:760 });
    await page.locator('#polar-direction').selectOption('decreasing');
    await page.waitForFunction(() => !document.querySelector('#start').disabled);
    assert.equal((await page.evaluate(() => window.testSnapshot())).polar_inverted, true);
    await page.locator('#start').click();
    await page.locator('#stop').waitFor({ state:'visible' });
    assert(await page.locator('#participant').isDisabled());
    assert(await page.locator('#start').isHidden());
    await page.locator('#marker-inventory-open').click();
    assert(await page.locator('#marker-inventory-dialog').isVisible());
    await page.locator('#marker-inventory-close').click();
    await page.evaluate(() => window.testProgress({ streams:[...window.testSnapshot().progress.streams,
      { uid:'derived-ui', source_id:'respyra-breathing-ui', name:'Respyra-Calibrated-Breathing', type:'Respiration',
        numeric:true, signal:'live', lsl_time:2, channels:[{ index:0, label:'Calibrated breathing', unit:'normalized', value:null }] }] }));
    await page.waitForTimeout(150);
    if (!await page.locator('#shell').isVisible()) assert.fail(JSON.stringify(await page.evaluate(() => {
      const shell = document.querySelector('#shell'); shell.hidden = false;
      const regions = ['#shell','.content','#hub','#streams','#hub-body','#stream-body','#stream-selection','.stream-section','#stream-list','#plot-section'];
      const geometry = regions.map(selector => { const e=document.querySelector(selector); return [selector,e.scrollWidth,e.clientWidth,e.scrollHeight,e.clientHeight]; });
      const result = { notice:document.querySelector('#no-fit').textContent, width:innerWidth, height:innerHeight,
        status:document.querySelector('#stream-status').textContent, geometry,
        rootFont:getComputedStyle(document.documentElement).fontSize, shellFont:getComputedStyle(shell).fontSize,
        typeFit:shell.dataset.typeFit, canvasHeight:document.querySelector('#plot-canvas').clientHeight,
        legend:document.querySelector('#plot-legend').textContent,
        plotRows:getComputedStyle(document.querySelector('#plot-section')).gridTemplateRows,
        plotChildren:[...document.querySelector('#plot-section').children].map(e=>[e.id||e.className,e.clientHeight,e.scrollHeight]) };
      shell.hidden = true; return result;
    })));
    assert.equal(await page.getByText('Respyra breathing', { exact:true }).count(), 1);
    await page.locator('#stop').click();
    await page.locator('#close').waitFor({ state:'visible' });
    const actions = await page.evaluate(() => window.testActions);
    assert.deepEqual(actions.map(action => action.ui_seq), actions.map((_, index) => index + 1));
    assert.equal(actions.filter(action => action.action === 'start').length, 1);
    assert.equal(actions.filter(action => action.action === 'abort').length, 1);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ result:'passed', layouts:8, actions:actions.length, start:1, stop:1, pageErrors:0 }));
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exit(1); });
