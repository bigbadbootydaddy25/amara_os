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

const OUT = path.join(__dirname, '..', 'osint-output');

function setup() {
  fs.mkdirSync(OUT, { recursive: true });
}

function save(filename, content) {
  fs.writeFileSync(path.join(OUT, filename), content);
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function snap(page, name) {
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true });
}

async function dumpText(page, name) {
  const text = await page.innerText('body').catch(() => '');
  save(`${name}.txt`, text);
  return text;
}

async function dumpHtml(page, name) {
  const html = await page.content().catch(() => '');
  save(`${name}.html`, html);
  return html;
}

// ---------------------------------------------------------------------------
// Parse raw body text into key:value pairs.
// Handles "Label: Value" and "Label\nValue" patterns common on assessor pages.
// ---------------------------------------------------------------------------
function parseBodyText(text) {
  const data = {};

  // Pattern 1: "Label: Value" on same line
  const inlineRe = /^([A-Za-z][A-Za-z\s\/\(\)#]{2,50}?):\s*(.+)$/gm;
  let m;
  while ((m = inlineRe.exec(text)) !== null) {
    const key = m[1].trim();
    const val = m[2].trim();
    if (val && val.length < 400) data[key] = val;
  }

  // Pattern 2: lines that look like field headers followed by value lines
  // e.g. "Owner Name\nCBSI LLC"
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  const KNOWN_LABELS = [
    'Owner Name', 'Owner', 'Mailing Address', 'Site Address', 'Location',
    'Land Use', 'Property Use', 'Property Type', 'Land Use Code',
    'Acreage', 'Lot Size', 'Lot Sqft', 'Square Feet',
    'Zoning', 'Zone',
    'Assessed Value', 'Total Assessed', 'Net Assessed', 'Appraised Value',
    'Land Value', 'Improvement Value',
    'APN', 'Parcel Number', 'Parcel ID',
    'Legal Description',
    'Tax District', 'Township', 'Range', 'Section',
    'Tax Year', 'Tax Amount', 'Taxes Due',
    'Last Sale Date', 'Last Sale Amount', 'Last Sale Price',
    'Year Built', 'Buildings',
  ];
  for (let i = 0; i < lines.length - 1; i++) {
    const line = lines[i];
    if (KNOWN_LABELS.some((lbl) => line.toLowerCase().includes(lbl.toLowerCase()))) {
      const nextLine = lines[i + 1];
      // Only use next line as value if it doesn't itself look like a label
      if (nextLine && !/^[A-Za-z\s]+:$/.test(nextLine) && nextLine.length < 200) {
        const cleanKey = line.replace(/:$/, '').trim();
        if (!data[cleanKey]) data[cleanKey] = nextLine;
      }
    }
  }

  return data;
}

// ---------------------------------------------------------------------------
// TASK 1 — Clark County Assessor
// ---------------------------------------------------------------------------
async function lookupAssessorApn(page, apn, hint) {
  const slug = apn.replace(/-/g, '_');
  const result = { apn, hint, error: null, data: {}, rawText: '', url: '' };

  try {
    // --- Try direct URL with APN query param first (bypasses form entirely) ---
    const directUrl = `https://maps.clarkcountynv.gov/assessor/AssessorParcelDetail/site.aspx?APN=${apn}`;
    console.log(`  → trying direct URL: ${directUrl}`);
    await page.goto(directUrl, { waitUntil: 'networkidle', timeout: 40000 });
    await sleep(2500);
    await snap(page, `debug-${slug}-direct`);
    const directText = await dumpText(page, `debug-${slug}-direct`);
    result.url = page.url();

    // Check if we got real data on the direct URL (look for owner/address signals)
    const hasData = /owner|address|acreage|zoning|land use/i.test(directText);

    if (hasData) {
      console.log('  ✓ Direct URL returned parcel data');
      result.rawText = directText;
      result.data = parseBodyText(directText);

      // Also try structured extraction
      const structured = await extractStructured(page);
      Object.assign(result.data, structured);

      await snap(page, `debug-${slug}-result`);
      return result;
    }

    // --- Fall back to form-based search ---
    console.log('  → Direct URL did not return data, trying form search');
    await page.goto(
      'https://maps.clarkcountynv.gov/assessor/AssessorParcelDetail/site.aspx',
      { waitUntil: 'networkidle', timeout: 40000 },
    );
    await sleep(2500);

    // Screenshot + dump the blank search form
    await snap(page, `debug-${slug}-form`);
    await dumpHtml(page, `debug-${slug}-form`);
    const formText = await dumpText(page, `debug-${slug}-form`);

    // Dump all inputs so we can see exactly what's on the page
    const inputDump = await page.evaluate(() =>
      [...document.querySelectorAll('input, select, textarea, button')].map((el) => ({
        tag: el.tagName, id: el.id, name: el.name, type: el.type,
        value: el.value, placeholder: el.placeholder,
        label: el.labels?.[0]?.innerText || '',
        className: el.className?.slice(0, 80) || '',
      })),
    );
    save(`debug-${slug}-inputs.json`, JSON.stringify(inputDump, null, 2));
    console.log(`  Form inputs: ${inputDump.map((i) => `${i.type}#${i.id}`).join(', ')}`);

    // Click the APN radio button if one exists
    const apnRadio = page.locator([
      'input[type="radio"][value*="APN" i]',
      'input[type="radio"][id*="APN" i]',
      'input[type="radio"][id*="apn" i]',
      'label:has-text("APN") input[type="radio"]',
    ].join(', ')).first();

    if (await apnRadio.isVisible({ timeout: 2000 }).catch(() => false)) {
      await apnRadio.click();
      await sleep(800);
      console.log('  ✓ Clicked APN radio button');
    } else {
      // Try clicking a label whose text contains "APN"
      const apnLabel = page.locator('label').filter({ hasText: /^APN$/i }).first();
      if (await apnLabel.isVisible({ timeout: 1500 }).catch(() => false)) {
        await apnLabel.click();
        await sleep(800);
        console.log('  ✓ Clicked APN label');
      }
    }

    // Fill APN input — try every plausible selector
    const apnSelectors = [
      'input[type="text"]:visible',        // most permissive — catches whatever appears after radio click
      '#ctl00_ContentPlaceHolder1_txtAPN',
      '#txtAPN',
      '#txtParcelNumber',
      'input[id*="APN" i]',
      'input[name*="APN" i]',
      'input[placeholder*="APN" i]',
      'input[placeholder*="parcel" i]',
      'input[id*="Parcel" i]',
    ];

    let filled = false;
    let usedSel = '';
    for (const sel of apnSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 1500 }).catch(() => false)) {
        await el.click({ clickCount: 3 });
        await el.fill(apn);
        filled = true;
        usedSel = sel;
        console.log(`  ✓ Filled APN using selector: ${sel}`);
        break;
      }
    }

    if (!filled) {
      result.error = `APN input not found on form. Page: "${await page.title()}"`;
      result.rawText = formText.slice(0, 1000);
      return result;
    }

    await sleep(500);

    // Submit
    const submitSelectors = [
      '#ctl00_ContentPlaceHolder1_btnSearch',
      '#btnSearch',
      'input[type="submit"]',
      'button[type="submit"]',
      'button:has-text("Search")',
      'input[value*="Search" i]',
      'input[value*="Go" i]',
    ];
    let submitted = false;
    for (const sel of submitSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 1500 }).catch(() => false)) {
        await el.click();
        submitted = true;
        console.log(`  ✓ Submitted using: ${sel}`);
        break;
      }
    }
    if (!submitted) {
      // Try pressing Enter on the input
      await page.keyboard.press('Enter');
      console.log('  ✓ Submitted via Enter key');
    }

    await page.waitForLoadState('networkidle', { timeout: 30000 });
    await sleep(3000);

    // Screenshot + dump immediately after submit
    await snap(page, `debug-${slug}-after-submit`);
    const afterSubmitText = await dumpText(page, `debug-${slug}-after-submit`);
    await dumpHtml(page, `debug-${slug}-after-submit`);

    // If a search results list appeared (multiple matches), click the first row
    const resultLinks = page.locator('table a, .grid a, #grdResults a, a[href*="APN"]');
    const linkCount = await resultLinks.count().catch(() => 0);
    if (linkCount > 0) {
      console.log(`  Found ${linkCount} result link(s), clicking first`);
      await resultLinks.first().click();
      await page.waitForLoadState('networkidle', { timeout: 20000 });
      await sleep(2500);
      await snap(page, `debug-${slug}-result`);
    }

    result.url = page.url();
    const finalText = await dumpText(page, `debug-${slug}-final`);
    await dumpHtml(page, `debug-${slug}-final`);
    result.rawText = finalText;

    // Parse the raw text
    result.data = parseBodyText(finalText);

    // Also try structured DOM extraction
    const structured = await extractStructured(page);
    Object.assign(result.data, structured);

  } catch (err) {
    result.error = err.message.slice(0, 400);
    console.error(`  ERROR: ${result.error}`);
    await snap(page, `debug-${slug}-error`).catch(() => {});
  }

  return result;
}

