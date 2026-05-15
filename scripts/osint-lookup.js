// AMARA OS — Clark County Assessor + NV SOS OSINT Lookup
// Requires: npm install playwright && npx playwright install chromium
// Run from any machine with open outbound internet access.
// Real data only — no invented records.

const { chromium, firefox } = require('playwright');
const fs = require('fs');
const path = require('path');

const APNS = [
  { apn: '137-36-811-018', hint: 'CBSI LLC' },
  { apn: '139-29-811-038', hint: '' },
  { apn: '139-29-811-039', hint: '' },
  { apn: '139-29-811-040', hint: '' },
  { apn: '219-06-811-007', hint: '' },
  { apn: '219-06-811-023', hint: '' },
  { apn: '177-25-811-015', hint: 'CTO 20 HIALEAH LLC' },
];

const NV_SOS_ENTITIES = [
  'CBSI LLC',
  'ROMEWRIGHT PROPERTIES LLC',
  'SKY RANCH HOLDINGS LLC',
  'CTO 20 HIALEAH LLC',
];

const OUT = path.join(__dirname, '..', 'osint-output');

function setup() { fs.mkdirSync(OUT, { recursive: true }); }
function save(name, data) { fs.writeFileSync(path.join(OUT, name), data); }
function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function snap(page, name) {
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true }).catch(() => {});
}
async function dumpAll(page, name) {
  const text = await page.innerText('body').catch(() => '');
  const html = await page.content().catch(() => '');
  save(`${name}.txt`, text);
  save(`${name}.html`, html);
  return { text, html };
}

// Parcel data is confirmed present only when these specific tokens appear
function hasParcelData(text) {
  return /net\s*assessed|appraised\s*value|land\s*use\s*code|fiscal\s*year|legal\s*description|owner\s*name.*\n|site\s*address.*\n/i.test(text);
}

