/**
 * Harris County TX — deed record scraper
 * Portal: https://www.cclerk.hctx.net/applications/websearch/RealProperty.aspx
 * Platform: ASP.NET WebForms with ViewState
 *
 * Cash signal: Absence of co-filed Deed of Trust on same parcel within same day.
 *              Also checks for "CASH" literal in consideration field.
 * Target ZIPs: 77026, 77028, 77033, 77021, 77012, 77051
 */

import { chromium } from 'playwright';
import {
  USER_AGENT,
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
  inZipList,
  makeTransaction,
  parseConsideration,
} from './utils.js';

const BASE_URL = 'https://www.cclerk.hctx.net';
const SEARCH_URL = `${BASE_URL}/applications/websearch/RealProperty.aspx`;
const COUNTY = 'HARRIS_TX';
const TARGET_ZIPS = ['77026', '77028', '77033', '77021', '77012', '77051'];
const DEED_TYPES = ['DEED', 'WARRANTY DEED', 'SPECIAL WARRANTY DEED', 'GENERAL WARRANTY DEED'];
const DOT_KEYWORDS = ['DEED OF TRUST', 'MORTGAGE', 'LIEN'];

export async function scrapeHarris() {
  const allowed = await checkRobotsTxt(BASE_URL, '/applications/websearch/RealProperty.aspx');
  if (!allowed) {
    return { county: COUNTY, transactions: [], error: 'Blocked by robots.txt' };
  }

  const browser = await createBrowser({ chromium });
  const page = await newPage(browser);
  const transactions = [];
  const errors = [];

  try {
    const { from, to } = dateRangeLast365();
    console.log(`[${COUNTY}] Scraping ${formatDate(from)} → ${formatDate(to)}`);

    await safeGoto(page, SEARCH_URL, { waitUntil: 'domcontentloaded' });
    await shortDelay();

    if (await detectCaptcha(page)) {
      throw new Error('CAPTCHA detected on Harris County portal');
    }

    // Harris County is an ASP.NET WebForms app — interact with the form fields
    await fillHarrisForm(page, from, to);

    // Submit and wait
    await submitHarrisForm(page);
    await randomDelay();

    if (await detectCaptcha(page)) {
      throw new Error('CAPTCHA detected after Harris County form submission');
    }

    // Paginate through results
    let pageNum = 1;
    while (true) {
      console.log(`[${COUNTY}] Processing result page ${pageNum}`);
      const rows = await extractHarrisRows(page);
      transactions.push(...rows);

      const hasNext = await goToNextPage(page);
      if (!hasNext) break;
      await randomDelay();
      pageNum++;
    }

    // Flag cash transactions
    flagCashTransactions(transactions);

    // Filter to target ZIPs (Harris includes situs address in results)
    const filtered = transactions.filter((t) => t.zip && TARGET_ZIPS.includes(t.zip));
    console.log(`[${COUNTY}] ${filtered.length} records in target ZIPs (${transactions.length} total)`);
    return { county: COUNTY, transactions: filtered, errors };
  } catch (err) {
    console.error(`[${COUNTY}] Fatal error: ${err.message}`);
    errors.push(err.message);
    return { county: COUNTY, transactions, errors };
  } finally {
    await browser.close();
  }
}

// ─── Form helpers ─────────────────────────────────────────────────────────────

async function fillHarrisForm(page, from, to) {
  // Harris County WebForms — typical field IDs for this ASP.NET portal
  const fromStr = formatDate(from);
  const toStr = formatDate(to);

  // Select instrument type: DEED
  await trySelectOption(page, [
    'select[id*="InstrumentType"]',
    'select[name*="InstrumentType"]',
    '#ctl00_ContentPlaceHolder1_ddlInstrumentType',
  ], 'DEED');

  await shortDelay();

  // Fill start date
  await tryFill(page, [
    'input[id*="BeginDate"]',
    'input[id*="StartDate"]',
    '#ctl00_ContentPlaceHolder1_txtBeginDate',
    'input[name*="BeginDate"]',
  ], fromStr);

  // Fill end date
  await tryFill(page, [
    'input[id*="EndDate"]',
    '#ctl00_ContentPlaceHolder1_txtEndDate',
    'input[name*="EndDate"]',
  ], toStr);

  await shortDelay();
}

async function submitHarrisForm(page) {
  const submitSelectors = [
    'input[type="submit"][value*="Search"]',
    'button[type="submit"]',
    '#ctl00_ContentPlaceHolder1_btnSearch',
    'input[id*="btnSearch"]',
  ];

  for (const sel of submitSelectors) {
    const el = await page.$(sel);
    if (el) {
      await el.click();
      await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {});
      return;
    }
  }
  throw new Error('Harris County: could not locate search submit button');
}

