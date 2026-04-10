// ─────────────────────────────────────────────────────────────────────────────
// DOM Inspector — discovers live selectors on PropStream before scraping
// Run first to verify the DOM structure, save a report, then proceed.
// ─────────────────────────────────────────────────────────────────────────────

import type { Page } from "playwright";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import { sleep } from "./rate-limiter.js";
import type { PropStreamBrowser } from "./browser.js";
import type { DOMSelectors } from "../types/index.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.resolve(__dirname, "../data");
const REPORT_PATH = path.join(DATA_DIR, "dom-inspection-report.json");

// Known PropStream URL patterns — may need adjustment
const LISTS_URL_PATTERNS = [
  "https://app.propstream.com/lists",
  "https://app.propstream.com/my-lists",
  "https://app.propstream.com/lead-lists",
  "https://app.propstream.com/#/lists",
];

export interface DOMInspectionReport {
  inspectedAt: string;
  currentUrl: string;
  listsNavItem: string | null;
  listsPageUrl: string | null;
  selectors: DOMSelectors;
  tableHeaders: string[];
  sampleListNames: string[];
  rawDomSnapshot: string;
  notes: string[];
}

export async function inspectDOM(
  page: Page,
  browser: PropStreamBrowser
): Promise<DOMInspectionReport> {
  console.log("[inspector] starting DOM inspection...");
  fs.mkdirSync(DATA_DIR, { recursive: true });

  const notes: string[] = [];
  const report: DOMInspectionReport = {
    inspectedAt: new Date().toISOString(),
    currentUrl: page.url(),
    listsNavItem: null,
    listsPageUrl: null,
    selectors: buildDefaultSelectors(),
    tableHeaders: [],
    sampleListNames: [],
    rawDomSnapshot: "",
    notes,
  };

  // 1. Find and click the Lists nav item
  const listsNavLink = await findListsNavigation(page, notes);
  if (listsNavLink) {
    report.listsNavItem = listsNavLink;
    await page.locator(listsNavLink).first().click();
    await sleep(2000);
    await browser.screenshot(page, "inspect-lists-nav");
    report.listsPageUrl = page.url();
    notes.push(`Navigated to lists page: ${page.url()}`);
  } else {
    // Try direct URL navigation
    for (const url of LISTS_URL_PATTERNS) {
      try {
        await page.goto(url, { waitUntil: "domcontentloaded", timeout: 10_000 });
        await sleep(1500);
        if (!page.url().includes("login")) {
          report.listsPageUrl = page.url();
          notes.push(`Direct navigation succeeded: ${url}`);
          break;
        }
      } catch {
        notes.push(`Direct URL failed: ${url}`);
      }
    }
  }

  await browser.screenshot(page, "inspect-lists-page");

  // 2. Inspect the lists page DOM
  const domAnalysis = await page.evaluate(() => {
    const snapshot: Record<string, unknown> = {};

    // Find tables
    const tables = Array.from(document.querySelectorAll("table"));
    snapshot.tableCount = tables.length;
    snapshot.tableHeaders = tables.map((t) =>
      Array.from(t.querySelectorAll("th")).map((th) => th.textContent?.trim())
    );

    // Find list-like elements (rows of lead lists)
    const listItems = Array.from(
      document.querySelectorAll('[class*="list"], [class*="List"], [data-testid*="list"]')
    ).slice(0, 20).map((el) => ({
      tag: el.tagName,
      classes: el.className,
      text: el.textContent?.trim().slice(0, 80),
    }));
    snapshot.listItems = listItems;

    // Find links containing "list" text
    const listLinks = Array.from(document.querySelectorAll("a"))
      .filter((a) => /list|leads?|queue/i.test(a.textContent ?? ""))
      .slice(0, 20)
      .map((a) => ({
        text: a.textContent?.trim(),
        href: a.href,
        classes: a.className,
      }));
    snapshot.listLinks = listLinks;

    // Pagination hints
    const paginators = Array.from(
      document.querySelectorAll(
        '[class*="pagina"], [class*="Pagina"], [aria-label*="page"], [aria-label*="Page"]'
      )
    ).slice(0, 5).map((el) => ({
      tag: el.tagName,
      classes: el.className,
      ariaLabel: el.getAttribute("aria-label"),
      text: el.textContent?.trim().slice(0, 100),
    }));
    snapshot.paginators = paginators;

    // Navigation items
    const navItems = Array.from(
      document.querySelectorAll('nav a, [role="navigation"] a, aside a, [class*="sidebar"] a')
    ).slice(0, 30).map((a) => ({
      text: a.textContent?.trim(),
      href: (a as HTMLAnchorElement).href,
      classes: a.className,
    }));
    snapshot.navItems = navItems;

    // All button text
    const buttons = Array.from(document.querySelectorAll("button"))
      .slice(0, 40)
      .map((b) => b.textContent?.trim().slice(0, 40));
    snapshot.buttons = buttons;

    return snapshot;
  });

  report.rawDomSnapshot = JSON.stringify(domAnalysis, null, 2);

  // 3. Extract table headers if found
  if (Array.isArray((domAnalysis as any).tableHeaders)) {
    report.tableHeaders = ((domAnalysis as any).tableHeaders as string[][])
      .flat()
      .filter(Boolean) as string[];
  }

  // 4. Extract sample list names from nav/link text
  const listLinks = (domAnalysis as any).listLinks ?? [];
  report.sampleListNames = listLinks
    .map((l: any) => l.text)
    .filter((t: string) => t && t.length < 50)
    .slice(0, 10);

  // 5. Refine selectors based on what we found
  report.selectors = await refineSelectors(page, domAnalysis, notes);

  // 6. If we found a data table, open first list and inspect it
  await inspectFirstList(page, browser, report, notes);

  // Save report
  fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2));
  console.log(`[inspector] report saved to ${REPORT_PATH}`);

  return report;
}

