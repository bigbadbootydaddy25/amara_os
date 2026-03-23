/**
 * AMARA OS — Zillow Playwright Scanner
 * Real automated scraper. No mocks. No manual input.
 * AMARA runs this silently in the background.
 *
 * Zillow public search does not require authentication.
 * Filters are passed via URL + UI interaction.
 * Rate limits: 8 req/min max. 4s delay between pages.
 */

import type { Browser, Page } from "playwright";
import { ZillowRawListing } from "./types";

// Distress-signaling search terms to rotate through
const DISTRESS_SEARCH_TERMS = [
  "fixer upper",
  "as-is",
  "estate sale",
  "investor special",
  "needs work",
  "motivated seller",
];

export interface ZillowScanConfig {
  market: string;
  state: string;
  zips: string[];
  minDom: number;       // minimum days on market
  priceReduced: boolean;
  maxPrice?: number;
  minPrice?: number;
  maxPages?: number;    // max pagination pages per ZIP
}

export async function scanZillowMarket(
  config: ZillowScanConfig
): Promise<ZillowRawListing[]> {
  const { chromium } = await import("playwright");

  const browser = await chromium.launch({
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-blink-features=AutomationControlled",
      "--disable-dev-shm-usage",
    ],
  });

  const allListings: ZillowRawListing[] = [];

  try {
    for (const zip of config.zips) {
      const zipListings = await scanZip(browser, zip, config);
      allListings.push(...zipListings);
      // Rate limit: pause between ZIPs
      await sleep(4000 + Math.random() * 2000);
    }
  } finally {
    await browser.close();
  }

  return allListings;
}

async function scanZip(
  browser: Browser,
  zip: string,
  config: ZillowScanConfig
): Promise<ZillowRawListing[]> {
  const page = await browser.newPage();

  // Stealth: randomize viewport and user agent
  await page.setViewportSize({
    width: 1280 + Math.floor(Math.random() * 200),
    height: 800 + Math.floor(Math.random() * 100),
  });

  await page.setExtraHTTPHeaders({
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
  });

  const listings: ZillowRawListing[] = [];

  try {
    // Build search URL for this ZIP
    const url = buildZillowSearchUrl(zip, config);
    console.log(`[AMARA:Zillow] Scanning ZIP ${zip} → ${url}`);

    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await sleep(2000 + Math.random() * 1000);

    const maxPages = config.maxPages ?? 3;
    let currentPage = 1;

    while (currentPage <= maxPages) {
      const pageListings = await extractListingsFromPage(page);
      listings.push(...pageListings);
      console.log(
        `[AMARA:Zillow] ZIP ${zip} page ${currentPage}: ${pageListings.length} listings extracted`
      );

      // Try next page
      const hasNext = await goToNextPage(page);
      if (!hasNext) break;
      currentPage++;
      await sleep(3000 + Math.random() * 2000);
    }
  } catch (err) {
    console.error(`[AMARA:Zillow] Error scanning ZIP ${zip}:`, err);
  } finally {
    await page.close();
  }

  return listings;
}

function buildZillowSearchUrl(zip: string, config: ZillowScanConfig): string {
  // Zillow search URL with filters encoded
  const priceReductionFilter = config.priceReduced
    ? "&price_reduced=1"
    : "";

  const priceRange = [
    config.minPrice ? `&price_min=${config.minPrice}` : "",
    config.maxPrice ? `&price_max=${config.maxPrice}` : "",
  ].join("");

  // Sort by days on market (longest first) — surfaces the most distressed
  return `https://www.zillow.com/homes/for_sale/${zip}_rb/?searchQueryState=` +
    encodeURIComponent(
      JSON.stringify({
        pagination: { currentPage: 1 },
        mapBounds: null,
        filterState: {
          sort: { value: "days" },
          isForSaleByAgent: { value: true },
          isForSaleByOwner: { value: true },
          isNewConstruction: { value: false },
          isMobileHome: { value: false },
          isLot: { value: false },
          ...(config.priceReduced && { isPriceReduced: { value: true } }),
          ...(config.minPrice && { price: { min: config.minPrice } }),
          ...(config.maxPrice && { price: { max: config.maxPrice } }),
        },
        isMapVisible: false,
        isListVisible: true,
        mapZoom: 13,
        regionSelection: [{ regionId: 0, regionType: 7 }],
      })
    );
}

