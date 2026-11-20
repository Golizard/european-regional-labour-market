/* Optional UI checks: Node.js and Playwright are development-only tools. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '..', 'docs');
const screenshotDir = process.env.MAP_SCREENSHOT_DIR;
const viewports = [
  ['desktop', 1440, 900], ['laptop', 1024, 768], ['tablet', 820, 1180],
  ['phone', 390, 844], ['small-phone', 320, 568], ['landscape', 844, 390],
];

function serve(request, response) {
  const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
  const file = path.resolve(root, `.${pathname === '/' ? '/index.html' : pathname}`);
  if (!file.startsWith(root + path.sep)) { response.writeHead(403).end(); return; }
  const types = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css' };
  try { response.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' }); response.end(fs.readFileSync(file)); }
  catch { response.writeHead(404).end(); }
}

async function assertLayout(page, width) {
  const layout = await page.evaluate(() => {
    const rect = (id) => {
      const r = document.getElementById(id).getBoundingClientRect();
      return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, height: r.height };
    };
    const r = document.querySelector('.atlas-top').getBoundingClientRect();
    return {
      map: rect('atlas-map-stage'), tray: rect('atlas-bottom'),
      top: { right: r.right, bottom: r.bottom },
      horizontalOverflow: document.documentElement.scrollWidth > innerWidth,
    };
  });
  assert.equal(layout.horizontalOverflow, false, 'Horizontal page overflow');
  assert.ok(layout.map.height >= 149, `Map too short: ${layout.map.height}`);
  if (width <= 720) {
    assert.ok(layout.top.bottom <= layout.map.top + 1, 'Header covers the map');
    assert.ok(layout.tray.top >= layout.map.bottom - 1, 'Bottom panel covers the map');
  } else {
    assert.ok(layout.top.right <= layout.map.left + 1, 'Sidebar covers the map');
  }
  return layout;
}

async function main() {
  const server = http.createServer(serve);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ headless: true });
  try {
    for (const [name, width, height] of viewports) {
      const context = await browser.newContext({ viewport: { width, height }, hasTouch: width <= 720, isMobile: width <= 720 });
      const page = await context.newPage();
      const errors = [];
      const externalRequests = [];
      page.on('pageerror', (error) => errors.push(error.message));
      page.on('response', (response) => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
      await page.route('**/*', (route) => {
        if (route.request().url().startsWith(origin + '/')) return route.continue();
        externalRequests.push(route.request().url());
        return route.abort();
      });
      await page.goto(origin, { waitUntil: 'networkidle' });
      await page.waitForFunction(() => window.labourAtlas?.regions.getLayers().length === 244);
      assert.equal(await page.title(), 'EU Labour Market — Regional Explorer, 2024');
      assert.equal(await page.locator('.atlas-region').count(), 244);
      const countryLabels = await page.evaluate(() => {
        const properties = window.labourAtlas.regions.getLayers().map((layer) => layer.feature.properties);
        return {
          complete: properties.every((region) => region.country_name?.trim() && region.country_code === region.region_code.slice(0, 2)),
          countries: new Set(properties.map((region) => region.country_code)).size,
          examples: ['PL43', 'EL30', 'FR10'].map((code) => properties.find((region) => region.region_code === code).country_name),
        };
      });
      assert.equal(countryLabels.complete, true);
      assert.equal(countryLabels.countries, 27);
      assert.deepEqual(countryLabels.examples, ['Poland', 'Greece', 'France']);
      assert.equal(await page.locator('#atlas-key').evaluate((element) => element.open), width > 720);
      const layout = await assertLayout(page, width);
      if (screenshotDir) {
        fs.mkdirSync(screenshotDir, { recursive: true });
        await page.screenshot({ path: path.join(screenshotDir, `${name}-gdp.png`) });
      }

      await page.getByRole('button', { name: 'Unemployment', exact: true }).click();
      assert.equal(await page.locator('#atlas-metric-title').innerText(), 'Unemployment');
      assert.equal(await page.locator('#atlas-coverage').innerText(), '241 / 244');
      assert.equal(await page.locator('#atlas-missing-key').isVisible(), true);
      assert.equal(await page.evaluate(() => window.labourAtlas.regions.getLayers().find((layer) => layer.feature.properties.region_code === 'PL43').options.fillColor), '#aab5bd');

      const regionPath = page.getByRole('button', { name: 'Explore Lubuskie', exact: true });
      if (width > 720) {
        await regionPath.hover();
        assert.match(await page.locator('.atlas-tooltip').innerText(), /Poland/);
      }
      if (width <= 720) await regionPath.tap(); else await regionPath.click();
      assert.equal(await page.locator('#atlas-region-name').innerText(), 'Lubuskie');
      assert.equal(await page.locator('#atlas-region-code').innerText(), 'Poland · PL43 · 2024');
      assert.equal(await page.locator('#atlas-region-gdp').innerText(), '25,000');
      assert.equal(await page.locator('#atlas-region-unemployment').innerText(), 'Not available');
      assert.match(await page.locator('#atlas-region-flags').innerText(), /low reliability/);
      await assertLayout(page, width);
      if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, `${name}-selected.png`) });

      await page.getByRole('button', { name: 'Clear selected region' }).click();
      await page.locator('#atlas-bottom').evaluate((element) => { element.scrollTop = 0; });
      await page.locator('#atlas-key > summary').click();
      assert.equal(await page.locator('#atlas-key').evaluate((element) => element.open), width <= 720);
      await assertLayout(page, width);
      await page.getByRole('button', { name: 'GDP per capita', exact: true }).click();
      assert.equal(await page.locator('#atlas-key').evaluate((element) => element.open), width <= 720, 'Metric switch reset legend expansion');
      assert.notEqual(await page.evaluate(() => window.labourAtlas.regions.getLayers().find((layer) => layer.feature.properties.region_code === 'PL43').options.fillColor), '#aab5bd');
      await page.getByRole('button', { name: 'All regions', exact: true }).click();
      assert.equal(await page.evaluate(() => window.labourAtlas.map.getBounds().contains([-12.83, 45.15])), true, 'Mayotte outside all-regions view');
      await page.getByRole('button', { name: 'Europe', exact: true }).click();
      assert.equal(await page.evaluate(() => window.labourAtlas.getState().activeMetric), 'gdp');
      if (name === 'desktop') {
        await page.getByRole('button', { name: 'Explore Lubuskie', exact: true }).focus();
        await page.keyboard.press('Enter');
        assert.equal(await page.evaluate(() => window.labourAtlas.getState().selectedRegion), 'PL43');
        await page.getByRole('button', { name: 'Clear selected region' }).click();
        await page.setViewportSize({ width: 390, height: 844 });
        await page.waitForTimeout(100);
        assert.equal(await page.locator('#atlas-key').evaluate((element) => element.open), false);
        await assertLayout(page, 390);
        await page.setViewportSize({ width, height });
        await page.waitForTimeout(100);
        assert.equal(await page.locator('#atlas-key').evaluate((element) => element.open), true);
      }
      assert.deepEqual(errors, [], `Browser errors at ${name}`);
      assert.deepEqual(externalRequests, [], `Unexpected external request at ${name}`);
      console.log(`PASS ${name} ${width}×${height}: 244 regions; map height ${Math.round(layout.map.height)}px; controls, selection, flags and extents work offline.`);
      await context.close();
    }
    const filePage = await browser.newPage();
    const fileErrors = [];
    const fileExternal = [];
    filePage.on('pageerror', (error) => fileErrors.push(error.message));
    filePage.on('request', (request) => { if (/^https?:/.test(request.url())) fileExternal.push(request.url()); });
    await filePage.goto(pathToFileURL(path.join(root, 'index.html')).href, { waitUntil: 'load' });
    await filePage.waitForFunction(() => window.labourAtlas?.regions.getLayers().length === 244);
    assert.deepEqual(fileErrors, []);
    assert.deepEqual(fileExternal, []);
    await filePage.close();
    console.log('PASS file:// opening, keyboard selection, responsive resizing and zero external asset requests.');
  } finally { await browser.close(); await new Promise((resolve) => server.close(resolve)); }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
