/**
 * Shared utilities for all county scrapers:
 * - User-agent & browser setup
 * - Rate limiting (2-4s random delay)
 * - robots.txt compliance check
 * - Retry wrapper (max 2 retries)
 * - Canonical transaction shape
 */

import axios from 'axios';
import robotsParser from 'robots-parser';

export const USER_AGENT = 'AMARA-OS Research Bot / Public Records Access';

// ─── Delay helpers ───────────────────────────────────────────────────────────

export function delay(minMs, maxMs) {
  const ms = Math.floor(Math.random() * (maxMs - minMs + 1)) + minMs;
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Standard inter-request delay: 2-4 seconds */
export const randomDelay = () => delay(2000, 4000);

/** Short pause for intra-page interactions */
export const shortDelay = () => delay(500, 1200);

// ─── robots.txt ──────────────────────────────────────────────────────────────

const robotsCache = new Map();

export async function checkRobotsTxt(baseUrl, path = '/') {
  try {
    if (!robotsCache.has(baseUrl)) {
      const url = `${baseUrl.replace(/\/$/, '')}/robots.txt`;
      const res = await axios.get(url, {
        headers: { 'User-Agent': USER_AGENT },
        timeout: 8000,
      });
      robotsCache.set(baseUrl, robotsParser(url, res.data));
    }
    const robots = robotsCache.get(baseUrl);
    const allowed = robots.isAllowed(path, USER_AGENT) !== false;
    if (!allowed) {
      console.warn(`[robots.txt] ${baseUrl}${path} disallowed — skipping`);
    }
    return allowed;
  } catch {
    // If robots.txt is missing or unreachable, assume allowed
    return true;
  }
}

// ─── Playwright browser factory ───────────────────────────────────────────────

export async function createBrowser(playwright) {
  return playwright.chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
}

export async function newPage(browser) {
  const ctx = await browser.newContext({
    userAgent: USER_AGENT,
    viewport: { width: 1280, height: 900 },
    extraHTTPHeaders: {
      'Accept-Language': 'en-US,en;q=0.9',
    },
  });
  const page = await ctx.newPage();

  // Abort image / font / media downloads to speed up scraping
  await page.route('**/*', (route) => {
    const type = route.request().resourceType();
    if (['image', 'font', 'media', 'stylesheet'].includes(type)) {
      route.abort();
    } else {
      route.continue();
    }
  });

  return page;
}

// ─── Safe navigation with retry ──────────────────────────────────────────────

export async function safeGoto(page, url, opts = {}) {
  const MAX_RETRIES = 2;
  let attempt = 0;

  while (attempt <= MAX_RETRIES) {
    try {
      const response = await page.goto(url, {
        waitUntil: 'domcontentloaded',
        timeout: 30000,
        ...opts,
      });

      if (response && response.status() === 429) {
        throw new Error(`HTTP 429 Too Many Requests for ${url}`);
      }
      return response;
    } catch (err) {
      attempt++;
      if (attempt > MAX_RETRIES) throw err;
      const backoff = attempt * 3000;
      console.warn(`[retry ${attempt}/${MAX_RETRIES}] ${url} — ${err.message} — waiting ${backoff}ms`);
      await delay(backoff, backoff + 1000);
    }
  }
}

// ─── Safe axios with retry ────────────────────────────────────────────────────

export async function safeAxios(config) {
  const MAX_RETRIES = 2;
  let attempt = 0;

  while (attempt <= MAX_RETRIES) {
    try {
      return await axios({ ...config, headers: { 'User-Agent': USER_AGENT, ...(config.headers || {}) } });
    } catch (err) {
      if (err.response?.status === 429 || err.response?.status === 503) {
        attempt++;
        if (attempt > MAX_RETRIES) throw err;
        const backoff = attempt * 4000;
        console.warn(`[retry ${attempt}/${MAX_RETRIES}] ${config.url} — ${err.message}`);
        await delay(backoff, backoff + 2000);
      } else {
        throw err;
      }
    }
  }
}

// ─── Date helpers ─────────────────────────────────────────────────────────────

export function formatDate(date, sep = '/') {
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const dd = String(date.getDate()).padStart(2, '0');
  const yyyy = date.getFullYear();
  return `${mm}${sep}${dd}${sep}${yyyy}`;
}

export function isoDate(date) {
  return date.toISOString().split('T')[0];
}

export function dateRangeLast365() {
  const to = new Date();
  const from = new Date();
  from.setFullYear(from.getFullYear() - 1);
  return { from, to };
}

// ─── CAPTCHA detection ───────────────────────────────────────────────────────

export async function detectCaptcha(page) {
  const content = await page.content();
  const signals = ['captcha', 'recaptcha', 'hcaptcha', 'cf-challenge', 'access denied', 'blocked'];
  return signals.some((s) => content.toLowerCase().includes(s));
}

// ─── ZIP filter ───────────────────────────────────────────────────────────────

export function extractZip(address) {
  if (!address) return null;
  const m = address.match(/\b(\d{5})(?:-\d{4})?\b/g);
  return m ? m[m.length - 1] : null;
}

export function inZipList(address, zipList) {
  const zip = extractZip(address);
  return zip ? zipList.includes(zip) : false;
}

// ─── Canonical transaction shape ─────────────────────────────────────────────

/**
 * @typedef {Object} Transaction
 * @property {string} source_county
 * @property {string} grantee
 * @property {string} grantor
 * @property {string} document_date      ISO YYYY-MM-DD
 * @property {string} document_type
 * @property {string} document_number
 * @property {string} legal_description
 * @property {string} apn
 * @property {number|null} consideration
 * @property {string} address
 * @property {string|null} zip
 * @property {boolean} cash_flag
 * @property {boolean} has_dot
 * @property {string} scraped_at         ISO timestamp
 */

export function makeTransaction(overrides = {}) {
  return {
    source_county: '',
    grantee: '',
    grantor: '',
    document_date: '',
    document_type: '',
    document_number: '',
    legal_description: '',
    apn: '',
    consideration: null,
    address: '',
    zip: null,
    cash_flag: false,
    has_dot: false,
    scraped_at: new Date().toISOString(),
    ...overrides,
  };
}

// ─── Parse consideration amounts ─────────────────────────────────────────────

export function parseConsideration(raw) {
  if (!raw) return null;
  const cleaned = String(raw).replace(/[^0-9.]/g, '');
  const val = parseFloat(cleaned);
  return isNaN(val) || val === 0 ? null : val;
}