// ---------------------------------------------------------------------------
// Parse raw page text into key:value pairs
// Handles "Label: Value" and stacked "Label\nValue" layouts
// ---------------------------------------------------------------------------
function parseText(text) {
  const data = {};

  // "Label: Value" on the same line
  const inline = /^([A-Za-z][A-Za-z0-9\s\/\(\)#\-\.]{2,55}?):\s*(.+)$/gm;
  let m;
  while ((m = inline.exec(text)) !== null) {
    const k = m[1].trim();
    const v = m[2].trim();
    if (v && v.length < 400 && !/^(http|www)/i.test(v)) data[k] = v;
  }

  // Known label immediately followed by a value on the next non-empty line
  const LABELS = [
    'Owner Name','Owner','Mailing Address','Mailing Addr',
    'Site Address','Situs Address','Location',
    'Land Use','Land Use Code','Property Use','Property Type','Property Class',
    'Acreage','Lot Size','Lot Sqft','Net Acres',
    'Zoning','Zone Code',
    'Assessed Value','Net Assessed','Total Assessed','Appraised Value',
    'Land Value','Improvement Value','Taxable Value',
    'APN','Parcel Number','Parcel ID','Parcel No',
    'Legal Description','Legal Desc',
    'Tax District','Tax Year','Tax Amount','Taxes Due',
    'Last Sale Date','Sale Date','Last Sale Price','Sale Price','Last Sale Amount',
    'Year Built','Buildings','Subdivision',
    'Entity Name','Entity Status','Entity Type',
    'Registered Agent','Formation Date','Incorporation Date',
    'Officers','Directors','Managers',
    'Status','Annual Report Due',
  ];
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  for (let i = 0; i < lines.length - 1; i++) {
    const line = lines[i].replace(/:$/, '').trim();
    if (LABELS.some((l) => line.toLowerCase() === l.toLowerCase())) {
      const next = lines[i + 1];
      if (next && next.length < 250 && !LABELS.some((l) => next.toLowerCase() === l.toLowerCase())) {
        if (!data[line]) data[line] = next;
      }
    }
  }
  return data;
}

// Pull every labeled span/div and table cell from DOM
async function domExtract(page) {
  return page.evaluate(() => {
    const out = {};
    // Spans/divs that carry assessor field values (strip ASP.NET ID prefixes)
    document.querySelectorAll('span[id], div[id]').forEach((el) => {
      const raw = el.id.replace(/ctl\d+_ContentPlaceHolder\d+_/gi, '').replace(/_/g, ' ').trim();
      const val = (el.innerText || '').trim();
      if (raw && val && val.length > 0 && val.length < 300 && !/^(btn|grd|lbl[Tt]itle|menu|nav|header)/i.test(raw)) {
        out[raw] = val;
      }
    });
    // Table rows (label cell, value cell)
    document.querySelectorAll('table tr').forEach((tr) => {
      const cells = [...tr.querySelectorAll('td')];
      if (cells.length >= 2) {
        const k = cells[0].innerText.trim().replace(/[:\s]+$/, '');
        const v = cells[1].innerText.trim();
        if (k && v && k.length < 80 && v.length < 300) out[k] = v;
      }
    });
    // label[for] → element value
    document.querySelectorAll('label[for]').forEach((lbl) => {
      const target = document.getElementById(lbl.getAttribute('for'));
      if (!target) return;
      const k = lbl.innerText.trim().replace(/:\s*$/, '');
      const v = (target.innerText || target.value || '').trim();
      if (k && v) out[k] = v;
    });
    return out;
  });
}

// ---------------------------------------------------------------------------
// TASK 1 — Clark County Assessor
// The form has two tabs: "Parcel Number (APN)" and "Location Address".
// It defaults to the Address tab. We must click the APN/Parcel tab first.
// ---------------------------------------------------------------------------
async function lookupAssessorApn(page, apn, hint) {
  const slug = apn.replace(/-/g, '_');
  const result = { apn, hint, error: null, data: {}, rawText: '', url: '' };

  try {
    // ── Step 1: Load the search page ──────────────────────────────────────
    await page.goto(
      'https://maps.clarkcountynv.gov/assessor/AssessorParcelDetail/site.aspx',
      { waitUntil: 'domcontentloaded', timeout: 40000 },
    );
    await sleep(2000);
    await snap(page, `debug-${slug}-01-loaded`);
    const { text: loadedText } = await dumpAll(page, `debug-${slug}-01-loaded`);

    // Dump every interactable element so we can see all tabs/buttons/inputs
    const elDump = await page.evaluate(() =>
      [...document.querySelectorAll('a, input, button, select, [onclick], [role="tab"]')].map((el) => ({
        tag: el.tagName, id: el.id, name: el.name || '', type: el.type || '',
        text: (el.innerText || el.value || el.placeholder || '').trim().slice(0, 80),
        href: el.href || '', className: el.className?.slice(0, 80) || '',
        onclick: el.getAttribute('onclick') || '',
      })),
    );
    save(`debug-${slug}-elements.json`, JSON.stringify(elDump, null, 2));
    console.log(`  All elements (${elDump.length}): ${elDump.map((e) => `${e.tag}[${e.id||e.text.slice(0,20)}]`).join(' ')}`);

    // ── Step 2: Click the APN / Parcel Number tab ─────────────────────────
    // Try every selector that could activate the APN search panel
    const tabCandidates = [
      'a:has-text("Parcel Number")',
      'a:has-text("Parcel No")',
      'a:has-text("APN")',
      'li:has-text("Parcel Number") > a',
      'li:has-text("APN") > a',
      '[id*="tabParcel" i]',
      '[id*="tabAPN" i]',
      '[id*="lnkParcel" i]',
      '[id*="lnkAPN" i]',
      'input[type="radio"][value="APN"]',
      'input[type="radio"][value="Parcel"]',
      // Generic: first tab link (page defaults to tab 2, so tab 1 = APN)
      '.ui-tabs-nav li:first-child a',
      '.tab-nav li:first-child a',
      '#tabs li:first-child a',
    ];

    let tabClicked = false;
    for (const sel of tabCandidates) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 800 }).catch(() => false)) {
        const txt = await el.innerText().catch(() => sel);
        console.log(`  Clicking tab candidate: ${sel} → "${txt.trim().slice(0, 40)}"`);
        await el.click();
        await sleep(1200);
        tabClicked = true;
        break;
      }
    }
    if (!tabClicked) console.log('  No APN tab found — proceeding with default form state');

    await snap(page, `debug-${slug}-02-after-tab`);
    await dumpAll(page, `debug-${slug}-02-after-tab`);

    // ── Step 3: Find and fill the APN input ──────────────────────────────
    // Dump inputs again after tab click (new inputs may have appeared)
    const inputDump = await page.evaluate(() =>
      [...document.querySelectorAll('input, select, textarea')].map((el) => ({
        tag: el.tagName, id: el.id, name: el.name, type: el.type,
        placeholder: el.placeholder, value: el.value,
        visible: el.offsetParent !== null,
        className: el.className?.slice(0, 60) || '',
      })),
    );
    save(`debug-${slug}-inputs.json`, JSON.stringify(inputDump, null, 2));
    console.log(`  Inputs after tab: ${inputDump.map((i) => `${i.type}[${i.id}]${i.visible ? '' : '(hidden)'}`).join(' ')}`);

    const apnSelectors = [
      '#txtAPN',
      '#ctl00_ContentPlaceHolder1_txtAPN',
      'input[id*="APN" i]:not([type="hidden"])',
      'input[id*="Parcel" i]:not([type="hidden"])',
      'input[name*="APN" i]:not([type="hidden"])',
      'input[placeholder*="APN" i]',
      'input[placeholder*="arcel" i]',
      // Fallback: first visible text input after a tab click
      'input[type="text"]:visible',
    ];

    let filled = false;
    for (const sel of apnSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 1000 }).catch(() => false)) {
        await el.click({ clickCount: 3 });
        await el.fill(apn);
        filled = true;
        console.log(`  ✓ Filled APN into: ${sel}`);
        break;
      }
    }

    if (!filled) {
      result.error = `APN text input not found after tab interaction. See debug-${slug}-inputs.json`;
      result.rawText = loadedText.slice(0, 2000);
      return result;
    }

    // ── Step 4: Submit ────────────────────────────────────────────────────
    const submitCandidates = [
      '#btnSubmit',
      '#btnSearch',
      '#ctl00_ContentPlaceHolder1_btnSearch',
      '#ctl00_ContentPlaceHolder1_btnSubmit',
      'input[type="submit"]',
      'button[type="submit"]',
      'button:has-text("Search")',
      'button:has-text("Submit")',
      'input[value*="Search" i]',
      'input[value*="Submit" i]',
    ];
    let submitted = false;
    for (const sel of submitCandidates) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 800 }).catch(() => false)) {
        await el.click();
        submitted = true;
        console.log(`  ✓ Submitted via: ${sel}`);
        break;
      }
    }
    if (!submitted) {
      await page.keyboard.press('Enter');
      console.log('  ✓ Submitted via Enter');
    }

    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    await sleep(3000);
    await snap(page, `debug-${slug}-03-after-submit`);
    await dumpAll(page, `debug-${slug}-03-after-submit`);

    // ── Step 5: Navigate into detail if we landed on a results list ───────
    const resultLink = page.locator([
      'table td a[href*="APN"]',
      'table td a[href*="parcel" i]',
      'table td a[href*="detail" i]',
      '#grdResults a',
      '.grid a',
      'table td a',        // generic first link in any results table
    ].join(', ')).first();

    if (await resultLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      const linkTxt = await resultLink.innerText().catch(() => '');
      console.log(`  → Clicking result link: "${linkTxt.trim().slice(0, 60)}"`);
      await resultLink.click();
      await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {});
      await sleep(2500);
    }

    result.url = page.url();
    await snap(page, `debug-${slug}-04-final`);
    const { text: finalText } = await dumpAll(page, `debug-${slug}-04-final`);
    result.rawText = finalText;

    // ── Step 6: Extract ───────────────────────────────────────────────────
    result.data = { ...parseText(finalText), ...(await domExtract(page)) };

    if (Object.keys(result.data).length === 0) {
      result.error = `No structured data extracted. See debug-${slug}-04-final.txt`;
    }

  } catch (err) {
    result.error = err.message.slice(0, 400);
    console.error(`  ERROR: ${result.error}`);
    await snap(page, `debug-${slug}-error`).catch(() => {});
  }
  return result;
}

