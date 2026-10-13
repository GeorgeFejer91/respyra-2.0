const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const base = 'https://georgefejer91.github.io/respyra-2.0/';
const root = path.resolve('companion');
const screenshots = path.resolve('.for-ai-local');
const sitePages = ['', 'download/','variables.html','markers.html','study.html','about.html'];

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
      const file = path.resolve(root, relative.endsWith('/') ? relative + 'index.html' : relative);
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
      './download');
    assert.equal(await page.locator('main a[href*="releases/download/"]').count(), 0, 'Installer choices belong on the download page');
    for (const name of ['Stream and data-flow wiki', 'Read the original preprint']) {
      assert(await page.getByRole('link', { name }).isVisible(), name);
    }
    const downloadRelease = JSON.parse(await fs.readFile('companion/download/release.json', 'utf8'));
    await page.goto(base + 'download/');
    assert.equal(page.url(), base + 'download/');
    assert(await page.getByRole('heading', {name:'Download Respyra Suite', exact:true}).isVisible(), (await page.locator('body').innerText()).slice(0, 300));
    assert.deepEqual(await page.locator('[data-installer]').evaluateAll(links => links.map(link => link.dataset.installer)), ['suite','respyra','polar','vernier']);
    assert.deepEqual(await page.locator('[data-installer]').evaluateAll(links => links.map(link => link.getAttribute('href'))),
      downloadRelease.installers.map(installer => `https://github.com/GeorgeFejer91/respyra-2.0/releases/download/${downloadRelease.tag}/${installer.file}`));
    assert.equal(await page.locator('main .download-link').count(), 1, 'The full suite is the primary download');
    assert(await page.locator('#suite').getByText(/Recommended: install all three apps together/).isVisible());
    assert(await page.locator('#suite').getByText(new RegExp('Latest tested release · ' + downloadRelease.installers[0].version)).isVisible());
    assert(await page.getByText(/Page updated:/).isVisible());
    assert.equal(await page.locator('time').getAttribute('datetime'), downloadRelease.pageUpdatedAt);
    const updateDate = new Intl.DateTimeFormat('en-GB', {day:'numeric', month:'long', year:'numeric', hour:'2-digit', minute:'2-digit', timeZone:'Europe/Berlin', timeZoneName:'short'}).format(new Date(downloadRelease.pageUpdatedAt));
    assert.equal(await page.locator('time').textContent(), updateDate);
    const catalogSource = await fs.readFile('mini-streams/docs/metric-catalog.js', 'utf8');
    const catalog = JSON.parse(catalogSource.slice(catalogSource.indexOf('['), catalogSource.lastIndexOf(']') + 1));
    const primaryIds = ['raw_ecg','raw_acc','heart_rate','rr_interval','adr_pca_waveform','adr_axis_mean_difference','adr_moving_average_phase'];
    const defaults = primaryIds.map(id => catalog.find(metric => metric.id === id));
    assert(defaults.every(Boolean));
    await page.goto(base + 'variables.html');
    assert.equal(await page.locator('main table').count(), 1, 'One canonical stream table');
    assert.equal(await page.locator('main .app-reference, main details, [data-variable-id], [data-support-id], [data-csv-id], #naming').count(), 0,
      'The variable page must not repeat the table in separate reference panels');
    assert(await page.getByText(/All available streams below are selected for recording by default, even when not displayed/).isVisible());
    const streamNames = [
      'Polar_rawECG', 'Polar_rawACC', 'Polar_HR', 'Polar_RR', 'Polar_ChestPCA', 'Polar_ChestDT',
      'Polar_BreathPhase', 'Polar_Link', 'Vernier_rawForce', 'Vernier_Link',
      'Respyra_rawForce_calibrated', 'Respyra_ChestPCA_calibrated', 'Respyra_ChestDT_calibrated', 'Respyra-Events',
    ];
    const inventory = page.locator('.stream-inventory');
    const streamRows = inventory.locator('.stream-row');
    assert.deepEqual(await inventory.locator('thead th').allTextContents(), ['Stream name', 'Recorded contents', 'Long-form description']);
    assert.deepEqual(await inventory.locator('tbody th code').allTextContents(), streamNames);
    assert.equal(await streamRows.count(), 14);
    assert((await streamRows.evaluateAll(rows => rows.map(row => row.children.length))).every(count => count === 3));
    assert.deepEqual(await inventory.locator('tbody').evaluateAll(groups => groups.map(group => ({
      source:group.id, count:group.querySelectorAll('.stream-row').length,
      label:document.getElementById(group.getAttribute('aria-labelledby')).textContent,
      columns:group.querySelector('.inventory-group th').colSpan,
    }))), [
      {source:'polar', count:8, label:'Polar Stream Mini · 8 streams', columns:3},
      {source:'vernier', count:2, label:'Vernier Stream Mini · 2 streams', columns:3},
      {source:'respyra', count:4, label:'Respyra 2.0 · 4 streams', columns:3},
    ]);
    assert.deepEqual(await inventory.locator('#polar .stream-row th code').allTextContents(),
      [...defaults.map(metric => 'Polar_' + metric.streamSuffix), 'Polar_Link']);
    assert((await inventory.locator('tbody td:last-child p').allTextContents()).every(text => text.length > 240), 'Every stream needs a substantive long-form description');
    assert((await streamRows.nth(8).textContent()).includes('Seven additional channels'));
    assert((await streamRows.nth(10).textContent()).includes('(Force − center) / amplitude'));
    for (const row of [4, 11]) assert((await streamRows.nth(row).textContent()).includes('principal component analysis (PCA)'), 'PCA must be written out in the inventory');
    assert((await streamRows.nth(4).textContent()).includes('plus PCA quality and validity'));
    assert((await streamRows.nth(5).textContent()).includes('plus DT validity, PCA validity and PCA quality'));
    await page.goto(base + 'about.html');
    assert(await page.getByText(/current Windows release is v2.3.15/).isVisible());
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
    await staticPage.goto(base + 'download/');
    assert(await staticPage.getByRole('heading', {name:'Download Respyra Suite', exact:true}).isVisible());
    assert.equal(await staticPage.locator('[data-installer]').count(), 4, 'All installers remain available without JavaScript');
    assert.equal(await staticPage.locator('time').getAttribute('datetime'), downloadRelease.pageUpdatedAt);
    await staticContext.close();
    for (const file of sitePages) {
      const screenshotName = file.replace(/\/$/, '') || 'index';
      await page.goto(base + file);
      await page.waitForFunction(() => document.querySelector('h1').dataset.pretextFit);
      assert.equal(await page.locator('nav[aria-label="Site navigation"] a').filter({hasText:/^Markers$/}).count(), 1);
      const downloadNav = page.getByRole('navigation', {name:'Site navigation'}).getByRole('link', {name:'Download', exact:true});
      assert.equal(new URL(await downloadNav.getAttribute('href'), page.url()).href, base + 'download');
      for (const image of await page.locator('img').all()) {
        await image.scrollIntoViewIfNeeded();
        await image.evaluate(image => image.decode());
      }
      // Every local file link and fragment must exist in the published payload.
      for (const href of await page.locator('a[href]').evaluateAll(links => links.map(link => link.getAttribute('href')))) {
        const url = new URL(href, page.url());
        if (url.origin !== new URL(base).origin || !url.pathname.startsWith(new URL(base).pathname)) continue;
        let relative = url.pathname.slice(new URL(base).pathname.length) || 'index.html';
        if (relative === 'download' || relative.endsWith('/')) relative = relative.replace(/\/$/, '') + '/index.html';
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
      if (file === 'variables.html' && (width === 390 || width === 960)) {
        await page.locator('#outlets').scrollIntoViewIfNeeded();
        await page.screenshot({ path:path.join(screenshots, `stream-inventory-${width}.png`) });
      }
      if (file === 'markers.html') {
        const panels = await page.locator('.app-reference').evaluateAll(elements => elements.map(element => ({
          width:element.scrollWidth - element.clientWidth, height:element.scrollHeight - element.clientHeight,
        })));
        assert(panels.every(panel => panel.width <= 1 && panel.height <= 1), JSON.stringify({ width,panels }));
        assert.notEqual(await page.locator('#marker-reset').getAttribute('data-pretext-fit'), null);
      }
        if (width === 320 || width === 960) await page.screenshot({ path:path.join(screenshots, `project-${screenshotName}-${width}.png`), fullPage:true });
        if (width === 960) {
          await page.evaluate(() => scrollTo(0,0));
          await page.screenshot({ path:path.join(screenshots, `project-${screenshotName}-top.png`) });
        }
      }
      await page.emulateMedia({ colorScheme:'dark', reducedMotion:'reduce' });
      const dark = await page.evaluate(() => ({ horizontal:document.documentElement.scrollWidth > innerWidth + 1 }));
      assert(!dark.horizontal, file + ' dark layout');
      await page.screenshot({ path:path.join(screenshots, `project-${screenshotName}-dark.png`), fullPage:true });
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
    await page.waitForURL(base + 'download/');
    assert(await page.getByRole('heading', { name:'Download Respyra Suite', exact:true }).isVisible());
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
      const colors = await page.locator('.stream-inventory tbody').evaluateAll(groups => groups.map(group => getComputedStyle(group).borderLeftColor));
      assert.deepEqual(colors, scheme === 'light' ? ['rgb(213, 0, 28)','rgb(229, 179, 27)','rgb(9, 105, 218)'] : ['rgb(255, 64, 85)','rgb(229, 179, 27)','rgb(127, 198, 255)']);
      assert.deepEqual(await page.locator('.inventory-group h2').evaluateAll(headings => headings.map(heading => getComputedStyle(heading).color)),
        scheme === 'light' ? ['rgb(185, 0, 24)','rgb(118, 90, 0)','rgb(9, 105, 218)'] : ['rgb(255, 120, 135)','rgb(240, 204, 85)','rgb(127, 198, 255)']);
    }
    assert.deepEqual(errors, []);
    const checkedPaths = ['companion/index.html','companion/download/index.html','companion/download/release.json','companion/study.html','companion/variables.html','companion/markers.html','companion/about.html',
      'companion/site.css','companion/site.js','companion/marker-catalog.json','companion/text-fit.js','companion/remote-profile.js',
      'scripts/prepare-download-page.mjs','scripts/prepare-marker-reference.mjs','scripts/prepare-web.mjs','src/mpi/event_markers/catalog.json','tests/check_project_site.cjs','package.json','pnpm-lock.yaml'];
    const hashes = {};
    for (const file of checkedPaths) hashes[file] = require('node:crypto').createHash('sha256').update(await fs.readFile(file)).digest('hex');
    await fs.writeFile(path.join(screenshots, 'markers-site-evidence.json'), JSON.stringify({
      result:'VERIFIED', checkedAt:new Date().toISOString(), node:process.version, playwright:require('playwright/package.json').version,
      browser:browser.version(), headless:true, currentMarkers:activeMarkers.length, pageLayouts:sitePages.length * 8, hashes,
    }, null, 2));
    console.log(`PASS: ${activeMarkers.length} current markers and retired catalog, exact timing/fields/dictionary, search/families/reset/deep links/keyboard/no-JS, app colors, six pages and 48 layouts, enlarged text, local links, verified download links/date, legacy download and private QR redirects`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
