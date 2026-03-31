"""
Playwright-based listing scraper for AMARA OS.

Targets: Redfin (public search), county MLS public portals, and any
source the operator has authorization to access. Zillow direct scraping
is NOT performed — use PropStream CSV export instead (see PropStream playbook).

Usage:
    from workers.remote.scraper import scrape_zip, ScrapeConfig
    listings = await scrape_zip("77008", config)
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

DISTRESS_KEYWORDS = [
    "as-is", "as is", "investor", "investors", "fixer", "fixer-upper",
    "tlc", "needs work", "repairs needed", "needs repairs", "estate",
    "estate sale", "probate", "inherited", "foreclosure", "pre-foreclosure",
    "preforeclosure", "short sale", "motivated", "motivated seller",
    "must sell", "opportunity", "cash only", "cash buyer", "potential",
    "rented", "tenant occupied", "do not disturb", "bring all offers",
    "priced to sell", "sold as-is", "handyman", "below market",
]

DOM_MINIMUM = 90


@dataclass
class ScrapeConfig:
    dom_min: int = DOM_MINIMUM
    price_min: int = 0
    price_max: int = 999_999
    max_pages: int = 5
    timeout_ms: int = 30_000
    headless: bool = True
    source: str = "redfin"    # "redfin" | "propstream_csv" | "county"
    retry_attempts: int = 3
    retry_delay_s: float = 2.0


@dataclass
class RawListing:
    address: str
    price: int
    beds: int
    baths: float
    sqft: int
    dom: int
    keywords: list[str]
    source: str
    url: str
    zip_code: str
    raw_description: str = ""


def _detect_keywords(text: str) -> list[str]:
    lower = text.lower()
    return [kw for kw in DISTRESS_KEYWORDS if kw in lower]


def _parse_price(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def _parse_sqft(text: str) -> int:
    m = re.search(r"([\d,]+)\s*sq", text, re.IGNORECASE)
    if m:
        return int(m.group(1).replace(",", ""))
    return 0


def _parse_dom(text: str) -> int:
    m = re.search(r"(\d+)\s*day", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 0


async def _scrape_redfin_zip(
    page,
    zip_code: str,
    config: ScrapeConfig,
) -> list[RawListing]:
    listings: list[RawListing] = []
    base_url = (
        f"https://www.redfin.com/zipcode/{zip_code}/filter/"
        f"min-price={config.price_min},"
        f"max-price={config.price_max},"
        f"min-days-on-market={config.dom_min}"
    )

    for page_num in range(1, config.max_pages + 1):
        url = base_url if page_num == 1 else f"{base_url}/page-{page_num}"
        logger.info("Scraping %s (page %d)", url, page_num)

        try:
            await page.goto(url, timeout=config.timeout_ms, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Scroll to trigger lazy-loaded cards
            for _ in range(3):
                await page.keyboard.press("End")
                await page.wait_for_timeout(800)

            cards = await page.query_selector_all('[data-rf-test-id="abp-homecard"]')
            if not cards:
                cards = await page.query_selector_all(".HomeCard")
            if not cards:
                logger.info("No cards found on page %d for ZIP %s", page_num, zip_code)
                break

            for card in cards:
                try:
                    raw = await card.inner_text()
                    link_el = await card.query_selector("a")
                    href = await link_el.get_attribute("href") if link_el else ""
                    card_url = f"https://www.redfin.com{href}" if href and href.startswith("/") else href or url

                    price_el = await card.query_selector('[data-rf-test-id="abp-price"],.homecardV2Price,.price')
                    price_text = await price_el.inner_text() if price_el else ""

                    address_el = await card.query_selector('[data-rf-test-id="abp-streetLine"],.homeAddressV2,.address')
                    address_text = await address_el.inner_text() if address_el else ""

                    stats_el = await card.query_selector('[data-rf-test-id="abp-homeStats"],.HomeStatsV2,.stats')
                    stats_text = await stats_el.inner_text() if stats_el else raw

                    dom_el = await card.query_selector('[data-rf-test-id="abp-daysOnMarket"],.daysOnMarket')
                    dom_text = await dom_el.inner_text() if dom_el else stats_text

                    beds = 0
                    baths = 0.0
                    bed_m = re.search(r"(\d+)\s*(?:bed|bd)", stats_text, re.IGNORECASE)
                    bath_m = re.search(r"([\d.]+)\s*(?:bath|ba)", stats_text, re.IGNORECASE)
                    if bed_m:
                        beds = int(bed_m.group(1))
                    if bath_m:
                        baths = float(bath_m.group(1))

                    price = _parse_price(price_text)
                    sqft = _parse_sqft(stats_text)
                    dom = _parse_dom(dom_text)
                    keywords = _detect_keywords(raw)

                    if not address_text or price == 0:
                        continue
                    if dom < config.dom_min:
                        continue

                    listings.append(RawListing(
                        address=address_text.strip(),
                        price=price,
                        beds=beds,
                        baths=baths,
                        sqft=sqft,
                        dom=dom,
                        keywords=keywords,
                        source="redfin",
                        url=card_url,
                        zip_code=zip_code,
                        raw_description=raw[:500],
                    ))
                except Exception as e:
                    logger.debug("Card parse error in ZIP %s: %s", zip_code, e)
                    continue

            # Stop paginating if we got fewer cards than expected (last page)
            if len(cards) < 10:
                break

        except Exception as e:
            logger.warning("Page load error ZIP %s page %d: %s", zip_code, page_num, e)
            break

    return listings


async def scrape_zip(
    zip_code: str,
    config: ScrapeConfig,
) -> list[RawListing]:
    """
    Scrape listings for a single ZIP code. Returns RawListing list.
    Retries up to config.retry_attempts times on failure.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")

    attempt = 0
    while attempt < config.retry_attempts:
        attempt += 1
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=config.headless)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 900},
                )
                page = await context.new_page()

                if config.source == "redfin":
                    results = await _scrape_redfin_zip(page, zip_code, config)
                else:
                    logger.warning("Unknown source '%s', skipping ZIP %s", config.source, zip_code)
                    results = []

                await browser.close()
                return results

        except Exception as e:
            logger.warning("scrape_zip attempt %d/%d failed for ZIP %s: %s",
                           attempt, config.retry_attempts, zip_code, e)
            if attempt < config.retry_attempts:
                await asyncio.sleep(config.retry_delay_s * attempt)

    logger.error("All scrape attempts failed for ZIP %s", zip_code)
    return []


async def scrape_zips_parallel(
    zip_codes: list[str],
    config: ScrapeConfig,
    concurrency: int = 3,
) -> list[RawListing]:
    """
    Scrape multiple ZIPs in parallel (bounded by concurrency).
    """
    semaphore = asyncio.Semaphore(concurrency)
    all_listings: list[RawListing] = []

    async def _bounded(zip_code: str) -> list[RawListing]:
        async with semaphore:
            return await scrape_zip(zip_code, config)

    tasks = [_bounded(z) for z in zip_codes]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            logger.warning("ZIP scrape failed: %s", result)
        elif isinstance(result, list):
            all_listings.extend(result)

    return all_listings
