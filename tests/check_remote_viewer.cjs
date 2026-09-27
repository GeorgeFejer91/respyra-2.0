// Real page modules in the Recorder's opaque iframe. Default transport is a
// deterministic bridge; RESPYRA_REAL_VDO=1 exercises public VDO instead.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

(async () => {
  const root = path.resolve(__dirname, '..');
  const recorder = process.env.RECORDER_COMPANION;
  assert(recorder, 'Set RECORDER_COMPANION to the Recorder companion directory');
  const base = 'https://georgefejer91.github.io/Remote-LSL-Recorder/';
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext();
  let child, delivery = Promise.resolve(), snapshot = {
    profile: 'respyra.observer/1', revision: 1, phase: 'waiting_recorder', inputReady: false,
    event: null, seq: null, lslTime: null, trial: null, condition: null, experimentPhase: null, screen: null,
  };
  const started = new Set(), calls = [], errors = [];
  let lanesReady = false;
  const pending = [];
  let granted = false;
  const nativeInvite = { room: `brsp_${'a'.repeat(64)}`, secret: 'b'.repeat(64), token: 'c'.repeat(64) };
  const target = await context.newPage(), viewer = await context.newPage();
  for (const page of [target, viewer]) page.on('pageerror', error => errors.push(error.message));
  const source = side => side === 'target' ? target : child;
  for (const [side, page] of [['target', target], ['viewer', viewer]]) {
    await page.exposeFunction('fixtureSend', (lane, data) => {
      const other = side === 'target' ? 'viewer' : 'target';
      const deliver = () => { delivery = delivery.then(() => source(other).evaluate(({ lane, data }) => {
        window.fixtureTransport.dispatchEvent(new CustomEvent(lane === 'control' ? 'controlmessage' : 'statemessage', { detail: { peerKey: 'fixture', data } }));
      }, { lane, data })).catch(error => errors.push(error.message)); };
      if (lanesReady) deliver(); else pending.push(deliver);
    });
    await page.exposeFunction('fixtureStart', async () => {
      started.add(side);
      if (started.size === 2) {
        await Promise.all(['target', 'viewer'].map(name => source(name).evaluate(() => {
          window.fixtureTransport.dispatchEvent(new CustomEvent('peeropen', { detail: { peerKey: 'fixture' } }));
        })));
        lanesReady = true;
        for (const deliver of pending.splice(0)) deliver();
      }
    });
  }
  await target.exposeFunction('fixtureInvoke', (command, args) => {
    if (command === 'launch_backend') return { phase: 'waiting_recorder', message: 'Waiting for marker subscriber' };
    if (command === 'viewer_action') {
      calls.push(args.action.action);
      if (args.action.action === 'start') { granted = true; return nativeInvite; }
      assert.equal(args.action.token, nativeInvite.token);
      if (args.action.action === 'stop') { granted = false; return null; }
      if (!granted) throw new Error('Grant revoked');
      return snapshot;
    }
    throw new Error(`Unexpected native mutation ${command}`);
  });
  await target.addInitScript(() => { window.__TAURI__ = { event: { listen: async () => () => {} }, core: { invoke: (command, args) => window.fixtureInvoke(command, args) } }; });
  await context.route('https://**/*', async route => {
    const url = new URL(route.request().url());
    let directory, relative;
    if (url.origin === 'https://respyra.test') { directory = path.join(root, 'web'); relative = url.pathname; }
    else if (url.href.startsWith(base + 'panels/respyra/')) { directory = path.join(root, 'companion'); relative = url.pathname.slice(new URL(base + 'panels/respyra/').pathname.length); }
    else if (url.href.startsWith(base)) { directory = recorder; relative = url.pathname.slice(new URL(base).pathname.length); }
    else return route.continue();
    if (relative === 'text-spacing.css') return route.fulfill({ contentType: 'text/css', body: '* {line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important} p {margin-bottom:2em!important}' });
    if (!process.env.RESPYRA_REAL_VDO && relative.endsWith('vendor/vdo-ninja-transport.js')) return route.fulfill({ contentType: 'text/javascript', body: `import { VdoNinjaTransport as ActualTransport } from './test-real-transport.js';
    export class VdoNinjaTransport extends ActualTransport {
      constructor(options){super(options);window.fixtureTransport=this;}
      async start(){await window.fixtureStart();}
      sendControl(_peerKey,data){void window.fixtureSend('control',data);return true;}
      sendState(_peerKey,data){void window.fixtureSend('state',data);return true;}
      async stop(){}
    }` });
    if (relative.endsWith('vendor/test-real-transport.js')) relative = relative.replace('test-real-transport.js', 'vdo-ninja-transport.js');
    const file = path.resolve(directory, '.' + (relative.startsWith('/') ? relative : '/' + relative), relative === '/' || relative === '' ? 'index.html' : '');
    if (!file.startsWith(path.resolve(directory) + path.sep)) return route.abort();
    try { await route.fulfill({ body: await fs.readFile(file), headers: { 'Access-Control-Allow-Origin': '*' }, contentType: { '.html':'text/html', '.js':'text/javascript', '.mjs':'text/javascript', '.css':'text/css', '.json':'application/json', '.woff2':'font/woff2' }[path.extname(file)] || 'application/octet-stream' }); }
    catch { await route.fulfill({ status: 404, body: 'Missing fixture file' }); }
  });
  try {
    await target.goto('https://respyra.test/index.html');
    assert.deepEqual(calls, []);
    await target.getByRole('button', { name: 'Start viewer', exact: true }).click();
    await target.locator('#viewer-qr img').waitFor();
    const link = await target.locator('#viewer-link').inputValue();
    assert(link.includes('#room='));
    assert(await target.locator('#viewer-qr img').evaluate(image => image.complete && image.naturalWidth > 0));
    await viewer.goto(base);
    await viewer.getByRole('button', { name: 'Add external page tab' }).click();
    await viewer.getByLabel('Tab name', { exact: true }).fill('Respyra 2.0');
    await viewer.getByLabel('Remote page URL').fill(link);
    await viewer.getByRole('button', { name: 'Load page', exact: true }).click();
    await viewer.frameLocator('iframe').getByRole('button', { name: 'Connect', exact: true }).waitFor();
    child = viewer.frames().find(frame => frame.url().startsWith(base + 'panels/respyra/'));
    assert(child);
    await child.locator('#connection-status').getByText('Private invitation received. Select Connect to observe Respyra.', { exact: true }).waitFor();
    assert.equal(await child.evaluate(() => location.hash), '');
    assert.equal(await child.locator('#observation').isVisible(), false);
    assert(!started.has('viewer'));
    const blocked = await child.evaluate(() => { let parentBlocked = false, storageBlocked = false; try { void parent.document.body; } catch { parentBlocked = true; } try { void localStorage.length; } catch { storageBlocked = true; } return { parentBlocked, storageBlocked }; });
    assert.deepEqual(blocked, { parentBlocked: true, storageBlocked: true });
    await child.getByRole('button', { name: 'Connect', exact: true }).click();
    await child.locator('#phase').getByText('waiting recorder', { exact: true }).waitFor({ timeout: 45000 });
    snapshot = { ...snapshot, phase: 'experiment', revision: 2, trial: 3, seq: 19, lslTime: 321.5, event: 'tracking.started', experimentPhase: 'tracking', condition: 'normal' };
    await child.locator('#trial').getByText('3', { exact: true }).waitFor();
    await child.locator('#lsl-time').getByText('321.5', { exact: true }).waitFor();
    for (const [width, size] of [[320, 16], [390, 16], [844, 16], [1280, 16], [320, 32]]) {
      await viewer.setViewportSize({ width, height: 844 });
      await child.evaluate(size => { document.documentElement.style.fontSize = size + 'px'; }, size);
      await child.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))));
      assert(await child.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `iframe overflow at ${width}/${size}`);
      const clipped = await child.locator('[data-measure]').evaluateAll(nodes => nodes.filter(node => node.getClientRects().length && (node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1)).map(node => node.textContent));
      assert.deepEqual(clipped, [], `clipped at ${width}/${size}`);
    }
    await child.addStyleTag({ url: base + 'panels/respyra/text-spacing.css' });
    assert(await child.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    assert(!(await child.locator('body').innerText()).includes(nativeInvite.secret));
    assert(!(await viewer.evaluate(() => JSON.stringify({ ...localStorage }))).includes(nativeInvite.secret));
    const route = (await child.locator('#connection-status').textContent()).match(/route (direct|relay|unknown)/u)?.[1] || 'unknown';
    await fs.mkdir(path.join(root, '.for-ai-local'), { recursive: true });
    await viewer.screenshot({ path: path.join(root, '.for-ai-local/recorder-respyra.png'), fullPage: true });
    await target.getByRole('button', { name: 'Stop viewer', exact: true }).click();
    await child.locator('#connection-status').getByText(/Disconnected/u).waitFor();
    assert.equal(granted, false);
    assert.equal(await target.locator('#viewer-link').inputValue(), '');
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ result: 'passed', transport: process.env.RESPYRA_REAL_VDO ? 'public VDO' : 'deterministic BRSP bridge', route, iframe: 'opaque', layouts: 5, native: 'mocked grant/projection', mutationCalls: 0 }));
  } catch (error) {
    console.error({ started: [...started], targetStatus: await target.locator('#viewer-status').textContent(), viewerStatus: await child?.locator('#connection-status').textContent(), errors });
    throw error;
  } finally { await context.close(); await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
