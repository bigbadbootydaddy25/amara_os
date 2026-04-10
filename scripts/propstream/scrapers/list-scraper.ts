// ─────────────────────────────────────────────────────────────────────────────
// Lead List Scraper — navigates to each list, paginates, extracts all records
// ─────────────────────────────────────────────────────────────────────────────

import type { Page } from "playwright";
import type { PropStreamBrowser } from "../lib/browser.js";
import { RateLimiter, sleep } from "../lib/rate-limiter.js";
import {
  appendRawPage,
  markListComplete,
  markListInProgress,
  recordError,
  rawListExists,
  ensureDataDir,
} from "../lib/storage.js";
import type { DOMSelectors, LeadListName, PageResult, RawRecord } from "../types/index.js";
import { ALL_LEAD_LISTS } from "../config/lists.js";

const MAX_PAGES_PER_LIST = 500; // safety cap
const MAX_RETRIES = 3;

// PropStream navigation candidates for the lead lists section
const LISTS_NAV_SELECTORS = [
  'a:has-text("Lists")',
  'a[href*="/lists"]',
  '[class*="nav"] a:has-text("List")',
  '[class*="sidebar"] a:has-text("List")',
  'nav a:has-text("My Lists")',
  'nav a:has-text("Lead Lists")',
];

export class LeadListScraper {
  private rateLimiter: RateLimiter;
  private selectors: DOMSelectors;

  constructor(
    private page: Page,
    private browser: PropStreamBrowser,
    selectors: DOMSelectors,
    rateLimiter?: RateLimiter
  ) {
    this.selectors = selectors;
    this.rateLimiter = rateLimiter ?? new RateLimiter();
  }

  // ── Public API ──────────────────────────────────────────────────────────────

  async scrapeAll(
    listsToScrape: LeadListName[] = ALL_LEAD_LISTS,
    skipCompleted = true
  ): Promise<void> {
    ensureDataDir();
    console.log(`\n[scraper] starting — ${listsToScrape.length} lists to scrape`);

    for (const listName of listsToScrape) {
      if (skipCompleted && rawListExists(listName)) {
        console.log(`[scraper] skipping ${listName} (already scraped)`);
        continue;
      }

      console.log(`\n[scraper] ▶ ${listName}`);
      try {
        await this.scrapeList(listName);
        markListComplete(listName);
        console.log(`[scraper] ✓ ${listName} complete`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error(`[scraper] ✗ ${listName} FAILED: ${msg}`);
        recordError(listName, msg);
        await this.browser.screenshot(this.page, `error-${listName.replace(/\s+/g, "_")}`);
      }

      await this.rateLimiter.wait("list");
    }

    console.log("\n[scraper] all lists processed");
  }

  async scrapeList(listName: LeadListName): Promise<void> {
    // Navigate to the list
    await this.navigateToList(listName);

    let page = 1;
    let hasMore = true;

    while (hasMore && page <= MAX_PAGES_PER_LIST) {
      markListInProgress(listName, page);
      console.log(`  [scraper] page ${page}`);

      let result: PageResult | null = null;
      for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        try {
          result = await this.extractPage(listName, page);
          break;
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          console.warn(`  [scraper] page ${page} attempt ${attempt} failed: ${msg}`);
          if (attempt === MAX_RETRIES) throw err;
          await this.rateLimiter.wait("default");
          await this.page.reload({ waitUntil: "domcontentloaded" });
          await sleep(1500);
        }
      }

      if (!result || result.records.length === 0) {
        console.log(`  [scraper] no records on page ${page} — stopping`);
        break;
      }

      appendRawPage(listName, result.records);
      console.log(`  [scraper] extracted ${result.records.length} records (page ${page}/${result.totalPages ?? "?"})`);

      hasMore = result.hasNextPage;
      if (hasMore) {
        await this.goToNextPage();
        await this.rateLimiter.wait("page");
        page++;
      }
    }
  }

  // ── Navigation ──────────────────────────────────────────────────────────────

  private async navigateToList(listName: LeadListName): Promise<void> {
    // First, make sure we're on the lists overview page
    await this.ensureOnListsPage();
    await sleep(1000);

    // Search for the list by name
    await this.findAndOpenList(listName);

    // Wait for data to load
    await this.waitForTableLoad();
  }

  private async ensureOnListsPage(): Promise<void> {
    const url = this.page.url();
    if (url.includes("/lists") || url.includes("lists")) {
      return; // already there
    }

    for (const sel of LISTS_NAV_SELECTORS) {
      try {
        const count = await this.page.locator(sel).count();
        if (count > 0) {
          await this.page.locator(sel).first().click();
          await this.page.waitForLoadState("domcontentloaded");
          await sleep(1500);
          return;
        }
      } catch { /* try next */ }
    }

    // Try direct URL navigation
    await this.page.goto("https://app.propstream.com/lists", {
      waitUntil: "domcontentloaded",
      timeout: 20_000,
    });
    await sleep(2000);
  }

