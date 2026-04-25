/**
 * Polk County FL / Davenport — deed record scraper
 * Portal: https://apps.polkcountyclerk.net/OfficialRecords/
 * Platform: Web UI with document type and date range filter
 *
 * Cash signal: Consideration amount present, no mortgage/DOT filed on same
 *              parcel within 30 days.
 * Target ZIPs: 34953, 34983, 34984, 33837
 */

import { chromium } from 'playwright';
import {
  checkRobotsTxt,
  createBrowser,
  newPage,
  safeGoto,
  randomDelay,
  shortDelay,
  detectCaptcha,
  formatDate,
  isoDate,
  dateRangeLast365,
  extractZip,
  makeTransaction,
  parseConsideration,
  delay,
} from './utils.js';

const BASE_URL = 'https://apps.polkcountyclerk.net';
const SEARCH_URL = `${BASE_URL}/OfficialRecords/`;
const COUNTY = 'POLK_FL';
const TARGET_ZIPS = ['34953', '34983', '34984', '33837'];

const DEED_DOC_TYPES = ['DEED', 'WARRANTY DEED', 'SPECIAL WARRANTY DEED', 'TRUSTEE DEED', 'QUIT CLAIM DEED'];
const DOT_KEYWORDS = ['MORTGAGE', 'DEED OF TRUST', 'MTG'];

export async function scrapePolk() {
  const allowed = await checkRobotsTxt(BASE_URL, '/OfficialRecords/');
  if (!allowed) {
    return { county: COUNTY, transactions: [], error: 'Blocked by robots.txt' };
  }

  const browser = await createBrowser({ chromium });
  const page = await newPage(browser);
  const errors = [];
  const allTransactions = [];

  try {
    const { from, to } = dateRangeLast365();
    console.log(`[${COUNTY}] Scraping ${formatDate(from)} → ${formatDate(to)}`);

    await safeGoto(page, SEARCH_URL, { waitUntil: 'domcontentloaded' });
    await shortDelay();

    if (await detectCaptcha(page)) {
      throw new Error('CAPTCHA detected on Polk County Official Records portal');
    }

    // Polk County may show a disclaimer/terms page first
    await acceptTermsIfPresent(page);

    // Search each deed type separately for maximum coverage
    for (const docType of DEED_DOC_TYPES) {
      console.log(`[${COUNTY}] Searching: ${docType}`);
      try {
        const rows = await searchAndExtract(page, from, to, docType);
        allTransactions.push(...rows);
        await randomDelay();
      } catch (err) {
        console.warn(`[${COUNTY}] Error for ${docType}: ${err.message}`);
        errors.push(`${docType}: ${err.message}`);
      }
    }

    // Cross-check mortgages for cash flag
    const dotRecords = await fetchDotRecords(page, from, to);
    applyDotCrossCheck(allTransactions, dotRecords);

    const filtered = allTransactions.filter((t) => t.zip && TARGET_ZIPS.includes(t.zip));
    console.log(`[${COUNTY}] ${filtered.length} records in target ZIPs (${allTransactions.length} total)`);
    return { county: COUNTY, transactions: filtered, errors };
  } catch (err) {
    console.error(`[${COUNTY}] Fatal error: ${err.message}`);
    errors.push(err.message);
    return { county: COUNTY, transactions: allTransactions, errors };
  } finally {
    await browser.close();
  }
}

// ─── Terms/disclaimer handling ────────────────────────────────────────────────

async function acceptTermsIfPresent(page) {
  const acceptSelectors = [
    'button:has-text("Accept")',
    'button:has-text("I Agree")',
    'a:has-text("Accept")',
    'input[value*="Accept"]',
    'input[value*="Agree"]',
  ];
  for (const sel of acceptSelectors) {
    const el = await page.$(sel);
    if (el) {
      await el.click();
      await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => {});
      await shortDelay();
      return;
    }
  }
}

// ─── Per-doc-type search ──────────────────────────────────────────────────────