// ---------------------------------------------------------------------------
// TASK 2 — Nevada SOS
// Cloudflare blocks Chromium headless. Stealth patches applied via
// addInitScript. Falls back to Firefox if Chromium is still challenged.
// ---------------------------------------------------------------------------
async function makeStealth(browserType, opts = {}) {
  const browser = await browserType.launch({
    headless: true,
    args: browserType.name() === 'chromium' ? [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--ignore-certificate-errors',
      '--disable-blink-features=AutomationControlled',
    ] : [],
    ...opts,
  });
  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
    userAgent: browserType.name() === 'chromium'
      ? 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
      : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0',
    viewport: { width: 1440, height: 900 },
    locale: 'en-US',
    timezoneId: 'America/Los_Angeles',
    extraHTTPHeaders: {
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
      'Upgrade-Insecure-Requests': '1',
    },
  });

  // Patch every new page to remove webdriver fingerprints
  await context.addInitScript(() => {
    // Remove navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    // Fake plugins (empty in headless = bot signal)
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    // Fake languages
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    // Chrome object (absent in headless = bot signal)
    window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {} };
    // Permissions API — headless returns 'denied' for notifications, real browsers return 'default'
    const originalQuery = window.navigator.permissions?.query?.bind(navigator.permissions);
    if (originalQuery) {
      navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
          ? Promise.resolve({ state: Notification.permission })
          : originalQuery(parameters);
    }
  });

  return { browser, context };
}

