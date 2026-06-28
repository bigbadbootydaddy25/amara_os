"""
BIRDDOG — AMARA's headless browser agent.
Wraps Playwright Chromium for web navigation, extraction, and form automation.

Usage (standalone):
    python birddog.py <url>

Usage (module):
    from birddog import Birddog
    async with Birddog() as dog:
        page = await dog.visit("https://example.com")
        text = await dog.extract_text(page)
        data = await dog.extract_dom(page)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Pre-installed Chromium binary — avoids the download on launch
_CHROMIUM_BIN = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
_CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--ignore-certificate-errors",
    "--disable-blink-features=AutomationControlled",
]
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3,4,5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {} };
const _origQuery = window.navigator.permissions?.query?.bind(navigator.permissions);
if (_origQuery) {
  navigator.permissions.query = p =>
    p.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : _origQuery(p);
}
"""


class Birddog:
    """Async context manager wrapping a stealth Playwright Chromium instance."""

    def __init__(self, headless: bool = True, timeout: int = 30_000) -> None:
        self.headless = headless
        self.timeout = timeout
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> "Birddog":
        self._pw = await async_playwright().start()
        executable = _CHROMIUM_BIN if Path(_CHROMIUM_BIN).exists() else None
        self._browser = await self._pw.chromium.launch(
            headless=self.headless,
            executable_path=executable,
            args=_CHROMIUM_ARGS,
        )
        self._context = await self._browser.new_context(
            ignore_https_errors=True,
            user_agent=_USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/Los_Angeles",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Upgrade-Insecure-Requests": "1",
            },
        )
        await self._context.add_init_script(_STEALTH_SCRIPT)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    # ------------------------------------------------------------------
    # Core navigation
    # ------------------------------------------------------------------

    async def new_page(self) -> Page:
        if self._context is None:
            raise RuntimeError("Birddog not started — use `async with Birddog()`")
        return await self._context.new_page()

    async def visit(self, url: str, wait: str = "domcontentloaded") -> Page:
        """Navigate to *url* and return the loaded Page."""
        page = await self.new_page()
        await page.goto(url, wait_until=wait, timeout=self.timeout)
        return page

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    async def extract_text(self, page: Page) -> str:
        return await page.inner_text("body").catch_value("") if hasattr(page, "catch_value") \
            else await page.inner_text("body")

    async def extract_dom(self, page: Page) -> dict[str, str]:
        """Pull labeled field values from spans, tables, and label[for] elements."""
        return await page.evaluate("""() => {
            const out = {};
            document.querySelectorAll('span[id], div[id]').forEach(el => {
                const raw = el.id
                    .replace(/ctl\\d+_ContentPlaceHolder\\d+_/gi, '')
                    .replace(/_/g, ' ').trim();
                const val = (el.innerText || '').trim();
                if (raw && val && val.length < 300 &&
                    !/^(btn|grd|lbl[Tt]itle|menu|nav|header)/i.test(raw))
                    out[raw] = val;
            });
            document.querySelectorAll('table tr').forEach(tr => {
                const cells = [...tr.querySelectorAll('td')];
                if (cells.length >= 2) {
                    const k = cells[0].innerText.trim().replace(/[:\\s]+$/, '');
                    const v = cells[1].innerText.trim();
                    if (k && v && k.length < 80 && v.length < 300) out[k] = v;
                }
            });
            document.querySelectorAll('label[for]').forEach(lbl => {
                const target = document.getElementById(lbl.getAttribute('for'));
                if (!target) return;
                const k = lbl.innerText.trim().replace(/:\\s*$/, '');
                const v = (target.innerText || target.value || '').trim();
                if (k && v) out[k] = v;
            });
            return out;
        }""")

    async def extract_links(self, page: Page, pattern: str = "") -> list[str]:
        """Return all href values on the page, optionally filtered by regex."""
        hrefs: list[str] = await page.evaluate(
            "() => [...document.querySelectorAll('a[href]')].map(a => a.href)"
        )
        if pattern:
            rx = re.compile(pattern, re.IGNORECASE)
            hrefs = [h for h in hrefs if rx.search(h)]
        return hrefs

    async def screenshot(self, page: Page, path: str, full_page: bool = True) -> None:
        await page.screenshot(path=path, full_page=full_page)

    # ------------------------------------------------------------------
    # Form helpers
    # ------------------------------------------------------------------

    async def fill_first_visible(
        self, page: Page, selectors: list[str], value: str
    ) -> str | None:
        """Try each selector; fill the first visible one. Returns matched selector."""
        for sel in selectors:
            el = page.locator(sel).first
            try:
                if await el.is_visible(timeout=1000):
                    await el.click(click_count=3)
                    await el.fill(value)
                    return sel
            except Exception:
                continue
        return None

    async def click_first_visible(
        self, page: Page, selectors: list[str]
    ) -> str | None:
        """Click the first visible element matching any selector."""
        for sel in selectors:
            el = page.locator(sel).first
            try:
                if await el.is_visible(timeout=800):
                    await el.click()
                    return sel
            except Exception:
                continue
        return None

    async def wait_for_idle(self, page: Page, timeout: int | None = None) -> None:
        await page.wait_for_load_state(
            "networkidle", timeout=timeout or self.timeout
        )

    # ------------------------------------------------------------------
    # Convenience: fetch page as structured data in one call
    # ------------------------------------------------------------------

    async def fetch(self, url: str) -> dict[str, Any]:
        """
        Navigate to *url* and return:
          { url, title, text, dom, links }
        """
        page = await self.visit(url)
        title = await page.title()
        text = await page.inner_text("body")
        dom = await self.extract_dom(page)
        links = await self.extract_links(page)
        await page.close()
        return {"url": page.url, "title": title, "text": text, "dom": dom, "links": links}


# ---------------------------------------------------------------------------
# CLI — python birddog.py <url>
# ---------------------------------------------------------------------------

async def _cli(url: str) -> None:
    async with Birddog() as dog:
        print(f"Fetching: {url}")
        result = await dog.fetch(url)
        print(f"TITLE  : {result['title']}")
        print(f"URL    : {result['url']}")
        print(f"TEXT   : {result['text'][:400].strip()}...")
        print(f"DOM    : {len(result['dom'])} fields")
        print(f"LINKS  : {len(result['links'])} found")
        if result["dom"]:
            print(json.dumps(result["dom"], indent=2)[:800])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python birddog.py <url>")
        sys.exit(1)
    asyncio.run(_cli(sys.argv[1]))