async function searchAndExtract(page, from, to, docType) {
  const results = [];

  // Navigate back to search form for each doc type
  await safeGoto(page, SEARCH_URL, { waitUntil: 'domcontentloaded' });
  await shortDelay();
  await acceptTermsIfPresent(page);

  // Polk County official records search form
  // Typically: Doc Type selector, Date range, Name/Instrument fields

  // Select document type
  const typeSelectors = [
    'select[name="DocumentType"]',
    'select[name="DocType"]',
    'select[id*="DocumentType"]',
    'select[id*="doctype"]',
    '#DocumentType',
    '#DocType',
  ];

  let docTypeSelected = false;
  for (const sel of typeSelectors) {
    const el = await page.$(sel);
    if (el) {
      const opts = await el.$$('option');
      for (const opt of opts) {
        const text = (await opt.textContent()).toUpperCase().trim();
        if (text === docType || text.includes(docType.split(' ')[0])) {
          const val = await opt.getAttribute('value');
          await el.selectOption({ value: val });
          docTypeSelected = true;
          break;
        }
      }
      if (docTypeSelected) break;
    }
  }

  await shortDelay();

  // Fill date range
  const fromStr = formatDate(from);
  const toStr = formatDate(to);

  const fromDateSelectors = [
    'input[name="BeginDate"]',
    'input[name="StartDate"]',
    'input[id*="BeginDate"]',
    'input[id*="StartDate"]',
    '#BeginDate',
    'input[placeholder*="From"]',
  ];
  const toDateSelectors = [
    'input[name="EndDate"]',
    'input[id*="EndDate"]',
    '#EndDate',
    'input[placeholder*="To"]',
  ];

  for (const sel of fromDateSelectors) {
    const el = await page.$(sel);
    if (el) { await el.fill(fromStr); break; }
  }
  for (const sel of toDateSelectors) {
    const el = await page.$(sel);
    if (el) { await el.fill(toStr); break; }
  }

  await shortDelay();

  // Submit search
  const submitSelectors = [
    'input[type="submit"]',
    'button[type="submit"]',
    'button:has-text("Search")',
    'input[value*="Search"]',
    '#btnSearch',
    '.search-btn',
  ];

  for (const sel of submitSelectors) {
    const el = await page.$(sel);
    if (el) {
      await el.click();
      break;
    }
  }

  await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {});
  await shortDelay();

  if (await detectCaptcha(page)) throw new Error(`CAPTCHA after Polk search for ${docType}`);

  // Check no-results
  const content = await page.content();
  if (content.toLowerCase().includes('no records') || content.toLowerCase().includes('0 records')) {
    return results;
  }

  // Paginate
  let pageNum = 1;
  while (true) {
    console.log(`[${COUNTY}] ${docType} — result page ${pageNum}`);
    const rows = await extractPolkRows(page, docType);
    results.push(...rows);

    if (rows.length === 0) break;

    const nextBtn = await page.$('a:has-text("Next"), button:has-text("Next"), input[value="Next"], .pagination-next:not(.disabled)');
    if (!nextBtn) break;

    await randomDelay();
    await nextBtn.click();
    await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {});
    pageNum++;

    if (pageNum > 200) {
      console.warn(`[${COUNTY}] Hit 200-page safety limit for ${docType}`);
      break;
    }
  }

  return results;
}

// ─── Row extraction ───────────────────────────────────────────────────────────

async function extractPolkRows(page, docTypeLabel) {
  const rows = [];

  // Polk County typically renders a table with clickable rows for detail
  const resultTable = await page.$('table#SearchResults, table.results-table, table[id*="Result"]');

  if (!resultTable) {
    // Fallback: scrape all table rows
    const tables = await page.$$('table');
    for (const table of tables) {
      const trs = await table.$$('tr');
      if (trs.length > 2) {
        rows.push(...(await parseTableRows(table, docTypeLabel)));
        break;
      }
    }
    return rows;
  }

  return await parseTableRows(resultTable, docTypeLabel);
}

