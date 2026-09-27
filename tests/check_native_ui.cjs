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
  try { await page.waitForFunction(()=>!document.getElementById('controls').disabled,{},{timeout:15000}); }
  catch(e) { console.error(await page.locator('body').innerText());console.error(await page.evaluate(()=>window.__TAURI__.core.invoke('launch_backend')));console.error(errors);throw e; }
  const mode=process.argv[2];
  let ui=page, phoneBrowser;
  if(mode==='remote') {
    await page.waitForFunction(()=>document.getElementById('accepted').textContent.includes('Synthetic raw Force'),{},{timeout:20000});
    const fences=await page.evaluate(async()=>{
      const call=action=>window.__TAURI__.core.invoke('viewer_action',{action});
      const invite=await call({action:'start'});
      const grant=await call({action:'claim',token:invite.token,peer_id:'native_probe',epoch:7,
        scopes:['experiment.observe','experiment.setup','experiment.run']});
      const binding={token:invite.token,owner:grant.owner,peer_id:'native_probe',epoch:7};
      const snapshot=()=>call({action:'snapshot',token:invite.token,owner:grant.owner});
      const initial=await snapshot(),revision=initial.revision;
      const command={commandId:'cmd_native_probe',scope:'experiment.setup',action:'field_edit',
        args:{ui_seq:1,ui_time_ms:1,field:'participant',value:'ownership-probe'},expectedRevision:revision};
      let denied=0;
      const reject=async action=>{try{await call(action);}catch{denied++;return;}throw new Error('Native fence allowed invalid request');};
      await reject({action:'snapshot',token:invite.token,owner:'wrong'});
      await reject({action:'claim',token:invite.token,peer_id:'second_phone',epoch:7,scopes:['experiment.observe']});
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
      const readGrant=await call({action:'claim',token:reader.token,peer_id:'native_reader',epoch:9,scopes:['experiment.observe']});
      if((await call({action:'snapshot',token:reader.token,owner:readGrant.owner})).setup!==null)throw new Error('Observe-only scope exposed participant');
      await reject({action:'dispatch',token:reader.token,owner:readGrant.owner,peer_id:'native_reader',epoch:9,sequence:1,command});
      await call({action:'stop',token:reader.token});
      await reject({action:'snapshot',token:reader.token,owner:readGrant.owner});
      return {denied,duplicateEffects:0,staleEffects:0};
    });
    assert.equal(fences.denied,8);
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
    await page.locator('#view').selectOption('phone');
    await page.locator('#viewer-start').click();
    await page.locator('#viewer-qr img').waitFor();
    const link=await page.locator('#viewer-link').inputValue();
    await page.locator('#viewer-qr img').screenshot({path:'.for-ai-local/native-qr.png'});
    const {execFileSync}=require('node:child_process');
    execFileSync('.venv/Scripts/python.exe',['-c',
      'import cv2,sys; image=cv2.imread(".for-ai-local/native-qr.png"); text,points,_=cv2.QRCodeDetector().detectAndDecode(image); assert text == sys.stdin.read(), "Displayed QR did not decode to the invitation"'],
      {input:link,timeout:15000});
    ui=await context.newPage();ui.on('pageerror',e=>errors.push(String(e)));
    await ui.setViewportSize({width:390,height:844});
    await ui.goto(link);
    await ui.locator('#connect').click();
    try {await ui.waitForFunction(()=>!document.getElementById('controls').disabled,{},{timeout:45000});}
    catch(error){console.error({native:await page.locator('#viewer-status').textContent(),phone:await ui.locator('#connection-status').textContent()});throw error;}
  }
  await ui.locator('#participant').fill(process.env.RESPIRA_TEST_PARTICIPANT || 'synthetic-native');
  await ui.locator('#participant').press('ArrowLeft');
  if(process.env.RESPIRA_INSTALLED_EXE && mode==='memory') await ui.locator('#save_csv').check();
  if(mode==='remote') {
    await ui.locator('#save_csv').check();
    await page.waitForFunction(()=>document.getElementById('save_csv').checked);
    await ui.locator('#save_csv').uncheck();
    await page.waitForFunction(()=>!document.getElementById('save_csv').checked);
  }
  if(mode==='select') {
    await page.locator('#view').selectOption('input');
    await page.locator('#scan').click();
    const choose = async name => {
      const row = page.locator('.stream').filter({hasText:name});
      await row.waitFor({state:'attached',timeout:20000});
      const previous = page.locator('#streams + .page-actions button').first();
      while (await previous.isEnabled()) await previous.click();
      for (let i=0; !(await row.isVisible()) && i<20; i++) await page.locator('#streams + .page-actions button').last().click();
      await row.locator('input').check();
    };
    await choose('Synthetic raw Force');
    assert(await page.locator('.stream').filter({hasText:'Synthetic normalized'}).count());
    await choose('Synthetic normalized');
    assert(await page.locator('#use').isDisabled());
    await choose('Synthetic raw Force');
    await page.locator('#use').click();
  }
  await ui.waitForFunction(()=>!document.getElementById('start').disabled,{},{timeout:20000});
  assert((await ui.locator('#accepted').textContent()).includes('Synthetic raw Force'));
  if(mode==='remote') {
    await ui.evaluate(()=>document.fonts.ready);
    const compact=await ui.evaluate(()=>({height:document.documentElement.scrollHeight,viewport:innerHeight,width:document.documentElement.scrollWidth}));
    await ui.screenshot({path:'.for-ai-local/native-phone-setup.png',fullPage:true});
    assert(compact.height<=compact.viewport+1,'Phone setup needs scrolling: '+JSON.stringify(compact));
  }
  const geometry=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1, measured:document.querySelectorAll('[data-pretext-fit]').length}));
  assert(!geometry.overflow && geometry.measured>10,JSON.stringify(geometry));
  for (const [width,size] of [[320,16],[1440,16],[320,32]]) {
    await page.setViewportSize({width,height:900});
    await page.evaluate(size=>{document.documentElement.style.fontSize=size+'px';},size);
    await page.waitForTimeout(100);
    const fit=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,clipped:[...document.querySelectorAll('[data-measure]')].filter(e=>e.getClientRects().length && (e.scrollWidth>e.clientWidth+1 || e.scrollHeight>e.clientHeight+1)).length}));
    assert(!fit.overflow && !fit.clipped,JSON.stringify({width,size,fit}));
  }
  await page.setViewportSize({width:820,height:900});
  await page.evaluate(()=>{document.documentElement.style.fontSize='16px';});
  await page.screenshot({path:`.for-ai-local/native-${mode}.png`,fullPage:true});
  if(mode==='select') {
    await page.locator('#cancel').click();
    await page.locator('#close').waitFor({state:'visible',timeout:20000});
    await page.locator('#close').click();
  } else {
    await ui.locator('#start').click();
    const fs=require('node:fs');
    for(let i=0;i<250 && !fs.existsSync(process.env.RESPYRA_UI_TEST_READY_PATH);i++) await new Promise(r=>setTimeout(r,100));
    assert(fs.existsSync(process.env.RESPYRA_UI_TEST_READY_PATH),'PsychoPy instructions did not reach a display flip');
    await ui.locator('#signal-state').getByText('Live',{exact:true}).waitFor({timeout:10000});
    assert.equal(await ui.locator('#battery').textContent(),'Not reported');
    if(mode==='remote') await ui.screenshot({path:'.for-ai-local/native-remote-controller.png',fullPage:true});
    await ui.locator('#abort').click();
    await ui.locator('#close').waitFor({state:'visible',timeout:15000});
    await ui.locator('#close').click();
  }
  if(phoneBrowser) await phoneBrowser.close();
  assert.deepEqual(errors,[]);
    console.log(JSON.stringify({mode,geometry,pageErrors:errors.length,publishedPhone:!!process.env.RESPYRA_PUBLISHED_PHONE,qrDecoded:mode==='remote'}));
})().catch(e=>{console.error(e);process.exit(1);});
