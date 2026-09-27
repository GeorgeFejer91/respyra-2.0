// Real page modules in the Recorder's opaque iframe. Default transport is a
// deterministic bridge; RESPYRA_REAL_VDO=1 exercises public VDO instead.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

(async () => {
  const root = path.resolve(__dirname, '..');
  const {validateControllerState} = await import('../web/remote-profile.js');
  const recorder = process.env.RECORDER_COMPANION;
  assert(recorder, 'Set RECORDER_COMPANION to the Recorder companion directory');
  const base = 'https://georgefejer91.github.io/Remote-LSL-Recorder/';
  const panelBase = 'https://georgefejer91.github.io/respyra-2.0/';
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext();
  let child, delivery = Promise.resolve(), snapshot = {
    profile:'respyra.controller/1', revision:1, monitorRevision:1, phase:'starting',
    message:'Marker outlet online', setup:null, progress:null,
  };
  const setup = { phase:'setup',ui_seq:0,study_name:'Respyra breathing validation',
    values:{participant:'',session:'001'},message:'Choose a Force stream',busy:false,
    can_start:false,can_use:false,selected_row:null,streams:[],source:null,omitted_streams:0,
    marker_name:'Respyra-Events',save_csv:false };
  let mutations = 0, ownerClaimed = false;
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
    if (command === 'launch_backend') return { phase: 'starting', message: 'Marker outlet online' };
    if (command === 'viewer_action') {
      calls.push(args.action.action);
      if (args.action.action === 'start') { granted = true; return nativeInvite; }
      assert.equal(args.action.token, nativeInvite.token);
      if (args.action.action === 'stop') { granted = false; return null; }
      if (!granted) throw new Error('Grant revoked');
      if (args.action.action === 'claim') { ownerClaimed = true; return {owner:'d'.repeat(64)}; }
      assert(ownerClaimed, 'No state or commands before native ownership');
      assert.equal(args.action.owner,'d'.repeat(64));
      if (args.action.action === 'dispatch') {
        const command = args.action.command;
        if (command.action === 'renew') return {ok:true,revision:snapshot.revision,result:null,error:null};
        assert.equal(command.expectedRevision,snapshot.revision,'Stale control revision');
        mutations++;
        setup.ui_seq++;
        const a=command.args;
        if(command.action==='field_edit') setup.values[a.field]=a.value;
        if(command.action==='scan') setup.streams=[
          {row:0,source_id:'processed',stream_name:'Normalized breathing',stream_type:'Respiration',compatible:false,reason:'Requires raw Force in N',force_channel_index:null},
          {row:1,source_id:'polar-stream-vernier-raw-'+ 'device'.repeat(25),stream_name:'Synthetic raw Force',stream_type:'VernierRaw',compatible:true,reason:'Compatible raw Force (N)',force_channel_index:1}];
        if(command.action==='select') {setup.selected_row=a.row;setup.can_use=setup.streams[a.row].compatible;}
        if(command.action==='use') setup.source={source_id:setup.streams[setup.selected_row].source_id,stream_name:'Synthetic raw Force'};
        setup.can_start=!!setup.source && Object.values(setup.values).every(value=>value.trim());
        snapshot.revision++;snapshot.monitorRevision++;
        if(command.action==='start') {snapshot.phase='experiment';snapshot.setup=null;}
        if(command.action==='abort') {snapshot.phase='finished';snapshot.setup=null;}
        return {ok:true,revision:snapshot.revision,result:null,error:null};
      }
      if(!validateControllerState(snapshot)) errors.push('Invalid synthetic controller projection: '+JSON.stringify(snapshot));
      assert(validateControllerState(snapshot),'Invalid synthetic controller projection');
      return snapshot;
    }
    throw new Error(`Unexpected native mutation ${command}`);
  });
  await target.addInitScript(() => { window.__TAURI__ = { event: { listen: async () => () => {} }, core: { invoke: (command, args) => window.fixtureInvoke(command, args) } }; });
  await context.route('https://**/*', async route => {
    const url = new URL(route.request().url());
    let directory, relative;
    if (url.origin === 'https://respyra.test') { directory = path.join(root, 'web'); relative = url.pathname; }
    else if (url.href.startsWith(panelBase)) { directory = path.join(root, 'companion'); relative = url.pathname.slice(new URL(panelBase).pathname.length); }
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
    await target.locator('.viewer-setup > summary').click();
    await target.getByRole('button', { name: 'Enable phone control', exact: true }).click();
    await target.locator('#viewer-qr img').waitFor();
    const link = await target.locator('#viewer-link').inputValue();
    assert(link.includes('#room='));
    assert(await target.locator('#viewer-qr img').evaluate(image => image.complete && image.naturalWidth > 0));
    await target.locator('dialog[open] > button').click();
    await viewer.goto(base);
    await viewer.getByRole('button', { name: 'Add external page tab' }).click();
    await viewer.getByLabel('Tab name', { exact: true }).fill('Respyra 2.0');
    await viewer.getByLabel('Remote page URL').fill(link);
    await viewer.getByRole('button', { name: 'Load page', exact: true }).click();
    await viewer.frameLocator('iframe').getByRole('button', { name: 'Connect', exact: true }).waitFor();
    child = viewer.frames().find(frame => frame.url().startsWith(panelBase));
    assert(child);
    await child.locator('#connection-status').getByText('Private invitation received. Select Connect to control Respyra.', { exact: true }).waitFor();
    assert.equal(await child.evaluate(() => location.hash), '');
    assert.equal(await child.locator('#controller').isVisible(), false);
    assert(!started.has('viewer'));
    const blocked = await child.evaluate(() => { let parentBlocked = false, storageBlocked = false; try { void parent.document.body; } catch { parentBlocked = true; } try { void localStorage.length; } catch { storageBlocked = true; } return { parentBlocked, storageBlocked }; });
    assert.deepEqual(blocked, { parentBlocked: true, storageBlocked: true });
    await child.getByRole('button', { name: 'Connect', exact: true }).click();
    await child.locator('#phase').getByText('Starting', { exact: true }).waitFor({ timeout: 45000 });
    assert.equal(mutations,0);
    snapshot={...snapshot,phase:'setup',revision:2,monitorRevision:2,setup,
      progress:{phase:'progress',health:{signal:'not_selected',sample_age_ms:null,battery_percent:null}}};
    await child.locator('#remote-view').selectOption('controls');
    await child.locator('#participant').fill('synthetic-phone');
    await child.locator('#participant').press('ArrowLeft');
    await child.locator('#session').fill('002');
    await child.locator('#input-details summary').click();
    await child.locator('#scan').click();
    await child.locator('input[value="0"]').click();
    await child.waitForFunction(()=>document.querySelector('input[value="0"]').checked && !document.getElementById('controls').disabled);
    assert(await child.locator('#use').isDisabled());
    await child.locator('input[value="1"]').click();
    await child.waitForFunction(()=>document.querySelector('input[value="1"]').checked && !document.getElementById('controls').disabled);
    await child.locator('#use').click();
    await child.waitForFunction(()=>!document.getElementById('start').disabled);
    assert.equal(setup.values.participant,'synthetic-phone');
    assert.equal(setup.values.session,'002');
    assert.equal(await child.locator('#battery').textContent(),'Not reported');
    await child.locator('#start').click();
    await child.locator('#phase').getByText('Running', {exact:true}).waitFor();
    snapshot = { ...snapshot, progress:{phase:'progress',trial:3,seq:19,lsl_time:321.5,event:'tracking.started',
      experiment_phase:'tracking',condition:'normal',screen:null,health:{signal:'live',sample_age_ms:100,battery_percent:null}} };
    await child.locator('#trial-summary').getByText(' · Trial 3 · normal', { exact: true }).waitFor();
    assert.equal(await child.locator('.diagnostics').getAttribute('open'), null);
    assert.equal(await child.locator('#invitation-field').isVisible(), false);
    await child.locator('.diagnostics summary').click();
    await child.locator('#lsl-time').getByText('321.5', { exact: true }).waitFor();
    for (const [width, size, height=844] of [[320, 16], [390, 16], [844, 16], [1280, 16], [320, 32], [844, 16, 390]]) {
      await viewer.setViewportSize({ width, height });
      await child.evaluate(size => { document.documentElement.style.fontSize = size + 'px'; }, size);
      await child.evaluate(() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done))));
      assert(await child.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `iframe overflow at ${width}/${size}`);
      const clipped = await child.locator('[data-measure]').evaluateAll(nodes => nodes.filter(node => node.getClientRects().length && (node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1)).map(node => node.textContent));
      assert.deepEqual(clipped, [], `clipped at ${width}/${size}`);
    }
    const spacingStyle=await child.addStyleTag({ url: panelBase + 'text-spacing.css' });
    assert(await child.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    assert(!(await child.locator('body').innerText()).includes(nativeInvite.secret));
    assert(!(await viewer.evaluate(() => JSON.stringify({ ...localStorage }))).includes(nativeInvite.secret));
    const route = (await child.locator('#route').textContent()).match(/route: (direct|relay|unknown)/u)?.[1] || 'unknown';
    await fs.mkdir(path.join(root, '.for-ai-local'), { recursive: true });
    await child.locator('.diagnostics summary').click();
    await child.locator('#remote-view').selectOption('data');
    await spacingStyle.evaluate(element=>element.remove());
    await child.evaluate(()=>{document.documentElement.style.fontSize='16px';window.scrollTo(0,0);});
    await viewer.setViewportSize({width:390,height:844});
    for (let i=0;i<3;i++) {
      snapshot={...snapshot,monitorRevision:snapshot.monitorRevision+1,
        progress:{...snapshot.progress,markers:{name:'Respyra-Events',source_id:'event-proof',online:true,emitted:19},
          recent:[{event:'tracking.started',seq:19,lsl_time:321.5}],
          health:{signal:'live',sample_age_ms:100,battery_percent:null,
            preview:{source_id:'synthetic-force',name:'Synthetic raw Force',force_index:1,lsl_time:321+i*.25,
              channels:[{index:0,label:'Respiration Rate',unit:'breaths/min',value:12}, {index:1,label:'Force',unit:'N',value:5+i}]}}}};
      await new Promise(resolve=>setTimeout(resolve,300));
    }
    await child.waitForFunction(()=>document.getElementById('trace-line').getAttribute('d')?.includes('L'));
    await child.locator('#monitor-channel').selectOption('0');
    assert.equal(await child.locator('#monitor-value').textContent(),'Live · 12.000 breaths/min');
    assert.equal(await child.locator('#monitor-markers li').textContent(),'19 · tracking.started');
    assert((await child.locator('#trace-markers').getAttribute('d')).includes('V140'));
    for (const [width,size,height=844] of [[320,16],[390,16],[844,16],[1280,16],[320,32],[844,16,390]]) {
      await viewer.setViewportSize({width,height});
      await child.evaluate(size=>{document.documentElement.style.fontSize=size+'px';},size);
      await child.evaluate(()=>new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done))));
      assert(await child.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`monitor overflow at ${width}/${size}`);
      const clipped=await child.locator('[data-measure]').evaluateAll(nodes=>nodes.filter(node=>node.getClientRects().length && (node.scrollWidth>node.clientWidth+1 || node.scrollHeight>node.clientHeight+1)).map(node=>node.textContent));
      assert.deepEqual(clipped,[],`monitor clipped at ${width}/${size}`);
    }
    await child.addStyleTag({url:panelBase+'text-spacing.css'});
    assert(await child.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await child.evaluate(()=>{document.documentElement.style.fontSize='16px';document.querySelector('link[href$="text-spacing.css"]')?.remove();window.scrollTo(0,0);});
    await viewer.setViewportSize({width:390,height:844});
    await viewer.screenshot({ path: path.join(root, '.for-ai-local/recorder-respyra.png'), fullPage: true });
    await child.locator('#abort').click();
    await child.locator('#phase').getByText('Finished', {exact:true}).waitFor();
    assert(mutations>=8,'Setup, selection, start and stop reached the target');
    await target.locator('.viewer-setup > summary').click();
    await target.getByRole('button', { name: 'Disable phone control', exact: true }).click();
    await child.locator('#connection-status').getByText(/Disconnected/u).waitFor();
    assert.equal(granted, false);
    assert.equal(await target.locator('#viewer-link').inputValue(), '');
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ result:'passed',transport:process.env.RESPYRA_REAL_VDO ? 'public VDO' : 'deterministic BRSP bridge',route,iframe:'opaque',layouts:12,native:'mocked ownership and backend',mutationCalls:mutations }));
  } catch (error) {
    console.error({ started: [...started], targetStatus: await target.locator('#viewer-status').textContent(), viewerStatus: await child?.locator('#connection-status').textContent(), errors,
      layout:await target.evaluate(()=>({view:document.body.dataset.view,mainHidden:document.querySelector('main').hidden,
        height:document.querySelector('main').getBoundingClientRect().height,viewport:innerHeight,notice:document.getElementById('viewport-notice').hidden})),
      controls:await child?.evaluate(()=>({view:document.body.dataset.view,phase:document.getElementById('controller').dataset.phase,hidden:document.getElementById('controller').hidden})) });
    throw error;
  } finally { await context.close(); await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
