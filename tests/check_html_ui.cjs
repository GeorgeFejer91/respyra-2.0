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
    window.__TAURI__ = { event:{listen:async (_name, cb) => {listener=cb; return () => {}; }}, core:{invoke:async (command,args) => {
      if(command === 'launch_backend') return structuredClone(state);
      if(command === 'close_app') return;
      const a=args.action; window.testActions.push(a); state.ui_seq=a.ui_seq;
      if(a.action==='field_edit') state.values[a.field]=a.value;
      if(a.action==='option') state.save_csv=a.enabled;
      if(a.action==='scan') {state.selected_row=null;state.can_use=false;state.streams=[{source_id:'processed',stream_name:'Normalized breathing',stream_type:'Respiration',compatible:false,reason:'Requires raw Force in N'}, {source_id:'polar-stream-vernier-raw-'+ 'device'.repeat(25), stream_name:'Synthetic Vernier Force',stream_type:'VernierRaw',compatible:true,reason:'Compatible: raw Force (N)',force_channel_index:1}];}
      if(a.action==='select') {state.selected_row=a.row; state.can_use=state.streams[a.row].compatible;}
      if(a.action==='use') {state.source={source_id:state.streams[state.selected_row].source_id,stream_name:state.streams[state.selected_row].stream_name};state.message='Ready for this experiment.';}
      state.can_start=!!state.source && Object.values(state.values).every(v=>v.trim());
      if(a.action==='start') {state.phase='experiment';state.message='Experiment running in PsychoPy.';}
      if(a.action==='cancel') {state.phase='finished';state.message='Experiment ended.';}
      listener({payload:structuredClone(state)});
    }}};
  });
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.locator('#participant').fill('synthetic participant');
  await page.locator('#participant').press('ArrowLeft');
  await page.locator('#session').fill('002');
  await page.locator('#save_csv').check();
  assert(await page.locator('#save_csv').isChecked());
  assert(await page.locator('#start').isDisabled());
  await page.locator('#input-details summary').click();
  await page.locator('#scan').click();
  await page.locator('input[value="0"]').check();
  assert(await page.locator('#use').isDisabled());
  await page.locator('input[value="1"]').check();
  await page.locator('#use').click();
  await page.waitForFunction(()=>!document.getElementById('start').disabled);
  assert.equal(await page.locator('#participant').inputValue(), 'synthetic participant');
  await page.locator('#input-details summary').click();
  await page.locator('#scan').click();
  await page.waitForFunction(()=>![...document.querySelectorAll('#streams input')].some(r=>r.checked));
  await page.locator('input[value="1"]').check();
  assert(!(await page.locator('#use').isDisabled()), 'Unchanged scan results must still be selectable');
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
    assert(layout.measured>10);
  }
  await page.setViewportSize({width:820,height:1000});
  await page.evaluate(()=>{document.documentElement.style.fontSize='16px';document.querySelector('style')?.remove();});
  await page.screenshot({path:'.for-ai-local/html-setup.png',fullPage:true});
  await page.locator('#start').click();
  await page.waitForFunction(()=>document.getElementById('controls').disabled);
  const actions=await page.evaluate(()=>window.testActions);
  assert.deepEqual(actions.map(a=>a.ui_seq),actions.map((_,i)=>i+1));
  assert(actions.some(a=>a.action==='field_key'&&a.key==='ArrowLeft'));
  assert(actions.some(a=>a.action==='field_edit'&&a.field==='session'&&a.value==='002'));
  assert.equal(actions.at(-1).action,'start');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({result:'passed',actions:actions.length,layouts:5,clipping:0,pageErrors:0}));
  await browser.close();
  await new Promise(resolve => server.close(resolve));
})().catch(e=>{console.error(e);process.exit(1);});
