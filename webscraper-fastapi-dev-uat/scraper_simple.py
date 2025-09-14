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
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urljoin, urlparse
import re

from playwright.async_api import async_playwright
from pydantic import HttpUrl
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleProductScraper:
    """Simple product scraper using direct HTML parsing"""
    
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
    
    async def extract_product_data(self, url: str) -> Dict[str, Any]:
        """Extract product data from a single product page"""
        try:
            self.log(f"Extracting product data from: {url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Navigate to the page
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
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
    
    async def extract_collection_links(self, collection_url: str) -> List[str]:
        """Extract product links from a collection page"""
        try:
            self.log(f"Extracting product links from: {collection_url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                await page.goto(collection_url, wait_until="networkidle", timeout=30000)
                content = await page.content()
                await browser.close()
                
                soup = BeautifulSoup(content, 'html.parser')
                return self._extract_product_links(soup, collection_url)
                
        except Exception as e:
            self.log(f"Error extracting collection links from {collection_url}: {e}", "ERROR")
            return []
    
    def _extract_product_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract product links from collection page HTML"""
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
            # Generic selectors
            '[data-product-url]',
            'a[href*="/products/"]',
            'a[href*="/product/"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                href = element.get('href')
                if href:
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        href = urljoin(base_url, href)
                    
                    # Filter valid product URLs
                    if (href.startswith('http') and 
                        ('/products/' in href or '/product/' in href) and 
                        href not in links):
                        links.append(href)
        
        return links

# async def scrape_all_products(self, urls: List[str], browser, concurrency: int = 5):
#     semaphore = asyncio.Semaphore(concurrency)

#     async def scrape_single(url):
#         async with semaphore:
#             page = await browser.new_page()
#             await page.goto(url, wait_until="networkidle", timeout=30000)
#             content = await page.content()
#             await page.close()
#             soup = BeautifulSoup(content, 'html.parser')
#             return await self._parse_product_data(soup, url)

#     return await asyncio.gather(*[scrape_single(u) for u in urls])
# Update the scraper_simple.py with better concurrency
async def scrape_all_products(self, urls: List[str], browser, concurrency: int = 10):
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
    """Scrape a single product using an existing browser instance"""
    page = await browser.new_page()
    try:
        # Set timeout and navigation options for better performance
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        
        # Use evaluate to get HTML content faster
        content = await page.evaluate("document.documentElement.outerHTML")
        soup = BeautifulSoup(content, 'html.parser')
        
        return await self._parse_product_data(soup, url)
    except Exception as e:
        self.log(f"Error scraping {url}: {e}", "ERROR")
        return {
            "url": url,
            "product_name": "Error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
    finally:
        await page.close()

# Update the AI scraper for better performance
async def _scrape_products_from_page(self, page_url: str, known_product_links: List[str] = None) -> List[Dict[str, Any]]:
    """Scrape all products from a single page with performance improvements"""
    products = []
    
    try:
        # Use a single browser instance for all product scrapes
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            if known_product_links:
                product_links = known_product_links
            else:
                # Get page content and analyze
                html_content = await self._fetch_page_content(page_url)
                if not html_content:
                    return products
                
                if self.ai_agent:
                    analysis = await self.ai_agent.analyze_page_structure(html_content, page_url)
                    product_links = analysis.product_links
                else:
                    # Fallback product link extraction
                    soup = BeautifulSoup(html_content, 'html.parser')
                    product_links = []
                    for a in soup.select('a[href*="/products/"], a[href*="/product/"]'):
                        href = a.get('href')
                        if href:
                            if href.startswith('/'):
                                href = urljoin(page_url, href)
                            if href.startswith('http'):
                                product_links.append(href)
            
            # Scrape products concurrently
            tasks = []
            for product_url in product_links[:20]:  # Limit to avoid too many requests
                tasks.append(self._scrape_single_product_with_browser(product_url, browser))
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Add successful results
            for result in results:
                if not isinstance(result, Exception) and "error" not in result:
                    products.append(result)
                    self.stats["products_found"] += 1
            
            await browser.close()
        
    except Exception as e:
        self.log(f"Error scraping products from page {page_url}: {e}", "ERROR")
    
    return products
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
            if '/collections/' in url or '/category/' in url or '/shop' in url:
                # Collection page - extract product links
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
# inside SimpleProductScraper class (scraper_simple.py)

# Update the scrape_collection_with_pagination method in SimpleProductScraper class
async def scrape_collection_with_pagination(self, url: str, max_pages: int = 20):
    """Scrape all products across paginated collection/category pages"""
    all_products = []
    current_url = url
    page_num = 1

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        while current_url and page_num <= max_pages:
            self.log(f"Scraping page {page_num}: {current_url}")
            await page.goto(current_url, wait_until="networkidle", timeout=60000)
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Extract product links
            product_links = self._extract_product_links(soup, current_url)
            self.log(f"Found {len(product_links)} product links on page {page_num}")

            if not product_links:
                self.log("⚠️ No product links found, stopping.", "WARNING")
                break

            # Scrape products in parallel
            products = await self.scrape_all_products(product_links, browser)
            all_products.extend(products)

            # Enhanced pagination detection
            next_page_url = self._find_next_page_url(soup, current_url)
            if next_page_url and next_page_url != current_url:
                current_url = next_page_url
                page_num += 1
            else:
                current_url = None  # no more pages

        await browser.close()
    return all_products

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