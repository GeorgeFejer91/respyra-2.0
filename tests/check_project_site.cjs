const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const base = 'https://georgefejer91.github.io/respyra-2.0/';
const root = path.resolve('companion');
const screenshots = path.resolve('.for-ai-local');

(async () => {
  await fs.mkdir(screenshots, { recursive:true });
  const browser = await chromium.launch({ channel:'chrome', headless:true });
  try {
    const context = await browser.newContext();
    const errors = [];
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(String(error)));
    await context.route(base + '**', async route => {
      const relative = new URL(route.request().url()).pathname.slice(new URL(base).pathname.length) || 'index.html';
      if (relative === 'text-spacing.css') return route.fulfill({ contentType:'text/css', body:'html{font-size:32px!important} *{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important} p{margin-bottom:2em!important}' });
      const file = path.resolve(root, relative);
      if (!file.startsWith(root + path.sep)) return route.abort();
      try {
      await route.fulfill({ body:await fs.readFile(file), contentType:{ '.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.svg':'image/svg+xml', '.png':'image/png', '.woff2':'font/woff2', '.json':'application/json' }[path.extname(file)] || 'application/octet-stream' });
      } catch { await route.fulfill({ status:404, body:'Missing site file' }); }
    });
    await page.goto(base);
    assert(await page.getByRole('heading', { name:'Breathing target-tracking studies on Windows' }).isVisible());
    assert(await page.getByRole('img', { name:/Respyra logo/u }).evaluate(image => image.complete && image.naturalWidth > 0));
    await page.waitForFunction(() => document.querySelector('h1').dataset.pretextFit);
    assert.notEqual(await page.locator('html').getAttribute('data-pretext-fit'), 'unavailable');
    assert.equal(await page.getByRole('link', { name:'Download Respyra Suite for Windows' }).getAttribute('href'),
      'https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v0.3.8/00-Respyra-Suite_0.3.8_x64-setup.exe');
    assert.equal(await page.getByRole('link', { name:'Respyra 2.0 only' }).getAttribute('href'),
      'https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v0.3.8/Respyra-2.0_0.3.8_x64-setup.exe');
    for (const [name, file] of [
      ['Download Vernier Stream Mini separately', 'Vernier-Stream-Mini_0.6.6_x64-setup.exe'],
      ['Download Polar Stream Mini separately', 'Polar-Stream-Mini_0.6.6_x64-setup.exe'],
    ]) {
      assert.equal(await page.getByRole('link', { name }).getAttribute('href'),
        'https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v0.3.8/' + file);
    }
    for (const name of ['Download Vernier Stream Mini separately', 'Download Polar Stream Mini separately', 'Stream and data-flow wiki', 'Read the original preprint']) {
      assert(await page.getByRole('link', { name }).isVisible(), name);
    }
    const catalogSource = await fs.readFile('mini-streams/docs/metric-catalog.js', 'utf8');
    const catalog = JSON.parse(catalogSource.slice(catalogSource.indexOf('['), catalogSource.lastIndexOf(']') + 1));
    const defaults = catalog.filter(metric => ['raw_ecg','raw_acc','heart_rate','rr_interval'].includes(metric.id)
      || ['Breathing','Breathing dynamics'].includes(metric.category));
    assert.equal(defaults.length, 37);
    await page.goto(base + 'variables.html');
    const polarIds = defaults.flatMap(metric => metric.id === 'raw_acc' ? ['raw_acc_x','raw_acc_y','raw_acc_z'] : [metric.id]);
    assert.deepEqual(await page.locator('#polar [data-variable-id]').evaluateAll(rows => rows.map(row => row.dataset.variableId)),
      [...polarIds, 'polar_signal_state','event_kind']);
    const vernierDiagnostics = ['sequence','dropped_rows_before','device_drop_reports_before','sample_period_us','decode_latency_ns','host_receive_timestamp_ns','encoding_code'];
    assert.deepEqual(await page.locator('#vernier [data-variable-id]').evaluateAll(rows => rows.map(row => row.dataset.variableId)),
      ['force','respiration_rate','steps','step_rate','vernier_breathing','vernier_signal_state',...vernierDiagnostics]);
    assert.equal(await page.locator('#respyra [data-variable-id]').count(), 3);
    assert.equal(await page.locator('[data-variable-id] strong').count(), 57);
    assert.equal(await page.locator('[data-csv-id] strong').count(), 13);
    assert(await page.getByText(/can advertise 51 outlets/).isVisible());
    const definitions = await page.locator('[data-variable-id] p').allTextContents();
    assert(definitions.every(text => text.length > 80), 'Every default variable needs a substantive definition');
    await page.goto(base + 'about.html');
    assert.equal(await page.getByRole('link', {name:'George Fejer · Google Scholar'}).getAttribute('href'), 'https://scholar.google.com/citations?hl=en&user=GPARoloAAAAJ');
    assert.equal(await page.getByRole('link', {name:'George Fejer · ORCID'}).getAttribute('href'), 'https://orcid.org/0000-0002-4904-5504');
    assert(await page.getByText(/Micah Allen and the Embodied Computation Group created/).isVisible());
    for (const file of ['', 'variables.html','study.html','about.html']) {
      await page.goto(base + file);
      await page.waitForFunction(() => document.querySelector('h1').dataset.pretextFit);
      for (const image of await page.locator('img').all()) {
        await image.scrollIntoViewIfNeeded();
        await image.evaluate(image => image.decode());
      }
      // Every local file link and fragment must exist in the published payload.
      for (const href of await page.locator('a[href]').evaluateAll(links => links.map(link => link.getAttribute('href')))) {
        const url = new URL(href, page.url());
        if (url.origin !== new URL(base).origin || !url.pathname.startsWith(new URL(base).pathname)) continue;
        const relative = url.pathname.slice(new URL(base).pathname.length) || 'index.html';
        const linked = await fs.readFile(path.join(root, relative));
        if (url.hash) assert(linked.toString().includes(`id="${url.hash.slice(1)}"`), 'Missing fragment: ' + href);
      }
      for (const [width,height] of [[320,720],[390,844],[844,390],[960,900],[1440,900],[1920,1080]]) {
      await page.setViewportSize({ width,height });
      await page.evaluate(() => document.fonts.ready);
      const result = await page.evaluate(() => ({
        horizontal:document.documentElement.scrollWidth > innerWidth + 1,
        clipped:[...document.querySelectorAll('[data-measure]')].filter(element =>
          element.getClientRects().length && (element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)).map(element => ({text:element.textContent.slice(0,60),scrollHeight:element.scrollHeight,clientHeight:element.clientHeight,scrollWidth:element.scrollWidth,clientWidth:element.clientWidth})),
      }));
      assert(!result.horizontal && !result.clipped.length, JSON.stringify({ width,result }));
        if (width === 320 || width === 960) await page.screenshot({ path:path.join(screenshots, `project-${file || 'index'}-${width}.png`), fullPage:true });
        if (width === 960) {
          await page.evaluate(() => scrollTo(0,0));
          await page.screenshot({ path:path.join(screenshots, `project-${file || 'index'}-top.png`) });
        }
      }
      await page.emulateMedia({ colorScheme:'dark', reducedMotion:'reduce' });
      await page.screenshot({ path:path.join(screenshots, `project-${file || 'index'}-dark.png`), fullPage:true });
      await page.emulateMedia({ colorScheme:'light' });
      await page.addStyleTag({ url:base + 'text-spacing.css' });
      await page.setViewportSize({ width:320,height:720 });
    const enlarged = await page.evaluate(() => ({
      horizontal:document.documentElement.scrollWidth > innerWidth + 1,
      outside:[...document.querySelectorAll('main *')].filter(element => element.getBoundingClientRect().right > innerWidth + 1).map(element => ({tag:element.tagName, text:element.textContent.slice(0,60),width:element.getBoundingClientRect().width})),
      overflowing:[...document.querySelectorAll('*')].filter(element => element.clientWidth && element.scrollWidth > element.clientWidth + 1).map(element=>({tag:element.tagName, text:element.textContent.slice(0,50),scroll:element.scrollWidth,width:element.clientWidth})),
      clipped:[...document.querySelectorAll('[data-measure]')].filter(element =>
        element.getClientRects().length && (element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)).map(element => element.textContent.slice(0,60)),
    }));
      assert(!enlarged.horizontal && !enlarged.clipped.length, file + ' enlarged text must reflow: ' + JSON.stringify(enlarged));
    }
    await page.goto(base + '#download');
    assert(await page.getByRole('heading', { name:'Download and set up' }).isVisible());
    const secret = 'b'.repeat(64);
    await page.goto(base + '#room=brsp_' + 'a'.repeat(64) + '&secret=' + secret);
    try { await page.locator('#viewer-name').waitFor({ timeout:5000 }); }
    catch { throw new Error(JSON.stringify({url:page.url(),errors,body:(await page.locator('body').innerText()).slice(0,300)})); }
    assert(new URL(page.url()).pathname.endsWith('/remote.html'));
    await page.waitForFunction(() => location.hash === '');
    assert(!page.url().includes(secret), 'Phone page must scrub the invitation');
    assert(await page.getByRole('button', { name:'Request access' }).isVisible());
    assert.deepEqual(errors, []);
    console.log('PASS: four study pages, 57 LSL definitions and 13 task CSV fields, pinned installer links, screenshots, 24 layouts, enlarged text, credits and private QR redirect');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