async function findListsNavigation(
  page: Page,
  notes: string[]
): Promise<string | null> {
  const candidates = [
    'nav a:has-text("Lists")',
    'nav a:has-text("My Lists")',
    'nav a:has-text("Lead Lists")',
    '[class*="sidebar"] a:has-text("Lists")',
    '[class*="nav"] a:has-text("Lists")',
    'a[href*="/lists"]',
    'a[href*="lists"]',
  ];

  for (const sel of candidates) {
    try {
      const count = await page.locator(sel).count();
      if (count > 0) {
        notes.push(`Found lists nav via: ${sel}`);
        return sel;
      }
    } catch {
      /* try next */
    }
  }
  notes.push("Could not find lists navigation automatically");
  return null;
}

async function refineSelectors(
  page: Page,
  domAnalysis: Record<string, unknown>,
  notes: string[]
): Promise<DOMSelectors> {
  const selectors = buildDefaultSelectors();

  // Table rows
  const tableRowCandidates = [
    "table tbody tr",
    '[class*="table"] [class*="row"]',
    '[class*="grid"] [class*="row"]',
    '[role="row"]',
    '[class*="TableRow"]',
    '[class*="list-row"]',
  ];
  for (const sel of tableRowCandidates) {
    const count = await page.locator(sel).count();
    if (count > 1) {
      selectors.listTableRows = sel;
      notes.push(`Table rows: ${sel} (${count} found)`);
      break;
    }
  }

  // Pagination
  const nextCandidates = [
    'button:has-text("Next")',
    'a:has-text("Next")',
    '[aria-label="Next page"]',
    '[aria-label="next"]',
    '[class*="next"]',
    '[class*="Next"]',
    'button[class*="next"]',
  ];
  for (const sel of nextCandidates) {
    const count = await page.locator(sel).count();
    if (count > 0) {
      selectors.paginationNext = sel;
      notes.push(`Pagination next: ${sel}`);
      break;
    }
  }

  return selectors;
}

async function inspectFirstList(
  page: Page,
  browser: PropStreamBrowser,
  report: DOMInspectionReport,
  notes: string[]
): Promise<void> {
  // Try to find and click on the first list entry
  const clickCandidates = [
    'table tbody tr:first-child td:first-child',
    '[class*="list-item"]:first-child',
    '[class*="ListItem"]:first-child',
  ];

  for (const sel of clickCandidates) {
    try {
      const count = await page.locator(sel).count();
      if (count > 0) {
        await page.locator(sel).first().click();
        await sleep(2000);
        await browser.screenshot(page, "inspect-first-list-open");

        // Capture column headers inside the opened list
        const headers = await page.evaluate(() =>
          Array.from(document.querySelectorAll("th, [class*='header'] [class*='cell']"))
            .map((h) => h.textContent?.trim())
            .filter(Boolean)
        );
        if (headers.length > 0) {
          report.tableHeaders = headers as string[];
          notes.push(`Captured ${headers.length} column headers from open list`);
        }

        // Go back
        await page.goBack();
        await sleep(1500);
        break;
      }
    } catch {
      /* try next */
    }
  }
}

function buildDefaultSelectors(): DOMSelectors {
  return {
    // These are educated guesses; the inspector overrides them with live values
    listTableRows:       "table tbody tr",
    listTableHeaders:    "table thead th",
    paginationNext:      'button:has-text("Next")',
    paginationCurrent:   '[class*="current-page"], [aria-current="page"]',
    paginationTotal:     '[class*="total-pages"], [class*="page-count"]',
    listItemLinks:       'table tbody tr[data-id], table tbody tr',
    listSearchInput:     'input[type="search"], input[placeholder*="search" i]',
    noResultsIndicator:  ':has-text("No results"), :has-text("No records")',
  };
}

export function loadCachedSelectors(): DOMSelectors | null {
  if (!fs.existsSync(REPORT_PATH)) return null;
  try {
    const report: DOMInspectionReport = JSON.parse(fs.readFileSync(REPORT_PATH, "utf-8"));
    console.log(`[inspector] loaded cached selectors from ${REPORT_PATH}`);
    return report.selectors;
  } catch {
    return null;
  }
}
