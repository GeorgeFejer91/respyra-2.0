const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const http = require('node:http');
  const fs = require('node:fs/promises');
  const path = require('node:path');
  const web = path.resolve(__dirname, '../web');
  const server = http.createServer(async (req, res) => {
    const file = path.resolve(web, '.' + (req.url === '/' ? '/index.html' : req.url));
    if (!file.startsWith(web + path.sep)) { res.writeHead(403); res.end(); return; }
    try {
      const bytes = await fs.readFile(file);
      res.setHeader('Content-Type', {'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.woff2':'font/woff2'}[path.extname(file)] || 'application/octet-stream');
      res.end(bytes);
    } catch { res.writeHead(404); res.end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({channel:'chrome', headless:true});
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.addInitScript(() => {
    let listener;
    const state = { phase:'setup', ui_seq:0, study_name:'Respyra breathing validation', values:{participant:'',session:'001'}, marker_name:'Respyra-Events',save_csv:false, message:'No breathing input selected.', busy:false, can_start:false, can_use:false, selected_row:null, streams:[], source:null };
    window.testActions = [];
    window.testProgress = progress => {
      state.progress = {...state.progress,...progress};
      listener({payload:structuredClone(state)});
    };
    window.testRecording = recording => window.testProgress({...state.progress,phase:'progress',recording});
    window.testSnapshot = () => structuredClone(state.progress);
    window.__TAURI__ = { event:{listen:async (_name, cb) => {listener=cb; return () => {}; }}, core:{invoke:async (command,args) => {
      if(command === 'launch_backend') return structuredClone(state);
      if(command === 'close_app') return;
      const a=args.action; window.testActions.push(a); state.ui_seq=a.ui_seq;
      if(a.action==='field_edit') state.values[a.field]=a.value;
      if(a.action==='option') state[a.field]=a.enabled;
      if(a.action==='scan') {state.selected_row=null;state.can_use=false;state.streams=[{source_id:'processed',stream_name:'Normalized breathing',stream_type:'Respiration',compatible:false,reason:'Requires raw Force in N'}, {source_id:'polar-stream-vernier-raw-'+ 'device'.repeat(25), stream_name:'Synthetic Vernier Force',stream_type:'VernierRaw',compatible:true,reason:'Compatible: raw Force (N)',force_channel_index:1}];}
      if(a.action==='select') {state.selected_row=a.row; state.can_use=state.streams[a.row].compatible;}
      if(a.action==='use') {state.source={source_id:state.streams[state.selected_row].source_id,stream_name:state.streams[state.selected_row].stream_name};state.message='Ready for this experiment.';}
      state.can_start=!!state.source && Object.values(state.values).every(v=>v.trim());
      if(a.action==='start') {state.phase='experiment';state.message='Experiment running in PsychoPy.';}
      if(a.action==='cancel') {state.phase='finished';state.message='Experiment ended.';}
      listener({payload:structuredClone(state)});
      return {ok:true};
    }}};
  });
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.waitForTimeout(200);
  await page.waitForFunction(() => !document.getElementById('controls').disabled);
  await page.waitForTimeout(100);
  await page.locator('#participant').fill('synthetic participant');
  await page.locator('#participant').press('ArrowLeft');
  await page.locator('#session').fill('002');
  await page.locator('#record_keyboard').check();
  await page.locator('#record_mouse').check();
  await page.locator('#input-settings > summary').click();
  await page.locator('#save_csv').check();
  assert(await page.locator('#save_csv').isChecked());
  assert(await page.locator('#start').isDisabled());
  await page.locator('#scan').click();
  await page.locator('input[value="0"]').check();
  assert(await page.locator('#use').isDisabled());
  await page.locator('#streams + .page-actions button').last().click();
  assert(await page.locator('main').isVisible(), 'Stream selection must fit');
  await page.locator('input[value="1"]').check();
  await page.locator('#use').click();
  await page.waitForFunction(()=>!document.getElementById('start').disabled);
  assert.equal(await page.locator('#participant').inputValue(), 'synthetic participant');
  await page.locator('#scan').click();
  await page.waitForFunction(()=>![...document.querySelectorAll('#streams input')].some(r=>r.checked));
  await page.locator('#streams + .page-actions button').last().click();
  await page.locator('input[value="1"]').check();
  assert(!(await page.locator('#use').isDisabled()), 'Unchanged scan results must still be selectable');
  await page.locator('dialog[open] > button').click();
  for(const [width,textSize,spacing] of [[320,16,false],[820,16,false],[1440,16,false],[320,32,false],[820,32,true]]) {
    await page.setViewportSize({width,height:900});
    await page.evaluate(({textSize,spacing})=>{
      document.documentElement.style.fontSize=textSize+'px';
      if(spacing) {const s=document.createElement('style');s.textContent='* {line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important} p {margin-bottom:2em!important}';document.head.append(s);}
    },{textSize,spacing});
    await page.waitForTimeout(150);
    const layout=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1, clipped:[...document.querySelectorAll('[data-measure]')].filter(e=>e.getClientRects().length && (e.scrollWidth>e.clientWidth+1||e.scrollHeight>e.clientHeight+1)).map(e=>e.textContent), measured:document.querySelectorAll('[data-pretext-fit]').length}));
    assert.equal(layout.overflow,false,JSON.stringify({width,textSize,spacing,layout}));
    assert.deepEqual(layout.clipped,[],JSON.stringify({width,textSize,spacing,layout}));
    assert(layout.measured>5);
  }
  await page.setViewportSize({width:820,height:1000});
  await page.evaluate(()=>{document.documentElement.style.fontSize='16px';document.querySelector('style')?.remove();});
  await page.evaluate(() => window.testRecording({phase:'recording',bytes_written:4096,
    output_file:'C:/Respira/data/test.xdf.partial', streams:[
      {name:'Raw Force',source_id:'force-proof'}, {name:'Late respiration',source_id:'late-'+'device'.repeat(30)}]}));
  for(let i=0;i<3;i++) await page.evaluate(i=>window.testProgress({
    phase:'progress',markers:{name:'Respyra-Events',emitted:19},recent:[
      {event:'calibration.completed',seq:18,lsl_time:321.25},{event:'tracking.started',seq:19,lsl_time:321.5}],
    health:{signal:'live',sample_age_ms:100,battery_percent:null,preview:{source_id:'force-proof',name:'Raw Force',force_index:1,lsl_time:321+i*.25,
      channels:[{index:0,label:'Respiration Rate',unit:'breaths/min',value:12},{index:1,label:'Force',unit:'N',value:5+i}]}},
    streams:[{uid:'raw-proof',source_id:'force-proof',name:'Raw Force',type:'VernierRaw',numeric:true,signal:'live',lsl_time:321+i*.25,
      channels:[{index:0,label:'Respiration Rate',unit:'breaths/min',value:12},{index:1,label:'Force',unit:'N',value:5+i}]},
      {uid:'other-proof',source_id:'other-proof',name:'Other device',type:'Signal',numeric:true,signal:'live',lsl_time:321+i*.25,
       channels:[0,1,2,3].map(index=>({index,label:'Signal '+index,unit:'mV',value:index+i}))},
      {uid:'external-markers',source_id:'external-markers',name:'External events',type:'Markers',numeric:false,signal:'live',lsl_time:321.1,
       channels:[{index:0,label:'Events',unit:'',value:'device.trigger'}]}]}),i);
  assert.equal(await page.locator('#view').count(), 0, 'The control center has no view picker');
  for (const [width,height] of [[820,760],[1440,900]]) {
    await page.setViewportSize({width,height});
    await page.waitForTimeout(100);
    assert(await page.locator('main').isVisible(), JSON.stringify({width,height,geometry:await page.evaluate(()=>{
      document.querySelector('main').hidden=false;
      return [...document.querySelectorAll('main > *, #controller > *')].map(e=>({id:e.id,tag:e.tagName,height:e.getBoundingClientRect().height,bottom:e.getBoundingClientRect().bottom}));
    })}));
    for (const id of ['setup','stream-overview','observation','recording-panel']) assert(await page.locator('#'+id).isVisible(), id+' must remain visible together');
    const fit = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight,
      clipped: [...document.querySelectorAll('[data-measure]')].filter(e => e.getClientRects().length && (e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1)).map(e => e.textContent)
    }));
    assert(fit.width <= width + 1 && fit.height <= height + 1, JSON.stringify({width,height,fit}));
    assert.deepEqual(fit.clipped, [], JSON.stringify({width,height,fit}));
  }
  await page.setViewportSize({width:820,height:760});
  assert.equal(await page.locator('#available-streams [role=tab]').count(),2);
  assert.equal(await page.locator('#channel-stack .channel-trace').count(),6);
  assert.equal(await page.locator('#channel-stack .trace-markers').count(),0, 'Markers have no channel lane');
  assert.equal(await page.locator('#marker-overlay line').count(),3, 'Program and external markers cross the shared plot');
  assert.equal(await page.locator('#marker-overlay line').first().getAttribute('y2'),'100');
  assert.notEqual(await page.locator('#marker-overlay line').first().getAttribute('stroke'),
    await page.locator('#marker-overlay line').last().getAttribute('stroke'), 'Marker groups have distinct colors');
  await page.locator('#tab-all').focus();
  await page.keyboard.press('ArrowRight');
  assert.equal(await page.locator('[data-preview="stream:raw-proof"]').getAttribute('aria-selected'),'true');
  await page.keyboard.press('Home');
  assert.equal(await page.locator('#tab-all').getAttribute('aria-selected'),'true');
  await page.locator('[data-preview="stream:other-proof"]').click();
  assert.equal(await page.locator('#channel-stack .channel-trace').count(),4);
  await page.locator('[data-preview="stream:raw-proof"]').click();
  assert.equal(await page.locator('#channel-stack .channel-trace').count(),2);
  await page.locator('#tab-markers').click();
  assert(await page.locator('#marker-panel').isVisible());
  const catalog = JSON.parse(await fs.readFile(path.resolve(web, '../src/mpi/event_markers/catalog.json'), 'utf8'));
  assert.equal(await page.locator('#marker-list .marker-definition').count(), Object.keys(catalog.events).length);
  assert(await page.locator('main').isVisible(), 'Marker catalog fits the active view');
  await page.screenshot({path:'.for-ai-local/html-markers.png',fullPage:true});
  await page.locator('#marker-filter').fill('tracking.started');
  assert(await page.locator('#marker-list').getByText('tracking.started', {exact:true}).isVisible());
  await page.locator('#marker-filter').fill('no-such-event');
  assert(await page.locator('#marker-list').getByText('No matching event markers.').isVisible());
  await page.locator('#marker-filter').fill('');
  await page.locator('#marker-list + .page-actions button').last().click();
  assert(await page.locator('#marker-list .marker-definition').nth(4).isVisible(), 'Catalog pages retain later events');
  await page.locator('#tab-all').click();
  const savedProgress = await page.evaluate(() => window.testSnapshot());
  await page.evaluate(progress => window.testProgress({...progress, streams:[...progress.streams,
    ...['late-a','late-b'].map(uid => ({uid,source_id:uid,name:uid,type:'Signal',numeric:true,signal:'live',lsl_time:321.5,
      channels:[{index:0,label:'Force',unit:'N',value:1}]}))]}), savedProgress);
  const streamNext = page.locator('.stream-tabs + .page-actions button').last();
  while (await streamNext.isEnabled()) await streamNext.click();
  assert(await page.locator('[data-preview="stream:late-b"]').isVisible(), 'Later streams remain reachable by tab paging');
  await page.locator('[data-preview="stream:late-b"]').click();
  assert.equal(await page.locator('#channel-stack .channel-trace').count(),1);
  await page.locator('.stream-tabs + .page-actions button').first().click();
  assert.equal(await page.locator('#tab-all').getAttribute('aria-selected'),'true', 'Paging away keeps a visible active tab');
  await page.evaluate(progress => window.testProgress(progress), savedProgress);
  await page.locator('#tab-all').click();
  for (const tab of ['#tab-all', '#tab-markers']) {
    await page.setViewportSize({width:820,height:760});
    await page.locator(tab).click();
    await page.setViewportSize({width:320,height:900});
    await page.waitForTimeout(100);
    const layout = await page.evaluate(() => ({
      main: !document.querySelector('main').hidden, notice: !document.getElementById('viewport-notice').hidden,
      overflow: document.documentElement.scrollWidth > innerWidth + 1 || document.documentElement.scrollHeight > innerHeight + 1,
      clipped: [...document.querySelectorAll('[data-measure]')].filter(e => e.getClientRects().length &&
        (e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1)).map(e => e.textContent)
    }));
    assert(layout.main || layout.notice, JSON.stringify(layout));
    assert.equal(layout.overflow, false, JSON.stringify(layout));
    assert.deepEqual(layout.clipped, [], JSON.stringify(layout));
  }
  await page.setViewportSize({width:820,height:760});
  await page.locator('#tab-all').click();
  assert(await page.evaluate(()=>{
    const bounds=document.getElementById('start').getBoundingClientRect();
    return Math.abs(bounds.left + bounds.width / 2 - innerWidth / 2) < 2;
  }), 'Start is centered in the action bar');
  assert(await page.locator('#channel-stack .trace-line').first().getAttribute('d'));
  await page.locator('.plot-frame + .page-actions button').last().click();
  assert(await page.locator('#channel-stack .channel-trace').last().isVisible());
  await page.locator('.plot-frame + .page-actions button').first().click();
  await page.setViewportSize({width:820,height:650});
  await page.waitForTimeout(100);
  assert(await page.locator('main').isVisible(), 'Paging adapts to short windows');
  const channelNext = page.locator('.plot-frame + .page-actions button').last();
  while (await channelNext.isEnabled()) await channelNext.click();
  assert(await page.locator('#channel-stack .channel-trace').last().isVisible());
  await page.setViewportSize({width:820,height:760});
  const channelPrevious = page.locator('.plot-frame + .page-actions button').first();
  while (await channelPrevious.isEnabled()) await channelPrevious.click();
  await page.locator('#recording-details > summary').click();
  await page.locator('#recorded-streams + .page-actions button').last().click();
  assert(await page.locator('#recorded-streams li').filter({hasText:'Late respiration'}).isVisible());
  assert((await page.locator('#recording-status').textContent()).includes('4096 bytes'));
  await page.waitForTimeout(100);
  assert(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight + 1 && document.documentElement.scrollWidth <= innerWidth + 1));
  await page.locator('dialog[open] > button').click();
  await page.setViewportSize({width:320,height:480});
  await page.evaluate(() => { document.documentElement.style.fontSize = '32px'; });
  await page.waitForTimeout(150);
  assert(await page.locator('#viewport-notice').isVisible(), 'Impossible fits must be explicit');
  assert((await page.locator('#viewport-notice').innerText()).includes('Enlarge the window'));
  assert(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight + 1 && document.documentElement.scrollWidth <= innerWidth + 1));
  await page.evaluate(() => { document.documentElement.style.fontSize = '16px'; });
  await page.setViewportSize({width:820,height:760});
  await page.locator('#input-settings > summary').click();
  assert(await page.locator('#marker_name').isEnabled());
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('dialog[open]').count(), 0);
  assert(await page.locator('#start').isEnabled(), 'Escape closes settings without cancelling the experiment');
  await page.screenshot({path:'.for-ai-local/html-setup.png',fullPage:true});
  await page.locator('#start').click();
  await page.waitForFunction(()=>document.getElementById('controls').disabled);
  assert(await page.locator('#setup').isVisible(), 'Session and source stay visible during the study');
  assert(await page.locator('#abort').isVisible(), 'Stop remains in the action bar');
  assert(await page.locator('#participant').isDisabled());
  assert(await page.locator('#start').isHidden());
  const actions=await page.evaluate(()=>window.testActions);
  assert.deepEqual(actions.map(a=>a.ui_seq),actions.map((_,i)=>i+1));
  assert(actions.some(a=>a.action==='field_key'&&a.key==='ArrowLeft'));
  assert(actions.some(a=>a.action==='field_edit'&&a.field==='session'&&a.value==='002'));
  assert.equal(actions.at(-1).action,'start');
  await page.evaluate(() => window.testRecording({phase:'complete',bytes_written:8192,
    output_file:'C:/Respira/data/test.xdf',streams:[{name:'Raw Force',source_id:'force-proof'}]}));
  await page.waitForFunction(() => document.getElementById('xdf-state').textContent === 'Saved');
  assert.equal(await page.locator('#recording-file').textContent(),'C:/Respira/data/test.xdf');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({result:'passed',actions:actions.length,reflowLayouts:5,controlCenterLayouts:2,recordingPagination:true,noFitRecovery:true,clipping:0,pageErrors:0}));
  await browser.close();
  await new Promise(resolve => server.close(resolve));
})().catch(e=>{console.error(e);process.exit(1);});