// Extract labeled data via DOM — spans, divs, table cells
async function extractStructured(page) {
  return page.evaluate(() => {
    const out = {};

    // Spans with IDs that often hold assessor field values
    document.querySelectorAll('span[id], div[id]').forEach((el) => {
      const id = el.id.replace(/ctl\d+_ContentPlaceHolder\d+_/i, '').replace(/_/g, ' ');
      const val = el.innerText?.trim();
      if (id && val && val.length > 0 && val.length < 300 && !/btn|grid|header|menu|nav/i.test(id)) {
        out[id] = val;
      }
    });

    // Table rows: col 0 = label, col 1 = value
    document.querySelectorAll('table tr').forEach((tr) => {
      const cells = [...tr.querySelectorAll('td')];
      if (cells.length >= 2) {
        const label = cells[0].innerText.trim().replace(/[:\s]+$/, '');
        const val = cells[1].innerText.trim();
        if (label && val && label.length < 80 && val.length < 300) out[label] = val;
      }
    });

    // Label[for] → value
    document.querySelectorAll('label[for]').forEach((lbl) => {
      const target = document.getElementById(lbl.getAttribute('for'));
      if (!target) return;
      const key = lbl.innerText.trim().replace(/:\s*$/, '');
      const val = target.innerText?.trim() || target.value?.trim() || '';
      if (key && val) out[key] = val;
    });

    return out;
  });
}

