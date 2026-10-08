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
  const errors=[],diagnostics=[];page.on('pageerror',e=>errors.push(String(e)));
  page.on('console',message=>{if(message.type()==='error')diagnostics.push(message.text());});
  const nativeReadyStart=Date.now();
  try { await page.waitForFunction(()=>document.getElementById('shell')?.getClientRects().length && !document.getElementById('participant').disabled,{},{timeout:30000}); }
  catch(e) { console.error(await page.locator('body').innerText());console.error(await page.evaluate(()=>({participantDisabled:document.getElementById('participant').disabled,startHidden:document.getElementById('start').hidden,closeHidden:document.getElementById('close').hidden})));console.error(await page.evaluate(()=>window.__TAURI__.core.invoke('launch_backend')));console.error(errors);throw e; }
  console.log(JSON.stringify({nativeReadyMs:Date.now()-nativeReadyStart}));
  const mode=process.argv[2];
  let ui=page, phoneBrowser;
  if(mode==='remote') {
    try {
      await page.waitForFunction(mock=>document.getElementById('hub-input-status').textContent.includes(mock ? 'Mock' : 'Synthetic raw Force'),
        !!process.env.RESPYRA_TEST_SOURCE_ID,{timeout:process.env.RESPYRA_TEST_SOURCE_ID ? 8000 : 20000});
    } catch(error) {
      console.error('source status',await page.locator('#hub-input-status').textContent());
      console.error('backend',await page.evaluate(async()=>{const state=await window.__TAURI__.core.invoke('launch_backend');
        return JSON.stringify({source:state.source,streams:state.progress?.streams,viewer_error:state.progress?.viewer_error});}));
      console.error('options',await page.locator('#feedback-source option').allTextContents());
      throw error;
    }
    if (process.env.RESPYRA_TEST_POLAR_METRIC) {
      await page.waitForFunction(async () => {
        const state = await window.__TAURI__.core.invoke('launch_backend');
        const samples = state.progress?.streams?.find(row => row.name.endsWith('_rawECG'))?.samples;
        return samples?.length >= 5 && samples.every((sample, index) =>
          Number.isFinite(sample[0]) && Number.isFinite(sample[1]) &&
          (!index || sample[0] > samples[index - 1][0]));
      }, {}, { timeout: 15000 });
      console.log('Installed Polar ECG preview received ordered sample batches');
      const ecgDisplay = page.getByRole('checkbox', { name: /^Display .*rawECG$/u });
      for (let attempt = 0; attempt < 10 && !await ecgDisplay.count(); attempt++)
        await page.locator('#stream-next').click();
      await ecgDisplay.check();
      await page.waitForFunction(() => [...document.querySelectorAll('#plot-canvas .plot-trace')]
        .some(path => path.dataset.channel?.toLowerCase().includes('ecg') && (path.getAttribute('d').match(/[ML]/gu) || []).length >= 100),
      {}, { timeout: 15000 });
      await page.screenshot({ path: '.for-ai-local/native-ecg-preview.png' });
      console.log('Installed Polar ECG plot retained at least 100 samples');
    }
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
      if(!(await import('./remote-profile.js')).validateControllerState(initial))
        throw new Error('Native remote snapshot failed browser validation: '+JSON.stringify(initial));
      const command={commandId:'cmd_native_probe',scope:'experiment.setup',action:'field_edit',
        args:{ui_seq:1,ui_time_ms:1,field:'participant',value:'7'},expectedRevision:revision};
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
      if(stale.ok || (await snapshot()).setup.values.participant!=='7')throw new Error('Stale mutation applied');
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
    await page.waitForFunction(()=>{const image=document.querySelector('#viewer-qr img');return image?.complete && image.naturalWidth>0;});
    let link=await page.locator('#viewer-link').inputValue();
    await page.screenshot({path:'.for-ai-local/native-qr-popup.png'});
    await page.locator('#viewer-qr img').screenshot({path:'.for-ai-local/native-qr.png'});
    const {execFileSync}=require('node:child_process');
    execFileSync('.venv/Scripts/python.exe',['-c',
      // Decode the rendered pixels. OpenCV sometimes needs nearest-neighbor
      // magnification at fractional Windows display scales; no QR data is added.
      'import cv2,sys; image=cv2.imread(".for-ai-local/native-qr.png"); image=cv2.copyMakeBorder(image,16,16,16,16,cv2.BORDER_CONSTANT,value=(255,255,255)); detector=cv2.QRCodeDetector(); decoded=[detector.detectAndDecode(cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_NEAREST))[0] for scale in (1,2)]; assert sys.stdin.read() in decoded, "Displayed QR did not decode to the invitation"'],
      {input:link,timeout:15000});
    ui=await context.newPage();ui.on('pageerror',e=>errors.push(String(e)));
    await ui.setViewportSize({width:390,height:844});
    await ui.goto(link);
    await ui.waitForURL(base+'remote.html',{timeout:10000});
    await ui.locator('#viewer-name').fill('Ada');
    await ui.locator('#connect').click();
    try {await ui.locator('#connection-status').getByText('Waiting for approval on the Respyra desktop…',{exact:true}).waitFor({timeout:45000});}
    catch(error){console.error({native:await page.locator('#viewer-status').textContent(),phone:await ui.locator('#connection-status').textContent(),diagnostics});throw error;}
    assert.equal(await ui.locator('#controller').isVisible(),false);
    assert(await ui.locator('#controls').evaluate(fieldset=>fieldset.disabled));
    await page.locator('#viewer-approval').waitFor();
    assert.equal(await page.locator('#viewer-requester').textContent(),'Ada');
    await page.screenshot({path:'.for-ai-local/native-remote-approval.png'});
    if(!process.env.RESPYRA_TEST_SOURCE_ID) {
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
    }
    await page.locator('#viewer-approve').click();
    try {await ui.waitForFunction(()=>!document.getElementById('controls').disabled,{},{timeout:45000});}
    catch(error){console.error({native:await page.locator('#viewer-status').textContent(),phone:await ui.locator('#connection-status').textContent(),diagnostics});throw error;}
  }
  if(mode==='remote') {
    assert(await ui.locator('#setup').isVisible() && await ui.locator('#lsl-monitor').isVisible());
  }
  const participant = process.env.RESPYRA_TEST_PARTICIPANT || '99';
  if (await ui.locator('#participant').evaluate(element => element.tagName === 'SELECT'))
    await ui.locator('#participant').selectOption(participant);
  else await ui.locator('#participant').fill(participant);
  await ui.locator('#participant').press('Tab');
  if (process.env.RESPYRA_TEST_RUN_ID && !await ui.locator('#variable-list input').count()) {
    await ui.locator(mode === 'remote' ? '#add-variable' : '#add-field').click();
    await ui.locator('#variable-list input').first().fill('TestRun');
    await ui.locator('#variable-list input').nth(1).fill(process.env.RESPYRA_TEST_RUN_ID);
  }
  if(mode==='memory' && !process.env.RESPYRA_TEST_SOURCE_ID) {
    await ui.locator('#include-keyboard-markers').check();
    await ui.locator('#include-mouse-markers').check();
  }
  assert.equal(await page.locator('#save-csv').count(),0);
  if(mode==='remote') assert.equal(await ui.locator('#save_csv').count(),0);
  if(mode==='select') {
    await page.locator('#refresh').click();
    await page.locator('#feedback-source option', {hasText:'Synthetic raw Force'}).waitFor({state:'attached',timeout:20000});
    assert(await page.locator('.stream-row').filter({hasText:'Synthetic normalized'}).count());
    await page.locator('#feedback-source').selectOption({label:'Synthetic raw Force'});
  }
  if(process.env.RESPYRA_TEST_POLAR_METRIC) {
    await page.locator('#polar-direction-field').waitFor({state:'visible',timeout:25000});
    await page.locator('#polar-direction').selectOption(process.env.RESPYRA_TEST_POLAR_INVERT ?
      'decreasing' : 'increasing');
  }
  try { await ui.waitForFunction(()=>!document.getElementById('start').disabled,{},{timeout:20000}); }
  catch(error) {
    console.error('setup readiness', JSON.stringify(await page.evaluate(async()=>{
      const state=await window.__TAURI__.core.invoke('launch_backend');
      return {phase:state.phase,setup:state.setup,progress:state.progress,source:state.source};
    })));
    console.error('phone readiness', await ui.locator('#setup').innerText());
    throw error;
  }
  if(mode!=='remote') assert((await page.locator('#hub-input-status').textContent()).includes(
    process.env.RESPYRA_TEST_SOURCE_ID ? 'Mock' : 'Synthetic raw Force'));
  if(mode==='remote') {
    await ui.evaluate(()=>document.fonts.ready);
    const compact=await ui.evaluate(()=>({height:document.documentElement.scrollHeight,viewport:innerHeight,width:document.documentElement.scrollWidth,viewportWidth:innerWidth}));
    await ui.screenshot({path:'.for-ai-local/native-phone-setup.png',fullPage:true});
    assert(compact.width<=compact.viewportWidth+1,
      'Phone setup overflows horizontally: '+JSON.stringify(compact));
  }
  const geometry=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1, measured:document.querySelectorAll('[data-measure]').length}));
  assert(!geometry.overflow && geometry.measured>10,JSON.stringify(geometry));
  for (const [width,size] of [[320,16],[1440,16],[320,32]]) {
    await page.setViewportSize({width,height:900});
    await page.evaluate(size=>{document.documentElement.style.fontSize=size+'px';},size);
    await page.waitForTimeout(100);
    const fit=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,
      clipped:[...document.querySelectorAll('[data-measure]')].filter(e=>e.getClientRects().length && (e.scrollWidth>e.clientWidth+1 || e.scrollHeight>e.clientHeight+1)).map(e=>({text:e.textContent,tag:e.tagName,width:e.clientWidth,scrollWidth:e.scrollWidth,height:e.clientHeight,scrollHeight:e.scrollHeight}))}));
    if(fit.clipped.length) await page.screenshot({path:'.for-ai-local/native-mock-clipped.png'});
    assert(!fit.overflow && (!await page.locator('#shell').isVisible() || !fit.clipped.length),JSON.stringify({width,size,fit}));
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
    assert(fs.existsSync(process.env.RESPYRA_UI_TEST_READY_PATH),
      mode==='memory' && !process.env.RESPYRA_FULL_MOCK_STUDY ?
        'PsychoPy did not advance from instructions to calibration after native Space' :
        'PsychoPy instructions did not reach a display flip');
    if(mode==='remote') {
      await ui.locator('#xdf-state').getByText('Recording', {exact:true}).waitFor({timeout:10000});
      if(!process.env.RESPYRA_PRIVATE_READY_PATH)
        await ui.locator('#signal-state').getByText('Live',{exact:true}).waitFor({timeout:10000});
    } else {
      await page.locator('#stream-status').getByText(/recording/u).waitFor({timeout:10000});
      try { await page.locator('#input-readiness').getByText('Receiving samples',{exact:true}).waitFor({timeout:10000}); }
      catch(error) {
        console.error('input readiness',await page.locator('#input-readiness').textContent(),
          'shell visible',await page.locator('#shell').isVisible(),
          'no fit',await page.locator('#no-fit').isVisible());
        console.error('health',await page.evaluate(async()=>{const state=await window.__TAURI__.core.invoke('launch_backend');
          return JSON.stringify({source:state.source,health:state.progress?.health,phase:state.phase,recording:state.progress?.recording});}));
        await page.screenshot({path:'.for-ai-local/native-memory-post-start.png'});
        throw error;
      }
    }
    if(mode==='remote') assert.equal(await ui.locator('#battery').textContent(),'Not reported');
    if(mode==='remote' && !process.env.RESPYRA_PRIVATE_READY_PATH) {
      await ui.waitForFunction(() => document.getElementById('monitor-value').textContent.includes('Live') && document.getElementById('trace-line').getAttribute('d')?.includes('L'));
      if(process.env.RESPYRA_TEST_SOURCE_ID) {
        assert((await ui.locator('#monitor-channel option').count())>=
          (process.env.RESPYRA_TEST_POLAR_METRIC ? 1 : 11));
        await ui.locator('#monitor-channel').selectOption('0');
        await ui.locator('#monitor-value').getByText(process.env.RESPYRA_TEST_POLAR_METRIC ?
          /Live · [-0-9.]+ g/u : /Live · [0-9.]+ N/u).waitFor();
      } else {
        assert.equal(await ui.locator('#monitor-channel option').count(),2);
        await ui.locator('#monitor-channel').selectOption('0');
        await ui.locator('#monitor-value').getByText('Live · 12.000 breaths/min', {exact:true}).waitFor();
        await ui.locator('#monitor-channel').selectOption('1');
      }
      await ui.waitForFunction(()=>document.getElementById('trace-line').getAttribute('d')?.split('L').length>=5);
      assert(await ui.locator('#monitor-markers li').count());
      const monitorFit=await ui.evaluate(()=>({height:document.documentElement.scrollHeight,viewport:innerHeight,width:document.documentElement.scrollWidth,viewportWidth:innerWidth}));
      assert(monitorFit.width<=monitorFit.viewportWidth+1,
        'Phone monitor overflows horizontally: '+JSON.stringify(monitorFit));
      await ui.screenshot({path:'.for-ai-local/native-remote-controller.png',fullPage:true});
    }
    if(process.env.RESPYRA_FULL_MOCK_STUDY) {
      const extra=48*Math.max(0,Number(process.env.RESPYRA_TEST_TRACKING_SECONDS || .15)-.15)*1000;
      await ui.locator('#close').waitFor({state:'visible',timeout:90000+extra});
    } else await ui.locator(mode==='remote' ? '#abort' : '#stop').click();
    await ui.locator('#close').waitFor({state:'visible',timeout:15000});
    if(mode==='remote') await ui.locator('#xdf-state').getByText('Saved', {exact:true}).waitFor({timeout:20000});
    else await page.locator('#stream-status').getByText(/XDF saved/u).waitFor({timeout:20000});
    let recording, file;
    for(let attempt=0;attempt<50;attempt++) {
      recording=await page.evaluate(async()=> (await window.__TAURI__.core.invoke('launch_backend')).progress.recording);
      file=recording.output_file;
      if(file?.endsWith('.xdf'))break;
      await page.waitForTimeout(100);
    }
    assert(file?.endsWith('.xdf'),JSON.stringify(recording));
    require('node:fs').writeFileSync(`.for-ai-local/native-${mode}-xdf.json`, JSON.stringify({file}));
    await ui.locator('#close').click();
  }
  if(phoneBrowser) await phoneBrowser.close();
  assert.deepEqual(errors,[]);
    console.log(JSON.stringify({mode,geometry,pageErrors:errors.length,publishedPhone:!!process.env.RESPYRA_PUBLISHED_PHONE,qrDecoded:mode==='remote'}));
})().catch(e=>{console.error(e);process.exit(1);});
