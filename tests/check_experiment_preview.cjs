const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');

(async () => {
  const web = path.resolve(__dirname, '../web');
  const out = path.resolve(__dirname, '../.for-ai-local');
  await fs.mkdir(out, { recursive: true });
  let discovery = { streams: [], error: null };
  const server = http.createServer(async (req, res) => {
    const pathname = new URL(req.url, 'http://localhost').pathname;
    if (pathname === '/api/streams' || pathname === '/api/refresh') {
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify(discovery));
      return;
    }
    const file = path.resolve(web, '.' + pathname);
    if (!file.startsWith(web + path.sep)) { res.writeHead(403).end(); return; }
    try {
      res.setHeader('Content-Type', { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.mjs': 'text/javascript', '.woff2': 'font/woff2' }[path.extname(file)] || 'application/octet-stream');
      res.end(await fs.readFile(file));
    } catch { res.writeHead(404).end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1200, height: 760 } });
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  try {
    await page.goto(`http://127.0.0.1:${server.address().port}/experiment-hub-preview.html`);
    await page.getByRole('button', { name: 'Remote Viewer' }).click();
    assert(await page.locator('#remote-preview-dialog').evaluate(dialog => dialog.open));
    await page.screenshot({ path:path.join(out, 'remote-viewer-preview-dialog.png') });
    assert(await page.getByText('This browser preview cannot issue a live pairing code.').isVisible());
    for (const [width, height] of [[390, 844], [800, 600], [1200, 760]]) {
      await page.setViewportSize({ width, height });
      const fits = await page.locator('#remote-preview-dialog').evaluate(dialog => {
        const box = dialog.getBoundingClientRect();
        return box.width <= innerWidth - 24 && box.height <= innerHeight - 24;
      });
      assert(fits, `Remote Viewer preview dialog fits ${width}×${height}`);
    }
    await page.getByRole('button', { name: 'Close', exact: true }).click();
    assert(!await page.locator('#remote-preview-dialog').evaluate(dialog => dialog.open));
    await page.waitForFunction(() => document.querySelector('#stream-status')?.textContent === 'No LSL streams found.');
    assert.equal(await page.locator('.stream-row').count(), 0);
    assert(await page.locator('#vernier-source').isDisabled());
    assert(await page.locator('#polar-source').isDisabled());
    assert(await page.locator('#start').isDisabled());
    assert(!String(await page.locator('body').textContent()).includes('Lab breathing belt'));
    await page.getByRole('checkbox', { name: 'Include keyboard markers' }).check();
    await page.keyboard.press('k');
    assert.equal(await page.locator('#plot-canvas .plot-input-event[data-kind="keyboard"]').count(), 1, 'markers also appear without a numeric stream');
    assert(!String(await page.locator('#plot-canvas').textContent()).includes('Select View on a numeric stream'));
    await page.getByRole('checkbox', { name: 'Include keyboard markers' }).uncheck();

    const raw = { uid: 'raw-1', source_id: 'polar-stream-vernier-raw-1', name: 'Synthetic raw Force', type: 'VernierRaw',
      numeric: true, signal: 'live', lsl_time: 1, compatible: true, reason: 'Compatible: raw Force (N)',
      channels: [{ index: 0, label: 'Force', unit: 'N', value: 2 }] };
    const heart = { uid: 'heart-1', source_id: 'heart-1', name: 'Polar heart rate', type: 'HeartRate',
      numeric: true, signal: 'live', lsl_time: 1, compatible: false, reason: 'Requires VernierRaw Force (N)',
      channels: [{ index: 0, label: 'Heart rate', unit: 'bpm', value: 72 }] };
    discovery = { streams: [raw, heart], error: null };
    await page.waitForFunction(() => document.querySelectorAll('.stream-row').length === 3);
    assert.deepEqual(await page.locator('.stream-row .stream-name').allTextContents(), ['Synthetic raw Force', 'Respyra breathing', 'Polar heart rate'], 'raw and processed streams lead the compact list');
    assert.equal(await page.locator('.stream-sub').count(), 0, 'stream chips show only one label');
    assert.equal(await page.locator('.stream-head').count(), 0, 'stream controls need no explanatory legend');
    assert.deepEqual(await page.locator('.stream-row').first().locator('.check span').allTextContents(), ['R', 'V']);
    assert.deepEqual(await page.locator('#plot-legend strong').allTextContents(), ['Force (N)'], 'viewer labels channels without repeating stream names');
    assert(!String(await page.locator('#plot-legend').textContent()).includes('waiting'));
    assert.equal(await page.locator('#vernier-source').inputValue(), raw.uid);
    assert.equal(await page.locator('#polar-source').inputValue(), '');
    assert(await page.locator('#polar-source').isDisabled());
    assert(await page.getByRole('checkbox', { name: 'Record Synthetic raw Force' }).isChecked());
    assert(await page.getByRole('checkbox', { name: 'Record Synthetic raw Force' }).isDisabled());
    assert(await page.getByRole('checkbox', { name: 'Record Respyra-Calibrated-Breathing' }).isChecked());
    assert(await page.getByRole('checkbox', { name: 'Record Respyra-Calibrated-Breathing' }).isDisabled());
    assert(!await page.getByRole('checkbox', { name: 'Record Polar heart rate' }).isChecked());
    await page.getByRole('checkbox', { name: 'Record Polar heart rate' }).check();
    assert(await page.getByRole('checkbox', { name: 'Display Polar heart rate' }).isChecked(), 'Record should also select View');
    await page.getByRole('checkbox', { name: 'Display Polar heart rate' }).uncheck();
    assert(await page.getByRole('checkbox', { name: 'Record Polar heart rate' }).isChecked(), 'View may be cleared independently');
    await page.getByRole('checkbox', { name: 'Record Polar heart rate' }).uncheck();
    assert(!await page.getByRole('checkbox', { name: 'Display Polar heart rate' }).isChecked(), 'clearing Record does not force View');
    assert(await page.locator('#start').isEnabled());
    assert.equal(await page.locator('#plot-canvas .plot-trace').count(), 0, 'one received point does not make a waveform');

    raw.lsl_time = 2; raw.channels[0].value = 3;
    await page.waitForFunction(() => document.querySelector('#plot-canvas .plot-trace[data-stream="raw-1"]'));
    const trace = await page.locator('#plot-canvas .plot-trace').first().evaluate(node => ({ min: +node.dataset.min, max: +node.dataset.max }));
    assert.deepEqual(trace, { min: 2, max: 3 });
    await page.getByRole('checkbox', { name: 'Display Polar heart rate' }).check();
    heart.lsl_time = 2; heart.channels[0].value = 74;
    await page.waitForFunction(() => document.querySelectorAll('#plot-canvas .plot-trace').length === 2);
    assert.deepEqual(await page.locator('#plot-legend strong').allTextContents(), ['Force (N)', 'Heart rate (bpm)']);
    assert.deepEqual(await page.locator('#plot-legend .plot-index').allTextContents(), ['1', '2']);
    assert.equal(await page.locator('#plot-canvas .plot-anchor').count(), 2, 'each visible channel gets a Y-axis anchor');
    assert.equal(await page.locator('#plot-canvas .plot-gridline').count(), 0, 'stacked lanes need no visible separators');
    const lanes = await page.locator('#plot-canvas .plot-trace').evaluateAll(paths => paths.map(node => {
      const top = Number(node.dataset.laneTop), bottom = Number(node.dataset.laneBottom);
      const y = [...node.getAttribute('d').matchAll(/[ML][\d.-]+ ([\d.-]+)/g)].map(match => Number(match[1]));
      return { top, bottom, within: y.every(value => value >= top - 1 && value <= bottom + 1) };
    }));
    assert(lanes[0].bottom < lanes[1].top && lanes.every(lane => lane.within), 'traces must occupy separate ordered lanes');
    assert(!await page.getByRole('checkbox', { name: 'Record Polar heart rate' }).isChecked(), 'View must not select Record');
    const keyboard = page.getByRole('checkbox', { name: 'Include keyboard markers' });
    const mouse = page.getByRole('checkbox', { name: 'Include mouse markers' });
    assert(!await keyboard.isChecked() && !await mouse.isChecked(), 'input markers start off');
    await page.keyboard.press('k');
    await page.locator('#plot-canvas').click();
    assert.equal(await page.locator('#plot-canvas .plot-input-event').count(), 0, 'unchecked input types produce no markers');
    await keyboard.check();
    await page.keyboard.press('k');
    await page.waitForFunction(() => document.querySelectorAll('#plot-canvas .plot-input-event[data-kind="keyboard"]').length === 1);
    await page.waitForTimeout(300);
    await mouse.check();
    await page.locator('#plot-canvas').click();
    await page.waitForFunction(() => document.querySelectorAll('#plot-canvas .plot-input-event[data-kind="mouse"]').length === 1);
    const inputLines = await page.locator('#plot-canvas .plot-input-event').evaluateAll(lines => lines.map(line => ({
      kind: line.dataset.kind, color: line.getAttribute('stroke'), top: Number(line.getAttribute('y1')), bottom: Number(line.getAttribute('y2')),
    })));
    assert.deepEqual(inputLines.map(line => line.kind), ['keyboard', 'mouse']);
    assert(inputLines.every(line => line.top < lanes[0].top && line.bottom > lanes[1].bottom), 'input markers cross all visible lanes');
    assert.notEqual(inputLines[0].color, inputLines[1].color, 'keyboard and mouse markers remain distinguishable');
    await page.screenshot({ path: path.join(out, 'experiment-preview-input-markers.png') });
    await keyboard.uncheck();
    await page.keyboard.press('q');
    assert.equal(await page.locator('#plot-canvas .plot-input-event[data-kind="keyboard"]').count(), 0, 'unchecking keyboard removes its markers and stops capture');
    await mouse.uncheck();
    assert.equal(await page.locator('#plot-canvas .plot-input-event').count(), 0, 'unchecking mouse removes its markers');
    await page.screenshot({ path: path.join(out, 'experiment-preview-discovered.png') });

    const second = { ...raw, uid: 'raw-2', source_id: 'polar-stream-vernier-raw-2', name: 'Second raw Force', lsl_time: 3 };
    discovery = { streams: [raw, second, heart], error: null };
    await page.waitForFunction(() => document.querySelector('#vernier-source').options.length === 3);
    await page.locator('#vernier-source').selectOption(second.uid);
    assert(await page.getByRole('checkbox', { name: 'Record Second raw Force' }).isChecked());
    assert(await page.getByRole('checkbox', { name: 'Record Second raw Force' }).isDisabled());
    assert(!await page.getByRole('checkbox', { name: 'Record Synthetic raw Force' }).isChecked(), 'old input becomes optional');
    assert(await page.getByRole('checkbox', { name: 'Record Respyra-Calibrated-Breathing' }).isChecked());

    const processed = { ...raw, uid: 'processed-1', source_id: 'respyra-breathing-raw-2',
      name: 'Respyra-Calibrated-Breathing', type: 'Respyra', compatible: false,
      channels: [{ index: 0, label: 'Breathing', unit: 'N', value: 1 }] };
    discovery = { streams: [raw, second, heart, processed], error: null };
    await page.waitForFunction(() => document.querySelector('.stream-row:nth-child(2) .stream-name')?.textContent === 'Respyra breathing' && !document.querySelector('.stream-row:nth-child(2) .stream-identity')?.title.includes('Created after calibration'));
    assert.equal(await page.getByRole('checkbox', { name: 'Record Respyra-Calibrated-Breathing' }).count(), 1, 'real Respyra outlet replaces its pending entry');
    assert(await page.getByRole('checkbox', { name: 'Record Respyra-Calibrated-Breathing' }).isChecked());
    assert(await page.getByRole('checkbox', { name: 'Record Respyra-Calibrated-Breathing' }).isDisabled());

    discovery = { streams: [raw, heart], error: null };
    await page.waitForFunction(() => document.querySelector('#vernier-source').options.length === 2);
    assert.equal(await page.locator('#vernier-source').inputValue(), '', 'a lost input must not silently switch to another belt');
    assert(await page.locator('#start').isDisabled());
    assert.equal(await page.getByRole('checkbox', { name: 'Record Respyra-Calibrated-Breathing' }).count(), 0);

    discovery = { streams: [
      { ...heart, uid: 'polar-base', name: 'Polar-H10-Mini-Mock-55596' },
      { ...heart, uid: 'polar-rate', name: 'Polar-H10-Mini-Mock-55596_heartRate' },
      { ...heart, uid: 'polar-ecg', name: 'Polar-H10-Mini-Mock-55596_rawECG' }
    ], error: null };
    await page.waitForFunction(() => document.querySelector('.stream-row .stream-name')?.textContent === 'H10 Mini');
    assert.deepEqual(await page.locator('.stream-row .stream-name').allTextContents(), ['H10 Mini', 'heartRate', 'rawECG'], 'shared outlet prefixes appear once in the selection context');

    discovery = { streams: [], error: null };
    await page.waitForFunction(() => document.querySelector('#stream-status')?.textContent === 'No LSL streams found.');
    assert.equal(await page.locator('.stream-row').count(), 0, 'vanished LSL outlets leave no stale example rows');
    assert(await page.locator('#start').isDisabled());
    for (const [width, height] of [[1200, 760], [800, 600], [390, 844]]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(80);
      assert(await page.locator('#shell').isVisible(), `both segments should fit at ${width}×${height}`);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1 || document.documentElement.scrollHeight > innerHeight + 1);
      assert(!overflow, `page should not scroll at ${width}×${height}`);
    }
    assert.deepEqual(errors, []);
    console.log('Live discovery preview checks passed: stream selection, stacked plot, keyboard/mouse markers, source changes, outlet removal, responsive fit.');
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