// ---------------------------------------------------------------------------
// TASK 2 — Nevada SOS
// ---------------------------------------------------------------------------
async function lookupNvSos(page, entityName, isFirst) {
  const slug = entityName.replace(/\s+/g, '_');
  const result = { entity: entityName, error: null, data: {}, searchRows: [], rawText: '', url: '' };

  try {
    await page.goto('https://esos.nv.gov/EntitySearch/OnlineEntitySearch', {
      waitUntil: 'networkidle',
      timeout: 40000,
    });
    await sleep(2500);

    // On the FIRST entity: screenshot the blank page and dump HTML for selector analysis
    if (isFirst) {
      await snap(page, 'debug-sos-blank');
      await dumpHtml(page, 'debug-sos');
      const blankText = await dumpText(page, 'debug-sos-blank');
      console.log('  Saved debug-sos-blank.png, debug-sos.html, debug-sos-blank.txt');

      const inputDump = await page.evaluate(() =>
        [...document.querySelectorAll('input, select, textarea, button')].map((el) => ({
          tag: el.tagName, id: el.id, name: el.name, type: el.type,
          value: el.value, placeholder: el.placeholder,
          label: el.labels?.[0]?.innerText || '',
          className: el.className?.slice(0, 80) || '',
        })),
      );
      save('debug-sos-inputs.json', JSON.stringify(inputDump, null, 2));
      console.log(`  SOS inputs: ${inputDump.map((i) => `${i.type}#${i.id}`).join(', ')}`);
    }

    // Try every plausible selector for the entity name field
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
        console.log(`  ✓ Filled entity name using: ${sel}`);
        break;
      }
    }

    if (!filled) {
      result.error = `Entity name input not found. Title: "${await page.title()}"`;
      return result;
    }

    await sleep(400);

    // Submit
    const submitSelectors = [
      '#btnEntitySearch',
      '#ctl00_ContentPlaceHolder1_btnEntitySearch',
      '#ctl00_ContentPlaceHolder1_btnSearch',
      'input[type="submit"]',
      'button[type="submit"]',
      'button:has-text("Search")',
      'input[value*="Search" i]',
    ];
    let submitted = false;
    for (const sel of submitSelectors) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 1500 }).catch(() => false)) {
        await el.click();
        submitted = true;
        console.log(`  ✓ Submitted using: ${sel}`);
        break;
      }
    }
    if (!submitted) {
      await page.keyboard.press('Enter');
      console.log('  ✓ Submitted via Enter');
    }

    await page.waitForLoadState('networkidle', { timeout: 30000 });
    await sleep(3000);

    await snap(page, `debug-sos-${slug}-results`);
    await dumpHtml(page, `debug-sos-${slug}-results`);
    const resultsText = await dumpText(page, `debug-sos-${slug}-results`);

    // Capture search result rows
    result.searchRows = await page.evaluate(() => {
      return [...document.querySelectorAll('table tr')].slice(1).map((tr) => {
        return [...tr.querySelectorAll('td')].map((td) => td.innerText.trim()).filter(Boolean);
      }).filter((r) => r.length > 0);
    });

    console.log(`  Search rows found: ${result.searchRows.length}`);

    // Click the first result link
    const firstLink = page.locator([
      '#grdEntityResults a',
      '#grdResults a',
      'table td a',
      'a[href*="EntityDetail"]',
      'a[href*="Detail"]',
    ].join(', ')).first();

    if (await firstLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      const linkText = await firstLink.innerText().catch(() => '');
      console.log(`  Clicking first result: "${linkText.slice(0, 60)}"`);
      await firstLink.click();
      await page.waitForLoadState('networkidle', { timeout: 20000 });
      await sleep(2500);
    } else {
      console.log('  No result link found — may be no match or different layout');
    }

    await snap(page, `debug-sos-${slug}-detail`);
    await dumpHtml(page, `debug-sos-${slug}-detail`);
    const detailText = await dumpText(page, `debug-sos-${slug}-detail`);

    result.url = page.url();
    result.rawText = detailText;

    // Parse structured data
    result.data = parseBodyText(detailText);

    // Also DOM extraction
    const structured = await extractStructured(page);
    Object.assign(result.data, structured);

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

  const browser = await chromium.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--ignore-certificate-errors',
      '--disable-blink-features=AutomationControlled',
    ],
  });

  const context = await browser.newContext({
    ignoreHTTPSErrors: true,
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 900 },
  });

  const page = await context.newPage();

  // Route logging: print every navigation so we can see redirects
  page.on('response', (res) => {
    if (res.status() >= 300 && res.status() < 400) {
      console.log(`  [redirect] ${res.status()} ${res.url().slice(0, 100)}`);
    }
    if (res.status() >= 400) {
      console.log(`  [error response] ${res.status()} ${res.url().slice(0, 100)}`);
    }
  });

  console.log('\n=== TASK 1: CLARK COUNTY ASSESSOR APN LOOKUPS ===\n');
  const apnResults = [];
  for (const { apn, hint } of APNS) {
    console.log(`\n--- APN: ${apn}${hint ? ` (${hint})` : ''} ---`);
    const r = await lookupAssessorApn(page, apn, hint);
    apnResults.push(r);
    if (r.error) {
      console.log(`  ERROR: ${r.error}`);
    } else {
      const keys = Object.keys(r.data).filter((k) => r.data[k]);
      console.log(`  Fields extracted (${keys.length}): ${keys.slice(0, 12).join(' | ')}`);
      if (keys.length > 0) console.log(JSON.stringify(r.data, null, 2));
    }
    await sleep(2000);
  }

  console.log('\n=== TASK 2: NEVADA SOS ENTITY LOOKUPS ===\n');
  const sosResults = [];
  for (let i = 0; i < NV_SOS_ENTITIES.length; i++) {
    const entity = NV_SOS_ENTITIES[i];
    console.log(`\n--- Entity: ${entity} ---`);
    const r = await lookupNvSos(page, entity, i === 0);
    sosResults.push(r);
    if (r.error) {
      console.log(`  ERROR: ${r.error}`);
    } else {
      console.log(`  Search rows: ${r.searchRows.length}`);
      const keys = Object.keys(r.data);
      console.log(`  Detail fields (${keys.length}): ${keys.slice(0, 12).join(' | ')}`);
      if (keys.length > 0) console.log(JSON.stringify(r.data, null, 2));
    }
    await sleep(2000);
  }

  await browser.close();

  const output = { timestamp: new Date().toISOString(), apnResults, sosResults };
  save('raw-results.json', JSON.stringify(output, null, 2));
  console.log(`\nAll done. Results: osint-output/raw-results.json`);
  console.log(`Debug files: osint-output/debug-*.{png,txt,html}`);
}

main().catch(console.error);
