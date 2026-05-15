'use strict';

/**
 * Playwright browser wrapper for JS-gated government portals.
 *
 * Uses the system Chromium binary at /opt/pw-browsers/chromium-*/chrome-linux/chrome
 * with automatic fallback detection. If no browser is available, all methods
 * reject with code BROWSER_UNAVAILABLE so callers can fall back gracefully.
 */

const fs   = require('node:fs');
const path = require('node:path');

const BROWSER_PATHS = [
  process.env.CHROMIUM_EXECUTABLE,
  '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  '/usr/bin/chromium-browser',
  '/usr/bin/chromium',
  '/usr/bin/google-chrome-stable',
  '/usr/bin/google-chrome',
].filter(Boolean);

const USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

const DEFAULT_TIMEOUT = 45_000;
const TABLE_WAIT      = 8_000;

function findChromium() {
  for (const p of BROWSER_PATHS) {
    if (fs.existsSync(p)) return p;
  }

  // Try glob-style search in /opt/pw-browsers
  try {
    const base = '/opt/pw-browsers';
    if (fs.existsSync(base)) {
      const dirs = fs.readdirSync(base).filter((d) => d.startsWith('chromium'));
      for (const d of dirs) {
        const candidate = path.join(base, d, 'chrome-linux/chrome');
        if (fs.existsSync(candidate)) return candidate;
      }
    }
  } catch { /* ignore */ }

  return null;
}

async function getLauncher() {
  const executablePath = findChromium();
  if (!executablePath) {
    const err = new Error('No Chromium binary found. Run: npm run install:browser');
    err.code = 'BROWSER_UNAVAILABLE';
    throw err;
  }

  let playwright;
  try {
    playwright = require('playwright');
  } catch {
    const err = new Error('playwright not installed. Run: npm install in scanner/');
    err.code = 'BROWSER_UNAVAILABLE';
    throw err;
  }

  return { playwright, executablePath };
}

/**
 * Open a URL in a headless Chromium page, wait for a CSS selector to appear,
 * then return the page's rendered HTML.
 *
 * opts:
 *   waitFor     — CSS selector to wait for (default: 'body')
 *   timeout     — page load timeout ms (default: 45000)
 *   cookies     — array of { name, value, domain, path } (optional)
 *   clickBefore — CSS selector to click before extracting (optional)
 *   screenshot  — path to save a screenshot on failure (optional)
 */
async function fetchRendered(url, opts = {}) {
  const { playwright, executablePath } = await getLauncher();

  const browser = await playwright.chromium.launch({
    executablePath,
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
  });

  const context = await browser.newContext({
    userAgent: USER_AGENT,
    viewport: { width: 1280, height: 900 },
    locale: 'en-US',
    timezoneId: 'America/New_York',
  });

  const page = await context.newPage();

  try {
    if (opts.cookies) {
      await context.addCookies(opts.cookies.map((c) => ({ ...c, url })));
    }

    await page.goto(url, {
      timeout:   opts.timeout ?? DEFAULT_TIMEOUT,
      waitUntil: 'networkidle',
    });

    const selector = opts.waitFor ?? 'body';
    await page.waitForSelector(selector, { timeout: TABLE_WAIT }).catch(() => { /* best effort */ });

    if (opts.clickBefore) {
      await page.click(opts.clickBefore).catch(() => { /* element may not exist */ });
      await page.waitForLoadState('networkidle').catch(() => { /* best effort */ });
    }

    return await page.content();
  } catch (err) {
    if (opts.screenshot) {
      try { await page.screenshot({ path: opts.screenshot, fullPage: true }); } catch { /* ignore */ }
    }
    throw err;
  } finally {
    await browser.close();
  }
}

/**
 * Click a download button on a page and capture the downloaded file content.
 * Returns { filename, content } or null if download fails.
 *
 * opts:
 *   clickSelector — CSS selector of the download button (required)
 *   timeout       — overall timeout ms
 */
async function clickDownload(url, opts = {}) {
  const { playwright, executablePath } = await getLauncher();

  const browser = await playwright.chromium.launch({
    executablePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });

  const context = await browser.newContext({
    userAgent: USER_AGENT,
    viewport:  { width: 1280, height: 900 },
    acceptDownloads: true,
  });

  const page = await context.newPage();

  try {
    await page.goto(url, { timeout: opts.timeout ?? DEFAULT_TIMEOUT, waitUntil: 'networkidle' });

    const selector = opts.clickSelector;
    await page.waitForSelector(selector, { timeout: TABLE_WAIT });

    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: opts.timeout ?? DEFAULT_TIMEOUT }),
      page.click(selector),
    ]);

    const filePath = await download.path();
    if (!filePath) return null;

    return {
      filename: download.suggestedFilename(),
      content:  fs.readFileSync(filePath, 'utf8'),
    };
  } catch {
    return null;
  } finally {
    await browser.close();
  }
}

/**
 * Fill a search form, submit, wait for results, and return rendered HTML.
 *
 * opts:
 *   fields   — { selector: value } map of form fields to fill
 *   submit   — CSS selector of submit button (default: '[type=submit]')
 *   waitFor  — CSS selector to wait for after submit
 *   timeout  — overall timeout ms
 *   pages    — max pagination clicks to follow (default: 0 = no pagination)
 *   nextBtn  — CSS selector of "Next" button for pagination
 */
async function fillAndFetch(url, opts = {}) {
  const { playwright, executablePath } = await getLauncher();

  const browser = await playwright.chromium.launch({
    executablePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });

  const context = await browser.newContext({
    userAgent: USER_AGENT,
    viewport:  { width: 1280, height: 900 },
  });

  const page = await context.newPage();
  const pages = [];

  try {
    await page.goto(url, { timeout: opts.timeout ?? DEFAULT_TIMEOUT, waitUntil: 'networkidle' });

    // Fill form fields
    for (const [selector, value] of Object.entries(opts.fields ?? {})) {
      await page.fill(selector, value).catch(() => { /* skip missing fields */ });
    }

    const submitSel = opts.submit ?? '[type="submit"]';
    await Promise.all([
      page.waitForNavigation({ timeout: opts.timeout ?? DEFAULT_TIMEOUT, waitUntil: 'networkidle' }).catch(() => {}),
      page.click(submitSel),
    ]);

    if (opts.waitFor) {
      await page.waitForSelector(opts.waitFor, { timeout: TABLE_WAIT }).catch(() => {});
    }

    pages.push(await page.content());

    // Pagination
    const maxPages = opts.pages ?? 0;
    let pg = 0;
    const nextSel = opts.nextBtn;

    while (nextSel && pg < maxPages) {
      const nextBtn = await page.$(nextSel);
      if (!nextBtn) break;
      const disabled = await nextBtn.getAttribute('disabled');
      const cls      = await nextBtn.getAttribute('class') ?? '';
      if (disabled !== null || cls.includes('disabled') || cls.includes('inactive')) break;

      await Promise.all([
        page.waitForNavigation({ timeout: 15_000, waitUntil: 'networkidle' }).catch(() => {}),
        nextBtn.click(),
      ]);

      if (opts.waitFor) await page.waitForSelector(opts.waitFor, { timeout: TABLE_WAIT }).catch(() => {});
      pages.push(await page.content());
      pg++;
    }

    return pages;
  } finally {
    await browser.close();
  }
}

module.exports = { fetchRendered, clickDownload, fillAndFetch };
