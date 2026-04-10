// ─────────────────────────────────────────────────────────────────────────────
// Browser — Playwright setup with stealth settings
// ─────────────────────────────────────────────────────────────────────────────

import { chromium, type Browser, type BrowserContext, type Page } from "playwright";
import * as path from "path";
import * as fs from "fs";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = path.resolve(__dirname, "../screenshots");
const USER_DATA_DIR  = path.resolve(__dirname, "../data/.browser-profile");

export interface BrowserConfig {
  headless: boolean;
  screenshotsEnabled: boolean;
  userDataDir?: string;
}

export const DEFAULT_BROWSER_CONFIG: BrowserConfig = {
  headless: true,
  screenshotsEnabled: true,
  userDataDir: USER_DATA_DIR,
};

export class PropStreamBrowser {
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private config: BrowserConfig;

  constructor(config: BrowserConfig = DEFAULT_BROWSER_CONFIG) {
    this.config = config;
    if (config.screenshotsEnabled) {
      fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
    }
    fs.mkdirSync(USER_DATA_DIR, { recursive: true });
  }

  async launch(): Promise<Page> {
    this.browser = await chromium.launch({
      headless: this.config.headless,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--disable-web-security",
        "--disable-features=VizDisplayCompositor",
        "--window-size=1440,900",
      ],
    });

    this.context = await this.browser.newContext({
      userAgent:
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      viewport: { width: 1440, height: 900 },
      locale: "en-US",
      timezoneId: "America/Chicago",
      // Persist cookies & session across runs
      storageState: this.getStorageStatePath(),
    });

    // Mask automation signals
    await this.context.addInitScript(() => {
      Object.defineProperty(navigator, "webdriver", { get: () => undefined });
      (window as any).chrome = { runtime: {} };
    });

    const page = await this.context.newPage();

    // Abort images/fonts to speed up scraping
    await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot}", (route) =>
      route.abort()
    );

    return page;
  }

  async screenshot(page: Page, name: string): Promise<void> {
    if (!this.config.screenshotsEnabled) return;
    const file = path.join(SCREENSHOT_DIR, `${name}-${Date.now()}.png`);
    await page.screenshot({ path: file, fullPage: false });
    console.log(`  [screenshot] saved: ${path.basename(file)}`);
  }

  async saveStorageState(): Promise<void> {
    if (!this.context) return;
    const statePath = this.getStorageStatePath();
    await this.context.storageState({ path: statePath });
    console.log("  [browser] session state saved");
  }

  async close(): Promise<void> {
    await this.saveStorageState();
    await this.context?.close();
    await this.browser?.close();
  }

  private getStorageStatePath(): string | undefined {
    const p = path.resolve(__dirname, "../data/.browser-state.json");
    return fs.existsSync(p) ? p : undefined;
  }
}