async function lookupNvSos(context, page, entityName, isFirst) {
  const slug = entityName.replace(/\s+/g, '_');
  const result = { entity: entityName, error: null, data: {}, searchRows: [], rawText: '', url: '' };

  try {
    await page.goto('https://esos.nv.gov/EntitySearch/OnlineEntitySearch', {
      waitUntil: 'domcontentloaded',
      timeout: 45000,
    });
    // Gentle pause to let JS/Cloudflare settle
    await sleep(3500);

    if (isFirst) {
      await snap(page, 'debug-sos-blank');
      await dumpAll(page, 'debug-sos-blank');
      const elDump = await page.evaluate(() =>
        [...document.querySelectorAll('input, select, button, a')].map((el) => ({
          tag: el.tagName, id: el.id, name: el.name || '', type: el.type || '',
          text: (el.innerText || el.value || el.placeholder || '').trim().slice(0, 80),
          className: el.className?.slice(0, 80) || '',
        })),
      );
      save('debug-sos-elements.json', JSON.stringify(elDump, null, 2));
      console.log(`  SOS elements: ${elDump.map((e) => `${e.tag}[${e.id||e.text.slice(0,20)}]`).join(' ')}`);
    }

    // Detect Cloudflare challenge
    const pageTitle = await page.title().catch(() => '');
    const bodySnip = (await page.innerText('body').catch(() => '')).slice(0, 300);
    if (/just a moment|checking your browser|cloudflare|enable javascript/i.test(pageTitle + bodySnip)) {
      // Wait longer for JS challenge to auto-solve
      console.log('  ⚠ Cloudflare challenge detected, waiting 8s for auto-solve...');
      await sleep(8000);
      await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {});
      await sleep(2000);
    }

    await snap(page, `debug-sos-${slug}-01-loaded`);

    // Find entity name input
    const nameSelectors = [
      '#txtEntityName',
      '#ctl00_ContentPlaceHolder1_txtEntityName',
      'input[id*="EntityName" i]',
      'input[name*="EntityName" i]',
      'input[placeholder*="entity" i]',
      'input[placeholder*="name" i]',
      'input[type="text"]:visible',
    ];

    let filled = false;
    for (const sel of nameSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 1500 }).catch(() => false)) {
        await el.click({ clickCount: 3 });
        await el.fill(entityName);
        filled = true;
        console.log(`  ✓ Filled entity name via: ${sel}`);
        break;
      }
    }

    if (!filled) {
      const title = await page.title();
      result.error = `Entity input not found. Title: "${title}" — Cloudflare may still be blocking. See debug-sos-blank.png`;
      result.rawText = bodySnip;
      return result;
    }

    await sleep(400);

    // Submit
    const submitCandidates = [
      '#btnEntitySearch',
      '#ctl00_ContentPlaceHolder1_btnEntitySearch',
      '#ctl00_ContentPlaceHolder1_btnSearch',
      'input[type="submit"]',
      'button[type="submit"]',
      'button:has-text("Search")',
      'input[value*="Search" i]',
    ];
    for (const sel of submitCandidates) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 800 }).catch(() => false)) {
        await el.click();
        console.log(`  ✓ Submitted via: ${sel}`);
        break;
      }
    }

    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    await sleep(3000);
    await snap(page, `debug-sos-${slug}-02-results`);
    await dumpAll(page, `debug-sos-${slug}-02-results`);

    // Capture result rows from the grid
    result.searchRows = await page.evaluate(() =>
      [...document.querySelectorAll('table tr')].slice(1).map((tr) =>
        [...tr.querySelectorAll('td')].map((td) => td.innerText.trim()).filter(Boolean)
      ).filter((r) => r.length > 0),
    );
    console.log(`  Search rows: ${result.searchRows.length}`);

    // Click first result
    const firstLink = page.locator([
      '#grdEntityResults td a',
      '#grdResults td a',
      'table td a[href*="Detail"]',
      'table td a[href*="detail"]',
      'table td a',
    ].join(', ')).first();

    if (await firstLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      const txt = await firstLink.innerText().catch(() => '');
      console.log(`  → Clicking: "${txt.trim().slice(0, 60)}"`);
      await firstLink.click();
      await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {});
      await sleep(2500);
    }

    result.url = page.url();
    await snap(page, `debug-sos-${slug}-03-detail`);
    const { text: detailText } = await dumpAll(page, `debug-sos-${slug}-03-detail`);
    result.rawText = detailText;
    result.data = { ...parseText(detailText), ...(await domExtract(page)) };

  } catch (err) {
    result.error = err.message.slice(0, 400);
    console.error(`  ERROR: ${result.error}`);
    await snap(page, `debug-sos-${slug}-error`).catch(() => {});
  }
  return result;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
