"""
Enhanced Simple Web Scraper for E-commerce Products
Universal extraction that works with ALL e-commerce websites
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urljoin, urlparse
import re
import tenacity
import traceback2 as traceback

from playwright.async_api import async_playwright
from pydantic import HttpUrl
from bs4 import BeautifulSoup
import httpx
import re
import json
from selectolax.parser import HTMLParser


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UniversalProductScraper:
    """Enhanced universal scraper that works with any e-commerce site"""
    
    def __init__(self):
        # Universal selectors that work across most e-commerce platforms
        self.universal_selectors = {
            'product_name': [
                'h1', 'h1.product-title', 'h1.product__title', 'h1.entry-title',
                '[data-testid*="title"]', '[data-testid*="name"]',
                '.product-name', '.item-title', '.prod-title', '.title',
                '[itemProp="name"]', '[itemprop="name"]', 'title',
                '.product-single__title', '.ProductItem-details-title'
            ],
            'price': [
                '.price', '.current-price', '.sale-price', '.regular-price',
                '[data-price]', '[data-testid*="price"]',
                '.price-current', '.price-now', '.cost', '.amount',
                '.woocommerce-Price-amount', 'p.price', '.precio', '.prix',
                '[itemProp="price"]', '[itemprop="price"]', '.money',
                '.price__current', '.price-item--regular'
            ],
            'images': [
                '.product-gallery img', '.product-images img', '.gallery img',
                '.product-photos img', '.product-media img', '.main-image img',
                '.product__media img', '.woocommerce-product-gallery img',
                '[data-product-image] img', '.image img', '.photo img',
                'img[src*="product"]', 'img[alt*="product"]', '.thumb img'
            ],
            'description': [
                '.product-description', '.description', '.product__description',
                '.entry-content', '.product-details', '.rte', '.specs',
                '.woocommerce-product-details__short-description',
                '[data-product-description]', '.details', '.info'
            ],
            'product_links': [
                'a[href*="/product"]', 'a[href*="/item"]', 'a[href*="/p/"]',
                '.product-item a', '.product-card a', '.product a',
                '.woocommerce-loop-product__link', '.item a',
                '[data-product-url]', '.product-link', '.grid-product__link',
                '.product__media a', '.product-single__photos a'
            ]
        }

class SimpleProductScraper:
    """Enhanced simple product scraper using direct HTML parsing with universal support"""
    
    def __init__(self, log_callback: Optional[Callable] = None, progress_callback: Optional[Callable] = None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.universal_scraper = UniversalProductScraper()
        # ---------------- STOCK HELPERS ----------------
    def _extract_stock_from_jsonld(self, offers: dict) -> Optional[str]:
        """Extract stock availability from JSON-LD offers"""
        availability = offers.get("availability")
        if availability:
            availability = str(availability).lower()
            if "instock" in availability:
                return "InStock"
            if "outofstock" in availability:
                return "OutOfStock"
        return None

    def _extract_stock_from_html(self, soup) -> Optional[str]:
        """Extract stock info from HTML content"""
        selectors = [".availability", ".stock", "[data-stock]", ".product-availability"]
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True).lower()
                if "in stock" in text or "available" in text:
                    return "InStock"
                if "out of stock" in text or "unavailable" in text:
                    return "OutOfStock"
        return None

    def _extract_stock_from_js(self, product_data: dict) -> Optional[str]:
        """Extract stock availability from inline JS product data"""
        for key in ["availability", "inStock", "stock", "is_available", "outOfStock"]:
            if key in product_data:
                val = str(product_data[key]).lower()
                if val in ["true", "1", "yes", "instock", "available"]:
                    return "InStock"
                if val in ["false", "0", "no", "outofstock", "unavailable"]:
                    return "OutOfStock"
        return None

    def log(self, message: str, level: str = "INFO", details: Dict[str, Any] = None):
        """Enhanced logging"""
        timestamp = datetime.now().isoformat()
        
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "session_id": self.session_id,
            "details": details or {}
        }
        
        logger.info(f"[{level}] {message}")
        
        if self.log_callback:
            try:
                self.log_callback(log_entry)
            except Exception as e:
                logger.error(f"Error in log callback: {e}")
    
    def update_progress(self, stage: str, percentage: int, details: str = ""):
        """Update progress"""
        progress_data = {
            "stage": stage,
            "percentage": percentage,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id
        }
        
        self.log(f"Progress: {stage} ({percentage}%) - {details}", "PROGRESS", progress_data)
        
        if self.progress_callback:
            try:
                self.progress_callback(progress_data)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    async def extract_product_data_hybrid(self, url: str) -> Dict[str, Any]:
        """
            ENHANCED Universal hybrid method that works for ALL e-commerce sites
            Tries multiple approaches in order of speed and reliability
            """
            
        
        methods = [
            ("platform_api", self._extract_using_platform_api),
            ("structured_data", self._extract_using_structured_data), 
            ("static_html", self._extract_using_static_html),
            ("browser_fast", lambda u: self._extract_using_browser(u, 10)),
            ("browser_medium", lambda u: self._extract_using_browser(u, 15)),
            ("browser_slow", lambda u: self._extract_using_browser(u, 25)),
            ("browser_extended", lambda u: self._extract_using_browser_extended(u)),  # New extended method
            ("universal_fallback", self._extract_universal_fallback)
        ]
        
        for method_name, method in methods:
            try:
                self.log(f"Trying extraction method: {method_name} for {url}")
                result = await method(url)
                
                # Validate result quality - if price is 0, try next method
                if result and self._is_valid_product_data(result):
                    price = result.get("price", 0)
                    
                    # If price is 0 but other data is valid, log it but don't reject immediately
                    if price <= 0:
                        self.log(f"Method {method_name} returned valid data but price=0, continuing...", "DEBUG")
                        # Don't return yet - try next methods for better price extraction
                    else:
                        result["extraction_method"] = method_name
                        self.log(f"✅ Success with method: {method_name}, price: {price}")
                        return result
                        
            except Exception as e:
                self.log(f"Method {method_name} failed: {e}", "DEBUG")
                continue
        
        # If we get here, return the best result even if price is 0
        for method_name, method in reversed(methods):
            try:
                result = await method(url)
                if result and ("product_name" in result or "product_images" in result):
                    result["extraction_method"] = f"{method_name}_fallback"
                    result["price_extraction_issue"] = "Price may be loaded dynamically"
                    return result
            except:
                continue
        
        return self._create_error_result(url, "All extraction methods failed")
    async def _wait_for_price_elements(self, page, timeout_seconds: int) -> bool:
        """Wait specifically for price-related elements to load"""
        try:
            # Common price selectors to wait for
            price_selectors = [
                '.price', '.current-price', '.sale-price', '.regular-price',
                '.woocommerce-Price-amount', '.amount', '[data-price]',
                '.price .woocommerce-Price-amount.amount bdi'
            ]
            
            # Wait for any price element to appear
            for selector in price_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=10000)  # 10s max per selector
                    self.log(f"✅ Price element found with selector: {selector}")
                    return True
                except Exception as e:
                    continue
            
            # Fallback: Wait for any element containing currency symbols
            try:
                await page.wait_for_function(
                    """
                    () => {
                        const text = document.body.innerText;
                        return /[₹$€£]|\\b(?:rs|rupees|dollars|euros|pounds)\\b/i.test(text);
                    }
                    """, 
                    timeout=5000
                )
                self.log("✅ Currency symbol found in page text")
                return True
            except:
                pass
                
            self.log("⚠️ No price elements found after waiting")
            return False
            
        except Exception as e:
            self.log(f"Error waiting for price elements: {e}", "DEBUG")
            return False
    


    def _is_valid_product_data(self, data):
        """Check if extracted data is valid and meaningful"""
        if not data or not isinstance(data, dict):
            return False
        
        name = data.get("product_name", "")
        price = data.get("price", 0)
        images = data.get("product_images", [])
        
        # Must have a meaningful product name
        if not name or name in ["Unknown Product", "Error", "Extraction Failed", ""]:
            return False
        
        # Must have either price or images
        if price <= 0 and not images:
            return False
        
        # Name should be reasonably long
        if len(name.strip()) < 3:
            return False
        
        return True

    async def _extract_using_platform_api(self, url: str) -> Optional[Dict[str, Any]]:
        """Try platform-specific APIs (Shopify, WooCommerce)"""
        platform = self._get_platform(url)
        
        if platform == 'shopify':
            return await self._extract_shopify_api(url)
        elif platform == 'woocommerce':
            return await self._extract_woocommerce_api(url)
        
        return None
    
    async def _extract_shopify_api(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract from Shopify product JSON API"""
        try:
            # Convert product URL to JSON API endpoint
            if '/products/' in url:
                json_url = url.replace('/products/', '/products/').rstrip('/') + '.js'
            else:
                return None
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(json_url)
                if response.status_code == 200:
                    data = response.json()
                    
                    return {
                        "product_name": data.get('title', ''),
                        "price": float(data.get('price', 0)) / 100 if data.get('price') else 0.0,
                        "product_images": data.get('images', []),
                        "description": data.get('description', '') or data.get('body_html', ''),
                        "extraction_method": "shopify_api"
                    }
        except Exception as e:
            self.log(f"Shopify API extraction failed: {e}", "DEBUG")
        return None

    async def _extract_woocommerce_api(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract from WooCommerce REST API if available"""
        try:
            # Try to find WooCommerce REST API endpoint
            domain = urlparse(url).netloc
            # This is a simplified attempt - real implementation would need API keys
            api_url = f"https://{domain}/wp-json/wc/v3/products"
            
            # For now, return None to fall back to other methods
            # Full WooCommerce API integration would require authentication
            return None
        except Exception as e:
            self.log(f"WooCommerce API extraction failed: {e}", "DEBUG")
        return None
    
    async def _extract_using_structured_data(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract from JSON-LD, microdata, and JavaScript variables"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                if response.status_code != 200:
                    return None
                
                html = response.text
                
                # Try JSON-LD first
                jsonld_data = self._parse_jsonld(html)
                if jsonld_data:
                    jsonld_data["extraction_method"] = "jsonld_structured_data"
                    return jsonld_data
                
                # Try JavaScript variables
                js_data = self._parse_js_variables(html)
                if js_data:
                    js_data["extraction_method"] = "javascript_variables"
                    return js_data
                
                # Try meta tags as fallback
                meta_data = self._parse_meta_tags(html)
                if meta_data:
                    meta_data["extraction_method"] = "meta_tags"
                    return meta_data
                
        except Exception as e:
            self.log(f"Structured data extraction failed: {e}", "DEBUG")
        
        return None
    
    def _parse_jsonld(self, html: str) -> Optional[Dict[str, Any]]:
        """Parse JSON-LD structured data"""
        # Find all JSON-LD script tags
        pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            try:
                data = json.loads(match.strip())
                
                # Handle arrays
                if isinstance(data, list):
                    data = next((item for item in data if item.get('@type') == 'Product'), None)
                
                # Check if it's a product
                if data and data.get('@type') == 'Product':
                    offers = data.get('offers', {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    
                    return {
                        "product_name": data.get('name', ''),
                        "price": float(offers.get('price', 0)) if offers.get('price') else 0.0,
                        "product_images": self._extract_images_from_jsonld(data),
                        "description": data.get('description', ''),
                        "brand": data.get('brand', {}).get('name', '') if isinstance(data.get('brand'), dict) else str(data.get('brand', '')),
                        "in_stock": self._extract_stock_from_jsonld(offers),
                    }
            except (json.JSONDecodeError, AttributeError):
                continue
        
        return None
    async def _wait_for_price_with_retry(self, page) -> bool:
        """Multiple strategies to wait for price loading"""
        strategies = [
            # Strategy 1: Wait for specific price selectors
            lambda: page.wait_for_selector('.price, .amount, [data-price]', timeout=10000),
            
            # Strategy 2: Wait for any numeric content that looks like prices
            lambda: page.wait_for_function(
                """
                () => {
                    const elements = document.querySelectorAll('body *');
                    for (let el of elements) {
                        const text = el.textContent || '';
                        if (text.match(/[₹$€£]\\s*\\d+/)) return true;
                    }
                    return false;
                }
                """, timeout=10000
            ),
            
            # Strategy 3: Wait for specific WooCommerce price elements
            lambda: page.wait_for_selector('.woocommerce-Price-amount, .price bdi', timeout=10000),
            
            # Strategy 4: Scroll and wait (triggers lazy loading)
            lambda: page.evaluate("""async () => {
                window.scrollTo(0, 300);
                await new Promise(resolve => setTimeout(resolve, 2000));
            }""")
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                await strategy()
                self.log(f"✅ Price loading strategy {i+1} successful")
                return True
            except Exception as e:
                self.log(f"Price strategy {i+1} failed: {e}", "DEBUG")
                continue
        
        return False
    async def _extract_using_browser_extended(self, url: str) -> Optional[Dict[str, Any]]:
        """Extended browser extraction with longer waits and price-specific retries"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    # Longer timeouts for difficult pages
                    page.set_default_timeout(45000)  # 45 seconds
                    page.set_default_navigation_timeout(45000)
                    
                    # Navigate and wait for load
                    await page.goto(url, wait_until="networkidle", timeout=45000)
                    
                    # Multiple strategies to ensure prices are loaded
                    price_found = await self._wait_for_price_with_retry(page)
                    
                    # Final content extraction
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    result = {
                        "product_name": self._extract_product_name_universal(soup),
                        "price": self._extract_price_universal(soup),
                        "product_images": self._extract_images_universal(soup, url),
                        "description": self._extract_description_universal(soup),
                        "extraction_method": "browser_extended",
                        "in_stock": self._extract_stock_from_html(soup),
                    }
                    
                    return result
                    
                finally:
                    await browser.close()
        except Exception as e:
            self.log(f"Extended browser extraction failed: {e}", "DEBUG")
            return None
    def _extract_images_from_jsonld(self, data: Dict[str, Any]) -> List[str]:
        """Extract images from JSON-LD data"""
        images = []
        
        # Handle different image formats in JSON-LD
        image_fields = ['image', 'images', 'photo', 'photos']
        
        for field in image_fields:
            if field in data:
                images_data = data[field]
                
                if isinstance(images_data, str):
                    images.append(images_data)
                elif isinstance(images_data, list):
                    for img in images_data:
                        if isinstance(img, str):
                            images.append(img)
                        elif isinstance(img, dict) and 'url' in img:
                            images.append(img['url'])
                elif isinstance(images_data, dict) and 'url' in images_data:
                    images.append(images_data['url'])
        
        return images
    
    def _parse_js_variables(self, html: str) -> Optional[Dict[str, Any]]:
        """Parse JavaScript variables containing product data"""
        # Common JavaScript variable patterns
        patterns = [
            r'window\.product\s*=\s*({.*?});',
            r'var\s+product\s*=\s*({.*?});',
            r'window\.productData\s*=\s*({.*?});',
            r'dataLayer\.push\(\s*({.*?"ecommerce".*?})\s*\);',
            r'"product"\s*:\s*({.*?})',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    
                    # Handle different data structures
                    product_data = None
                    if data.get('title') or data.get('name'):
                        product_data = data
                    elif data.get('ecommerce', {}).get('detail', {}).get('products'):
                        product_data = data['ecommerce']['detail']['products'][0]
                    
                    if product_data:
                        return {
                            "product_name": product_data.get('title') or product_data.get('name', ''),
                            "price": self._parse_price_from_js(product_data),
                            "product_images": self._extract_images_from_js(product_data),
                            "description": product_data.get('description', '') or product_data.get('body_html', ''),
                        }
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return None

    def _parse_price_from_js(self, product_data: Dict[str, Any]) -> float:
        """Parse price from JavaScript product data"""
        price = 0.0
        
        # Try different price field names
        price_fields = ['price', 'current_price', 'regular_price', 'sale_price', 'amount', 'value']
        
        for field in price_fields:
            if field in product_data:
                try:
                    price_val = product_data[field]
                    if isinstance(price_val, (int, float)):
                        return float(price_val)
                    elif isinstance(price_val, str):
                        return self._parse_price_universal(price_val)
                except (ValueError, TypeError):
                    continue
        
        # Try nested price structures
        if 'pricing' in product_data and isinstance(product_data['pricing'], dict):
            return self._parse_price_from_js(product_data['pricing'])
        
        if 'price_range' in product_data and isinstance(product_data['price_range'], dict):
            min_price = product_data['price_range'].get('min_price')
            if min_price:
                return self._parse_price_from_js({'price': min_price})
        
        return 0.0

    def _extract_images_from_js(self, product_data: Dict[str, Any]) -> List[str]:
        """Extract images from JavaScript product data"""
        images = []
        
        # Try different image field names
        image_fields = ['images', 'image', 'photos', 'photo', 'media', 'media_gallery']
        
        for field in image_fields:
            if field in product_data:
                images_data = product_data[field]
                
                if isinstance(images_data, str):
                    images.append(images_data)
                elif isinstance(images_data, list):
                    for img in images_data:
                        if isinstance(img, str):
                            images.append(img)
                        elif isinstance(img, dict):
                            # Try various URL fields
                            for url_field in ['url', 'src', 'source', 'link', 'href']:
                                if url_field in img:
                                    images.append(img[url_field])
                                    break
        
        return images

    def _parse_meta_tags(self, html: str) -> Optional[Dict[str, Any]]:
        """Parse meta tags for product information"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract from Open Graph tags
        og_title = soup.find('meta', property='og:title')
        og_price = soup.find('meta', property='product:price:amount')
        og_image = soup.find('meta', property='og:image')
        og_description = soup.find('meta', property='og:description')
        
        # Extract from standard meta tags
        meta_title = soup.find('meta', {'name': 'title'})
        meta_description = soup.find('meta', {'name': 'description'})
        
        # Build result
        result = {}
        
        if og_title:
            result['product_name'] = og_title.get('content', '')
        elif meta_title:
            result['product_name'] = meta_title.get('content', '')
        
        if og_price:
            try:
                result['price'] = float(og_price.get('content', 0))
            except ValueError:
                result['price'] = 0.0
        
        if og_image:
            result['product_images'] = [og_image.get('content', '')]
        
        if og_description:
            result['description'] = og_description.get('content', '')
        elif meta_description:
            result['description'] = meta_description.get('content', '')
        
        # Only return if we found meaningful data
        if result.get('product_name') and result.get('product_name') != 'Unknown Product':
            return result
        
        return None
    #_extract_price_from_nested_spans method
    def _extract_price_from_nested_spans(self, soup: BeautifulSoup) -> float:
        """Extract price from deeply nested span structures like WooCommerce with supercape.in specific handling"""
        
        # SUPERCAPE.IN SPECIFIC SELECTORS FIRST
        supercape_selectors = [
            '.price .woocommerce-Price-amount.amount bdi',
            '.etheme-product-grid-content .price .woocommerce-Price-amount.amount bdi',
            '.woocommerce-Price-amount.amount bdi',
            '.price bdi',
        ]
        
        # Debug: Print what we're working with
        self.log(f"DEBUG: Looking for price elements...")
        
        for i, selector in enumerate(supercape_selectors, 1):
            try:
                elements = soup.select(selector)
                self.log(f"DEBUG: Selector {i} '{selector}': found {len(elements)} elements")
                
                for j, element in enumerate(elements):
                    # Get the raw text
                    raw_text = element.get_text(strip=True)
                    self.log(f"DEBUG: Element {j+1} raw text: '{raw_text}'")
                    
                    if raw_text:
                        # Parse the price
                        price = self._parse_price_universal(raw_text)
                        self.log(f"DEBUG: Parsed price: {price}")
                        
                        if price > 0:
                            self.log(f"SUCCESS: Extracted price {price} using selector '{selector}'")
                            return price
                            
            except Exception as e:
                self.log(f"DEBUG: Error with selector '{selector}': {e}")
                continue
        
        # FALLBACK: Try more generic selectors
        fallback_selectors = [
            '.price .amount',
            '.price',
            '.woocommerce-Price-amount',
            '[class*="price"]',
            '.amount'
        ]
        
        self.log(f"DEBUG: Trying fallback selectors...")
        
        for i, selector in enumerate(fallback_selectors, 1):
            try:
                elements = soup.select(selector)
                self.log(f"DEBUG: Fallback selector {i} '{selector}': found {len(elements)} elements")
                
                for j, element in enumerate(elements):
                    raw_text = element.get_text(strip=True)
                    self.log(f"DEBUG: Fallback element {j+1} text: '{raw_text}'")
                    
                    if raw_text and ('₹' in raw_text or 'rs' in raw_text.lower() or any(c.isdigit() for c in raw_text)):
                        price = self._parse_price_universal(raw_text)
                        self.log(f"DEBUG: Fallback parsed price: {price}")
                        
                        if price > 0:
                            self.log(f"SUCCESS: Extracted price {price} using fallback selector '{selector}'")
                            return price
                            
            except Exception as e:
                self.log(f"DEBUG: Error with fallback selector '{selector}': {e}")
                continue
        
        self.log(f"DEBUG: No price found with any selector")
        return 0.0
    async def _extract_using_static_html(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract from static HTML using universal selectors"""
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    return {
                        "product_name": self._extract_product_name_universal(soup),
                        "price": self._extract_price_universal(soup),
                        "product_images": self._extract_images_universal(soup, url),
                        "description": self._extract_description_universal(soup),
                        "extraction_method": "static_html_parsing",
                        "in_stock": self._extract_stock_from_html(soup),
                    }
        except Exception as e:
            self.log(f"Static HTML extraction failed: {e}", "DEBUG")
        
        return None
    
    def _extract_product_name_universal(self, soup: BeautifulSoup) -> str:
        """Extract product name using universal selectors"""
        for selector in self.universal_scraper.universal_selectors['product_name']:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text and len(text) > 2:
                    return self._fix_duplicate_title(text)
        
        # Fallback to page title
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True).split('|')[0].strip()
        
        return "Unknown Product"
    
    

    # Update your existing _extract_price_universal method 
    # (Find this method in your code and replace it with this version)
    def _extract_price_universal(self, soup: BeautifulSoup) -> float:
        """Extract price using universal selectors with enhanced supercape.in support"""
        
        self.log(f"DEBUG: Starting price extraction")
        
        # FIRST: Try supercape-specific nested extraction
        nested_price = self._extract_price_from_nested_spans(soup)
        if nested_price > 0:
            self.log(f"SUCCESS: Got price from nested spans: {nested_price}")
            return nested_price
        
        self.log(f"DEBUG: Nested spans failed, trying universal selectors")
        
        # SECOND: Try universal selectors
        for i, selector in enumerate(self.universal_scraper.universal_selectors['price'], 1):
            try:
                elements = soup.select(selector)
                self.log(f"DEBUG: Universal selector {i} '{selector}': {len(elements)} elements")
                
                for j, element in enumerate(elements):
                    price_text = element.get_text(strip=True)
                    self.log(f"DEBUG: Universal element {j+1} text: '{price_text}'")
                    
                    if price_text:
                        price = self._parse_price_universal(price_text)
                        if price > 0:
                            self.log(f"SUCCESS: Got price from universal selector: {price}")
                            return price
            except Exception as e:
                self.log(f"DEBUG: Error with universal selector '{selector}': {e}")
                continue
        
        self.log(f"DEBUG: All price extraction methods failed")
        return 0.0
    def _parse_price_universal(self, price_text: str) -> float:
        """Enhanced universal price parser with better Indian Rupee handling"""
        if not price_text:
            self.log(f"DEBUG: Empty price text")
            return 0.0
        
        self.log(f"DEBUG: Parsing price text: '{price_text}'")
        
        import re
        
        # Step 1: Remove currency symbols and clean
        # Handle Indian Rupee symbol specifically
        cleaned = price_text
        
        # Remove various currency symbols
        currency_symbols = ['₹', '$', '€', '£', '¥', '¢', '₨', '₩', '₪', 'Rs', 'rs', 'INR', 'inr']
        for symbol in currency_symbols:
            cleaned = cleaned.replace(symbol, '')
        
        # Remove currency words
        cleaned = re.sub(r'\b(rupees?|dollars?|euros?|pounds?)\b', '', cleaned, flags=re.IGNORECASE)
        
        # Keep only digits, dots, commas, and spaces
        cleaned = re.sub(r'[^\d.,\s]', '', cleaned)
        cleaned = cleaned.strip()
        
        self.log(f"DEBUG: After cleaning: '{cleaned}'")
        
        if not cleaned:
            self.log(f"DEBUG: No digits found after cleaning")
            return 0.0
        
        # Step 2: Handle different number formats
        try:
            # Remove spaces
            cleaned = cleaned.replace(' ', '')
            
            # Case 1: Has both comma and dot
            if ',' in cleaned and '.' in cleaned:
                # Find last comma and dot positions
                last_comma = cleaned.rfind(',')
                last_dot = cleaned.rfind('.')
                
                if last_comma > last_dot:
                    # Comma is decimal (1.234,56 format)
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    # Dot is decimal (1,234.56 format)  
                    cleaned = cleaned.replace(',', '')
            
            # Case 2: Only comma
            elif ',' in cleaned:
                parts = cleaned.split(',')
                if len(parts) == 2 and len(parts[1]) <= 2:
                    # Decimal comma (499,00)
                    cleaned = cleaned.replace(',', '.')
                else:
                    # Thousands separator (1,000)
                    cleaned = cleaned.replace(',', '')
            
            # Case 3: Only dots or plain number - use as is
            
            self.log(f"DEBUG: Final cleaned for conversion: '{cleaned}'")
            
            result = float(cleaned)
            self.log(f"DEBUG: Successfully converted to float: {result}")
            return result
            
        except ValueError as e:
            self.log(f"DEBUG: Float conversion failed: {e}")
            
            # Last resort: extract first sequence of digits
            digits = re.findall(r'\d+', cleaned)
            if digits:
                try:
                    result = float(digits[0])
                    self.log(f"DEBUG: Fallback extraction: {result}")
                    return result
                except ValueError:
                    pass
            
            self.log(f"DEBUG: All parsing attempts failed")
            return 0.0
    def _extract_images_universal(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract product images using universal selectors"""
        images = []
        
        for selector in self.universal_scraper.universal_selectors['images']:
            elements = soup.select(selector)
            for img in elements:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-large_image')
                if src:
                    # Convert relative URLs to absolute
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = urljoin(base_url, src)
                    
                    if src not in images and src.startswith('http'):
                        images.append(src)
        
        return images[:20]  # Limit to 20 images

    def _extract_description_universal(self, soup: BeautifulSoup) -> str:
        """Extract product description using universal selectors"""
        for selector in self.universal_scraper.universal_selectors['description']:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text and len(text) > 10:  # Ensure it's meaningful content
                    return text[:2000]  # Limit length
        
        # Fallback to meta description
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc.get('content')[:1000]
        
        return ""
    
    async def _extract_using_browser(self, url: str, timeout_seconds: int) -> Optional[Dict[str, Any]]:
        """Browser extraction with price-specific waiting"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    # Set timeouts
                    page.set_default_timeout(timeout_seconds * 1000)
                    page.set_default_navigation_timeout(timeout_seconds * 1000)
                    
                    # Load page
                    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
                    
                    # Wait specifically for price elements to load
                    price_found = await self._wait_for_price_elements(page, timeout_seconds)
                    
                    if not price_found:
                        # If no price found, wait for network to be idle
                        try:
                            await page.wait_for_load_state("networkidle", timeout=5000)
                        except:
                            pass
                    
                    # Additional wait for dynamic content
                    await asyncio.sleep(2)
                    
                    # Get content and parse
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    return {
                        "product_name": self._extract_product_name_universal(soup),
                        "price": self._extract_price_universal(soup),
                        "product_images": self._extract_images_universal(soup, url),
                        "description": self._extract_description_universal(soup),
                        "extraction_method": f"browser_{timeout_seconds}s_timeout",
                        "in_stock": self._extract_stock_from_html(soup),
                        "price_wait_successful": price_found  # Debug info
                    }
                    
                finally:
                    await browser.close()
        except Exception as e:
            self.log(f"Browser extraction with {timeout_seconds}s failed: {e}", "DEBUG")
            return None
    async def _extract_universal_fallback(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Universal fallback extraction for any website
        Uses the most generic selectors and techniques
        """
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                })
                
                if response.status_code != 200:
                    return None
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract using most universal methods possible
                product_name = self._extract_name_universal_fallback(soup)
                price = self._extract_price_universal_fallback(soup)
                images = self._extract_images_universal_fallback(soup, url)
                description = self._extract_description_universal_fallback(soup)
                
                return {
                    "product_name": product_name,
                    "price": price,
                    "product_images": images,
                    "description": description,
                    "extraction_method": "universal_fallback",
                    "in_stock": self._extract_stock_from_html(soup),

                }
                
        except Exception as e:
            self.log(f"Universal fallback failed: {e}", "ERROR")
            return None

    def _extract_name_universal_fallback(self, soup: BeautifulSoup) -> str:
        """Extract product name using the most universal methods"""
        
        # Try in order of reliability
        strategies = [
            # Strategy 1: Most common heading tags
            lambda: self._try_selectors(soup, ['h1', 'h2.product-title', '.product-name h1', '.title h1']),
            
            # Strategy 2: Common product title classes
            lambda: self._try_selectors(soup, ['.product-title', '.product-name', '.item-title', '.prod-title']),
            
            # Strategy 3: Data attributes
            lambda: self._try_selectors(soup, ['[data-product-title]', '[data-title]', '[data-name]']),
            
            # Strategy 4: Microdata
            lambda: self._try_selectors(soup, ['[itemprop="name"]', '[itemscope] [itemprop="name"]']),
            
            # Strategy 5: Any heading that looks like a product
            lambda: self._extract_likely_product_heading(soup),
            
            # Strategy 6: Page title cleanup
            lambda: self._extract_from_page_title(soup)
        ]
        
        for strategy in strategies:
            try:
                result = strategy()
                if result and len(result.strip()) > 2:
                    return self._clean_product_name(result)
            except:
                continue
        
        return "Unknown Product"

    def _try_selectors(self, soup: BeautifulSoup, selectors: List[str]) -> str:
        """Try a list of selectors and return first meaningful result"""
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if text and len(text) > 2:
                        return text
            except:
                continue
        return ""

    def _extract_likely_product_heading(self, soup: BeautifulSoup) -> str:
        """Find headings that are likely to be product names"""
        headings = soup.find_all(['h1', 'h2', 'h3'])
        
        for heading in headings:
            text = heading.get_text(strip=True)
            if text and len(text) > 5 and len(text) < 200:
                # Check if it looks like a product name (has product-related keywords or is prominent)
                parent_classes = ' '.join(heading.parent.get('class', []) if heading.parent else [])
                heading_classes = ' '.join(heading.get('class', []))
                combined_classes = (parent_classes + ' ' + heading_classes).lower()
                
                # If heading has product-related classes or is an h1, it's likely the product name
                if any(keyword in combined_classes for keyword in ['product', 'item', 'title', 'name']) or heading.name == 'h1':
                    return text
        
        return ""

    def _extract_from_page_title(self, soup: BeautifulSoup) -> str:
        """Extract product name from page title"""
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Clean up title (remove site name, etc.)
            parts = title.split('|')
            if len(parts) > 1:
                return parts[0].strip()
            parts = title.split(' - ')
            if len(parts) > 1:
                return parts[0].strip()
            return title
        return ""

    def _clean_product_name(self, name: str) -> str:
        """Clean and fix product name"""
        if not name:
            return name
        
        # Fix duplicate names (common issue)
        name = self._fix_duplicate_title(name)
        
        # Remove excessive whitespace
        name = ' '.join(name.split())
        
        # Remove common prefixes/suffixes
        prefixes_to_remove = ['product:', 'item:', 'buy ', 'shop ']
        suffixes_to_remove = [' | buy online', ' - buy now', ' online']
        
        name_lower = name.lower()
        for prefix in prefixes_to_remove:
            if name_lower.startswith(prefix):
                name = name[len(prefix):].strip()
                break
        
        for suffix in suffixes_to_remove:
            if name_lower.endswith(suffix):
                name = name[:-len(suffix)].strip()
                break
        
        return name

    def _extract_price_universal_fallback(self, soup: BeautifulSoup) -> float:
        """Extract price using universal fallback methods"""
        
        # Try multiple strategies
        strategies = [
            # Strategy 1: Most common price selectors
            lambda: self._try_price_selectors(soup, [
                '.price', '.current-price', '.sale-price', '.cost', '.amount', '.money'
            ]),
            
            # Strategy 2: Data attributes
            lambda: self._try_price_selectors(soup, ['[data-price]', '[data-cost]', '[data-amount]']),
            
            # Strategy 3: Microdata
            lambda: self._try_price_selectors(soup, ['[itemprop="price"]', '[itemProp="price"]']),
            
            # Strategy 4: Text search for currency patterns
            lambda: self._find_price_in_text(soup),
            
            # Strategy 5: Meta tags
            lambda: self._extract_price_from_meta(soup)
        ]
        
        for strategy in strategies:
            try:
                price = strategy()
                if price and price > 0:
                    return price
            except:
                continue
        
        return 0.0

    def _try_price_selectors(self, soup: BeautifulSoup, selectors: List[str]) -> float:
        """Try price selectors and return first valid price"""
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    price_text = element.get_text(strip=True)
                    price = self._parse_price_universal(price_text)
                    if price > 0:
                        return price
            except:
                continue
        return 0.0

    def _find_price_in_text(self, soup: BeautifulSoup) -> float:
        """Find price patterns in the page text"""
        # Look for currency symbols followed by numbers
        text = soup.get_text()
        
        # Currency patterns (₹, $, €, £, etc.)
        currency_patterns = [
            r'₹\s*(\d+(?:[,.]?\d+)*)',  # Indian Rupee
            r'\$\s*(\d+(?:[,.]?\d+)*)',  # Dollar
            r'€\s*(\d+(?:[,.]?\d+)*)',   # Euro
            r'£\s*(\d+(?:[,.]?\d+)*)',   # Pound
            r'(\d+(?:[,.]?\d+)*)\s*(?:rs|rupees|dollars|euros|pounds)',  # Word-based
            r'price[:\s]*(\d+(?:[,.]?\d+)*)',  # Price: 123
            r'cost[:\s]*(\d+(?:[,.]?\d+)*)'    # Cost: 123
        ]
        
        for pattern in currency_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    price = self._parse_price_universal(match)
                    if price > 0:
                        return price
                except:
                    continue
        
        return 0.0

    def _extract_price_from_meta(self, soup: BeautifulSoup) -> float:
        """Extract price from meta tags"""
        meta_selectors = [
            'meta[property="product:price:amount"]',
            'meta[name="price"]',
            'meta[property="og:price:amount"]'
        ]
        
        for selector in meta_selectors:
            meta = soup.select_one(selector)
            if meta:
                content = meta.get('content', '')
                price = self._parse_price_universal(content)
                if price > 0:
                    return price
        
        return 0.0

    def _extract_images_universal_fallback(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract images using universal fallback methods"""
        images = []
        
        # Strategy 1: Look for any img tags in likely product areas
        likely_containers = soup.select('div, section, article, main')
        
        for container in likely_containers:
            # Check if container has product-related classes or many images
            container_class = ' '.join(container.get('class', [])).lower()
            container_id = container.get('id', '').lower()
            
            # Skip navigation, footer, header areas
            if any(skip in container_class + container_id for skip in 
                   ['nav', 'menu', 'footer', 'header', 'sidebar', 'breadcrumb']):
                continue
            
            # Find images in this container
            imgs = container.find_all('img')
            for img in imgs:
                src = (img.get('src') or img.get('data-src') or 
                      img.get('data-lazy-src') or img.get('data-original'))
                
                if src:
                    # Process and validate image URL
                    processed_url = self._process_image_url(src, base_url)
                    if processed_url and processed_url not in images:
                        # Filter out likely non-product images
                        if not self._is_likely_non_product_image(processed_url, img):
                            images.append(processed_url)
        
        # Strategy 2: Look for images with product-related attributes
        product_imgs = soup.select('img[alt*="product"], img[alt*="item"], img[src*="product"]')
        for img in product_imgs:
            src = img.get('src') or img.get('data-src')
            if src:
                processed_url = self._process_image_url(src, base_url)
                if processed_url and processed_url not in images:
                    images.append(processed_url)
        
        return images[:15]  # Limit to prevent too many images

    def _is_likely_non_product_image(self, url: str, img_element) -> bool:
        """Check if image is likely not a product image"""
        url_lower = url.lower()
        alt_text = (img_element.get('alt') or '').lower()
        
        # Skip common non-product images
        skip_patterns = [
            'logo', 'banner', 'icon', 'arrow', 'button', 'bg', 'background',
            'social', 'payment', 'shipping', 'footer', 'header', 'nav'
        ]
        
        for pattern in skip_patterns:
            if pattern in url_lower or pattern in alt_text:
                return True
        
        # Check image dimensions if available
        width = img_element.get('width')
        height = img_element.get('height')
        if width and height:
            try:
                w, h = int(width), int(height)
                # Skip very small images (likely icons)
                if w < 50 or h < 50:
                    return True
                # Skip very wide/thin images (likely banners)
                if w > h * 4 or h > w * 4:
                    return True
            except ValueError:
                pass
        
        return False

    def _process_image_url(self, src: str, base_url: str) -> str:
        """Process and clean image URL"""
        if not src:
            return None
        
        # Convert relative URLs to absolute
        if src.startswith('//'):
            src = 'https:' + src
        elif src.startswith('/'):
            from urllib.parse import urljoin
            src = urljoin(base_url, src)
        
        # Validate URL format and length
        if src.startswith('http') and len(src) < 500:
            return src
        
        return None

    def _extract_description_universal_fallback(self, soup: BeautifulSoup) -> str:
        """Extract description using universal fallback methods"""
        
        # Try multiple strategies
        strategies = [
            # Strategy 1: Common description selectors
            lambda: self._try_description_selectors(soup, [
                '.description', '.product-description', '.details', '.content',
                '.info', '.about', '.summary', '.overview'
            ]),
            
            # Strategy 2: Data attributes and microdata
            lambda: self._try_description_selectors(soup, [
                '[data-description]', '[itemprop="description"]', '[data-content]'
            ]),
            
            # Strategy 3: Find paragraphs in likely content areas
            lambda: self._extract_description_from_paragraphs(soup),
            
            # Strategy 4: Meta description as fallback
            lambda: self._extract_description_from_meta(soup)
        ]
        
        for strategy in strategies:
            try:
                desc = strategy()
                if desc and len(desc.strip()) > 20:  # Meaningful description
                    return desc.strip()[:2000]  # Limit length
            except:
                continue
        
        return ""

    def _try_description_selectors(self, soup: BeautifulSoup, selectors: List[str]) -> str:
        """Try description selectors and return first meaningful result"""
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if text and len(text) > 20:
                        return text
            except:
                continue
        return ""

    def _extract_description_from_paragraphs(self, soup: BeautifulSoup) -> str:
        """Extract description from paragraphs in content areas"""
        # Look for paragraphs in main content areas
        content_areas = soup.select('main, article, .content, .main, section')
        
        for area in content_areas:
            paragraphs = area.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 50 and len(text) < 1000:  # Reasonable description length
                    # Skip if it looks like navigation or boilerplate
                    text_lower = text.lower()
                    if not any(skip in text_lower for skip in 
                              ['click here', 'read more', 'terms', 'privacy', 'cookie']):
                        return text
        
        return ""

    def _extract_description_from_meta(self, soup: BeautifulSoup) -> str:
        """Extract description from meta tags"""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc.get('content')
        
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            return og_desc.get('content')
        
        return ""

    def _get_platform(self, url: str) -> str:
        """Enhanced platform detection from URL"""
        domain = urlparse(url).netloc.lower()
        
        # Check for known platforms
        if any(pattern in domain for pattern in ['shopify', 'myshopify']):
            return 'shopify'
        elif any(pattern in domain for pattern in ['woocommerce']):
            return 'woocommerce'
        elif 'alayacotton' in domain:
            return 'shopify'  # Alaya Cotton uses Shopify
        elif 'deashaindia' in domain:
            return 'shopify'  # Deasha India uses Shopify
        elif 'ajmerachandanichowk' in domain:
            return 'woocommerce'  # Ajmera uses WooCommerce
        else:
            # Use 'universal' instead of defaulting to domain
            return 'universal'
    
    def _get_brand(self, url: str) -> str:
        """Get brand name from URL"""
        domain = urlparse(url).netloc.lower()
        if 'deashaindia.com' in domain:
            return 'Deasha India'
        elif 'ajmerachandanichowk.com' in domain:
            return 'Ajmera Chandani Chowk'
        elif 'alayacotton' in domain:
            return 'Alaya Cotton'
        else:
            # Extract brand from domain name
            domain_parts = domain.replace('www.', '').split('.')
            if domain_parts:
                return domain_parts[0].replace('-', ' ').title()
            return domain

    def _fix_duplicate_title(self, title: str) -> str:
        """Fix duplicated product titles"""
        if not title:
            return title
        
        # Check for exact duplication (like "NAMENAME")
        length = len(title)
        if length % 2 == 0:
            mid = length // 2
            first_half = title[:mid]
            second_half = title[mid:]
            if first_half == second_half:
                return first_half
        
        # Check for word-level duplication
        words = title.split()
        if len(words) % 2 == 0 and len(words) > 1:
            mid = len(words) // 2
            first_half = ' '.join(words[:mid])
            second_half = ' '.join(words[mid:])
            if first_half == second_half:
                return first_half
        
        return title

    # ENHANCED COLLECTION AND URL EXTRACTION METHODS

    def is_collection_url(self, url: str) -> bool:
        """Enhanced collection URL detection that works for all websites"""
        url_lower = url.lower()
        
        # Definitive collection patterns
        collection_patterns = [
            '/collections/', '/collection/', '/category/', '/categories/',
            '/product-category/', '/shop/', '/store/', '/browse/',
            '/all-products/', '/products', '/items/', '/catalog/',
            '/c/', '/cat/', '/department/', '/section/', '/tags/',
            '/brand/', '/brands/', '/search', '/filter'
        ]
        
        # Check for collection patterns
        for pattern in collection_patterns:
            if pattern in url_lower:
                # Make sure it's not a single product URL
                if not any(single in url_lower for single in ['/product/', '/item/', '/p/']):
                    return True
        
        # Check URL structure - collections often have shorter paths or query parameters
        parsed_url = urlparse(url)
        path = parsed_url.path
        path_segments = [seg for seg in path.split('/') if seg]
        
        # If URL has only 1-2 path segments after domain, likely a collection
        if len(path_segments) <= 2 and any(keyword in url_lower for keyword in 
                                          ['shop', 'store', 'product', 'item', 'collection']):
            return True
        
        # Check for query parameters that suggest collections
        query_params = parsed_url.query.lower()
        if any(param in query_params for param in ['category', 'collection', 'type', 'filter', 'tag', 'brand']):
            return True
        
        return False

    async def extract_collection_links(self, url: str, max_pages: int = 20) -> List[str]:
        """
        Extract product links from a collection/category page.
        Supports pagination up to `max_pages`.
        """
        product_links = []
        seen = set()

        try:
            for page in range(1, max_pages + 1):
                page_url = url
                if page > 1:
                    # Common pagination patterns: ?page=2 or /page/2/
                    if "?" in url:
                        page_url = f"{url}&page={page}"
                    else:
                        page_url = f"{url}?page={page}"

                self.log(f"Fetching collection page: {page_url}")

                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.get(page_url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                    })

                if response.status_code != 200:
                    self.log(f"Page {page} returned status {response.status_code}, stopping pagination", "WARNING")
                    break

                soup = BeautifulSoup(response.text, "html.parser")

                # Extract product links using universal selectors
                for selector in self.universal_scraper.universal_selectors['product_links']:
                    for a in soup.select(selector):
                        href = a.get("href")
                        if href:
                            # Normalize link
                            if href.startswith("/"):
                                href = urljoin(url, href)
                            if href.startswith("http") and href not in seen:
                                seen.add(href)
                                product_links.append(href)

                # Stop if no new links were found on this page
                if len(product_links) == len(seen):
                    self.log(f"No new products found on page {page}, stopping pagination", "INFO")
                    break

        except Exception as e:
            self.log(f"Error while extracting collection links: {e}", "ERROR")

        return product_links
    
    async def _extract_links_http(self, collection_url: str) -> List[str]:
        """Extract product links using HTTP requests"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(collection_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    return self._extract_product_links_universal(soup, collection_url)
        except Exception as e:
            self.log(f"HTTP link extraction failed: {e}", "DEBUG")
        return []

    async def _extract_links_browser(self, collection_url: str) -> List[str]:
        """Extract product links using browser"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                await page.goto(collection_url, wait_until="domcontentloaded", timeout=25000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass
                content = await page.content()
                await browser.close()
                
                soup = BeautifulSoup(content, 'html.parser')
                return self._extract_product_links_universal(soup, collection_url)
        except Exception as e:
            self.log(f"Browser link extraction failed: {e}", "DEBUG")
        return []

    def _extract_product_links_universal(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Enhanced universal product link extraction"""
        links = []
        
        # Enhanced selectors for all e-commerce platforms
        selectors = [
            # Shopify selectors
            '.product-item a', '.product-card a', '.grid-product__link',
            '.product-link', '.product__media a',
            # WooCommerce selectors
            '.woocommerce-loop-product__link', '.product-item-link',
            '.product a', '.products li a', '.woocommerce-LoopProduct-link',
            # Magento selectors
            '.product-item-link', '.product-image-wrapper a',
            # BigCommerce selectors
            '.product .card-figure a', '.productGrid .card a',
            # Generic selectors
            '[data-product-url]', 'a[href*="/products/"]',
            'a[href*="/product/"]', 'a[href*="/item/"]', 'a[href*="/p/"]',
            # Additional patterns for various platforms
            '.product-grid-item a', '.product-list-item a',
            '.item a', '.product-thumb a', '.card a[href*="product"]',
            # More universal patterns
            'a[href*="product"]', 'a[href*="item"]'
        ]
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    href = element.get('href')
                    if href:
                        # Convert relative URLs to absolute
                        if href.startswith('/'):
                            href = urljoin(base_url, href)
                        elif not href.startswith('http'):
                            href = urljoin(base_url, '/') + href.lstrip('/')
                        
                        # Filter valid product URLs
                        if self._is_valid_product_url(href, base_url) and href not in links:
                            links.append(href)
                            
                        if len(links) >= 100:  # Reasonable limit
                            break
            except Exception as e:
                self.log(f"Error with selector {selector}: {e}", "DEBUG")
                continue
                
            if len(links) >= 100:
                break
        
        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        return unique_links

    def _is_valid_product_url(self, href: str, base_url: str) -> bool:
        """Check if URL is a valid product URL"""
        if not href or not href.startswith('http'):
            return False
        
        href_lower = href.lower()
        base_domain = urlparse(base_url).netloc.lower()
        url_domain = urlparse(href).netloc.lower()
        
        # Must be from same domain
        if base_domain not in url_domain and url_domain not in base_domain:
            return False
        
        # Should contain product indicators
        product_indicators = ['/product/', '/products/', '/item/', '/p/']
        has_product_indicator = any(indicator in href_lower for indicator in product_indicators)
        
        # Should NOT contain exclusion patterns
        exclusion_patterns = [
            '/cart', '/checkout', '/account', '/login', '/register', 
            '/search', '/contact', '/about', '/policy', '/terms',
            '/collections/', '/category/', '/shop', '.js', '.css',
            '.jpg', '.png', '.gif', '.pdf', 'javascript:', 'mailto:'
        ]
        has_exclusion = any(pattern in href_lower for pattern in exclusion_patterns)
        
        # URL should be reasonable length
        if len(href) > 500:
            return False
        
        return has_product_indicator and not has_exclusion

    # ENHANCED COLLECTION SCRAPING WITH PAGINATION

    async def scrape_collection_with_pagination(self, url: str, max_pages: int = 20, progress_callback: Optional[Callable] = None):
        """Enhanced collection scraping with universal pagination support"""
        all_products = []
        current_url = url
        page_num = 1

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            while current_url and page_num <= max_pages:
                self.log(f"Scraping page {page_num}: {current_url}")
                
                if progress_callback:
                    await progress_callback({
                        "stage": "scraping",
                        "percentage": 10 + (page_num * 70 // max_pages),
                        "details": f"Scraping page {page_num} of {max_pages}"
                    })
                
                try:
                    await page.goto(current_url, wait_until="domcontentloaded", timeout=25000)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except:
                        pass
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')

                    # Extract product links
                    product_links = self._extract_product_links_universal(soup, current_url)
                    self.log(f"Found {len(product_links)} product links on page {page_num}")

                    if not product_links:
                        self.log("No product links found, stopping.", "WARNING")
                        break

                    # Scrape products in parallel using hybrid method
                    products = await self.scrape_all_products_hybrid(product_links, browser)
                    all_products.extend(products)

                    # Enhanced pagination detection
                    next_page_url = self._find_next_page_url_universal(soup, current_url, page_num)
                    if next_page_url and next_page_url != current_url:
                        current_url = next_page_url
                        page_num += 1
                    else:
                        self.log("No more pages found", "INFO")
                        break
                        
                except Exception as e:
                    self.log(f"Error scraping page {page_num}: {e}", "ERROR")
                    break

            await browser.close()
        return all_products

    def _find_next_page_url_universal(self, soup: BeautifulSoup, current_url: str, current_page: int) -> Optional[str]:
        """Enhanced universal pagination detection"""
        
        # Strategy 1: Look for next page links
        next_selectors = [
            'a[rel="next"]', '.pagination a.next', '.page-numbers a.next',
            '.pagination__next', '.next-page', 'a:contains("Next")',
            'a:contains(">")', 'a:contains("»")', '.pager-next a',
            '.pagination-next a', 'a[aria-label*="next"]'
        ]
        
        for selector in next_selectors:
            try:
                next_element = soup.select_one(selector)
                if next_element and next_element.get('href'):
                    next_url = urljoin(current_url, next_element['href'])
                    if next_url != current_url:
                        return next_url
            except:
                continue
        
        # Strategy 2: Look for numbered pagination
        page_selectors = [
            f'.pagination a:contains("{current_page + 1}")',
            f'.page-numbers a:contains("{current_page + 1}")',
            f'a[href*="page={current_page + 1}"]',
            f'a[href*="page/{current_page + 1}"]'
        ]
        
        for selector in page_selectors:
            try:
                page_element = soup.select_one(selector)
                if page_element and page_element.get('href'):
                    next_url = urljoin(current_url, page_element['href'])
                    if next_url != current_url:
                        return next_url
            except:
                continue
        
        # Strategy 3: Construct next page URL based on current URL pattern
        return self._construct_next_page_url(current_url, current_page)

    def _construct_next_page_url(self, current_url: str, current_page: int) -> Optional[str]:
        """Construct next page URL based on URL pattern"""
        try:
            next_page = current_page + 1
            
            # Pattern 1: ?page=N
            if f"page={current_page}" in current_url:
                return current_url.replace(f"page={current_page}", f"page={next_page}")
            elif "page=" in current_url:
                # Replace existing page parameter
                import re
                return re.sub(r'page=\d+', f'page={next_page}', current_url)
            
            # Pattern 2: /page/N
            if f"/page/{current_page}" in current_url:
                return current_url.replace(f"/page/{current_page}", f"/page/{next_page}")
            elif "/page/" in current_url:
                import re
                return re.sub(r'/page/\d+', f'/page/{next_page}', current_url)
            
            # Pattern 3: ?p=N
            if f"p={current_page}" in current_url:
                return current_url.replace(f"p={current_page}", f"p={next_page}")
            elif "p=" in current_url:
                import re
                return re.sub(r'p=\d+', f'p={next_page}', current_url)
            
            # Pattern 4: Add page parameter if none exists
            if current_page == 1:
                separator = "&" if "?" in current_url else "?"
                return f"{current_url}{separator}page={next_page}"
        
        except Exception as e:
            self.log(f"Error constructing next page URL: {e}", "DEBUG")
        
        return None

    async def scrape_all_products_hybrid(self, urls: List[str], browser, concurrency: int = 5):
        """Enhanced parallel product scraping with multiple fallback methods"""
        semaphore = asyncio.Semaphore(concurrency)
        
        async def scrape_with_semaphore(url):
            async with semaphore:
                # Try the enhanced hybrid method
                return await self.extract_product_data_hybrid(url)
        
        # Use asyncio.gather with return_exceptions to continue even if some fail
        results = await asyncio.gather(*[scrape_with_semaphore(u) for u in urls], return_exceptions=True)
        
        # Filter out exceptions and return only successful results
        successful_results = []
        for result in results:
            if (not isinstance(result, Exception) and 
                result and 
                self._is_valid_product_data(result)):
                successful_results.append(result)
        
        return successful_results

# Keep all your existing extract_product_data and other methods...
# [Rest of the original methods remain unchanged]

# Enhanced API function
async def scrape_urls_simple_api(
    urls: List[str],
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
    max_pages: int = 20
) -> Dict[str, Any]:
    """
    Enhanced Simple API function to scrape ALL product data from ANY e-commerce website
    - Handles full pagination
    - Deduplicates product URLs
    - Ensures stock details are included
    """
    scraper = SimpleProductScraper(log_callback, progress_callback)

    try:
        scraper.log("Starting enhanced universal scraping process")
        scraper.update_progress("initialization", 5, "Setting up universal scraper")

        all_products = []
        seen_urls = set()
        total_pages_scraped = 0

        for i, url in enumerate(urls):
            scraper.update_progress("analyzing_urls", 10 + (i * 5), f"Processing URL {i+1}/{len(urls)}")

            if scraper.is_collection_url(url):
                scraper.log(f"Detected collection page: {url}")

                # ✅ Extract all product links across pages
                product_links = await scraper.extract_collection_links(url, max_pages=max_pages)

                scraper.log(f"Found {len(product_links)} product links in collection {url}")

                for link in product_links:
                    if link not in seen_urls:
                        seen_urls.add(link)
                        data = await scraper.extract_product_data_hybrid(link)
                        if data and scraper._is_valid_product_data(data):
                            data["source_url"] = link 
                            all_products.append(data)
                            total_pages_scraped += 1

            else:
                # ✅ Direct product page
                if url not in seen_urls:
                    seen_urls.add(url)
                    scraper.update_progress("scraping_products", 50, f"Scraping product {url}")
                    data = await scraper.extract_product_data_hybrid(url)
                    if data and scraper._is_valid_product_data(data):
                        all_products.append(data)
                        total_pages_scraped += 1

        scraper.update_progress("completed", 100, f"Completed! Found {len(all_products)} unique products")
        scraper.log("Enhanced universal scraping completed successfully", "SUCCESS")

        # ✅ Final result with metadata
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result = {
            "metadata": {
                "timestamp": timestamp,
                "total_products": len(all_products),
                "total_pages_scraped": total_pages_scraped,
                "scraper_type": "enhanced-universal",
                "urls_processed": len(urls),
                "unique_urls": len(seen_urls),
                "success_rate": round((len(all_products) / max(total_pages_scraped, 1)) * 100, 2)
            },
            "products": all_products
        }

        # Save results into logs
        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)
        output_file = os.path.join(logs_dir, f"enhanced_scrape_{timestamp}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        scraper.log(f"Results saved to {output_file}")
        return result

    except Exception as e:
        scraper.log(f"Error in enhanced universal scraping: {e}", "ERROR")
        scraper.log(f"Traceback: {traceback.format_exc()}", "ERROR")
        raise e

if __name__ == "__main__":
    # Test the enhanced scraper
    async def test_enhanced_scraper():
        test_urls = [
            "https://example-website.com/collections/all",
            "https://another-site.com/shop/",
            "https://test-store.com/products/sample-product"
        ]
        
        result = await scrape_urls_simple_api(test_urls, max_pages=10)
        self.log(json.dumps(result, indent=2))