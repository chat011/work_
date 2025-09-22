"""
Simple Web Scraper for E-commerce Products
Direct extraction without complex AI agent interactions
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable,Union
from urllib.parse import urljoin, urlparse
import re
import tenacity

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

class SimpleProductScraper:
    """Simple product scraper using direct HTML parsing with enhanced pagination"""
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
                        return self._parse_price_text(price_val)
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

    def _parse_price_text(self, price_text: str) -> float:
        """Parse price text to extract numeric value"""
        if not price_text:
            return 0.0
        
        # Extract all numbers with decimal points or commas
        numbers = re.findall(r'\d+[,.]?\d*', price_text)
        
        valid_prices = []
        for num in numbers:
            # Clean and convert to float
            cleaned = num.replace(',', '')
            try:
                price = float(cleaned)
                if price > 0:
                    valid_prices.append(price)
            except ValueError:
                continue
        
        if valid_prices:
            # Return the first valid price (usually the main price)
            return valid_prices[0]
        
        return 0.0

    def _extract_images_universal(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract product images using universal selectors"""
        images = []
        
        # Image selectors for different platforms
        selectors = [
            # Shopify selectors
            '.product__media img', '.product-single__photos img', '.ProductItem-gallery img',
            '.product-photos img', '.product-images img', '.product-media img',
            '.product__photo img',
            # WooCommerce selectors
            '.woocommerce-product-gallery img', '.product-images img', '.wp-post-image',
            # Generic selectors
            '[data-product-image] img', '.product-gallery img',
            # Universal selectors
            '.main-image img', '.product-image img', '.gallery img',
            '.image img', '.photo img', '.thumb img',
            '[itemprop="image"]', 'img[src*="product"]', 'img[alt*="product"]'
        ]
        
        for selector in selectors:
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
        selectors = [
            # Shopify selectors
            '.product__description', '.product-single__description', '.ProductItem-details-excerpt',
            '.product-description', '.rte', '.product-single__description-full',
            # WooCommerce selectors
            '.woocommerce-product-details__short-description', '.product-short-description',
            '.entry-content',
            # Generic selectors
            '[data-product-description]', '.description', '.product-details',
            '.product-info', '.specs', '.details', '[itemprop="description"]'
        ]
        
        for selector in selectors:
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
    async def extract_product_data_hybrid(self, url: str) -> Dict[str, Any]:
        """
        Universal hybrid method that works for ALL e-commerce sites
        Tries multiple approaches in order of speed and reliability
        """
        methods = [
            self._extract_using_platform_api,
            self._extract_using_structured_data,
            self._extract_using_static_html,
            lambda u: self._extract_using_browser(u, 10),  # Fast browser
            lambda u: self._extract_using_browser(u, 15),  # Medium browser
            lambda u: self._extract_using_browser(u, 20),  # Slow browser
        ]
        
        for method in methods:
            try:
                result = await method(url)
                if result and result.get("product_name") and result.get("product_name") != "Unknown Product":
                    self.log(f"✅ Success with method: {result.get('extraction_method')}")
                    return result
            except Exception as e:
                self.log(f"Method failed: {e}", "DEBUG")
                continue
        
        # All methods failed
        return {
            "url": url,
            "product_name": "Error",
            "error": "All extraction methods failed",
            "timestamp": datetime.now().isoformat()
        }
        
    async def _extract_using_platform_api(self, url: str) -> Optional[Dict[str, Any]]:
        """Try platform-specific APIs (Shopify, WooCommerce)"""
        platform = self._get_platform(url)
        
        if platform == 'shopify':
            return await self._extract_shopify_api(url)
        elif platform == 'woocommerce':
            return await self._extract_woocommerce_api(url)
        
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
        import json
        
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
                    }
            except (json.JSONDecodeError, AttributeError):
                continue
        
        return None
    
    def _parse_js_variables(self, html: str) -> Optional[Dict[str, Any]]:
        """Parse JavaScript variables containing product data"""
        import json
        
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
                        "extraction_method": "static_html_parsing"
                    }
        except Exception as e:
            self.log(f"Static HTML extraction failed: {e}", "DEBUG")
        
        return None
    
    def _extract_product_name_universal(self, soup: BeautifulSoup) -> str:
        """Extract product name using universal selectors"""
        selectors = [
            'h1.product-title', 'h1.product__title', 'h1[data-testid="product-title"]',
            '.product-single__title', '.product__title', 'h1.ProductItem-details-title',
            'h1.entry-title', 'h1.product_title', 'h1', '.product-title',
            '[data-product-title]', '.pdp-product-name', '.product-name',
            '.item-title', '.prod-title', '.title', '[itemProp="name"]'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text and len(text) > 2:
                    return text
        
        # Fallback to page title
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True).split('|')[0].strip()
        
        return "Unknown Product"
    
    def _extract_price_universal(self, soup: BeautifulSoup) -> float:
        """Extract price using universal selectors"""
        price_selectors = [
            '.price__current .money', '.product-price .money', '.price-current',
            '.current-price', '.price .money', '.price-item--regular',
            '.woocommerce-Price-amount', 'p.price', '.price',
            '[data-price]', '.ProductItem-details-checkout-price',
            '.price-now', '.current_price', '.regular-price', '.sale-price',
            '.product-price-value', '.price-box .price', '[itemProp="price"]',
            '.cost', '.amount', '.precio', '.prix'
        ]
        
        for selector in price_selectors:
            elements = soup.select(selector)
            for element in elements:
                price_text = element.get_text(strip=True)
                price = self._parse_price_text(price_text)
                if price > 0:
                    return price
        
        return 0.0
    
    async def _extract_using_browser(self, url: str, timeout_seconds: int) -> Optional[Dict[str, Any]]:
        """Browser extraction with specified timeout"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    # Set timeouts
                    page.set_default_timeout(timeout_seconds * 1000)
                    page.set_default_navigation_timeout(timeout_seconds * 1000)
                    
                    # Load with specified timeout
                    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
                    
                    # Progressive waiting based on timeout
                    if timeout_seconds >= 15:
                        try:
                            await page.wait_for_selector('h1, .price, .product-title', timeout=3000)
                        except:
                            pass
                    
                    # Wait proportional to timeout
                    await asyncio.sleep(min(timeout_seconds / 5, 4))
                    
                    if timeout_seconds >= 20:
                        try:
                            await page.wait_for_load_state("networkidle", timeout=5000)
                        except:
                            pass
                    
                    # Get content and parse
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    return {
                        "product_name": self._extract_product_name_universal(soup),
                        "price": self._extract_price_universal(soup),
                        "product_images": self._extract_images_universal(soup, url),
                        "description": self._extract_description_universal(soup),
                        "extraction_method": f"browser_{timeout_seconds}s_timeout"
                    }
                    
                finally:
                    await browser.close()
        except Exception as e:
            self.log(f"Browser extraction with {timeout_seconds}s failed: {e}", "DEBUG")
            return None
    
    def __init__(self, log_callback: Optional[Callable] = None, progress_callback: Optional[Callable] = None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def log(self, message: str, level: str = "INFO", details: Dict[str, Any] = None):
        """Simple logging"""
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
    
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
        retry=tenacity.retry_if_exception_type(Exception)
    )
    async def extract_product_data(self, url: str) -> Dict[str, Any]:
        """Extract product data from a single product page with retry logic"""
        try:
            self.log(f"Extracting product data from: {url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Navigate to the page
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass  # Continue even if networkidle times out
                
                # Get page content
                content = await page.content()
                await browser.close()
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                # Extract product data using direct parsing
                product_data = await self._parse_product_data(soup, url)
                
                return product_data
                
        except Exception as e:
            self.log(f"Error extracting product data from {url}: {e}", "ERROR")
            return {
                "url": url,
                "product_name": "Error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _parse_product_data(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Parse product data from HTML soup"""
        try:
            # Initialize product data structure
            product_data = {
                "product_name": "",
                "price": 0.0,
                "discounted_price": None,
                "product_images": [],
                "description": "",
                "sizes": [],
                "colors": [],
                "material": "",
                "metadata": {
                    "platform": self._get_platform(url),
                    "extracted_at": datetime.now().isoformat(),
                    "availability": "true",
                    "sku": "",
                    "brand": self._get_brand(url),
                    "categories": [],
                    "tags": [],
                    "rating": None,
                    "review_count": None,
                    "specifications": {},
                    "variants": []
                },
                "source_url": url,
                "timestamp": datetime.now().isoformat()
            }
            
            # Extract product name
            product_data["product_name"] = self._extract_product_name(soup)
            
            # Extract prices
            price_info = self._extract_prices(soup)
            product_data["price"] = price_info.get("price", 0.0)
            product_data["discounted_price"] = price_info.get("discounted_price")
            
            # Extract images
            product_data["product_images"] = self._extract_images(soup, url)
            
            # Extract description
            product_data["description"] = self._extract_description(soup)
            
            # Extract sizes and colors
            product_data["sizes"] = self._extract_sizes(soup)
            product_data["colors"] = self._extract_colors(soup)
            
            # Extract material
            product_data["material"] = self._extract_material(soup)
            
            # Extract metadata
            product_data["metadata"].update(self._extract_metadata(soup, url))
            
            # Extract variants
            product_data["metadata"]["variants"] = self._extract_variants(soup)
            
            return product_data
            
        except Exception as e:
            self.log(f"Error parsing product data: {e}", "ERROR")
            return {
                "url": url,
                "product_name": "Parse Error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _get_platform(self, url: str) -> str:
        """Determine the platform from URL"""
        domain = urlparse(url).netloc.lower()
        if 'shopify' in domain or '.myshopify.com' in domain:
            return 'shopify'
        elif 'deashaindia.com' in domain:
            return 'shopify'  # Deasha India uses Shopify
        elif 'ajmerachandanichowk.com' in domain:
            return 'woocommerce'  # Ajmera uses WooCommerce
        else:
            return domain
    
    def _get_brand(self, url: str) -> str:
        """Get brand name from URL"""
        domain = urlparse(url).netloc.lower()
        if 'deashaindia.com' in domain:
            return 'Deasha India'
        elif 'ajmerachandanichowk.com' in domain:
            return 'Ajmera Chandani Chowk'
        else:
            return domain
    
    def _extract_product_name(self, soup: BeautifulSoup) -> str:
        """Extract product name"""
        selectors = [
            'h1.product-title',
            'h1.product__title',
            'h1[data-testid="product-title"]',
            '.product-single__title',
            '.product__title',
            'h1.ProductItem-details-title',
            'h1.entry-title',  # WooCommerce
            'h1.product_title',  # WooCommerce
            'h1',
            '.product-title',
            '[data-product-title]'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                # Fix duplicate text (common Shopify issue)
                title = self._fix_duplicate_title(title)
                return title
        
        # Fallback to title tag
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True).split('|')[0].strip()
            return self._fix_duplicate_title(title)
        
        return "Unknown Product"
    
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
    
    def _extract_prices(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract price information with improved parsing"""
        price_info = {"price": 0.0, "discounted_price": None}
        
        # Price selectors for different platforms
        price_selectors = [
            # Shopify selectors
            '.price__current .money',
            '.product-price .money',
            '.price-current',
            '.current-price',
            '.price .money',
            '.price-item--regular',
            '.price__regular .price-item',
            '.price__regular',
            '.price-item',
            # WooCommerce selectors
            '.woocommerce-Price-amount',
            '.price ins .woocommerce-Price-amount',
            '.price .amount',
            'p.price',
            '.price',
            # Generic selectors
            '[data-price]',
            '.ProductItem-details-checkout-price'
        ]
        
        # Compare at price selectors (original price when on sale)
        compare_selectors = [
            '.price__compare .money',
            '.compare-price',
            '.was-price',
            '.price-compare',
            '.price del .woocommerce-Price-amount',  # WooCommerce
            '.price del .amount',
            '[data-compare-price]',
            '.price-item--sale'
        ]
        
        # Extract current price
        for selector in price_selectors:
            elements = soup.select(selector)
            for element in elements:
                price_text = element.get_text(strip=True)
                price = self._parse_price_improved(price_text)
                if price > 0:
                    price_info["price"] = price
                    break
            if price_info["price"] > 0:
                break
        
        # Extract compare price (original price when discounted)
        for selector in compare_selectors:
            elements = soup.select(selector)
            for element in elements:
                compare_text = element.get_text(strip=True)
                compare_price = self._parse_price_improved(compare_text)
                if compare_price > 0:
                    # If compare price exists and is higher than current price, current is discounted
                    if compare_price > price_info["price"]:
                        price_info["discounted_price"] = price_info["price"]
                        price_info["price"] = compare_price
                    break
        
        return price_info
    
    def _parse_price_improved(self, price_text: str) -> float:
        """Improved price parsing that handles various formats"""
        if not price_text:
            return 0.0
        
        # Extract all numbers with decimal points or commas
        numbers = re.findall(r'\d+[,.]?\d*', price_text)
        
        valid_prices = []
        for num in numbers:
            # Clean and convert to float
            cleaned = num.replace(',', '')
            try:
                price = float(cleaned)
                if price > 0:
                    valid_prices.append(price)
            except:
                continue
        
        if valid_prices:
            # Return the first valid price (usually the main price)
            return valid_prices[0]
        
        return 0.0
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract product images"""
        images = []
        
        # Image selectors for different platforms
        selectors = [
            # Shopify selectors
            '.product__media img',
            '.product-single__photos img',
            '.ProductItem-gallery img',
            '.product-photos img',
            '.product-images img',
            '.product-media img',
            '.product__photo img',
            # WooCommerce selectors
            '.woocommerce-product-gallery img',
            '.product-images img',
            '.wp-post-image',
            # Generic selectors
            '[data-product-image] img',
            '.product-gallery img'
        ]
        
        for selector in selectors:
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
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract product description"""
        selectors = [
            # Shopify selectors
            '.product__description',
            '.product-single__description',
            '.ProductItem-details-excerpt',
            '.product-description',
            '.rte',
            '.product-single__description-full',
            # WooCommerce selectors
            '.woocommerce-product-details__short-description',
            '.product-short-description',
            '.entry-content',
            # Generic selectors
            '[data-product-description]'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)[:2000]  # Limit length
        
        return ""
    
    def _extract_sizes(self, soup: BeautifulSoup) -> List[str]:
        """Extract available sizes"""
        sizes = []
        
        # First try to get sizes from Shopify product JSON
        sizes_from_json = self._extract_variants_from_json(soup, 'size')
        if sizes_from_json:
            return sizes_from_json
        
        # Size selectors for different platforms
        selectors = [
            # Shopify variant selectors
            'select[data-index="0"] option',
            'select[name*="size"] option',
            '.variant-input-wrap:has(label:contains("Size")) input',
            '.product-form__option[data-option-name*="size"] .product-form__option-value',
            '[data-option="Size"] option',
            '.size-selector option',
            '.variant-option-size .variant-option-value',
            # WooCommerce selectors
            'select[data-attribute_name*="size"] option',
            'select[name*="attribute_pa_size"] option',
            '.variations select option',
            # Generic selectors
            '.size-options option',
            '.product-options select option'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                size = element.get_text(strip=True)
                if size and size.lower() not in ['default title', 'select size', 'choose an option'] and size not in sizes:
                    sizes.append(size)
        
        return sizes
    
    def _extract_colors(self, soup: BeautifulSoup) -> List[str]:
        """Extract available colors"""
        colors = []
        
        # First try to get colors from Shopify product JSON
        colors_from_json = self._extract_variants_from_json(soup, 'color')
        if colors_from_json:
            return colors_from_json
        
        # Color selectors for different platforms
        selectors = [
            # Shopify variant selectors
            'select[data-index="1"] option',
            'select[name*="color"] option',
            '.variant-input-wrap:has(label:contains("Color")) input',
            '.product-form__option[data-option-name*="color"] .product-form__option-value',
            '[data-option="Color"] option',
            '.color-selector option',
            '.variant-option-color .variant-option-value',
            # WooCommerce selectors
            'select[data-attribute_name*="color"] option',
            'select[name*="attribute_pa_color"] option',
            '.variations select option',
            # Generic selectors
            '.color-options option',
            '.product-options select option'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                color = element.get_text(strip=True)
                if color and color.lower() not in ['default title', 'select color', 'choose an option'] and color not in colors:
                    colors.append(color)
        
        return colors
    
    def _extract_material(self, soup: BeautifulSoup) -> str:
        """Extract material information"""
        material_text = ""
        
        # Check description for material keywords
        description_selectors = [
            '.product__description', 
            '.product-single__description',
            '.woocommerce-product-details__short-description',
            '.entry-content'
        ]
        
        for selector in description_selectors:
            description = soup.select_one(selector)
            if description:
                text = description.get_text()
                # Look for FABRIC section
                fabric_match = re.search(r'FABRIC[:\s]*(.*?)(?:PRODUCT|WASHING|$)', text, re.IGNORECASE | re.DOTALL)
                if fabric_match:
                    material_text = fabric_match.group(1).strip()[:200]
                    break
                
                # Look for material keywords
                material_keywords = ['cotton', 'silk', 'georgette', 'chiffon', 'organza', 'polyester', 'rayon']
                for keyword in material_keywords:
                    if keyword.lower() in text.lower():
                        # Extract sentence containing the material
                        sentences = text.split('.')
                        for sentence in sentences:
                            if keyword.lower() in sentence.lower():
                                material_text = sentence.strip()[:200]
                                break
                        if material_text:
                            break
                
                if material_text:
                    break
        
        return material_text
    
    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract additional metadata"""
        metadata = {
            "availability": "true",
            "sku": "",
            "brand": self._get_brand(url),
            "categories": [],
            "tags": []
        }
        
        # Extract categories from breadcrumbs and navigation
        breadcrumb_selectors = [
            '.breadcrumb a',
            '.breadcrumbs a', 
            '.breadcrumb-item a',
            '.woocommerce-breadcrumb a',
            'nav.breadcrumb a',
            '.breadcrumb-trail a',
            # Shopify specific selectors
            '.breadcrumbs__list a',
            'nav[aria-label="breadcrumb"] a',
            # Generic navigation
            'nav a[href*="collections"]',
            'nav a[href*="category"]'
        ]
        
        for selector in breadcrumb_selectors:
            breadcrumbs = soup.select(selector)
            if breadcrumbs:
                for crumb in breadcrumbs:
                    text = crumb.get_text(strip=True)
                    href = crumb.get('href', '')
                    # Include if it's a category/collection link or meaningful breadcrumb
                    if (text and text.lower() not in ['home', 'products', 'shop', 'all'] and 
                        text not in metadata["categories"] and
                        (('/collections/' in href) or ('/category/' in href) or 
                         any(keyword in text.lower() for keyword in ['saree', 'dress', 'lehenga', 'suit']))):
                        metadata["categories"].append(text)
        
        # Try to extract categories from JSON-LD
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            if script.string:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and 'category' in data:
                        category = data['category']
                        if isinstance(category, str) and category not in metadata["categories"]:
                            metadata["categories"].append(category)
                        elif isinstance(category, list):
                            for cat in category:
                                if isinstance(cat, str) and cat not in metadata["categories"]:
                                    metadata["categories"].append(cat)
                except:
                    continue
        
        # Extract availability
        availability_indicators = soup.find_all(text=re.compile(r'(in stock|out of stock|sold out|available)', re.IGNORECASE))
        for indicator in availability_indicators:
            text = indicator.strip().lower()
            if 'out of stock' in text or 'sold out' in text:
                metadata["availability"] = "OutOfStock"
                break
            elif 'in stock' in text or 'available' in text:
                metadata["availability"] = "InStock"
                break
        
        return metadata
    
    def _extract_variants_from_json(self, soup: BeautifulSoup, variant_type: str) -> List[str]:
        """Extract specific variant type (size/color) from Shopify product JSON"""
        variants = []
        
        # Look for Shopify product JSON in various script tags
        all_scripts = soup.find_all('script')
        for script in all_scripts:
            if script.string and ('product' in script.string.lower() and 'variants' in script.string.lower()):
                try:
                    # Try to find JSON objects in the script
                    script_content = script.string
                    
                    # Look for window.product = {...} or similar patterns
                    patterns = [
                        r'window\.product\s*=\s*({.*?});',
                        r'var\s+product\s*=\s*({.*?});',
                        r'"product"\s*:\s*({.*?})',
                        r'product:\s*({.*?})'
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, script_content, re.DOTALL)
                        for match in matches:
                            try:
                                product_data = json.loads(match)
                                if isinstance(product_data, dict) and 'options' in product_data:
                                    # Extract from product options
                                    for option in product_data['options']:
                                        if isinstance(option, dict):
                                            option_name = option.get('name', '').lower()
                                            if variant_type.lower() in option_name:
                                                values = option.get('values', [])
                                                if isinstance(values, list):
                                                    variants.extend([str(v) for v in values if v])
                                
                                # Also check variants array
                                if 'variants' in product_data and isinstance(product_data['variants'], list):
                                    for variant in product_data['variants']:
                                        if isinstance(variant, dict) and 'title' in variant:
                                            title = variant['title']
                                            # Extract size/color from variant title
                                            if isinstance(title, str) and title.lower() not in ['default title']:
                                                # Split variant title to get individual options
                                                parts = [p.strip() for p in title.split('/')]
                                                for part in parts:
                                                    if part and part not in variants:
                                                        variants.append(part)
                                
                                if variants:
                                    return list(set(variants))  # Remove duplicates
                            except (json.JSONDecodeError, KeyError):
                                continue
                except Exception:
                    continue
        
        return variants
    
    def _extract_variants(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract product variants"""
        variants = []
        
        # Look for Shopify product JSON
        scripts = soup.find_all('script', type='application/json')
        for script in scripts:
            if script.string:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and 'variants' in data:
                        for variant in data['variants']:
                            if isinstance(variant, dict):
                                variant_info = {
                                    "id": variant.get('id'),
                                    "title": variant.get('title'),
                                    "price": variant.get('price', 0) / 100 if variant.get('price') else 0,
                                    "discounted_price": variant.get('compare_at_price', 0) / 100 if variant.get('compare_at_price') else None
                                }
                                variants.append(variant_info)
                except:
                    continue
        
        # Look for WooCommerce variations
        if not variants:
            variation_selectors = [
                '.variations select option',
                '.product-options select option'
            ]
            
            for selector in variation_selectors:
                options = soup.select(selector)
                for option in options:
                    value = option.get('value')
                    text = option.get_text(strip=True)
                    if value and text and text.lower() not in ['choose an option', 'select']:
                        variants.append({
                            "id": value,
                            "title": text,
                            "price": 0,
                            "discounted_price": None
                        })
        
        return variants
    
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
        retry=tenacity.retry_if_exception_type(Exception)
    )
    async def extract_collection_links(self, collection_url: str) -> List[str]:
        """Extract product links from a collection page with retry logic"""
        try:
            self.log(f"Extracting product links from: {collection_url}")
            
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
                return self._extract_product_links(soup, collection_url)
                
        except Exception as e:
            self.log(f"Error extracting collection links from {collection_url}: {e}", "ERROR")
            return []
    
    # In scraper_simple.py, update the _extract_product_links method
    def _extract_product_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract product links from collection page HTML with improved logic"""
        links = []
        
        # Product link selectors for different platforms
        selectors = [
            # Shopify selectors
            '.product-item a',
            '.product-card a',
            '.grid-product__link',
            '.product-link',
            '.product__media a',
            # WooCommerce selectors
            '.woocommerce-loop-product__link',
            '.product-item-link',
            '.product a',
            '.products li a',
            '.woocommerce-LoopProduct-link',
            # Generic selectors
            '[data-product-url]',
            'a[href*="/products/"]',
            'a[href*="/product/"]',
            'a[href*="/item/"]',
            'a[href*="/p/"]',
            # Additional patterns for various e-commerce platforms
            '.product-grid-item a',
            '.product-list-item a',
            '.item a',
            '.product-thumb a'
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
                        if (href.startswith('http') and 
                            href not in links and 
                            len(href) < 500):  # Reasonable URL length
                            
                            # Additional filtering to exclude non-product pages
                            is_likely_product = any(pattern in href.lower() for pattern in [
                                '/product/', '/products/', '/item/', '/p/'
                            ])
                            
                            is_excluded = any(pattern in href.lower() for pattern in [
                                '/cart', '/checkout', '/account', '/login', '/register', 
                                '/search', '/contact', '/about', '/policy', '/terms'
                            ])
                            
                            if is_likely_product and not is_excluded:
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

    async def scrape_all_products(self, urls: List[str], browser, concurrency: int = 5):
        """Scrape multiple products concurrently with improved performance"""
        semaphore = asyncio.Semaphore(concurrency)
        
        async def scrape_with_semaphore(url):
            async with semaphore:
                return await self._scrape_single_product_with_browser(url, browser)
        
        # Use asyncio.gather with return_exceptions to continue even if some fail
        results = await asyncio.gather(*[scrape_with_semaphore(u) for u in urls], return_exceptions=True)
        
        # Filter out exceptions and return only successful results
        return [r for r in results if not isinstance(r, Exception)]

    async def _scrape_single_product_with_browser(self, url: str, browser):
        """Scrape a single product using an existing browser instance with improved timeout handling"""
        page = await browser.new_page()
        try:           
            # Wait for additional content to load with shorter timeout
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except:
                pass
            
            # Use evaluate to get HTML content faster
            content = await page.evaluate("document.documentElement.outerHTML")
            soup = BeautifulSoup(content, 'html.parser')
            
            return await self._parse_product_data(soup, url)
        except Exception as e:
            # Enhanced error handling - try alternative loading strategies
            if "Timeout" in str(e):
                self.log(f"Timeout for {url}, trying alternative approach", "WARNING")
                try:
                    # Try with just basic loading
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    # Don't wait for full load, just get what we can
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    return await self._parse_product_data(soup, url)
                except Exception as e2:
                    self.log(f"Alternative approach also failed for {url}: {e2}", "ERROR")
                    return {
                        "url": url,
                        "product_name": "Timeout Error",
                        "error": f"Multiple timeout attempts failed: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                        "price": 0.0,
                        "product_images": [],
                        "description": "",
                        "sizes": [],
                        "colors": [],
                        "material": ""
                    }
            else:
                self.log(f"Error scraping {url}: {e}", "ERROR")
                return {
                    "url": url,
                    "product_name": "Error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "price": 0.0,
                    "product_images": [],
                    "description": "",
                    "sizes": [],
                    "colors": [],
                    "material": ""
                }
        finally:
            await page.close()
            
    async def scrape_collection_with_pagination(self, url: str, max_pages: int = 20, progress_callback: Optional[Callable] = None):
        """Scrape all products across paginated collection/category pages with enhanced pagination"""
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
                    product_links = self._extract_product_links(soup, current_url)
                    self.log(f"Found {len(product_links)} product links on page {page_num}")

                    if not product_links:
                        self.log("⚠️ No product links found, stopping.", "WARNING")
                        break

                    # Scrape products in parallel using hybrid method
                    products = await self.scrape_all_products_hybrid(product_links, browser)
                    all_products.extend(products)

                    # Enhanced pagination detection
                    next_page_url = self._find_next_page_url(soup, current_url)
                    if next_page_url and next_page_url != current_url:
                        current_url = next_page_url
                        page_num += 1
                    else:
                        current_url = None  # no more pages
                        
                except Exception as e:
                    self.log(f"Error scraping page {page_num}: {e}", "ERROR")
                    # Try to continue with next page if possible
                    next_page_url = self._find_next_page_url(soup, current_url)
                    if next_page_url and next_page_url != current_url:
                        current_url = next_page_url
                        page_num += 1
                    else:
                        current_url = None

            await browser.close()
        return all_products
    async def scrape_all_products_hybrid(self, urls: List[str], browser, concurrency: int = 5):
        """Scrape multiple products concurrently with hybrid method"""
        semaphore = asyncio.Semaphore(concurrency)
        
        async def scrape_with_semaphore(url):
            async with semaphore:
                # Try HTTP methods first for speed
                try:
                    http_result = await self._extract_using_structured_data(url)
                    if http_result and http_result.get("product_name") and http_result.get("product_name") != "Unknown Product":
                        return http_result
                except:
                    pass
                
                # Fall back to browser if HTTP methods fail
                return await self._scrape_single_product_with_browser(url, browser)
        
        # Use asyncio.gather with return_exceptions to continue even if some fail
        results = await asyncio.gather(*[scrape_with_semaphore(u) for u in urls], return_exceptions=True)
        
        # Filter out exceptions and return only successful results
        return [r for r in results if not isinstance(r, Exception) and r and "error" not in r]
    def _find_next_page_url(self, soup: BeautifulSoup, current_url: str) -> str:
        """Find the next page URL with improved detection"""
        # Check for various pagination patterns
        next_selectors = [
            'a[rel="next"]',
            '.pagination a.next',
            '.page-numbers a.next',
            '.pagination__next',
            '.next-page',
            'a:contains("Next")',
            'a:contains(">")',
            'a:contains("»")'
        ]
        
        # Also check for numbered pagination
        current_page_num = self._extract_page_number(current_url)
        if current_page_num:
            next_page_num = current_page_num + 1
            # Try to construct next page URL based on pattern
            if "page=" in current_url:
                next_url = current_url.replace(f"page={current_page_num}", f"page={next_page_num}")
            elif "/page/" in current_url:
                parts = current_url.split("/page/")
                if len(parts) > 1:
                    next_url = f"{parts[0]}/page/{next_page_num}/{parts[1].split('/', 1)[1] if '/' in parts[1] else ''}"
                else:
                    next_url = f"{current_url.rstrip('/')}/page/{next_page_num}"
            else:
                next_url = f"{current_url}{'&' if '?' in current_url else '?'}page={next_page_num}"
            
            # Check if this constructed URL makes sense
            if next_url != current_url:
                return next_url
        
        # Fallback to selector-based detection
        for selector in next_selectors:
            next_element = soup.select_one(selector)
            if next_element and next_element.get('href'):
                next_url = urljoin(current_url, next_element['href'])
                if next_url != current_url:
                    return next_url
        
        return None

    def _extract_page_number(self, url: str) -> int:
        """Extract page number from URL"""
        patterns = [
            r'page=(\d+)',
            r'/page/(\d+)',
            r'/p(\d+)',
            r'p=(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        return 1  # Default to page 1 if no page number found

class UniversalEcommerceScraper:
    """Universal scraper that works for ANY e-commerce site"""
    
    def __init__(self, log_callback=None, progress_callback=None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def log(self, message: str, level: str = "INFO", details: Dict[str, Any] = None):
        """Simple logging"""
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
    
    # Update the extract_product_data_universal method to handle collections

    async def extract_product_data_universal(self, url: str) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Universal product extraction that works for ANY e-commerce site
        Returns either a single product or a list of products for collections
        """
        # First check if this is a collection URL
        if self._is_collection_url(url):
            self.log(f"Detected collection URL: {url}")
            products = await self.extract_from_collection(url)
            return {
                "collection_url": url,
                "products": products,
                "total_products": len(products),
                "extraction_method": "collection_extraction"
            }
        
        # If it's not a collection, proceed with single product extraction
        # Try faster methods first
        methods = [
            self._extract_via_http_structured_data,  # Fastest
            self._extract_via_http_html_parsing,     # Fast
            lambda u: self._extract_via_browser(u, 8),  # Medium-fast browser
            lambda u: self._extract_via_browser(u, 12), # Medium browser
            lambda u: self._extract_via_browser(u, 18), # Slow browser
        ]
        
        for method in methods:
            try:
                result = await method(url)
                if result and result.get("product_name") and result.get("product_name") != "Unknown Product":
                    self.log(f"✅ Success with method: {result.get('extraction_method')}")
                    # Ensure all required fields are present
                    result = self._ensure_required_fields(result, url)
                    return result
            except Exception as e:
                self.log(f"Method {method.__name__} failed: {str(e)[:100]}", "DEBUG")
                continue
        
        # All methods failed
        return {
            "url": url,
            "product_name": "Error - All extraction methods failed",
            "error": "All extraction methods failed",
            "timestamp": datetime.now().isoformat(),
            "price": 0.0,
            "product_images": [],
            "description": "",
            "sizes": [],
            "colors": [],
            "material": ""
        }

    def _ensure_required_fields(self, result: Dict[str, Any], url: str) -> Dict[str, Any]:
        """Ensure all required fields are present in the result"""
        required_fields = {
            "product_name": "",
            "price": 0.0,
            "discounted_price": None,
            "product_images": [],
            "description": "",
            "sizes": [],
            "colors": [],
            "material": "",
            "metadata": {
                "platform": self._detect_platform(url),
                "extracted_at": datetime.now().isoformat(),
                "availability": "unknown",
                "sku": "",
                "brand": self._extract_brand_from_url(url),
                "categories": [],
                "tags": [],
                "rating": None,
                "review_count": None,
                "specifications": {},
                "variants": []
            },
            "source_url": url,
            "timestamp": datetime.now().isoformat()
        }
        
        # Merge the result with default fields
        for key, default_value in required_fields.items():
            if key not in result:
                result[key] = default_value
            elif isinstance(default_value, dict) and isinstance(result.get(key), dict):
                # For nested dictionaries, merge them
                for sub_key, sub_default in default_value.items():
                    if sub_key not in result[key]:
                        result[key][sub_key] = sub_default
        
        return result
    
    def _detect_platform(self, url: str) -> str:
        """Detect the e-commerce platform from URL"""
        domain = urlparse(url).netloc.lower()
        
        # Platform detection patterns
        platforms = {
            'shopify': ['shopify', 'myshopify.com'],
            'woocommerce': ['woocommerce', 'wordpress'],
            'magento': ['magento'],
            'bigcommerce': ['bigcommerce'],
            'prestashop': ['prestashop'],
            'opencart': ['opencart'],
            'wix': ['wix.com'],
            'squarespace': ['squarespace'],
            'custom': []  # Default for custom platforms
        }
        
        for platform, patterns in platforms.items():
            if any(pattern in domain for pattern in patterns):
                return platform
        
        # Check for common e-commerce indicators
        if any(indicator in domain for indicator in ['shop', 'store', 'boutique', 'market']):
            return 'custom_ecommerce'
        
        return 'unknown'
    
    def _extract_brand_from_url(self, url: str) -> str:
        """Extract brand name from URL"""
        domain = urlparse(url).netloc
        # Remove www and domain extensions
        brand = domain.replace('www.', '').split('.')[0]
        # Capitalize first letter of each word
        return ' '.join(word.capitalize() for word in brand.split('-'))
    
    # Update the HTTP request methods in your UniversalEcommerceScraper class

    async def _extract_via_http_structured_data(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract product data using HTTP and structured data with better error handling"""
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Referer': 'https://www.google.com/',
                    'DNT': '1',
                }
                
                response = await client.get(url, headers=headers)
                
                if response.status_code == 422:
                    self.log(f"Received 422 error for {url}, trying alternative approach", "WARNING")
                    return None
                    
                if response.status_code != 200:
                    return None
                
                html = response.text
                
                # Try JSON-LD first (most reliable structured data)
                jsonld_data = self._parse_jsonld(html)
                if jsonld_data:
                    jsonld_data["extraction_method"] = "jsonld_structured_data"
                    return jsonld_data
                
                # Try JavaScript variables (common in many platforms)
                js_data = self._parse_javascript_variables(html)
                if js_data:
                    js_data["extraction_method"] = "javascript_variables"
                    return js_data
                
                # Try microdata (less common but still used)
                microdata = self._parse_microdata(html)
                if microdata:
                    microdata["extraction_method"] = "microdata"
                    return microdata
                
                # Try Open Graph and meta tags
                meta_data = self._parse_meta_tags(html)
                if meta_data:
                    meta_data["extraction_method"] = "meta_tags"
                    return meta_data
                
        except httpx.HTTPError as e:
            self.log(f"HTTP error for {url}: {e}", "DEBUG")
        except Exception as e:
            self.log(f"HTTP structured data extraction failed: {e}", "DEBUG")
        
        return None
    def _parse_jsonld(self, html: str) -> Optional[Dict[str, Any]]:
        """Parse JSON-LD structured data"""
        import json
        
        # Find all JSON-LD script tags
        pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
        
        for match in matches:
            try:
                data = json.loads(match.strip())
                
                # Handle arrays
                if isinstance(data, list):
                    data = next((item for item in data if item.get('@type') in ['Product', 'IndividualProduct']), None)
                
                # Check if it's a product
                if data and data.get('@type') in ['Product', 'IndividualProduct']:
                    offers = data.get('offers', {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    
                    # Extract images
                    images = []
                    image_data = data.get('image', [])
                    if isinstance(image_data, str):
                        images = [image_data]
                    elif isinstance(image_data, list):
                        images = [img if isinstance(img, str) else img.get('url', '') for img in image_data]
                    elif isinstance(image_data, dict):
                        images = [image_data.get('url', '')]
                    
                    return {
                        "product_name": data.get('name', ''),
                        "price": float(offers.get('price', 0)) if offers.get('price') else 0.0,
                        "product_images": images,
                        "description": data.get('description', ''),
                        "brand": data.get('brand', {}).get('name', '') if isinstance(data.get('brand'), dict) else str(data.get('brand', '')),
                        "sku": data.get('sku', ''),
                        "rating": data.get('aggregateRating', {}).get('ratingValue') if isinstance(data.get('aggregateRating'), dict) else None,
                        "review_count": data.get('aggregateRating', {}).get('reviewCount') if isinstance(data.get('aggregateRating'), dict) else None,
                    }
            except (json.JSONDecodeError, AttributeError, ValueError):
                continue
        
        return None
    
    def _parse_javascript_variables(self, html: str) -> Optional[Dict[str, Any]]:
        """Parse JavaScript variables containing product data"""
        import json
        
        # Common JavaScript variable patterns
        patterns = [
            r'window\.product\s*=\s*({.*?});',
            r'var\s+product\s*=\s*({.*?});',
            r'window\.productData\s*=\s*({.*?});',
            r'dataLayer\.push\(\s*({.*?"ecommerce".*?})\s*\);',
            r'product:\s*({.*?})',
            r'"product"\s*:\s*({.*?})',
            r'productInfo\s*=\s*({.*?});',
            r'itemData\s*=\s*({.*?});',
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
                    elif data.get('product'):
                        product_data = data['product']
                    
                    if product_data:
                        # Extract images
                        images = []
                        image_field = product_data.get('images') or product_data.get('image') or product_data.get('media')
                        if isinstance(image_field, str):
                            images = [image_field]
                        elif isinstance(image_field, list):
                            images = [img if isinstance(img, str) else img.get('url', '') for img in image_field]
                        
                        return {
                            "product_name": product_data.get('title') or product_data.get('name', ''),
                            "price": self._parse_price_from_data(product_data),
                            "product_images": images,
                            "description": product_data.get('description', '') or product_data.get('body_html', ''),
                            "sku": product_data.get('sku', ''),
                        }
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return None
    
    def _parse_price_from_data(self, data: Dict[str, Any]) -> float:
        """Parse price from product data"""
        # Try different price field names
        price_fields = ['price', 'current_price', 'regular_price', 'sale_price', 'amount', 'value', 'price_amount']
        
        for field in price_fields:
            if field in data:
                price_val = data[field]
                if isinstance(price_val, (int, float)):
                    return float(price_val)
                elif isinstance(price_val, str):
                    # Extract numeric value from string
                    numbers = re.findall(r'\d+\.?\d*', price_val)
                    if numbers:
                        try:
                            return float(numbers[0])
                        except ValueError:
                            continue
        
        # Try nested price structures
        if 'pricing' in data and isinstance(data['pricing'], dict):
            return self._parse_price_from_data(data['pricing'])
        
        if 'price_range' in data and isinstance(data['price_range'], dict):
            min_price = data['price_range'].get('min_price')
            if min_price:
                return self._parse_price_from_data({'price': min_price})
        
        return 0.0
    
    def _parse_microdata(self, html: str) -> Optional[Dict[str, Any]]:
        """Parse microdata (itemscope, itemtype, etc.)"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find product microdata
        product_elem = soup.find(attrs={'itemtype': 'http://schema.org/Product'})
        if not product_elem:
            return None
        
        result = {}
        
        # Extract name
        name_elem = product_elem.find(attrs={'itemprop': 'name'})
        if name_elem:
            result['product_name'] = name_elem.get_text(strip=True)
        
        # Extract price
        price_elem = product_elem.find(attrs={'itemprop': 'price'})
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            result['price'] = self._parse_price_text(price_text)
        
        # Extract description
        desc_elem = product_elem.find(attrs={'itemprop': 'description'})
        if desc_elem:
            result['description'] = desc_elem.get_text(strip=True)
        
        # Extract images
        image_elems = product_elem.find_all(attrs={'itemprop': 'image'})
        images = []
        for img_elem in image_elems:
            src = img_elem.get('src') or img_elem.get('content')
            if src:
                images.append(src)
        result['product_images'] = images
        
        return result if result else None
    
    def _parse_meta_tags(self, html: str) -> Optional[Dict[str, Any]]:
        """Parse meta tags for product information"""
        soup = BeautifulSoup(html, 'html.parser')
        
        result = {}
        
        # Extract from Open Graph tags
        og_title = soup.find('meta', property='og:title')
        og_price = soup.find('meta', property='product:price:amount')
        og_image = soup.find('meta', property='og:image')
        og_description = soup.find('meta', property='og:description')
        
        # Extract from Twitter cards
        twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        twitter_description = soup.find('meta', attrs={'name': 'twitter:description'})
        
        # Extract from standard meta tags
        meta_title = soup.find('meta', attrs={'name': 'title'})
        meta_description = soup.find('meta', attrs={'name': 'description'})
        
        # Build result
        if og_title:
            result['product_name'] = og_title.get('content', '')
        elif twitter_title:
            result['product_name'] = twitter_title.get('content', '')
        elif meta_title:
            result['product_name'] = meta_title.get('content', '')
        
        if og_price:
            try:
                result['price'] = float(og_price.get('content', 0))
            except ValueError:
                result['price'] = 0.0
        
        images = []
        if og_image:
            images.append(og_image.get('content', ''))
        if twitter_image:
            images.append(twitter_image.get('content', ''))
        result['product_images'] = images
        
        if og_description:
            result['description'] = og_description.get('content', '')
        elif twitter_description:
            result['description'] = twitter_description.get('content', '')
        elif meta_description:
            result['description'] = meta_description.get('content', '')
        
        # Only return if we found meaningful data
        if result.get('product_name') and result.get('product_name') != 'Unknown Product':
            return result
        
        return None
    
    async def _extract_via_http_html_parsing(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract product data using HTTP and HTML parsing"""
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                }
                
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    return {
                        "product_name": self._extract_product_name_universal(soup),
                        "price": self._extract_price_universal(soup),
                        "product_images": self._extract_images_universal(soup, url),
                        "description": self._extract_description_universal(soup),
                        "sizes": self._extract_sizes_universal(soup),
                        "colors": self._extract_colors_universal(soup),
                        "material": self._extract_material_universal(soup),
                        "extraction_method": "static_html_parsing"
                    }
        except Exception as e:
            self.log(f"HTTP HTML parsing failed: {e}", "DEBUG")
        
        return None
    
    def _extract_product_name_universal(self, soup: BeautifulSoup) -> str:
        """Extract product name using universal selectors"""
        selectors = [
            'h1.product-title', 'h1.product__title', 'h1[data-testid="product-title"]',
            '.product-single__title', '.product__title', 'h1.ProductItem-details-title',
            'h1.entry-title', 'h1.product_title', 'h1', '.product-title',
            '[data-product-title]', '.pdp-product-name', '.product-name',
            '.item-title', '.prod-title', '.title', '[itemprop="name"]',
            '.product-detail__title', '.product-name', '.productHeader',
            '.productTitle', '.product__name', '.productDetail__productName'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text and len(text) > 2:
                    return text
        
        # Fallback to page title
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text(strip=True).split('|')[0].strip()
        
        return "Unknown Product"
    
    def _extract_price_universal(self, soup: BeautifulSoup) -> float:
        """Extract price using universal selectors"""
        price_selectors = [
            '.price__current .money', '.product-price .money', '.price-current',
            '.current-price', '.price .money', '.price-item--regular',
            '.woocommerce-Price-amount', 'p.price', '.price',
            '[data-price]', '.ProductItem-details-checkout-price',
            '.price-now', '.current_price', '.regular-price', '.sale-price',
            '.product-price-value', '.price-box .price', '[itemprop="price"]',
            '.cost', '.amount', '.precio', '.prix', '.price-tag',
            '.product-price', '.product__price', '.price--large',
            '.productPrice', '.money', '.price__amount'
        ]
        
        for selector in price_selectors:
            elements = soup.select(selector)
            for element in elements:
                price_text = element.get_text(strip=True)
                price = self._parse_price_text(price_text)
                if price > 0:
                    return price
        
        return 0.0
    
    def _parse_price_text(self, price_text: str) -> float:
        """Parse price text to extract numeric value"""
        if not price_text:
            return 0.0
        
        # Extract all numbers with decimal points or commas
        numbers = re.findall(r'\d+[,.]?\d*', price_text)
        
        valid_prices = []
        for num in numbers:
            # Clean and convert to float
            cleaned = num.replace(',', '')
            try:
                price = float(cleaned)
                if price > 0:
                    valid_prices.append(price)
            except ValueError:
                continue
        
        if valid_prices:
            # Return the first valid price (usually the main price)
            return valid_prices[0]
        
        return 0.0
    
    def _extract_images_universal(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract product images using universal selectors"""
        images = []
        
        # Image selectors for different platforms
        selectors = [
            # Shopify selectors
            '.product__media img', '.product-single__photos img', '.ProductItem-gallery img',
            '.product-photos img', '.product-images img', '.product-media img',
            '.product__photo img',
            # WooCommerce selectors
            '.woocommerce-product-gallery img', '.product-images img', '.wp-post-image',
            # Generic selectors
            '[data-product-image] img', '.product-gallery img',
            # Universal selectors
            '.main-image img', '.product-image img', '.gallery img',
            '.image img', '.photo img', '.thumb img',
            '[itemprop="image"]', 'img[src*="product"]', 'img[alt*="product"]',
            '.product__image img', '.product-image-wrap img', '.product-slider img',
            '.swiper-slide img', '.slide img', '.carousel img',
            '.zoomImg', '.product-img', '.item-img'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for img in elements:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-large_image') or img.get('data-zoom-image')
                if src:
                    # Convert relative URLs to absolute
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = urljoin(base_url, src)
                    elif not src.startswith('http'):
                        src = urljoin(base_url, '/' + src.lstrip('/'))
                    
                    if src not in images and src.startswith('http'):
                        images.append(src)
        
        return images[:20]  # Limit to 20 images
    
    def _extract_description_universal(self, soup: BeautifulSoup) -> str:
        """Extract product description using universal selectors"""
        selectors = [
            # Shopify selectors
            '.product__description', '.product-single__description', '.ProductItem-details-excerpt',
            '.product-description', '.rte', '.product-single__description-full',
            # WooCommerce selectors
            '.woocommerce-product-details__short-description', '.product-short-description',
            '.entry-content',
            # Generic selectors
            '[data-product-description]', '.description', '.product-details',
            '.product-info', '.specs', '.details', '[itemprop="description"]',
            '.product__text', '.productDescription', '.product-desc',
            '.product__description-content', '.product-info__description',
            '.product-tabs__content', '.tab-content'
        ]
        
        for selector in selectors:
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
    
    def _extract_sizes_universal(self, soup: BeautifulSoup) -> List[str]:
        """Extract available sizes using universal selectors"""
        sizes = []
        
        # Size selectors for different platforms
        selectors = [
            'select[data-index="0"] option', 'select[name*="size"] option',
            '.variant-input-wrap:has(label:contains("Size")) input',
            '.product-form__option[data-option-name*="size"] .product-form__option-value',
            '[data-option="Size"] option', '.size-selector option',
            '.variant-option-size .variant-option-value',
            'select[data-attribute_name*="size"] option',
            'select[name*="attribute_pa_size"] option', '.variations select option',
            '.size-options option', '.product-options select option',
            '.swatch[data-option-name*="size"]', '.size-swatch',
            '.product__size', '.size-chart', '.size-guide'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                size = element.get_text(strip=True)
                if size and size.lower() not in ['default title', 'select size', 'choose an option'] and size not in sizes:
                    sizes.append(size)
        
        return sizes
    
    def _extract_colors_universal(self, soup: BeautifulSoup) -> List[str]:
        """Extract available colors using universal selectors"""
        colors = []
        
        # Color selectors for different platforms
        selectors = [
            'select[data-index="1"] option', 'select[name*="color"] option',
            '.variant-input-wrap:has(label:contains("Color")) input',
            '.product-form__option[data-option-name*="color"] .product-form__option-value',
            '[data-option="Color"] option', '.color-selector option',
            '.variant-option-color .variant-option-value',
            'select[data-attribute_name*="color"] option',
            'select[name*="attribute_pa_color"] option', '.variations select option',
            '.color-options option', '.product-options select option',
            '.swatch[data-option-name*="color"]', '.color-swatch',
            '.product__color', '.color-chart'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                color = element.get_text(strip=True)
                if color and color.lower() not in ['default title', 'select color', 'choose an option'] and color not in colors:
                    colors.append(color)
        
        return colors
    
    def _extract_material_universal(self, soup: BeautifulSoup) -> str:
        """Extract material information using universal selectors"""
        material_text = ""
        
        # Check description for material keywords
        description_selectors = [
            '.product__description', '.product-single__description',
            '.woocommerce-product-details__short-description', '.entry-content',
            '.description', '.product-details', '.specs', '.details'
        ]
        
        for selector in description_selectors:
            description = soup.select_one(selector)
            if description:
                text = description.get_text()
                
                # Look for material section
                material_match = re.search(r'(MATERIAL|FABRIC|COMPOSITION)[:\s]*(.*?)(?:PRODUCT|WASHING|$)', text, re.IGNORECASE | re.DOTALL)
                if material_match:
                    material_text = material_match.group(2).strip()[:200]
                    break
                
                # Look for material keywords
                material_keywords = ['cotton', 'silk', 'georgette', 'chiffon', 'organza', 'polyester', 'rayon', 'linen', 'wool', 'nylon', 'spandex', 'elastane', 'viscose']
                for keyword in material_keywords:
                    if keyword.lower() in text.lower():
                        # Extract sentence containing the material
                        sentences = text.split('.')
                        for sentence in sentences:
                            if keyword.lower() in sentence.lower():
                                material_text = sentence.strip()[:200]
                                break
                        if material_text:
                            break
                
                if material_text:
                    break
        
        return material_text
    
    async def _extract_via_browser(self, url: str, timeout_seconds: int) -> Optional[Dict[str, Any]]:
        """Browser extraction with specified timeout"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    # Set timeouts
                    page.set_default_timeout(timeout_seconds * 1000)
                    page.set_default_navigation_timeout(timeout_seconds * 1000)
                    
                    # Load with specified timeout
                    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
                    
                    # Progressive waiting based on timeout
                    if timeout_seconds >= 15:
                        try:
                            await page.wait_for_selector('h1, .price, .product-title', timeout=5000)
                        except:
                            pass
                    
                    # Wait proportional to timeout
                    await asyncio.sleep(min(timeout_seconds / 5, 4))
                    
                    if timeout_seconds >= 20:
                        try:
                            await page.wait_for_load_state("networkidle", timeout=8000)
                        except:
                            pass
                    
                    # Get content and parse
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    return {
                        "product_name": self._extract_product_name_universal(soup),
                        "price": self._extract_price_universal(soup),
                        "product_images": self._extract_images_universal(soup, url),
                        "description": self._extract_description_universal(soup),
                        "sizes": self._extract_sizes_universal(soup),
                        "colors": self._extract_colors_universal(soup),
                        "material": self._extract_material_universal(soup),
                        "extraction_method": f"browser_{timeout_seconds}s_timeout"
                    }
                    
                finally:
                    await browser.close()
        except Exception as e:
            self.log(f"Browser extraction with {timeout_seconds}s failed: {e}", "DEBUG")
            return None
    
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
        retry=tenacity.retry_if_exception_type(Exception)
    )
    async def extract_product_data(self, url: str) -> Dict[str, Any]:
        """Extract product data using universal hybrid approach"""
        return await self.extract_product_data_universal(url)
    # Add these methods to your UniversalEcommerceScraper class

    def _is_collection_url(self, url: str) -> bool:
        """Check if a URL is a collection/category page"""
        url_lower = url.lower()
        
        # Patterns that indicate collection pages
        collection_patterns = [
            '/collections/', '/collection/', '/category/', '/product-category/',
            '/shop/', '/products/', '/c/', '/browse/', '/all-products/', '/all/',
            '/list/', '/grid/', '/catalog/', '/boutique/', '/store/'
        ]
        
        # Patterns that indicate individual product pages
        product_patterns = [
            '/product/', '/item/', '/p/', '/detail/', '/prod/'
        ]
        
        # Check if it's definitely a collection
        for pattern in collection_patterns:
            if pattern in url_lower:
                # Make sure it's not a product page that happens to contain collection words
                if not any(p in url_lower for p in product_patterns):
                    return True
        
        # Check if it's definitely a product
        for pattern in product_patterns:
            if pattern in url_lower:
                return False
        
        # For URLs that don't match clear patterns, check content-based heuristics
        # This will be handled in the content analysis
        return False

    async def extract_from_collection(self, url: str, max_products: int = 50, 
                                progress_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """Extract all products from a collection page with progress reporting"""
        self.log(f"Processing collection: {url}")
        
        if progress_callback:
            await progress_callback(5, f"Extracting product URLs from {url}")
        
        # First try to extract product URLs using HTTP (faster)
        product_urls = await self._extract_product_urls_via_http(url, max_products)
        
        # If HTTP extraction failed, use browser
        if not product_urls:
            if progress_callback:
                await progress_callback(10, "Using browser to extract product URLs")
            product_urls = await self._extract_product_urls_via_browser(url, max_products)
        
        self.log(f"Found {len(product_urls)} product URLs in collection")
        
        if not product_urls:
            return []
        
        if progress_callback:
            await progress_callback(20, f"Found {len(product_urls)} products, starting extraction")
        
        # Process product URLs concurrently with a semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(3)  # Reduced from 5 to 3 to avoid overloading
        products = []
        completed = 0
        
        async def process_product(product_url):
            nonlocal completed
            async with semaphore:
                try:
                    # Try HTTP methods first for speed
                    http_result = await self._extract_via_http_structured_data(product_url)
                    if http_result and http_result.get("product_name") and http_result.get("product_name") != "Unknown Product":
                        result = http_result
                    else:
                        # Fall back to browser if HTTP methods fail
                        browser_result = await self._extract_via_browser(product_url, 10)
                        if browser_result and browser_result.get("product_name") and browser_result.get("product_name") != "Unknown Product":
                            result = browser_result
                        else:
                            result = None
                    
                    if result:
                        # Ensure all required fields are present
                        result = self._ensure_required_fields(result, product_url)
                        products.append(result)
                    
                    completed += 1
                    if progress_callback:
                        progress = 20 + (completed * 70 // len(product_urls))
                        await progress_callback(progress, f"Processed {completed}/{len(product_urls)} products")
                        
                    return result
                        
                except Exception as e:
                    self.log(f"Error processing product {product_url}: {e}", "ERROR")
                    completed += 1
                    return None
        
        # Create tasks for all product URLs
        tasks = [process_product(url) for url in product_urls[:max_products]]
        
        # Execute all tasks concurrently with a timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=120  # 2 minutes total timeout for all products
            )
        except asyncio.TimeoutError:
            self.log(f"Timeout processing collection {url}", "ERROR")
        
        if progress_callback:
            await progress_callback(95, "Finalizing product data")
        
        return products
    async def _extract_product_urls_from_collection(self, url: str, max_urls: int = 50) -> List[str]:
        """Extract product URLs from a collection page with optimized performance"""
        try:
            # First try HTTP extraction (faster than browser)
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.get(url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        return self._extract_product_urls_from_html(soup, url, max_urls)
            except:
                pass  # Fall back to browser if HTTP fails
            
            # If HTTP extraction fails, use browser
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    
                    # Extract product links directly with JavaScript for better performance
                    product_urls = await page.evaluate("""
                        () => {
                            const links = new Set();
                            // Select all potential product links
                            const selectors = [
                                'a[href*="/product/"]',
                                'a[href*="/products/"]',
                                'a[href*="/item/"]',
                                'a[href*="/p/"]',
                                '.product-item a',
                                '.product-card a',
                                '.product-link',
                                '.grid-product__link',
                                '.woocommerce-loop-product__link'
                            ];
                            
                            selectors.forEach(selector => {
                                document.querySelectorAll(selector).forEach(link => {
                                    const href = link.href;
                                    if (href && 
                                        !href.includes('/cart') && 
                                        !href.includes('/checkout') &&
                                        !href.includes('/account') &&
                                        !href.includes('/search') &&
                                        !href.includes('/contact') &&
                                        !href.includes('/about')) {
                                        links.add(href);
                                    }
                                });
                            });
                            
                            return Array.from(links).slice(0, 50); // Limit to 50 URLs
                        }
                    """)
                    
                    await browser.close()
                    return product_urls
                    
                except Exception as e:
                    await browser.close()
                    self.log(f"Error extracting product URLs from collection: {e}", "ERROR")
                    return []
                    
        except Exception as e:
            self.log(f"Error extracting product URLs: {e}", "ERROR")
            return []

    def _extract_product_urls_from_html(self, soup: BeautifulSoup, base_url: str, max_urls: int) -> List[str]:
        """Extract product URLs from HTML content"""
        urls = set()
        
        # Common product link patterns
        patterns = [
            'a[href*="/product/"]',
            'a[href*="/products/"]',
            'a[href*="/item/"]',
            'a[href*="/p/"]',
            '.product-item a',
            '.product-card a',
            '.product-link',
            '.grid-product__link',
            '.woocommerce-loop-product__link'
        ]
        
        for pattern in patterns:
            elements = soup.select(pattern)
            for element in elements:
                href = element.get('href')
                if href:
                    # Convert relative URLs to absolute
                    if href.startswith('//'):
                        href = 'https:' + href
                    elif href.startswith('/'):
                        href = urljoin(base_url, href)
                    elif not href.startswith('http'):
                        href = urljoin(base_url, '/' + href.lstrip('/'))
                    
                    # Filter out non-product URLs
                    if (href.startswith('http') and 
                        not any(exclude in href for exclude in ['/cart', '/checkout', '/account', '/search', '/contact', '/about']) and
                        len(urls) < max_urls):
                        urls.add(href)
        
        return list(urls)[:max_urls]
# In scraper_simple.py, update the scrape_urls_simple_api function
async def scrape_urls_simple_api(
    urls: List[str], 
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
    max_pages: int = 20
) -> Dict[str, Any]:
    """
    Simple API function to scrape product data from URLs
    """
    scraper = SimpleProductScraper(log_callback, progress_callback)
    
    try:
        scraper.log("Starting simple scraping process")
        scraper.update_progress("initialization", 5, "Setting up scraper")
        
        all_products = []
        total_pages_scraped = 0
        
        for i, url in enumerate(urls):
            scraper.update_progress("analyzing_urls", 10 + (i * 10), f"Processing URL {i+1}/{len(urls)}")
            
            # Check if it's a collection or individual product
            if scraper.is_collection_url(url):
                # Collection page - extract product links
                scraper.log(f"Detected collection page: {url}")
                product_links = await scraper.extract_collection_links(url)
                scraper.log(f"Found {len(product_links)} product links in collection")
                
                # Limit products per collection
                product_links = product_links[:max_pages]
                
                # Scrape each product
                for j, product_url in enumerate(product_links):
                    progress = 30 + ((i * len(product_links) + j) / (len(urls) * max_pages)) * 60
                    scraper.update_progress("scraping_products", int(progress), f"Scraping product {j+1}/{len(product_links)}")
                    
                    product_data = await scraper.extract_product_data(product_url)
                    if product_data and "error" not in product_data:
                        all_products.append(product_data)
                    
                    total_pages_scraped += 1
                    
                    # Small delay to be respectful
                    await asyncio.sleep(0.5)
            
            else:
                # Individual product page
                scraper.update_progress("scraping_products", 50, f"Scraping individual product")
                product_data = await scraper.extract_product_data(url)
                if product_data and "error" not in product_data:
                    all_products.append(product_data)
                total_pages_scraped += 1
        
        scraper.update_progress("completed", 100, f"Completed! Found {len(all_products)} products")
        scraper.log("Simple scraping completed successfully", "SUCCESS")
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result = {
            "metadata": {
                "timestamp": timestamp,
                "total_products": len(all_products),
                "total_pages_scraped": total_pages_scraped,
                "scraper_type": "simple-direct"
            },
            "products": all_products
        }
        
        # Save to logs directory
        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)
        
        output_file = os.path.join(logs_dir, f"simple_scrape_{timestamp}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        scraper.log(f"Results saved to {output_file}")
        
        return result
        
    except Exception as e:
        scraper.log(f"Error in simple scraping: {e}", "ERROR")
        raise e
def is_collection_url(self, url: str) -> bool:
    """Check if a URL is likely a collection/category page"""
    url_lower = url.lower()
    
    # Patterns that indicate collection pages
    collection_patterns = [
        '/collections/',
        '/collection/',
        '/category/',
        '/product-category/',
        '/shop/',
        '/products/',
        '/c/',
        '/browse/',
        '/all-products/',
        '/all/'
    ]
    
    # Patterns that indicate individual product pages
    product_patterns = [
        '/product/',
        '/products/',  # This can be both collection and product, so we need additional checks
        '/item/',
        '/p/'
    ]
    
    # Check if it's definitely a collection
    for pattern in collection_patterns:
        if pattern in url_lower and not any(p in url_lower for p in product_patterns if p != '/products/'):
            return True
    
    # Check if it's definitely a product
    for pattern in product_patterns:
        if pattern in url_lower:
            # Special case for /products/ which can be both
            if pattern == '/products/' and '/product/' in url_lower:
                continue  # This is likely a product page
            return False
    
    # Default to collection for e-commerce sites with unknown patterns
    ecommerce_domains = ['shop', 'store', 'boutique', 'market']
    domain = urlparse(url).netloc.lower()
    if any(ecom_domain in domain for ecom_domain in ecommerce_domains):
        return True
        
    return False