async function parseTableRows(table, docTypeLabel) {
  const rows = [];
  const trs = await table.$$('tbody tr, tr:not(:first-child)');

  for (const tr of trs) {
    try {
      const cells = await tr.$$('td');
      if (cells.length < 3) continue;

      const getCellText = async (i) => cells[i] ? (await cells[i].textContent()).trim() : '';

      // Polk County typical column order:
      // Date | Instrument# | DocType | Book/Page | Grantor | Grantee | Consideration | Parcel | Address
      const docDate = await getCellText(0);
      const docNum = await getCellText(1);
      const docType = await getCellText(2);
      const grantor = await getCellText(4);
      const grantee = await getCellText(5);
      const consideration = await getCellText(6);
      const parcel = await getCellText(7);
      const address = await getCellText(8);

      if (!docNum && !grantee) continue;

      // Polk County includes parcel ID in results; parse ZIP from address
      const zip = extractZip(address);

      rows.push(makeTransaction({
        source_county: COUNTY,
        grantee: grantee.toUpperCase().trim(),
        grantor: grantor.toUpperCase().trim(),
        document_date: normalizeDate(docDate),
        document_type: (docType || docTypeLabel).toUpperCase().trim(),
        document_number: docNum.trim(),
        apn: parcel.trim(),
        consideration: parseConsideration(consideration),
        address: address.toUpperCase(),
        zip,
      }));
    } catch {
      // Skip malformed rows
    }
  }

  return rows;
}

// ─── DOT cross-check ──────────────────────────────────────────────────────────

async function fetchDotRecords(page, from, to) {
  const dotRecords = [];

  for (const dotType of ['MORTGAGE', 'DEED OF TRUST']) {
    try {
      await safeGoto(page, SEARCH_URL, { waitUntil: 'domcontentloaded' });
      await shortDelay();
      await acceptTermsIfPresent(page);

      const typeSelectors = ['select[name="DocumentType"]', '#DocumentType', 'select[id*="DocumentType"]'];
      for (const sel of typeSelectors) {
        const el = await page.$(sel);
        if (el) {
          const opts = await el.$$('option');
          for (const opt of opts) {
            const text = (await opt.textContent()).toUpperCase();
            if (text.includes(dotType)) {
              const val = await opt.getAttribute('value');
              await el.selectOption({ value: val });
              break;
            }
          }
          break;
        }
      }

      await shortDelay();

      const fromSelectors = ['input[name="BeginDate"]', '#BeginDate'];
      const toSelectors = ['input[name="EndDate"]', '#EndDate'];
      for (const sel of fromSelectors) {
        const el = await page.$(sel);
        if (el) { await el.fill(formatDate(from)); break; }
      }
      for (const sel of toSelectors) {
        const el = await page.$(sel);
        if (el) { await el.fill(formatDate(to)); break; }
      }

      await shortDelay();
      await page.click('input[type="submit"], button[type="submit"]');
      await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {});

      const rows = await extractPolkRows(page, dotType);
      dotRecords.push(...rows);
      await randomDelay();
    } catch (err) {
      console.warn(`[${COUNTY}] DOT fetch failed for ${dotType}: ${err.message}`);
    }
  }

  return dotRecords;
}

function applyDotCrossCheck(transactions, dotRecords) {
  // Build a set of parcel+date keys for DOT records (±30 days window)
  const dotParcelDates = new Map(); // apn -> array of dates

  for (const dot of dotRecords) {
    if (!dot.apn) continue;
    if (!dotParcelDates.has(dot.apn)) dotParcelDates.set(dot.apn, []);
    dotParcelDates.get(dot.apn).push(dot.document_date);
  }

  for (const t of transactions) {
    if (!t.apn || !t.document_date) {
      t.cash_flag = false;
      t.has_dot = false;
      continue;
    }

    const deedDate = new Date(t.document_date);
    if (isNaN(deedDate.getTime())) {
      t.cash_flag = false;
      t.has_dot = false;
      continue;
    }

    const dotDates = dotParcelDates.get(t.apn) || [];
    let hasDot = false;

    for (const dotDateStr of dotDates) {
      const dotDate = new Date(dotDateStr);
      if (isNaN(dotDate.getTime())) continue;
      const diffDays = Math.abs((deedDate - dotDate) / (1000 * 60 * 60 * 24));
      if (diffDays <= 30) {
        hasDot = true;
        break;
      }
    }

    // Also check if consideration is missing (no sale = no cash signal)
    const hasConsideration = t.consideration !== null && t.consideration > 0;
    t.has_dot = hasDot;
    t.cash_flag = !hasDot && hasConsideration;
  }
}

function normalizeDate(raw) {
  if (!raw) return '';
  const mdy = raw.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (mdy) return `${mdy[3]}-${mdy[1].padStart(2, '0')}-${mdy[2].padStart(2, '0')}`;
  const iso = raw.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  return raw;
}
