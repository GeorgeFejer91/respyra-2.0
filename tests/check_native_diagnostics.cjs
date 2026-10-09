const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  let browser;
  for (let n=0;n<120;n++) {
    try { browser=await chromium.connectOverCDP('http://127.0.0.1:9227'); break; }
    catch { await new Promise(resolve=>setTimeout(resolve,100)); }
  }
  assert(browser, 'Native CDP unavailable');
  const pages = () => browser.contexts().flatMap(context=>context.pages());
  let page;
  for (let n=0;n<120;n++) {
    page=pages().find(candidate=>candidate.url().includes('tauri.localhost') && !candidate.url().includes('error-report'));
    if (page) break;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  assert(page, 'Native experiment window missing');
  const mode=process.argv[2], errors=[];
  page.on('pageerror', error=>errors.push(String(error)));
  const snapshot=()=>page.evaluate(()=>window.__TAURI__.core.invoke('launch_backend'));
  const waitState=async(predicate,timeout=40000)=>{
    const deadline=Date.now()+timeout;
    let state;
    while(Date.now()<deadline){state=await snapshot();if(predicate(state))return state;await new Promise(r=>setTimeout(r,100));}
    throw new Error('State timeout: '+JSON.stringify(state));
  };
  await page.waitForFunction(()=>document.getElementById('troubleshooting') && !document.getElementById('troubleshooting').disabled);
  if (mode==='on') assert(await page.locator('#troubleshooting').isChecked());
  if (mode==='remember') {
    assert(!await page.locator('#troubleshooting').isChecked(), 'Troubleshooting opt-out was forgotten');
  } else {
    if ((await page.locator('#troubleshooting').isChecked()) !== (mode!=='off')) await page.locator('#troubleshooting').click();
    await waitState(state=>state.troubleshooting===(mode!=='off'));
    await page.waitForFunction(enabled => document.getElementById('troubleshooting').checked===enabled &&
      !document.getElementById('troubleshooting').disabled, mode!=='off');
    if (mode==='native-exit') {
      fs.writeFileSync(process.env.RESPYRA_DIAGNOSTIC_DROP_FILE, 'kill');
    } else {
      await page.locator('#participant').selectOption('99');
      await page.waitForFunction(()=>!document.getElementById('start').disabled);
      await page.locator('#start').click();
      await waitState(state=>state.phase==='experiment' && state.progress?.prompt?.screen==='instructions');
      fs.writeFileSync(process.env.RESPYRA_DIAGNOSTIC_DROP_FILE, 'stop-samples');
      const deadline=Date.now()+30000;
      while ((await snapshot()).phase!=='error' && Date.now()<deadline) {
        if (await page.locator('#prompt-continue').isVisible() && await page.locator('#prompt-continue').isEnabled())
          await page.locator('#prompt-continue').click();
        await new Promise(resolve=>setTimeout(resolve,150));
      }
    }
    await waitState(state=>state.phase==='error');
    const state=await snapshot();
    assert(state.message);
    if (mode==='off') {
      assert.equal(state.diagnostic, null);
      assert(!pages().some(candidate=>candidate.url().includes('error-report.html')));
    } else {
      let popup;
      for (let n=0;n<500;n++) {
        popup=pages().find(candidate=>candidate.url().includes('error-report.html'));
        if (popup) break;
        await new Promise(resolve=>setTimeout(resolve,100));
      }
      assert(popup, 'Failure did not open a separate report window');
      popup.on('pageerror', error=>errors.push(String(error)));
      await popup.waitForFunction(()=>document.getElementById('error-report')?.value.includes('Respyra troubleshooting report'));
      assert.equal(await popup.evaluate(()=>window.__TAURI__.window.getCurrentWindow().label), 'error-report');
      const text=await popup.locator('#error-report').inputValue();
      assert.match(text, mode==='native-exit' ? /Engine exit:/ : /Traceback[\s\S]*LSLForceError/);
      assert.equal(fs.readFileSync(state.diagnostic.saved_path,'utf8').replace(/\r\n/g,'\n'), text);
      // Mock clipboard writes so verification never replaces the user's clipboard.
      await popup.evaluate(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copied=text;}}}));
      await popup.locator('#error-copy').click();
      assert.equal(await popup.evaluate(()=>window.copied), text);
      await popup.screenshot({path:path.join(process.env.RESPYRA_DIAGNOSTIC_EVIDENCE,mode+'-popup.png')});
      await popup.locator('#error-dismiss').click();
      for (let n=0;n<50 && !popup.isClosed();n++) await new Promise(resolve=>setTimeout(resolve,100));
      assert(popup.isClosed());
      assert(!page.isClosed(), 'Closing the popup closed the experiment window');
    }
  }
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({mode,result:'passed',separateWindow:mode==='on'||mode==='native-exit'}));
  await page.evaluate(()=>{void window.__TAURI__.core.invoke('close_app',{reason:'close_button'});});
  await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
