const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async()=>{
  let browser;
  for(let i=0;i<100;i++) {
    try {browser=await chromium.connectOverCDP('http://127.0.0.1:9227');break;} catch{await new Promise(r=>setTimeout(r,100));}
  }
  assert(browser,'WebView2 CDP unavailable');
  let page;
  for(let i=0;i<100;i++) {
    page=browser.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes('tauri.localhost'));
    if(page)break;
    await new Promise(r=>setTimeout(r,100));
  }
  assert(page,'Respyra WebView missing');
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  try { await page.waitForFunction(()=>document.getElementById('shell')?.getClientRects().length && !document.getElementById('participant').disabled,{},{timeout:15000}); }
  catch(e) { console.error(await page.locator('body').innerText());console.error(await page.evaluate(()=>window.__TAURI__.core.invoke('launch_backend')));console.error(errors);throw e; }
  const mode=process.argv[2];
  let ui=page, phoneBrowser;
  if(mode==='remote') {
    await page.waitForFunction(()=>document.getElementById('hub-input-status').textContent.includes('Synthetic raw Force'),{},{timeout:20000});
    const fences=await page.evaluate(async()=>{
      const call=action=>window.__TAURI__.core.invoke('viewer_action',{action});
      const invite=await call({action:'start'});
      const request=await call({action:'claim',token:invite.token,peer_id:'native_probe',epoch:7,
        scopes:['experiment.observe','experiment.setup','experiment.run'],name:'Native probe'});
      if(request.name!=='Native probe')throw new Error('Native approval lost the requested name');
      let denied=0;
      const reject=async action=>{try{await call(action);}catch{denied++;return;}throw new Error('Native fence allowed invalid request');};
      await reject({action:'snapshot',token:invite.token,owner:request.request});
      await reject({action:'review',token:invite.token,request:'wrong',approve:true});
      const grant=await call({action:'review',token:invite.token,request:request.request,approve:true});
      const binding={token:invite.token,owner:grant.owner,peer_id:'native_probe',epoch:7};
      const snapshot=()=>call({action:'snapshot',token:invite.token,owner:grant.owner});
      const initial=await snapshot(),revision=initial.revision;
      const command={commandId:'cmd_native_probe',scope:'experiment.setup',action:'field_edit',
        args:{ui_seq:1,ui_time_ms:1,field:'participant',value:'ownership-probe'},expectedRevision:revision};
      await reject({action:'snapshot',token:invite.token,owner:'wrong'});
      await reject({action:'claim',token:invite.token,peer_id:'second_phone',epoch:7,scopes:['experiment.observe'],name:'Second phone'});
      await reject({action:'dispatch',...binding,peer_id:'wrong_peer',sequence:1,command});
      await reject({action:'dispatch',...binding,epoch:8,sequence:1,command});
      const first=await call({action:'dispatch',...binding,sequence:1,command});
      if(!first.ok)throw new Error('Native probe command rejected');
      const duplicate=await call({action:'dispatch',...binding,sequence:2,command});
      if(JSON.stringify(duplicate)!==JSON.stringify(first))throw new Error('Duplicate receipt changed');
      const after=await snapshot();
      if(after.setup.ui_seq!==initial.setup.ui_seq+1)throw new Error('Duplicate produced a second Python effect');
      const stale=await call({action:'dispatch',...binding,sequence:3,command:{...command,commandId:'cmd_stale_probe',args:{...command.args,value:'stale'}}});
      if(stale.ok || (await snapshot()).setup.values.participant!=='ownership-probe')throw new Error('Stale mutation applied');
      const unknown=await call({action:'dispatch',...binding,sequence:4,command:{...command,commandId:'cmd_unknown_probe',action:'shell',expectedRevision:after.revision}});
      if(unknown.ok)throw new Error('Unknown action applied');
      await reject({action:'dispatch',...binding,sequence:5,command:{...command,args:{...command.args,value:'changed-body'}}});
      await reject({action:'snapshot',token:invite.token,owner:grant.owner});
      await call({action:'stop',token:invite.token});
      const reader=await call({action:'start'});
      const readRequest=await call({action:'claim',token:reader.token,peer_id:'native_reader',epoch:9,scopes:['experiment.observe'],name:'Reader'});
      const readGrant=await call({action:'review',token:reader.token,request:readRequest.request,approve:true});
      if((await call({action:'snapshot',token:reader.token,owner:readGrant.owner})).setup!==null)throw new Error('Observe-only scope exposed participant');
      await reject({action:'dispatch',token:reader.token,owner:readGrant.owner,peer_id:'native_reader',epoch:9,sequence:1,command});
      await call({action:'stop',token:reader.token});
      await reject({action:'snapshot',token:reader.token,owner:readGrant.owner});
      const rejected=await call({action:'start'});
      const pending=await call({action:'claim',token:rejected.token,peer_id:'native_rejected',epoch:10,scopes:['experiment.observe'],name:'Rejected phone'});
      await call({action:'review',token:rejected.token,request:pending.request,approve:false});
      await reject({action:'review',token:rejected.token,request:pending.request,approve:true});
      await reject({action:'snapshot',token:rejected.token,owner:pending.request});
      return {denied,duplicateEffects:0,staleEffects:0};
    });
    assert.equal(fences.denied,12);
    const fs=require('node:fs/promises'),path=require('node:path');
    const base='https://georgefejer91.github.io/respyra-2.0/';
    phoneBrowser=await chromium.launch({channel:'chrome',headless:true});
    const context=await phoneBrowser.newContext();
    if (!process.env.RESPYRA_PUBLISHED_PHONE) await context.route(base+'**',async route=>{
      const relative=new URL(route.request().url()).pathname.slice(new URL(base).pathname.length)||'index.html';
      const file=path.resolve('companion',relative);
      assert(file.startsWith(path.resolve('companion')+path.sep));
      await route.fulfill({body:await fs.readFile(file),contentType:{'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2'}[path.extname(file)]||'application/octet-stream'});
    });
    await page.locator('#viewer-open').click();
    await page.locator('#viewer-qr img').waitFor();
    let link=await page.locator('#viewer-link').inputValue();
    await page.screenshot({path:'.for-ai-local/native-qr-popup.png'});
    await page.locator('#viewer-qr img').screenshot({path:'.for-ai-local/native-qr.png'});
    const {execFileSync}=require('node:child_process');
    execFileSync('.venv/Scripts/python.exe',['-c',
      // Decode the rendered pixels. OpenCV sometimes needs nearest-neighbor
      // magnification at fractional Windows display scales; no QR data is added.
      'import cv2,sys; image=cv2.imread(".for-ai-local/native-qr.png"); detector=cv2.QRCodeDetector(); decoded=[detector.detectAndDecode(cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST))[0] for scale in (1,2)]; assert sys.stdin.read() in decoded, "Displayed QR did not decode to the invitation"'],
      {input:link,timeout:15000});
    ui=await context.newPage();ui.on('pageerror',e=>errors.push(String(e)));
    await ui.setViewportSize({width:390,height:844});
    await ui.goto(link);
    await ui.locator('#viewer-name').fill('Ada');
    await ui.locator('#connect').click();
    await ui.locator('#connection-status').getByText('Waiting for approval on the Respyra desktop…',{exact:true}).waitFor({timeout:45000});
    assert.equal(await ui.locator('#controller').isVisible(),false);
    assert(await ui.locator('#controls').evaluate(fieldset=>fieldset.disabled));
    await page.locator('#viewer-approval').waitFor();
    assert.equal(await page.locator('#viewer-requester').textContent(),'Ada');
    await page.screenshot({path:'.for-ai-local/native-remote-approval.png'});
    await page.locator('#viewer-reject').click();
    await ui.locator('#connection-status').getByText(/Disconnected/u).waitFor();
    assert.equal(await ui.locator('#controller').isVisible(),false);
    await page.locator('#viewer-start').click();
    await page.locator('#viewer-qr img').waitFor();
    const replacement=await page.locator('#viewer-link').inputValue();
    assert.notEqual(replacement,link,'Rejection rotates the private invitation');
    link=replacement;
    await ui.goto(link);
    await ui.locator('#viewer-name').fill('Ada');
    await ui.locator('#connect').click();
    try { await ui.locator('#connection-status').getByText('Waiting for approval on the Respyra desktop…',{exact:true}).waitFor({timeout:45000}); }
    catch(error) { console.error({native:await page.locator('#viewer-status').textContent(),phone:await ui.locator('#connection-status').textContent()}); throw error; }
    assert.equal(await ui.locator('#controller').isVisible(),false);
    await page.locator('#viewer-approval').waitFor();
    await page.locator('#viewer-approve').click();
    try {await ui.waitForFunction(()=>!document.getElementById('controls').disabled,{},{timeout:45000});}
    catch(error){console.error({native:await page.locator('#viewer-status').textContent(),phone:await ui.locator('#connection-status').textContent()});throw error;}
  }
  if(mode==='remote') {
    assert(await ui.locator('#setup').isVisible() && await ui.locator('#lsl-monitor').isVisible());
  }
  await ui.locator('#participant').fill(process.env.RESPIRA_TEST_PARTICIPANT || 'synthetic-native');
  await ui.locator('#participant').press('ArrowLeft');
  if(mode==='memory') {
    await ui.locator('#include-keyboard-markers').check();
    await ui.locator('#include-mouse-markers').check();
  }
  if(process.env.RESPIRA_INSTALLED_EXE && mode==='memory') {
    await page.locator('#settings-open').click();
    await page.locator('#save-csv').check();
    await page.locator('#settings-done').click();
  }
  if(mode==='remote') {
    await ui.locator('#save_csv').check();
    await page.waitForFunction(()=>document.getElementById('save-csv').checked);
    await ui.locator('#save_csv').uncheck();
    await page.waitForFunction(()=>!document.getElementById('save-csv').checked);
  }
  if(mode==='select') {
    await page.locator('#refresh').click();
    await page.locator('#breathing-source option', {hasText:'Synthetic raw Force'}).waitFor({state:'attached',timeout:20000});
    assert(await page.locator('.stream-row').filter({hasText:'Synthetic normalized'}).count());
    await page.locator('#breathing-source').selectOption({label:'Synthetic raw Force'});
  }
  await ui.waitForFunction(()=>!document.getElementById('start').disabled,{},{timeout:20000});
  if(mode!=='remote') assert((await page.locator('#hub-input-status').textContent()).includes('Synthetic raw Force'));
  if(mode==='remote') {
    await ui.evaluate(()=>document.fonts.ready);
    const compact=await ui.evaluate(()=>({height:document.documentElement.scrollHeight,viewport:innerHeight,width:document.documentElement.scrollWidth}));
    await ui.screenshot({path:'.for-ai-local/native-phone-setup.png',fullPage:true});
    assert(compact.height<=compact.viewport+1,'Phone setup needs scrolling: '+JSON.stringify(compact));
  }
  const geometry=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1, measured:document.querySelectorAll('[data-measure]').length}));
  assert(!geometry.overflow && geometry.measured>10,JSON.stringify(geometry));
  for (const [width,size] of [[320,16],[1440,16],[320,32]]) {
    await page.setViewportSize({width,height:900});
    await page.evaluate(size=>{document.documentElement.style.fontSize=size+'px';},size);
    await page.waitForTimeout(100);
    const fit=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,clipped:[...document.querySelectorAll('[data-measure]')].filter(e=>e.getClientRects().length && (e.scrollWidth>e.clientWidth+1 || e.scrollHeight>e.clientHeight+1)).length}));
    assert(!fit.overflow && (!await page.locator('#shell').isVisible() || !fit.clipped),JSON.stringify({width,size,fit}));
  }
  await page.setViewportSize({width:820,height:900});
  await page.evaluate(()=>{document.documentElement.style.fontSize='16px';});
  await page.screenshot({path:`.for-ai-local/native-${mode}.png`,fullPage:true});
  if(mode==='select') {
    await page.evaluate(()=>{ void window.__TAURI__.core.invoke('close_app',{reason:'close_button'}); });
  } else {
    await ui.locator('#start').click();
    const fs=require('node:fs');
    for(let i=0;i<250 && !fs.existsSync(process.env.RESPYRA_UI_TEST_READY_PATH);i++) await new Promise(r=>setTimeout(r,100));
    assert(fs.existsSync(process.env.RESPYRA_UI_TEST_READY_PATH),'PsychoPy instructions did not reach a display flip');
    if(mode==='remote') {
      await ui.locator('#xdf-state').getByText('Recording', {exact:true}).waitFor({timeout:10000});
      await ui.locator('#signal-state').getByText('Live',{exact:true}).waitFor({timeout:10000});
    } else {
      await page.locator('#stream-status').getByText(/recording/u).waitFor({timeout:10000});
      await page.locator('#input-readiness').getByText('Receiving samples',{exact:true}).waitFor({timeout:10000});
    }
    if(mode==='remote') assert.equal(await ui.locator('#battery').textContent(),'Not reported');
    if(mode==='remote') {
      await ui.waitForFunction(() => document.getElementById('monitor-value').textContent.includes('Live') && document.getElementById('trace-line').getAttribute('d')?.includes('L'));
      assert.equal(await ui.locator('#monitor-channel option').count(),2);
      await ui.locator('#monitor-channel').selectOption('0');
      await ui.locator('#monitor-value').getByText('Live · 12.000 breaths/min', {exact:true}).waitFor();
      await ui.locator('#monitor-channel').selectOption('1');
      await ui.waitForFunction(()=>document.getElementById('trace-line').getAttribute('d')?.split('L').length>=5);
      assert(await ui.locator('#monitor-markers li').count());
      const monitorFit=await ui.evaluate(()=>({height:document.documentElement.scrollHeight,viewport:innerHeight,width:document.documentElement.scrollWidth,viewportWidth:innerWidth}));
      assert(monitorFit.height<=monitorFit.viewport+1 && monitorFit.width<=monitorFit.viewportWidth+1,'Phone monitor needs scrolling: '+JSON.stringify(monitorFit));
      await ui.screenshot({path:'.for-ai-local/native-remote-controller.png',fullPage:true});
    }
    await ui.locator(mode==='remote' ? '#abort' : '#stop').click();
    await ui.locator('#close').waitFor({state:'visible',timeout:15000});
    if(mode==='remote') await ui.locator('#xdf-state').getByText('Saved', {exact:true}).waitFor({timeout:20000});
    else await page.locator('#stream-status').getByText(/XDF saved/u).waitFor({timeout:20000});
    const file=await page.evaluate(async()=> (await window.__TAURI__.core.invoke('launch_backend')).progress.recording.output_file);
    assert(file.endsWith('.xdf'));
    require('node:fs').writeFileSync(`.for-ai-local/native-${mode}-xdf.json`, JSON.stringify({file}));
    await ui.locator('#close').click();
  }
  if(phoneBrowser) await phoneBrowser.close();
  assert.deepEqual(errors,[]);
    console.log(JSON.stringify({mode,geometry,pageErrors:errors.length,publishedPhone:!!process.env.RESPYRA_PUBLISHED_PHONE,qrDecoded:mode==='remote'}));
})().catch(e=>{console.error(e);process.exit(1);});
