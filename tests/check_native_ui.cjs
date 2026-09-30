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
  await page.locator('#participant').fill('synthetic-native');
  await page.locator('#participant').press('ArrowLeft');
  if(mode==='select') {
    await page.locator('#scan').click();
    await page.locator('.stream').filter({hasText:'Synthetic raw Force'}).locator('input').check({timeout:20000});
    assert(await page.locator('.stream').filter({hasText:'Synthetic normalized'}).count());
    await page.locator('.stream').filter({hasText:'Synthetic normalized'}).locator('input').check();
    assert(await page.locator('#use').isDisabled());
    await page.locator('.stream').filter({hasText:'Synthetic raw Force'}).locator('input').check();
    await page.locator('#use').click();
  }
  await page.waitForFunction(()=>!document.getElementById('start').disabled,{},{timeout:20000});
  assert((await page.locator('#accepted').textContent()).includes('Synthetic raw Force'));
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
    await page.locator('#start').click();
    // The HTML shell hides while the real PsychoPy window runs. Request the
    // same closed native lifecycle command used by its window close button.
    const fs=require('node:fs');
    for(let i=0;i<250 && !fs.existsSync(process.env.RESPYRA_UI_TEST_READY_PATH);i++) await new Promise(r=>setTimeout(r,100));
    assert(fs.existsSync(process.env.RESPYRA_UI_TEST_READY_PATH),'PsychoPy instructions did not reach a display flip');
    await page.evaluate(()=>window.__TAURI__.core.invoke('close_app', {reason:'protocol_failure'}));
  }
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({mode,geometry,pageErrors:errors.length}));
})().catch(e=>{console.error(e);process.exit(1);});