  private async findAndOpenList(listName: LeadListName): Promise<void> {
    // Attempt 1: find a link or row that contains the list name text
    const exactTextSelectors = [
      `a:has-text("${listName}")`,
      `[class*="list-item"]:has-text("${listName}")`,
      `tr:has-text("${listName}")`,
      `[class*="row"]:has-text("${listName}")`,
      `td:has-text("${listName}")`,
      `[role="row"]:has-text("${listName}")`,
    ];

    for (const sel of exactTextSelectors) {
      try {
        const count = await this.page.locator(sel).count();
        if (count > 0) {
          await this.rateLimiter.wait("action");
          await this.page.locator(sel).first().click();
          await this.page.waitForLoadState("domcontentloaded");
          await sleep(1500);
          return;
        }
      } catch { /* try next */ }
    }

    // Attempt 2: look for a search box to filter lists
    const searchSel = this.selectors.listSearchInput;
    try {
      const count = await this.page.locator(searchSel).count();
      if (count > 0) {
        await this.page.locator(searchSel).fill(listName);
        await sleep(1000);
        // Click first result
        const resultSel = `a:has-text("${listName}"), tr:has-text("${listName}")`;
        const rCount = await this.page.locator(resultSel).count();
        if (rCount > 0) {
          await this.page.locator(resultSel).first().click();
          await this.page.waitForLoadState("domcontentloaded");
          await sleep(1500);
          return;
        }
      }
    } catch { /* fall through */ }

    // Attempt 3: look at full DOM for matching text
    const found = await this.page.evaluate((name: string) => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let node: Text | null;
      while ((node = walker.nextNode() as Text | null)) {
        if (node.textContent?.trim() === name) {
          const el = node.parentElement;
          if (el) {
            el.click();
            return true;
          }
        }
      }
      return false;
    }, listName);

    if (!found) {
      throw new Error(`Cannot locate list "${listName}" in the DOM`);
    }

    await this.page.waitForLoadState("domcontentloaded");
    await sleep(2000);
  }

  private async waitForTableLoad(): Promise<void> {
    // Wait for either a table row or a "no results" indicator
    try {
      await this.page.waitForSelector(
        `${this.selectors.listTableRows}, ${this.selectors.noResultsIndicator}`,
        { timeout: 15_000 }
      );
    } catch {
      // Best effort — proceed anyway
      await sleep(2000);
    }
  }

  // ── Extraction ──────────────────────────────────────────────────────────────

  private async extractPage(
    listName: LeadListName,
    pageNum: number
  ): Promise<PageResult> {
    const sourceUrl = this.page.url();

    // Extract column headers
    const headers = await this.extractHeaders();

    // Extract all data rows
    const rows = await this.page.evaluate(
      ({ rowSel, headersSel }: { rowSel: string; headersSel: string }) => {
        const rows = Array.from(document.querySelectorAll(rowSel));
        return rows.map((row) => {
          const cells = Array.from(row.querySelectorAll("td, [class*='cell']"));
          return cells.map((c) => c.textContent?.trim() ?? "");
        });
      },
      { rowSel: this.selectors.listTableRows, headersSel: this.selectors.listTableHeaders }
    );

    const records: RawRecord[] = rows
      .filter((row) => row.some((cell) => cell.length > 0)) // skip empty rows
      .map((row, idx) => {
        const fields: Record<string, string> = {};
        headers.forEach((h, i) => {
          if (h) fields[h] = row[i] ?? "";
        });
        // If no headers, use positional keys
        if (headers.length === 0) {
          row.forEach((cell, i) => { fields[`col_${i}`] = cell; });
        }
        const incomplete = row.some((cell) => cell === "") || row.length < (headers.length * 0.7);
        return {
          listType: listName,
          rowIndex: (pageNum - 1) * 1000 + idx,
          fields,
          incomplete,
          scrapedAt: new Date().toISOString(),
          sourceUrl,
        } satisfies RawRecord;
      });

    // Determine pagination state
    const paginationInfo = await this.getPaginationInfo();

    return {
      records,
      hasNextPage: paginationInfo.hasNext,
      currentPage: pageNum,
      totalPages: paginationInfo.total,
    };
  }

  private async extractHeaders(): Promise<string[]> {
    return this.page.evaluate((sel: string) => {
      // Try table headers
      const ths = Array.from(document.querySelectorAll(sel));
      if (ths.length > 0) {
        return ths.map((th) => th.textContent?.trim() ?? "");
      }
      // Fallback: first row cells if it looks like a header row
      const firstRow = document.querySelector("tr:first-child");
      if (firstRow) {
        return Array.from(firstRow.querySelectorAll("th, td"))
          .map((c) => c.textContent?.trim() ?? "");
      }
      return [];
    }, this.selectors.listTableHeaders);
  }

  private async getPaginationInfo(): Promise<{ hasNext: boolean; total: number | null }> {
    return this.page.evaluate(
      ({ nextSel, totalSel }: { nextSel: string; totalSel: string }) => {
        // Check if "Next" button exists and is enabled
        const nextBtn = document.querySelector(nextSel);
        const hasNext =
          !!nextBtn &&
          !nextBtn.hasAttribute("disabled") &&
          !(nextBtn as HTMLElement).classList.contains("disabled") &&
          nextBtn.getAttribute("aria-disabled") !== "true";

        // Try to read total pages
        const totalEl = document.querySelector(totalSel);
        const totalText = totalEl?.textContent ?? "";
        const totalMatch = totalText.match(/(\d+)/);
        const total = totalMatch ? parseInt(totalMatch[1], 10) : null;

        // Also check for page info in "Page X of Y" style text
        const pageInfoEl = Array.from(document.querySelectorAll("span, div, p"))
          .find((el) => /page\s+\d+\s+of\s+\d+/i.test(el.textContent ?? ""));
        if (pageInfoEl) {
          const m = pageInfoEl.textContent?.match(/page\s+\d+\s+of\s+(\d+)/i);
          if (m) return { hasNext: parseInt(m[1]) > 0, total: parseInt(m[1]) };
        }

        return { hasNext, total };
      },
      { nextSel: this.selectors.paginationNext, totalSel: this.selectors.paginationTotal }
    );
  }

  private async goToNextPage(): Promise<void> {
    const nextSel = this.selectors.paginationNext;
    try {
      await this.page.locator(nextSel).first().click();
      await this.page.waitForLoadState("domcontentloaded");
      await this.waitForTableLoad();
    } catch (err) {
      throw new Error(`Failed to navigate to next page: ${err}`);
    }
  }
}
