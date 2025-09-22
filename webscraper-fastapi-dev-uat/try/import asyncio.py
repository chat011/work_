import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.DEBUG)


class HybridScraper:
    def __init__(self):
        self.logger = logging.getLogger("HybridScraper")

    def log(self, msg: str, level: str = "INFO"):
        if level == "DEBUG":
            self.logger.debug(msg)
        else:
            self.logger.info(msg)

    async def extract(self, url: str, max_pages: int = 3) -> List[Dict[str, Any]]:
        """Main hybrid extraction pipeline."""
        results = []

        # 1. Platform API
        platform_data = await self._extract_using_platform_api(url)
        if platform_data:
            results.append(platform_data)
            return results

        # 2. Structured data (JSON-LD / meta tags)
        structured = await self._extract_using_http_json(url)
        if structured:
            results.append(structured)
            return results

        # 3. Static HTML parsing
        html_data = await self._extract_using_http_html(url)
        if html_data:
            results.append(html_data)
            return results

        # 4. Browser fast (10s)
        browser_data = await self._extract_using_browser(url, 10)
        if browser_data:
            results.append(browser_data)
            return results

        # 5. Browser medium (15s)
        browser_data = await self._extract_using_browser(url, 15)
        if browser_data:
            results.append(browser_data)
            return results

        return results

    # ---------------- PLATFORM DETECTION ----------------

    async def _extract_using_platform_api(self, url: str) -> Optional[Dict[str, Any]]:
        """Probe for Shopify/WooCommerce and try platform-specific APIs."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                })
                html = resp.text if resp.status_code == 200 else ""
        except Exception as e:
            self.log(f"Platform probe failed for {url}: {e}", "DEBUG")
            html = ""

        lower = (html or "").lower()
        if 'cdn.shopify.com' in lower or 'shopify' in lower or '.myshopify.com' in lower:
            self.log(f"Detected Shopify platform for {url}", "DEBUG")
            result = await self._extract_shopify_api(url)
            if result:
                return result

        if 'woocommerce' in lower or 'wp-content/plugins/woocommerce' in lower:
            self.log(f"Detected WooCommerce platform for {url}", "DEBUG")
            result = await self._extract_woocommerce_api(url)
            if result:
                return result

        return None

    async def _extract_shopify_api(self, url: str) -> Optional[Dict[str, Any]]:
        """Try Shopify product JSON endpoint."""
        try:
            parsed = urlparse(url)
            path = parsed.path or ''
            m = re.search(r'/products/([^/?#]+)', path)
            if not m:
                return None

            handle = m.group(1)
            api_url = f"{parsed.scheme}://{parsed.netloc}/products/{handle}.json"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(api_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                })
                if resp.status_code != 200:
                    return None

                data = resp.json()
                product = data.get('product') or (data.get('products') and data['products'][0])
                if not product:
                    return None

                price = 0.0
                try:
                    if product.get('variants'):
                        price = float(product['variants'][0].get('price') or 0.0)
                except Exception:
                    price = 0.0

                images = []
                for img in product.get('images', []):
                    if isinstance(img, str):
                        images.append(img)
                    elif isinstance(img, dict):
                        images.append(img.get('src') or img.get('url'))

                return {
                    "product_name": product.get('title') or product.get('name', ''),
                    "price": price,
                    "product_images": images,
                    "description": product.get('body_html') or product.get('description', ''),
                    "metadata": {"platform": "shopify", "raw_api": True},
                    "extraction_method": "shopify_api",
                    "source_url": url
                }
        except Exception as e:
            self.log(f"Shopify API extraction error: {e}", "DEBUG")
            return None

    async def _extract_woocommerce_api(self, url: str) -> Optional[Dict[str, Any]]:
        """Placeholder: add WooCommerce REST API extraction if needed."""
        return None

    # ---------------- BROWSER EXTRACTION ----------------

    async def _extract_using_browser(self, url: str, timeout_seconds: int) -> Optional[Dict[str, Any]]:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True, args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                               '(KHTML, like Gecko) Chrome/120 Safari/537.36',
                    viewport={'width': 1280, 'height': 800}
                )
                page = await context.new_page()
                page.set_default_timeout(timeout_seconds * 1000)

                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)

                selectors = [
                    'script[type="application/ld+json"]',
                    '[itemprop="name"]',
                    'h1',
                    '.product',
                    '.product__title',
                    '.product-single__title',
                    '.ProductItem-details-title'
                ]
                for sel in selectors:
                    try:
                        await page.wait_for_selector(sel, timeout=2000)
                        break
                    except:
                        continue

                await asyncio.sleep(min(max(1, timeout_seconds // 6), 5))

                js_product = None
                try:
                    js_product = await page.evaluate("""() => {
                        try {
                            if (window.__INITIAL_STATE__) return window.__INITIAL_STATE__;
                            if (window.product) return window.product;
                            if (window.Shopify && window.Shopify.product) return window.Shopify.product;
                            return null;
                        } catch (e) { return null; }
                    }""")
                except Exception:
                    js_product = None

                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')

                if js_product and isinstance(js_product, dict):
                    name = js_product.get('title') or js_product.get('name', '')
                    price = 0.0
                    try:
                        if js_product.get('price'):
                            price = float(js_product['price'])
                        elif js_product.get('variants'):
                            price = float(js_product['variants'][0].get('price') or 0.0)
                    except Exception:
                        pass

                    images = []
                    if js_product.get('images'):
                        for x in js_product['images'][:20]:
                            if isinstance(x, str):
                                images.append(x)
                            elif isinstance(x, dict):
                                images.append(x.get('src') or x.get('url'))

                    await context.close()
                    await browser.close()
                    return {
                        "product_name": name,
                        "price": price,
                        "product_images": images,
                        "description": js_product.get('description', ''),
                        "extraction_method": f"browser_js_{timeout_seconds}s",
                        "source_url": url
                    }

                await context.close()
                await browser.close()
                return {
                    "product_name": self._extract_product_name_universal(soup),
                    "price": self._extract_price_universal(soup),
                    "product_images": self._extract_images_universal(soup, url),
                    "description": self._extract_description_universal(soup),
                    "extraction_method": f"browser_html_{timeout_seconds}s",
                    "source_url": url
                }

        except Exception as e:
            self.log(f"Browser extraction {timeout_seconds}s failed: {e}", "DEBUG")
            return None

    # ---------------- SIMPLE HTTP EXTRACTION ----------------

    async def _extract_using_http_json(self, url: str) -> Optional[Dict[str, Any]]:
        return None

    async def _extract_using_http_html(self, url: str) -> Optional[Dict[str, Any]]:
        return None

    # ---------------- UNIVERSAL HELPERS ----------------

    def _extract_product_name_universal(self, soup):
        h1 = soup.find("h1")
        return h1.get_text(strip=True) if h1 else ""

    def _extract_price_universal(self, soup):
        text = soup.get_text(" ")
        m = re.search(r'₹\s?(\d+)', text)
        if m:
            return float(m.group(1))
        return 0.0

    def _extract_images_universal(self, soup, base_url):
        images = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("http"):
                images.append(src)
        return images

    def _extract_description_universal(self, soup):
        p = soup.find("p")
        return p.get_text(strip=True) if p else ""
