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
    const serve = async route => {
      const relative = new URL(route.request().url()).pathname.slice(new URL(base).pathname.length) || 'index.html';
      if (relative === 'text-spacing.css') return route.fulfill({ contentType:'text/css', body:'html{font-size:32px!important} *{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important} p{margin-bottom:2em!important}' });
      const file = path.resolve(root, relative);
      if (!file.startsWith(root + path.sep)) return route.abort();
      try {
      await route.fulfill({ body:await fs.readFile(file), contentType:{ '.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.svg':'image/svg+xml', '.png':'image/png', '.woff2':'font/woff2', '.json':'application/json' }[path.extname(file)] || 'application/octet-stream' });
      } catch { await route.fulfill({ status:404, body:'Missing site file' }); }
    };
    await context.route(base + '**', serve);
    await page.goto(base);
    assert(await page.getByRole('heading', { name:'Breathing target-tracking studies on Windows' }).isVisible());
    assert(await page.getByRole('img', { name:/Respyra logo/u }).evaluate(image => image.complete && image.naturalWidth > 0));
    await page.waitForFunction(() => document.querySelector('h1').dataset.pretextFit);
    assert.notEqual(await page.locator('html').getAttribute('data-pretext-fit'), 'unavailable');
    assert.equal(await page.getByRole('link', { name:'Download Respyra Suite for Windows' }).getAttribute('href'),
      'https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v2.3.12/00-Respyra-Suite_2.3.12_x64-setup.exe');
    assert.equal(await page.getByRole('link', { name:'Respyra 2.0 only' }).getAttribute('href'),
      'https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v2.3.12/Respyra-2.0_2.3.12_x64-setup.exe');
    for (const [name, file] of [
      ['Download Vernier Stream Mini separately', 'Vernier-Stream-Mini_0.6.9_x64-setup.exe'],
      ['Download Polar Stream Mini separately', 'Polar-Stream-Mini_0.6.9_x64-setup.exe'],
    ]) {
      assert.equal(await page.getByRole('link', { name }).getAttribute('href'),
        'https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v2.3.12/' + file);
    }
    for (const name of ['Download Vernier Stream Mini separately', 'Download Polar Stream Mini separately', 'Stream and data-flow wiki', 'Read the original preprint']) {
      assert(await page.getByRole('link', { name }).isVisible(), name);
    }
    const catalogSource = await fs.readFile('mini-streams/docs/metric-catalog.js', 'utf8');
    const catalog = JSON.parse(catalogSource.slice(catalogSource.indexOf('['), catalogSource.lastIndexOf(']') + 1));
    const primaryIds = ['raw_ecg','raw_acc','heart_rate','rr_interval','adr_pca_waveform','adr_axis_mean_difference','adr_moving_average_phase'];
    const defaults = primaryIds.map(id => catalog.find(metric => metric.id === id));
    assert(defaults.every(Boolean));
    await page.goto(base + 'variables.html');
    assert.deepEqual(await page.locator('#polar [data-variable-id]').evaluateAll(rows => rows.map(row => row.dataset.variableId)),
      primaryIds);
    for (const metric of defaults) assert((await page.locator(`[data-variable-id="${metric.id}"] code`).textContent()).includes('Polar-H10-Mini_' + metric.streamSuffix));
    assert.deepEqual(await page.locator('#polar [data-support-id]').evaluateAll(rows => rows.map(row => row.dataset.supportId)),
      ['adr_pca_quality','adr_pca_valid','adr_axis_difference_valid','polar_signal_state']);
    assert.equal(await page.locator('#polar-support').getAttribute('open'), null);
    await page.locator('#polar-support summary').click();
    assert(await page.locator('[data-support-id="adr_pca_valid"]').isVisible());
    const vernierDiagnostics = ['sequence','dropped_rows_before','device_drop_reports_before','sample_period_us','decode_latency_ns','host_receive_timestamp_ns','encoding_code'];
    assert.deepEqual(await page.locator('#vernier [data-variable-id]').evaluateAll(rows => rows.map(row => row.dataset.variableId)),
      ['force','respiration_rate','steps','step_rate','vernier_signal_state',...vernierDiagnostics]);
    assert.equal(await page.locator('#respyra [data-variable-id]').count(), 3);
    assert.equal(await page.locator('[data-variable-id] strong').count(), 22);
    assert.equal(await page.locator('[data-csv-id] strong').count(), 13);
    assert(await page.getByText(/can advertise 17 default outlets/).isVisible());
    assert.equal(await page.locator('#vernier-optional').getAttribute('open'), null);
    await page.locator('#vernier-optional summary').click();
    assert(await page.locator('[data-optional-id="vernier_breathing"]').isVisible());
    assert(await page.getByText(/Two outlets start selected/).isVisible());
    const definitions = await page.locator('[data-variable-id] p').allTextContents();
    assert(definitions.every(text => text.length > 80), 'Every default variable needs a substantive definition');
    await page.goto(base + 'about.html');
    assert(await page.getByText(/current Windows release is v2.3.12/).isVisible());
    assert.equal(await page.getByRole('link', {name:'George Fejer · Google Scholar'}).getAttribute('href'), 'https://scholar.google.com/citations?hl=en&user=GPARoloAAAAJ');
    assert.equal(await page.getByRole('link', {name:'George Fejer · ORCID'}).getAttribute('href'), 'https://orcid.org/0000-0002-4904-5504');
    assert(await page.getByText(/Micah Allen and the Embodied Computation Group created/).isVisible());
    const markerCatalog = JSON.parse(await fs.readFile('src/mpi/event_markers/catalog.json', 'utf8'));
    const activeMarkers = Object.entries(markerCatalog.events).filter(([, event]) => event.active !== false)
      .sort(([a], [b]) => a.localeCompare(b));
    assert.deepEqual(JSON.parse(await fs.readFile('companion/marker-catalog.json', 'utf8')), markerCatalog);
    await page.goto(base + 'markers.html');
    await page.waitForFunction(() => document.querySelector('#marker-filters').hidden === false);
    assert.deepEqual(await page.locator('#marker-list > li').evaluateAll(rows => rows.map(row => row.dataset.markerName)), activeMarkers.map(([name]) => name));
    for (const [name, event] of activeMarkers) {
      const row = page.locator(`[data-marker-name="${name}"]`);
      assert((await row.textContent()).includes(event.when), name + ' emission timing');
      assert.deepEqual(await row.locator('[data-marker-field]').evaluateAll(fields => fields.map(field => field.dataset.markerField)), event.fields);
    }
    const dictionary = { ...markerCatalog.common_fields, ...markerCatalog.event_field_definitions };
    assert.deepEqual(await page.locator('[data-field-name]').evaluateAll(rows => Object.fromEntries(rows.map(row => [row.dataset.fieldName, row.querySelector('dd').textContent]))), dictionary);
    assert.equal(await page.locator('#retired [data-retired]').count(), Object.values(markerCatalog.events).filter(event => event.active === false).length);
    await page.locator('#marker-search').fill('TRACKING.STARTED');
    assert.equal(await page.locator('#marker-list > li:visible').count(), 1);
    assert(await page.locator('[data-marker-name="tracking.started"]').isVisible());
    await page.locator('#marker-reset').click();
    for (const group of new Set(activeMarkers.map(([name]) => name.split('.')[0]))) {
      await page.locator('#marker-family').selectOption(group);
      assert.equal(await page.locator('#marker-list > li:visible').count(), activeMarkers.filter(([name]) => name.startsWith(group + '.')).length);
    }
    await page.locator('#marker-reset').click();
    await page.locator('#marker-search').fill('pre_recording_events');
    assert(await page.locator('[data-marker-name="recording.started"]').isVisible());
    await page.locator('#marker-search').fill('this marker does not exist');
    assert.equal(await page.locator('#marker-list > li:visible').count(), 0);
    assert(await page.locator('#marker-empty').isVisible());
    // A direct event link reveals its full row even when filters hid it.
    await page.evaluate(() => { location.hash = 'event-tracking.started'; });
    await page.locator('[data-marker-name="tracking.started"]').waitFor({ state:'visible' });
    await page.locator('#marker-search').focus();
    await page.keyboard.press('Tab');
    assert(await page.locator('#marker-family').evaluate(element => element === document.activeElement));
    await page.keyboard.press('Tab');
    assert(await page.locator('#marker-reset').evaluate(element => element === document.activeElement));
    await page.setViewportSize({ width:960,height:900 });
    await page.locator('#inventory').scrollIntoViewIfNeeded();
    await page.screenshot({ path:path.join(screenshots, 'project-markers-inventory.png') });
    const staticContext = await browser.newContext({ javaScriptEnabled:false });
    await staticContext.route(base + '**', serve);
    const staticPage = await staticContext.newPage();
    await staticPage.goto(base + 'markers.html');
    assert.equal(await staticPage.locator('#marker-list > li:visible').count(), activeMarkers.length);
    assert(await staticPage.locator('#fields').isVisible());
    assert(await staticPage.locator('#marker-filters').evaluate(element => element.hidden));
    await staticContext.close();
    for (const file of ['', 'variables.html','markers.html','study.html','about.html']) {
      await page.goto(base + file);
      await page.waitForFunction(() => document.querySelector('h1').dataset.pretextFit);
      assert.equal(await page.locator('nav[aria-label="Site navigation"] a[href="./markers.html"]').count(), 1);
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
      for (const [width,height] of [[320,720],[390,844],[600,720],[601,720],[844,390],[960,900],[1440,390],[1920,1080]]) {
      await page.setViewportSize({ width,height });
      await page.evaluate(() => document.fonts.ready);
      const result = await page.evaluate(() => ({
        horizontal:document.documentElement.scrollWidth > innerWidth + 1,
        clipped:[...document.querySelectorAll('[data-measure]')].filter(element =>
          element.getClientRects().length && (element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)).map(element => ({text:element.textContent.slice(0,60),scrollHeight:element.scrollHeight,clientHeight:element.clientHeight,scrollWidth:element.scrollWidth,clientWidth:element.clientWidth})),
      }));
      assert(!result.horizontal && !result.clipped.length, JSON.stringify({ width,result }));
      if (file === 'markers.html') {
        const panels = await page.locator('.app-reference').evaluateAll(elements => elements.map(element => ({
          width:element.scrollWidth - element.clientWidth, height:element.scrollHeight - element.clientHeight,
        })));
        assert(panels.every(panel => panel.width <= 1 && panel.height <= 1), JSON.stringify({ width,panels }));
        assert.notEqual(await page.locator('#marker-reset').getAttribute('data-pretext-fit'), null);
      }
        if (width === 320 || width === 960) await page.screenshot({ path:path.join(screenshots, `project-${file || 'index'}-${width}.png`), fullPage:true });
        if (width === 960) {
          await page.evaluate(() => scrollTo(0,0));
          await page.screenshot({ path:path.join(screenshots, `project-${file || 'index'}-top.png`) });
        }
      }
      await page.emulateMedia({ colorScheme:'dark', reducedMotion:'reduce' });
      const dark = await page.evaluate(() => ({ horizontal:document.documentElement.scrollWidth > innerWidth + 1 }));
      assert(!dark.horizontal, file + ' dark layout');
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
    await page.goto(base + 'study.html');
    assert(await page.locator('#visualization').getByText(/automatically saves a six-panel image/).isVisible());
    assert(await page.locator('#troubleshooting').getByText(/separate Error report window/).isVisible());
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
    await page.goto(base + 'variables.html');
    for (const scheme of ['light','dark']) {
      await page.emulateMedia({ colorScheme:scheme });
      const colors = await page.locator('.source-links .polar, .source-links .vernier, .source-links .respyra').evaluateAll(links => links.map(link => getComputedStyle(link).borderBottomColor));
      assert.deepEqual(colors, scheme === 'light' ? ['rgb(213, 0, 28)','rgb(229, 179, 27)','rgb(9, 105, 218)'] : ['rgb(255, 64, 85)','rgb(229, 179, 27)','rgb(127, 198, 255)']);
      assert.deepEqual(await page.locator('#polar, #vernier, #respyra').evaluateAll(panels => panels.map(panel => getComputedStyle(panel).borderLeftColor)), colors);
    }
    assert.deepEqual(errors, []);
    const checkedPaths = ['companion/index.html','companion/study.html','companion/variables.html','companion/markers.html','companion/about.html',
      'companion/site.css','companion/site.js','companion/marker-catalog.json','companion/text-fit.js','companion/remote-profile.js',
      'scripts/prepare-marker-reference.mjs','scripts/prepare-web.mjs','src/mpi/event_markers/catalog.json','tests/check_project_site.cjs','package.json','pnpm-lock.yaml'];
    const hashes = {};
    for (const file of checkedPaths) hashes[file] = require('node:crypto').createHash('sha256').update(await fs.readFile(file)).digest('hex');
    await fs.writeFile(path.join(screenshots, 'markers-site-evidence.json'), JSON.stringify({
      result:'VERIFIED', checkedAt:new Date().toISOString(), node:process.version, playwright:require('playwright/package.json').version,
      browser:browser.version(), headless:true, currentMarkers:activeMarkers.length, pageLayouts:40, hashes,
    }, null, 2));
    console.log(`PASS: ${activeMarkers.length} current markers and retired catalog, exact timing/fields/dictionary, search/families/reset/deep links/keyboard/no-JS, app colors, five pages and 40 layouts, enlarged text, local links, installer links, credits and private QR redirect`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
