// ─────────────────────────────────────────────────────────────────────────────
// Auth — PropStream login flow
// ─────────────────────────────────────────────────────────────────────────────

import type { Page } from "playwright";
import { sleep } from "./rate-limiter.js";
import type { PropStreamBrowser } from "./browser.js";

const LOGIN_URL = "https://app.propstream.com/login";
const POST_LOGIN_URL_FRAGMENT = "/dashboard";

export interface Credentials {
  email: string;
  password: string;
}

export async function login(
  page: Page,
  browser: PropStreamBrowser,
  creds: Credentials
): Promise<void> {
  console.log("[auth] navigating to login page...");
  await page.goto(LOGIN_URL, { waitUntil: "domcontentloaded", timeout: 30_000 });
  await sleep(1500);

  await browser.screenshot(page, "01-login-page");

  // Find email field — try multiple selector patterns
  const emailSelectors = [
    'input[type="email"]',
    'input[name="email"]',
    'input[name="username"]',
    'input[placeholder*="email" i]',
    'input[placeholder*="Email" i]',
    "#email",
    "#username",
  ];
  const passwordSelectors = [
    'input[type="password"]',
    'input[name="password"]',
    "#password",
  ];
  const submitSelectors = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Log In")',
    'button:has-text("Sign In")',
    'button:has-text("Login")',
  ];

  const emailField = await findFirst(page, emailSelectors, "email input");
  await emailField.click();
  await sleep(300);
  await emailField.fill(creds.email);
  await sleep(400);

  const passField = await findFirst(page, passwordSelectors, "password input");
  await passField.click();
  await sleep(300);
  await passField.fill(creds.password);
  await sleep(500);

  await browser.screenshot(page, "02-credentials-filled");

  const submitBtn = await findFirst(page, submitSelectors, "submit button");
  await submitBtn.click();

  // Wait for redirect away from login page
  try {
    await page.waitForURL(
      (url) => !url.pathname.includes("/login"),
      { timeout: 20_000 }
    );
  } catch {
    // Check if we hit an error message
    const errorText = await page.evaluate(() => {
      const el =
        document.querySelector('[class*="error"]') ||
        document.querySelector('[class*="alert"]') ||
        document.querySelector('[role="alert"]');
      return el?.textContent?.trim() ?? "";
    });
    if (errorText) {
      throw new Error(`Login failed: ${errorText}`);
    }
    // If no error but still on login, take screenshot and throw
    await browser.screenshot(page, "03-login-failed");
    throw new Error("Login redirect did not occur — check credentials or CAPTCHA");
  }

  await sleep(2000);
  await browser.screenshot(page, "04-post-login");
  console.log("[auth] logged in successfully. Current URL:", page.url());
}

async function findFirst(
  page: Page,
  selectors: string[],
  label: string
) {
  for (const sel of selectors) {
    try {
      const el = page.locator(sel).first();
      const count = await el.count();
      if (count > 0) return el;
    } catch {
      /* try next */
    }
  }
  throw new Error(
    `[auth] Could not locate ${label}. Tried: ${selectors.join(", ")}`
  );
}