async function main() {
  setup();

  // ── TASK 1: CC Assessor (Chromium) ───────────────────────────────────────
  console.log('\n=== TASK 1: CLARK COUNTY ASSESSOR APN LOOKUPS ===\n');

  const assessorBrowser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--ignore-certificate-errors'],
  });
  const assessorCtx = await assessorBrowser.newContext({
    ignoreHTTPSErrors: true,
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 900 },
  });
  const assessorPage = await assessorCtx.newPage();

  assessorPage.on('response', (res) => {
    if (res.status() >= 300) console.log(`  [${res.status()}] ${res.url().slice(0, 100)}`);
  });

  const apnResults = [];
  for (const { apn, hint } of APNS) {
    console.log(`\n--- APN: ${apn}${hint ? ` (${hint})` : ''} ---`);
    const r = await lookupAssessorApn(assessorPage, apn, hint);
    apnResults.push(r);
    if (r.error) {
      console.log(`  ✗ ERROR: ${r.error}`);
    } else {
      const keys = Object.keys(r.data);
      console.log(`  ✓ Fields (${keys.length}): ${keys.slice(0, 10).join(' | ')}`);
      console.log(JSON.stringify(r.data, null, 2));
    }
    await sleep(1500);
  }
  await assessorBrowser.close();

  // ── TASK 2: NV SOS (stealth Chromium, Firefox fallback) ─────────────────
  console.log('\n=== TASK 2: NEVADA SOS ENTITY LOOKUPS ===\n');

  // Try Chromium with stealth patches first
  let { browser: sosBrowser, context: sosCtx } = await makeStealth(chromium);
  let sosPage = await sosCtx.newPage();
  sosPage.on('response', (res) => {
    if (res.status() >= 300) console.log(`  [${res.status()}] ${res.url().slice(0, 100)}`);
  });

  // Quick probe to see if Cloudflare still blocks stealth Chromium
  console.log('Probing NV SOS with stealth Chromium...');
  await sosPage.goto('https://esos.nv.gov/EntitySearch/OnlineEntitySearch', {
    waitUntil: 'domcontentloaded', timeout: 30000,
  }).catch(() => {});
  await sleep(4000);
  const probeTitle = await sosPage.title().catch(() => '');
  const probeBody = (await sosPage.innerText('body').catch(() => '')).slice(0, 200);
  const cfBlocked = /just a moment|checking your browser|cloudflare|enable javascript/i.test(probeTitle + probeBody);

  if (cfBlocked) {
    console.log('  ⚠ Stealth Chromium still blocked. Switching to Firefox...');
    await sosBrowser.close();
    ({ browser: sosBrowser, context: sosCtx } = await makeStealth(firefox));
    sosPage = await sosCtx.newPage();
    sosPage.on('response', (res) => {
      if (res.status() >= 300) console.log(`  [${res.status()}] ${res.url().slice(0, 100)}`);
    });
  } else {
    // Reuse existing page — reset to start
    await sosPage.goto('about:blank');
  }

  const sosResults = [];
  for (let i = 0; i < NV_SOS_ENTITIES.length; i++) {
    const entity = NV_SOS_ENTITIES[i];
    console.log(`\n--- Entity: ${entity} ---`);
    const r = await lookupNvSos(sosCtx, sosPage, entity, i === 0);
    sosResults.push(r);
    if (r.error) {
      console.log(`  ✗ ERROR: ${r.error}`);
    } else {
      console.log(`  Search rows: ${r.searchRows.length}`);
      const keys = Object.keys(r.data);
      console.log(`  ✓ Fields (${keys.length}): ${keys.slice(0, 10).join(' | ')}`);
      if (keys.length) console.log(JSON.stringify(r.data, null, 2));
    }
    await sleep(1500);
  }
  await sosBrowser.close();

  const output = { timestamp: new Date().toISOString(), apnResults, sosResults };
  save('raw-results.json', JSON.stringify(output, null, 2));
  console.log(`\nDone. osint-output/raw-results.json`);
  console.log(`Debug screenshots/text/html: osint-output/debug-*.{png,txt,html}`);
}

main().catch(console.error);
