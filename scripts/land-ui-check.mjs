// One-off Playwright smoke test for the /land page, run manually during
// development. Not part of `npm test` — it drives a real browser against
// the dev server and mocks the three provider routes at the browser
// network layer, since this sandbox has no outbound access to Nominatim/
// Overpass/USDA. Delete or keep at the maintainer's discretion.
import { chromium } from 'playwright';

const BASE_URL = process.env.LAND_UI_CHECK_URL || 'http://localhost:3000';

const GEOCODE_MULTI = {
  results: [
    { displayName: '123 Main St, Austin, TX, USA', lat: 30.2672, lon: -97.7431, boundingBox: null, category: 'place' },
    { displayName: '123 Main St, Buda, TX, USA', lat: 30.0855, lon: -97.8403, boundingBox: null, category: 'place' },
  ],
};

const GEOCODE_SINGLE = {
  results: [{ displayName: '456 Ranch Rd, Dripping Springs, TX, USA', lat: 30.19, lon: -98.09, boundingBox: null, category: 'place' }],
};

const POWER_LINES_WITH_DATA = {
  lines: [
    {
      id: 1,
      kind: 'line',
      voltage: 138000,
      operator: 'Oncor',
      path: [
        [-98.1, 30.18],
        [-98.08, 30.2],
      ],
    },
  ],
  points: [{ id: 2, kind: 'tower', voltage: 138000, lon: -98.09, lat: 30.19 }],
  bbox: { minLon: -98.1, minLat: 30.18, maxLon: -98.08, maxLat: 30.2 },
};

const SOIL_CAUTION = {
  suitability: 'caution',
  reason: 'Dominant soil drainage class is "Somewhat poorly drained" — may need an engineered system.',
  dominantComponent: {
    mapUnitSymbol: 'TxA',
    mapUnitName: 'Test soil',
    componentName: 'Testland',
    componentPercent: 80,
    drainageClass: 'Somewhat poorly drained',
    hydric: 'No',
  },
  components: [],
};

function ok(name, condition) {
  console.log(`${condition ? 'PASS' : 'FAIL'} — ${name}`);
  if (!condition) process.exitCode = 1;
}

async function main() {
  // executablePath override is for sandboxes with a pre-installed, version-
  // mismatched Chromium (set LAND_UI_CHECK_CHROMIUM); a normal machine with
  // `npx playwright install` run should leave this unset.
  const browser = await chromium.launch(
    process.env.LAND_UI_CHECK_CHROMIUM ? { executablePath: process.env.LAND_UI_CHECK_CHROMIUM } : {},
  );
  const page = await browser.newPage();
  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', (err) => consoleErrors.push(String(err)));

  await page.route('**/api/land/geocode**', async (route) => {
    const url = new URL(route.request().url());
    const q = url.searchParams.get('q') || '';
    const body = q.includes('Main St') ? GEOCODE_MULTI : GEOCODE_SINGLE;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.route('**/api/land/power-lines**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(POWER_LINES_WITH_DATA) });
  });
  await page.route('**/api/land/soil**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(SOIL_CAUTION) });
  });

  // 'load', not 'networkidle': the map's base-tile requests go to a domain
  // this sandbox blocks and retry indefinitely, so the network never goes
  // idle. Every subsequent wait targets a specific element instead.
  await page.goto(`${BASE_URL}/land`, { waitUntil: 'load' });
  await page.getByTestId('land-map').waitFor({ state: 'visible', timeout: 10_000 });
  ok('map container mounted', await page.getByTestId('land-map').isVisible());

  // Multi-result search: results list should render, nothing auto-selected.
  await page.getByTestId('search-input').fill('Main St');
  await page.getByTestId('search-button').click();
  await page.getByTestId('search-results').waitFor({ state: 'visible', timeout: 5000 });
  const resultCount = await page.getByTestId('search-results').locator('li').count();
  ok('multi-result search shows a results list', resultCount === 2);

  // Click a result: soil + power summaries should populate.
  await page.getByTestId('search-results').locator('button').first().click();
  await page.getByTestId('soil-result').waitFor({ state: 'visible', timeout: 5000 });
  const soilBadge = page.getByTestId('soil-badge');
  ok('soil badge shows CAUTION suitability', (await soilBadge.getAttribute('data-suitability')) === 'caution');
  ok('soil reason text rendered', (await page.getByTestId('soil-result').innerText()).includes('engineered system'));

  await page.getByTestId('power-summary').waitFor({ state: 'visible', timeout: 5000 });
  const powerText = await page.getByTestId('power-summary').innerText();
  ok('power summary reports 1 line segment and 1 point', powerText.includes('1 line segment') && powerText.includes('1 tower/pole/substation point'));

  // Layer toggle should flip the checkbox state without erroring.
  const toggle = page.getByTestId('power-lines-toggle');
  ok('power-lines toggle starts checked', await toggle.isChecked());
  await toggle.click();
  ok('power-lines toggle unchecks', !(await toggle.isChecked()));

  // Single-result search should auto-select without showing a list.
  await page.getByTestId('search-input').fill('456 Ranch');
  await page.getByTestId('search-button').click();
  await page.getByTestId('soil-badge').waitFor({ state: 'visible', timeout: 5000 });
  const listVisible = await page.getByTestId('search-results').isVisible().catch(() => false);
  ok('single-result search auto-selects (no list shown)', !listVisible);

  await page.screenshot({ path: 'scripts/land-ui-check.png', fullPage: true });

  // Basemap tile fetches are expected to fail in a sandboxed CI/dev
  // environment with no outbound access to arcgisonline.com; that's a
  // network-policy artifact, not an app bug. Any OTHER console error is real.
  const unexpectedErrors = consoleErrors.filter((e) => !e.includes('arcgisonline.com') && !e.includes('ERR_TUNNEL_CONNECTION_FAILED'));
  ok(
    `no unexpected console/page errors (${consoleErrors.length} expected basemap-tile network errors filtered out)`,
    unexpectedErrors.length === 0,
  );
  if (unexpectedErrors.length) console.log('Unexpected errors:', unexpectedErrors);

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
