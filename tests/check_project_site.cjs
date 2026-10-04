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
        await route.fulfill({ body:await fs.readFile(file), contentType:{ '.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.svg':'image/svg+xml', '.woff2':'font/woff2', '.json':'application/json' }[path.extname(file)] || 'application/octet-stream' });
      } catch { await route.fulfill({ status:404, body:'Missing site file' }); }
    });
    await page.goto(base);
    assert(await page.getByRole('heading', { name:'Breathing target-tracking studies on Windows' }).isVisible());
    assert(await page.getByRole('img', { name:/Respyra logo/u }).evaluate(image => image.complete && image.naturalWidth > 0));
    await page.waitForFunction(() => document.querySelector('h1').dataset.pretextFit);
    assert.notEqual(await page.locator('html').getAttribute('data-pretext-fit'), 'unavailable');
    assert.equal(await page.getByRole('link', { name:'Download Respyra Suite for Windows' }).getAttribute('href'),
      'https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v0.3.6/00-Respyra-Suite_0.3.6_x64-setup.exe');
    for (const [name, file] of [
      ['Download Vernier Stream Mini separately', 'Vernier-Stream-Mini_0.6.5_x64-setup.exe'],
      ['Download Polar Stream Mini separately', 'Polar-Stream-Mini_0.6.5_x64-setup.exe'],
    ]) {
      assert.equal(await page.getByRole('link', { name }).getAttribute('href'),
        'https://github.com/GeorgeFejer91/respyra-2.0/releases/download/v0.3.6/' + file);
    }
    for (const name of ['Download Vernier Stream Mini separately', 'Download Polar Stream Mini separately', 'Stream and data-flow wiki', 'Read the original preprint']) {
      assert(await page.getByRole('link', { name }).isVisible(), name);
    }
    for (const [width,height] of [[320,720],[390,844],[960,900],[1440,900]]) {
      await page.setViewportSize({ width,height });
      await page.evaluate(() => document.fonts.ready);
      const result = await page.evaluate(() => ({
        horizontal:document.documentElement.scrollWidth > innerWidth + 1,
        clipped:[...document.querySelectorAll('[data-measure]')].filter(element =>
          element.getClientRects().length && (element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)).map(element => ({text:element.textContent.slice(0,60),scrollHeight:element.scrollHeight,clientHeight:element.clientHeight,scrollWidth:element.scrollWidth,clientWidth:element.clientWidth})),
      }));
      assert(!result.horizontal && !result.clipped.length, JSON.stringify({ width,result }));
      if (width === 320 || width === 960) await page.screenshot({ path:path.join(screenshots, `project-site-${width}.png`), fullPage:true });
    }
    await page.addStyleTag({ url:base + 'text-spacing.css' });
    await page.setViewportSize({ width:320,height:720 });
    const enlarged = await page.evaluate(() => ({
      horizontal:document.documentElement.scrollWidth > innerWidth + 1,
      clipped:[...document.querySelectorAll('[data-measure]')].filter(element =>
        element.getClientRects().length && (element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)).map(element => element.textContent.slice(0,60)),
    }));
    assert(!enlarged.horizontal && !enlarged.clipped.length, 'Enlarged text must reflow: ' + JSON.stringify(enlarged));
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
    console.log('PASS: project landing, links, logo, reflow and private QR redirect');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
