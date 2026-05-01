import { chromium, Browser, Page } from 'playwright';

let browser: Browser | null = null;

export async function getBrowser(): Promise<Browser> {
  if (!browser || !browser.isConnected()) {
    browser = await chromium.launch({ headless: true });
  }
  return browser;
}

export async function closeBrowser(): Promise<void> {
  if (browser) {
    await browser.close();
    browser = null;
  }
}

export interface ScrapeResult {
  url: string;
  title: string;
  text: string;
  error?: string;
}

export async function scrapeUrl(url: string, selector?: string): Promise<ScrapeResult> {
  let page: Page | null = null;
  try {
    const b = await getBrowser();
    page = await b.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20_000 });

    const title = await page.title();
    const text = selector
      ? await page.locator(selector).innerText().catch(() => '')
      : await page.evaluate(() => document.body.innerText.slice(0, 8000));

    return { url, title, text };
  } catch (err) {
    return { url, title: '', text: '', error: String(err) };
  } finally {
    await page?.close();
  }
}

// Zillow DOM tracker — find SFR listings that crossed 90 days on market
export async function scrapeZillowDom(market: string): Promise<ScrapeResult[]> {
  // Zillow scraping requires a real session/cookies in production.
  // Stub returns empty — wire Playwright session when available.
  console.log(`[browser-automator] Zillow DOM scrape stub for market: ${market}`);
  return [];
}

// County clerk search stub — adapt per county
export async function scrapeCountyClerk(county: string, searchTerm: string): Promise<ScrapeResult> {
  console.log(`[browser-automator] County clerk scrape stub: ${county} / ${searchTerm}`);
  return { url: '', title: county, text: `County clerk scrape for "${searchTerm}" not yet wired.` };
}
