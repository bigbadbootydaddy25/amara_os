// AMARA OS — Clark County Assessor + NV SOS OSINT Lookup
// Requires: npm install playwright && npx playwright install chromium
// Run from any machine with open outbound internet access.
// Real data only — no invented records.

const { chromium } = require('playwright');
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

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function outDir() {
  const dir = path.join(__dirname, '..', 'osint-output');
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

async function lookupAssessorApn(page, apn, hint) {
  const result = { apn, hint, error: null, data: {}, rawText: '' };
  try {
    await page.goto(
      'https://maps.clarkcountynv.gov/assessor/AssessorParcelDetail/site.aspx',
      { waitUntil: 'networkidle', timeout: 40000 },
    );
    await sleep(2000);

    // Dump DOM inputs on first call to help diagnose selector issues
    const inputs = await page.evaluate(() =>
      [...document.querySelectorAll('input, select, button')].map((el) => ({
        tag: el.tagName, id: el.id, name: el.name, type: el.type,
        placeholder: el.placeholder, className: el.className.slice(0, 60),
      })),
    );
    result._inputs = inputs;

    // Try every plausible selector for APN entry
    const apnSelectors = [
      '#ctl00_ContentPlaceHolder1_txtAPN',
      '#txtAPN',
      'input[id*="APN"]',
      'input[id*="apn"]',
      'input[name*="APN"]',
      'input[name*="apn"]',
      'input[placeholder*="APN" i]',
      'input[placeholder*="Parcel" i]',
      '#ctl00_ContentPlaceHolder1_txtParcelNumber',
      'input[id*="Parcel"]',
      'input[type="text"]',
    ];

    let filled = false;
    for (const sel of apnSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 1500 }).catch(() => false)) {
        await el.triple_click ? el.triple_click() : el.click({ clickCount: 3 });
        await el.fill(apn);
        filled = true;
        result._usedSelector = sel;
        break;
      }
    }

    if (!filled) {
      result.error = `Input not found. Page title: "${await page.title()}". URL: ${page.url()}`;
      result.rawText = (await page.innerText('body').catch(() => '')).slice(0, 500);
      return result;
    }

    // Submit
    const submitSelectors = [
      '#ctl00_ContentPlaceHolder1_btnSearch',
      'input[type="submit"]',
      'button[type="submit"]',
      'button:has-text("Search")',
      'input[value="Search"]',
      'input[value="Go"]',
    ];
    for (const sel of submitSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 1500 }).catch(() => false)) {
        await el.click();
        break;
      }
    }

    await page.waitForLoadState('networkidle', { timeout: 30000 });
    await sleep(2500);

    // If a results list appeared, click the first link
    const firstLink = page.locator('table a, .results a, .search-results a').first();
    if (await firstLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await firstLink.click();
      await page.waitForLoadState('networkidle', { timeout: 20000 });
      await sleep(2000);
    }

    result.url = page.url();
    result.rawText = (await page.innerText('body')).slice(0, 5000);

    // Extract all label:value pairs
    result.data = await page.evaluate(() => {
      const out = {};
      // Table rows
      document.querySelectorAll('tr').forEach((tr) => {
        const cells = [...tr.querySelectorAll('td, th')];
        if (cells.length >= 2) {
          const label = cells[0].innerText.trim().replace(/[:\s]+$/, '');
          const value = cells[1].innerText.trim();
          if (label && value && label.length < 80 && value.length < 300) out[label] = value;
        }
      });
      // Definition lists
      document.querySelectorAll('dt').forEach((dt) => {
        const dd = dt.nextElementSibling;
        if (dd?.tagName === 'DD') out[dt.innerText.trim()] = dd.innerText.trim();
      });
      // Label/for pairs
      document.querySelectorAll('label[for]').forEach((lbl) => {
        const el = document.getElementById(lbl.getAttribute('for'));
        if (el) out[lbl.innerText.trim().replace(/:\s*$/, '')] = el.innerText.trim() || el.value || '';
      });
      return out;
    });

    // Screenshot for verification
    await page.screenshot({
      path: `osint-output/apn-${apn.replace(/-/g, '_')}.png`,
      fullPage: true,
    });
  } catch (err) {
    result.error = err.message.slice(0, 300);
  }
  return result;
}