// ─── Row extraction ───────────────────────────────────────────────────────────

async function extractHarrisRows(page) {
  const rows = [];

  // Harris WebForms renders results in a GridView (HTML table)
  const resultTable = await page.$('table[id*="GridView"], table[id*="gvResults"], table.results-table, #ctl00_ContentPlaceHolder1_GridView1');
  if (!resultTable) return rows;

  const trs = await resultTable.$$('tr:not(:first-child)');

  for (const tr of trs) {
    try {
      const cells = await tr.$$('td');
      if (cells.length < 4) continue;

      const getCellText = async (idx) => {
        if (!cells[idx]) return '';
        return (await cells[idx].textContent()).trim();
      };

      // Column order varies — try to identify by header context
      // Typical Harris order: Doc#, Date, Instrument, Grantor, Grantee, Consideration, Address
      const docNum = await getCellText(0);
      const docDate = await getCellText(1);
      const docType = await getCellText(2);
      const grantor = await getCellText(3);
      const grantee = await getCellText(4);
      const consideration = await getCellText(5);
      const address = await getCellText(6);

      if (!docNum && !grantee) continue;

      // Check for "CASH" literal in consideration
      const considRaw = consideration.toUpperCase();
      const isCashLiteral = considRaw.includes('CASH');

      rows.push(makeTransaction({
        source_county: COUNTY,
        grantee: grantee.toUpperCase().trim(),
        grantor: grantor.toUpperCase().trim(),
        document_date: normalizeDate(docDate),
        document_type: docType.toUpperCase().trim(),
        document_number: docNum.trim(),
        apn: '',
        consideration: parseConsideration(consideration),
        address: address.toUpperCase(),
        zip: extractZip(address),
        // Preliminary cash signal from consideration field
        cash_flag: isCashLiteral,
      }));
    } catch {
      // Skip malformed rows
    }
  }

  return rows;
}

// ─── Pagination ───────────────────────────────────────────────────────────────

async function goToNextPage(page) {
  // ASP.NET GridView pager typically has a "Next" link or page number links
  const nextSelectors = [
    'a:has-text("Next")',
    'a[id*="Next"]',
    'td[colspan] a:last-child',
    '.pagination-next',
  ];

  for (const sel of nextSelectors) {
    const el = await page.$(sel);
    if (el) {
      const text = (await el.textContent()).trim();
      if (text === '...' || text.toLowerCase().includes('next') || /^\d+$/.test(text)) {
        await el.click();
        await page.waitForLoadState('domcontentloaded', { timeout: 30000 }).catch(() => {});
        return true;
      }
    }
  }
  return false;
}

// ─── Cash flagging ────────────────────────────────────────────────────────────

function flagCashTransactions(transactions) {
  const dotKeys = new Set();

  for (const t of transactions) {
    if (DOT_KEYWORDS.some((k) => t.document_type.includes(k))) {
      dotKeys.add(`${t.apn || t.document_number}|${t.document_date}`);
    }
  }

  for (const t of transactions) {
    if (!DEED_TYPES.some((d) => t.document_type.includes(d.split(' ')[0]))) continue;
    const key = `${t.apn || t.document_number}|${t.document_date}`;
    t.has_dot = dotKeys.has(key);
    // cash_flag already true if "CASH" literal found; also set if no DOT
    t.cash_flag = t.cash_flag || !t.has_dot;
  }
}

// ─── ASP.NET form helpers ─────────────────────────────────────────────────────

async function trySelectOption(page, selectors, value) {
  for (const sel of selectors) {
    const el = await page.$(sel);
    if (el) {
      try {
        await el.selectOption({ label: value });
        return;
      } catch {
        try {
          await el.selectOption({ value });
        } catch {
          // Try partial match
          const options = await el.$$('option');
          for (const opt of options) {
            const label = (await opt.textContent()).toUpperCase();
            if (label.includes(value.toUpperCase())) {
              const val = await opt.getAttribute('value');
              await el.selectOption({ value: val });
              return;
            }
          }
        }
      }
    }
  }
}

async function tryFill(page, selectors, value) {
  for (const sel of selectors) {
    const el = await page.$(sel);
    if (el) {
      await el.fill(value);
      return;
    }
  }
}

// ─── Date normalizer ──────────────────────────────────────────────────────────

function normalizeDate(raw) {
  if (!raw) return '';
  const mdy = raw.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (mdy) return `${mdy[3]}-${mdy[1].padStart(2, '0')}-${mdy[2].padStart(2, '0')}`;
  const iso = raw.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  return raw;
}