async function extractListingsFromPage(page: Page): Promise<ZillowRawListing[]> {
  try {
    // Wait for listing cards to load
    await page.waitForSelector('[data-test="property-card"]', {
      timeout: 15000,
    });
  } catch {
    // Try alternative selectors
    try {
      await page.waitForSelector(".property-card", { timeout: 8000 });
    } catch {
      console.warn("[AMARA:Zillow] No listing cards found on page");
      return [];
    }
  }

  const listings = await page.evaluate(() => {
    const cards = document.querySelectorAll(
      '[data-test="property-card"], .property-card, article[data-zpid]'
    );

    return Array.from(cards).map((card) => {
      const getText = (sel: string) =>
        card.querySelector(sel)?.textContent?.trim() ?? null;
      const getAttr = (sel: string, attr: string) =>
        (card.querySelector(sel) as HTMLElement)?.getAttribute(attr) ?? null;

      // Extract address
      const addressEl = card.querySelector(
        "address, [data-test='property-card-addr'], .list-card-addr"
      );
      const address = addressEl?.textContent?.trim() ?? null;

      // Extract price
      const priceEl = card.querySelector(
        "[data-test='property-card-price'], .list-card-price, .property-card-price"
      );
      const price = priceEl?.textContent?.trim() ?? null;

      // Extract beds/baths/sqft
      const detailsEl = card.querySelector(
        "[data-test='property-card-details'], .list-card-details"
      );
      const details = detailsEl?.textContent?.trim() ?? null;

      // Extract DOM (days on Zillow)
      const domEl = card.querySelector(
        "[data-test='property-card-days'], .list-card-days, [class*='days']"
      );
      const dom = domEl?.textContent?.trim() ?? null;

      // Extract "Price reduced" badge
      const priceReducedEl = card.querySelector(
        "[data-test='price-reduced'], .price-reduced, [class*='price-reduced']"
      );
      const priceReduced = !!priceReducedEl;

      // Link to detail page
      const linkEl = card.querySelector(
        "a[href*='/homedetails/'], a[data-test='property-card-link']"
      ) as HTMLAnchorElement | null;
      const detailUrl = linkEl?.href ?? null;

      // ZPID from URL or data attribute
      const zpid =
        card.getAttribute("data-zpid") ??
        detailUrl?.match(/\/(\d+)_zpid/)?.[1] ??
        null;

      // Status badge (For Sale, Pending, etc.)
      const statusEl = card.querySelector(
        "[data-test='property-card-status'], .list-card-status, [class*='status']"
      );
      const status = statusEl?.textContent?.trim() ?? "For Sale";

      return {
        zpid,
        address,
        price,
        details,
        dom,
        priceReduced,
        status,
        detailUrl,
        scrapedAt: new Date().toISOString(),
      };
    });
  });

  // Filter out empty/invalid listings
  return listings.filter(
    (l) => l.address && l.price
  ) as ZillowRawListing[];
}

async function extractListingDetail(
  page: Page,
  detailUrl: string
): Promise<Partial<ZillowRawListing>> {
  try {
    await page.goto(detailUrl, { waitUntil: "domcontentloaded", timeout: 20000 });
    await sleep(1500);

    return await page.evaluate(() => {
      const getText = (sel: string) =>
        document.querySelector(sel)?.textContent?.trim() ?? null;

      // Remarks / description
      const remarks =
        document.querySelector(
          "[data-testid='description-text'], .ds-description-section, .listing-overview-overview"
        )?.textContent?.trim() ?? null;

      // Zestimate
      const zestimate =
        document.querySelector(
          "[data-testid='zestimate'], .zestimate-price"
        )?.textContent?.trim() ?? null;

      // Rent estimate
      const rentEstimate =
        document.querySelector("[data-testid='rent-zestimate']")?.textContent?.trim() ??
        null;

      // Price history
      const priceHistoryRows = Array.from(
        document.querySelectorAll(
          "[data-testid='price-history-row'], .price-history tr"
        )
      ).map((row) => row.textContent?.trim() ?? "");

      // Year built
      const factItems = Array.from(
        document.querySelectorAll(".ds-home-fact-list li, [data-testid='home-details-facts'] li")
      );
      let yearBuilt: string | null = null;
      for (const item of factItems) {
        const text = item.textContent ?? "";
        if (text.toLowerCase().includes("built")) {
          const match = text.match(/\d{4}/);
          if (match) yearBuilt = match[0];
        }
      }

      return { remarks, zestimate, rentEstimate, yearBuilt, priceHistoryRows };
    });
  } catch (err) {
    console.error(`[AMARA:Zillow] Error fetching detail page:`, err);
    return {};
  }
}

async function goToNextPage(page: Page): Promise<boolean> {
  try {
    const nextBtn = await page.$(
      '[aria-label="Next page"], [title="Next page"], button[rel="next"]'
    );
    if (!nextBtn) return false;
    const isDisabled = await nextBtn.getAttribute("disabled");
    if (isDisabled !== null) return false;
    await nextBtn.click();
    await page.waitForLoadState("domcontentloaded");
    return true;
  } catch {
    return false;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