async function lookupNvSos(page, entityName) {
  const result = { entity: entityName, error: null, data: {}, rawText: '', results: [] };
  try {
    await page.goto('https://esos.nv.gov/EntitySearch/OnlineEntitySearch', {
      waitUntil: 'networkidle',
      timeout: 40000,
    });
    await sleep(2000);

    const inputs = await page.evaluate(() =>
      [...document.querySelectorAll('input, select, button')].map((el) => ({
        tag: el.tagName, id: el.id, name: el.name, type: el.type,
        placeholder: el.placeholder, className: el.className.slice(0, 60),
      })),
    );
    result._inputs = inputs;

    const nameSelectors = [
      '#txtEntityName',
      '#ctl00_ContentPlaceHolder1_txtEntityName',
      'input[id*="EntityName" i]',
      'input[name*="EntityName" i]',
      'input[placeholder*="Entity Name" i]',
      'input[placeholder*="name" i]',
      'input[type="text"]',
    ];

    let filled = false;
    for (const sel of nameSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 1500 }).catch(() => false)) {
        await el.click({ clickCount: 3 });
        await el.fill(entityName);
        filled = true;
        result._usedSelector = sel;
        break;
      }
    }

    if (!filled) {
      result.error = `Input not found. Title: "${await page.title()}" URL: ${page.url()}`;
      result.rawText = (await page.innerText('body').catch(() => '')).slice(0, 500);
      return result;
    }

    const submitSelectors = [
      '#btnEntitySearch',
      '#ctl00_ContentPlaceHolder1_btnSearch',
      'input[type="submit"]',
      'button[type="submit"]',
      'button:has-text("Search")',
      'input[value="Search"]',
    ];
    for (const sel of submitSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 1500 }).catch(() => false)) {
        await el.click();
        break;
      }
    }

    await page.waitForLoadState('networkidle', { timeout: 30000 });
    await sleep(2500);

    // Collect all result rows before clicking into detail
    result.results = await page.evaluate(() => {
      const rows = [...document.querySelectorAll('table tr')].slice(1);
      return rows.map((tr) => {
        const cells = [...tr.querySelectorAll('td')];
        return cells.map((c) => c.innerText.trim()).filter(Boolean);
      }).filter((r) => r.length > 0);
    });

    // Click first result to get detail
    const firstLink = page.locator('table td a, #grdEntityResults a').first();
    if (await firstLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await firstLink.click();
      await page.waitForLoadState('networkidle', { timeout: 20000 });
      await sleep(2000);
    }

    result.url = page.url();
    result.rawText = (await page.innerText('body')).slice(0, 5000);

    result.data = await page.evaluate(() => {
      const out = {};
      document.querySelectorAll('tr').forEach((tr) => {
        const cells = [...tr.querySelectorAll('td, th')];
        if (cells.length >= 2) {
          const label = cells[0].innerText.trim().replace(/[:\s]+$/, '');
          const value = cells[1].innerText.trim();
          if (label && value && label.length < 80) out[label] = value;
        }
      });
      document.querySelectorAll('label[for]').forEach((lbl) => {
        const el = document.getElementById(lbl.getAttribute('for'));
        if (el) out[lbl.innerText.trim().replace(/:\s*$/, '')] = el.innerText.trim() || el.value || '';
      });
      return out;
    });

    await page.screenshot({
      path: `osint-output/sos-${entityName.replace(/\s+/g, '_')}.png`,
      fullPage: true,
    });
  } catch (err) {
    result.error = err.message.slice(0, 300);
  }
  return result;
}

async function main() {
  outDir();

  const browser = await chromium.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--ignore-certificate-errors',
    ],
  });

  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 900 },
  });

  process.chdir(path.join(__dirname, '..'));
  const page = await context.newPage();

  console.log('\n=== TASK 1: CLARK COUNTY ASSESSOR APN LOOKUPS ===\n');
  const apnResults = [];
  for (const { apn, hint } of APNS) {
    console.log(`\nLooking up APN: ${apn}${hint ? ` (${hint})` : ''}`);
    const r = await lookupAssessorApn(page, apn, hint);
    apnResults.push(r);
    if (r.error) {
      console.log(`  ERROR: ${r.error}`);
      if (r.rawText) console.log(`  RAW: ${r.rawText.slice(0, 200)}`);
    } else {
      console.log(`  DATA FIELDS: ${Object.keys(r.data).join(' | ')}`);
      console.log(JSON.stringify(r.data, null, 2));
    }
    await sleep(1500);
  }

  console.log('\n=== TASK 2: NEVADA SOS ENTITY LOOKUPS ===\n');
  const sosResults = [];
  for (const entity of NV_SOS_ENTITIES) {
    console.log(`\nLooking up: ${entity}`);
    const r = await lookupNvSos(page, entity);
    sosResults.push(r);
    if (r.error) {
      console.log(`  ERROR: ${r.error}`);
      if (r.rawText) console.log(`  RAW: ${r.rawText.slice(0, 200)}`);
    } else {
      console.log(`  SEARCH RESULTS TABLE: ${JSON.stringify(r.results)}`);
      console.log(`  DETAIL DATA: ${JSON.stringify(r.data, null, 2)}`);
    }
    await sleep(1500);
  }

  await browser.close();

  // Save full structured output
  const output = { timestamp: new Date().toISOString(), apnResults, sosResults };
  fs.writeFileSync('osint-output/raw-results.json', JSON.stringify(output, null, 2));
  console.log('\nSaved: osint-output/raw-results.json');
}

main().catch(console.error);
