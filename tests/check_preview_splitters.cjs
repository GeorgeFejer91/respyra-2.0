const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');

(async () => {
  const web = path.resolve(__dirname, '../web');
  const captures = path.resolve(__dirname, '../.for-ai-local');
  await fs.mkdir(captures, { recursive: true });
  const sample = { streams: Array.from({ length: 6 }, (_, index) => ({
    uid: `stream-${index}`, name: index ? `Example stream ${index}` : 'Vernier Stream Mini',
    source_id: `source-${index}`, type: 'VernierRaw', signal: 'live', compatible: index === 0,
    numeric: true, channels: [{ index: 0, label: 'Force', unit: 'N', value: index + 1 }],
    lsl_time: index + 1, reason: 'receiving samples',
  })) };
  const server = http.createServer(async (request, response) => {
    if (request.url === '/api/streams') { response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify(sample)); return; }
    if (request.url === '/api/refresh') { response.end('{}'); return; }
    const file = path.resolve(web, '.' + new URL(request.url, 'http://localhost').pathname);
    if (!file.startsWith(web + path.sep)) { response.writeHead(403).end(); return; }
    try {
      const data = await fs.readFile(file);
      response.setHeader('Content-Type', { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.mjs': 'text/javascript', '.woff2': 'font/woff2' }[path.extname(file)] || 'application/octet-stream');
      response.end(data);
    } catch { response.writeHead(404).end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1200, height: 760 } });
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  const geometry = () => page.evaluate(() => {
    const box = selector => {
      const { x, y, width, height } = document.querySelector(selector).getBoundingClientRect();
      return { x, y, width, height };
    };
    const regions = ['#shell', '.content', '#hub', '#streams', '#hub-body', '#stream-body', '#stream-selection', '.stream-section', '#stream-list', '#plot-section'];
    return {
      visible: !document.querySelector('#shell').hidden,
      overflow: document.documentElement.scrollWidth > innerWidth + 1 || document.documentElement.scrollHeight > innerHeight + 1 ||
        regions.some(selector => { const element = document.querySelector(selector); return element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1; }),
      hub: box('#hub'), streams: box('#streams'), selection: box('#stream-selection'), plot: box('#plot-section'), canvas: box('#plot-canvas'),
      variableGap: box('#hub .section').y - (box('.participant').y + box('.participant').height),
      rows: document.querySelectorAll('.stream-row').length,
    };
  });
  const drag = async (selector, dx, dy) => {
    const box = await page.locator(selector).boundingBox();
    const x = box.x + box.width / 2, y = box.y + box.height / 2;
    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.mouse.move(x + dx, y + dy, { steps: 4 });
    await page.mouse.up();
    await page.waitForTimeout(100);
  };
  try {
    await page.goto(`http://127.0.0.1:${server.address().port}/experiment-hub-preview.html`);
    await page.waitForFunction(() => document.querySelector('.stream-row')?.dataset.pretextRowHeight, null, { timeout: 5000 }).catch(async error => {
      throw new Error(`${error.message}; page errors: ${errors.join(' | ')}; rows: ${await page.locator('.stream-row').count()}; stream list: ${await page.locator('#stream-list').textContent()}; no-fit: ${await page.locator('#no-fit').isVisible()}`);
    });
    let initial = await geometry();
    assert(initial.visible && !initial.overflow && initial.rows >= 6, JSON.stringify(initial));
    assert(initial.plot.y + initial.plot.height - initial.canvas.y - initial.canvas.height < 8, `plot should fill its region: ${JSON.stringify(initial)}`);
    await page.screenshot({ path: path.join(captures, 'preview-splitters-initial.png') });

    await drag('#hub-divider', -80, 0);
    const narrowHub = await geometry();
    assert(narrowHub.hub.width < initial.hub.width - 60 && narrowHub.streams.width > initial.streams.width + 60, 'side divider should exchange width');
    assert(!narrowHub.overflow && narrowHub.visible, 'narrow hub should fit');
    await page.locator('#hub-divider').focus();
    await page.keyboard.press('ArrowRight');
    const keyboardHub = await geometry();
    assert(keyboardHub.hub.width > narrowHub.hub.width + 15, 'side divider should support arrow keys');

    await drag('#selection-divider', 0, 90);
    const tallSelection = await geometry();
    assert(tallSelection.selection.height > keyboardHub.selection.height + 65, 'stream selection should grow');
    assert(tallSelection.plot.height < keyboardHub.plot.height - 65, 'plot should give up height');
    assert(!tallSelection.overflow && tallSelection.visible, 'resized selection should fit');
    await page.screenshot({ path: path.join(captures, 'preview-splitters-resized.png') });
    await page.locator('#selection-divider').focus();
    await page.keyboard.press('ArrowUp');
    const keyboardSelection = await geometry();
    assert(keyboardSelection.selection.height < tallSelection.selection.height - 15, 'height divider should support arrow keys');

    await page.reload();
    await page.waitForFunction(() => document.querySelector('.stream-row')?.dataset.pretextRowHeight);
    const restored = await geometry();
    assert(Math.abs(restored.hub.width - keyboardHub.hub.width) < 3, 'hub size should persist');
    assert(Math.abs(restored.selection.height - keyboardSelection.selection.height) < 3, 'selection size should persist');
    assert(!restored.overflow && restored.visible);

    await page.setViewportSize({ width: 1200, height: 1000 });
    await page.waitForTimeout(100);
    const tall = await geometry();
    assert(tall.visible && !tall.overflow && tall.variableGap > restored.variableGap, 'hub groups should stretch with height');
    await page.setViewportSize({ width: 800, height: 600 });
    await page.waitForTimeout(100);
    const compact = await geometry();
    assert(compact.visible && !compact.overflow, `compact layout should fit: ${JSON.stringify(compact)}`);
    await page.setViewportSize({ width: 1200, height: 900 });
    await page.evaluate(() => { document.documentElement.style.fontSize = '28px'; window.dispatchEvent(new Event('resize')); });
    await page.waitForTimeout(100);
    const enlarged = await geometry();
    assert(enlarged.visible && !enlarged.overflow, `200% text should fit: ${JSON.stringify(enlarged)}`);
    await page.evaluate(() => { document.documentElement.style.fontSize = ''; window.dispatchEvent(new Event('resize')); });
    await page.waitForTimeout(100);
    for (const index of [1, 2, 3, 4]) await page.getByRole('checkbox', { name: `Display Example stream ${index}` }).check();
    await page.waitForFunction(() => !document.querySelector('#channel-pager').hidden);
    const manyChannels = await geometry();
    assert(!await page.locator('#channel-pager').isHidden(), `channel pager should appear; checked views: ${await page.locator('.stream-row input[aria-label^="Display "]:checked').count()}; count: ${await page.locator('#plot-count').textContent()}`);
    assert(manyChannels.visible && !manyChannels.overflow, 'channel pager should keep the plot bounded');
    assert(manyChannels.plot.y + manyChannels.plot.height - manyChannels.canvas.y - manyChannels.canvas.height < 8, 'plot should still fill the viewer with a pager');
    const anchorY = await page.locator('#plot-canvas .plot-anchor').evaluateAll(lines => lines.map(line => Number(line.getAttribute('y1'))));
    assert(anchorY.length >= 1 && anchorY.length <= 4 && anchorY.every((y, index) => !index || y > anchorY[index - 1]), 'visible channel anchors should stack in order');
    await page.evaluate(() => { document.documentElement.style.fontSize = '28px'; window.dispatchEvent(new Event('resize')); });
    await page.waitForTimeout(100);
    const enlargedChannels = await geometry();
    assert(enlargedChannels.visible && !enlargedChannels.overflow, 'stacked lanes should fit with 200% text');
    await page.evaluate(() => { document.documentElement.style.fontSize = ''; window.dispatchEvent(new Event('resize')); });
    await page.waitForTimeout(100);
    for (const [width, height] of [[761, 900], [760, 900], [390, 844]]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(100);
      const small = await geometry();
      assert(small.visible && !small.overflow, `${width}×${height} should fit: ${JSON.stringify(small)}`);
    }
    await page.setViewportSize({ width: 1200, height: 760 });
    await page.waitForTimeout(100);
    await page.locator('#selection-divider').focus();
    await page.keyboard.press('Home');
    await page.waitForTimeout(100);
    const maximumViewer = await geometry();
    assert(maximumViewer.visible && !maximumViewer.overflow, `maximum viewer should fit: ${JSON.stringify(maximumViewer)}`);
    await page.locator('#hub-divider').focus();
    await page.keyboard.press('Home');
    await page.waitForTimeout(100);
    const minimumHub = await geometry();
    assert(minimumHub.visible && !minimumHub.overflow, `minimum hub should fit: ${JSON.stringify(minimumHub)}`);
    await page.setViewportSize({ width: 320, height: 568 });
    await page.waitForTimeout(100);
    assert(await page.locator('#no-fit').isVisible(), 'unsupported minimum should show the explicit no-fit message');
    await page.setViewportSize({ width: 1200, height: 760 });
    await page.waitForTimeout(100);
    assert((await geometry()).visible, 'supported size should recover from no-fit');
    assert.deepEqual(errors, []);
    console.log('Preview splitters passed: drag, keyboard, persistence, stretch, and compact no-scroll layout.');
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
