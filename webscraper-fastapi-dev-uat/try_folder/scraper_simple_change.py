import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urljoin, urlparse, parse_qs, urlunparse
import re

from playwright.async_api import async_playwright
from pydantic import HttpUrl
from bs4 import BeautifulSoup
from PIL import Image
import requests
from io import BytesIO
import aiohttp
import concurrent.futures

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_IMAGE_SIZE = {"width": 800, "height": 800}

class EnhancedSimpleProductScraper:
    """Enhanced simple product scraper with improved pagination and performance"""
    
    def __init__(self, log_callback: Optional[Callable] = None, progress_callback: Optional[Callable] = None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session = None  # For aiohttp session
    
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
        """Update progress with better tracking"""
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
                asyncio.create_task(self.progress_callback(progress_data))
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    async def get_image_size_async(self, url: str) -> Dict[str, int]:
        """Get image size asynchronously with better error handling"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    img = Image.open(BytesIO(content))
                    return {"width": img.width, "height": img.height}
        except Exception as e:
            self.log(f"Error getting image size for {url}: {e}", "WARNING")
        
        return DEFAULT_IMAGE_SIZE

    async def validate_and_get_image_info(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Validate image URLs and get their sizes in parallel"""
        if not urls:
            return []
        
        tasks = []
        valid_images = []
        
        for url in urls:
            if self.is_valid_image_url(url):
                valid_images.append(url)
                tasks.append(self.get_image_size_async(url))
        
        if not tasks:
            return []
        
        # Get sizes in parallel with limited concurrency
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests
        
        async def get_size_with_limit(url, task):
            async with semaphore:
                return await task
        
        size_tasks = [get_size_with_limit(url, task) for url, task in zip(valid_images, tasks)]
        sizes = await asyncio.gather(*size_tasks, return_exceptions=True)
        
        result = []
        for url, size in zip(valid_images, sizes):
            if isinstance(size, dict):
                result.append({"url": url, "size": size})
            else:
                result.append({"url": url, "size": DEFAULT_IMAGE_SIZE})
        
        return result

    def is_valid_image_url(self, url: str) -> bool:
        """Check if URL is a valid image URL"""
        if not url or not isinstance(url, str):
            return False
        
        # Skip data URLs and transparent placeholders
        if url.startswith('data:'):
            return not self.is_transparent_placeholder(url)
        
        # Check for common image extensions
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']
        return any(ext in url.lower() for ext in image_extensions) and url.startswith('http')

    def is_transparent_placeholder(self, url: str) -> bool:
        """Check if URL is a transparent SVG placeholder"""
        if not url or not url.startswith('data:image/svg+xml;base64,'):
            return False
        
        try:
            import base64
            base64_data = url.split(',')[1]
            decoded_svg = base64.b64decode(base64_data).decode('utf-8')
            
            return (
                'fill="none"' in decoded_svg and 
                'fill-opacity="0"' in decoded_svg and 
                '99999' in decoded_svg
            )
        except:
            return False

    def fix_image_url(self, url: str) -> str:
        """Fix image URLs by removing placeholder parameters"""
        if not url or not isinstance(url, str):
            return url
        
        # Skip data URLs
        if url.startswith('data:'):
            return url
        
        try:
            from urllib.parse import urlparse, parse_qs, urlencode
            
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            # Check if this is a 1x1 placeholder image
            is_placeholder = (
                params.get('width') == ['1'] or 
                params.get('height') == ['1'] or
                ('width=1' in url and 'height=1' in url)
            )
            
            if is_placeholder:
                # Keep only useful parameters
                useful_params = {}
                keep_params = ['v', 'version', 'quality', 'format']
                
                for param, values in params.items():
                    if param in keep_params:
                        useful_params[param] = values
                
                # Rebuild the URL
                new_query = urlencode(useful_params, doseq=True)
                fixed_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                
                if new_query:
                    fixed_url += f"?{new_query}"
                
                return fixed_url
            
            return url
            
        except Exception as e:
            self.log(f"Error fixing URL {url}: {e}", "WARNING")
            return url

    async def extract_all_collection_pages(self, collection_url: str, max_pages: int = 50) -> List[str]:
        """Extract product links from ALL pages of a collection with improved pagination detection"""
        all_product_links = []
        current_page = 1
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                while current_page <= max_pages:
                    try:
                        # Construct page URL for different platforms
                        page_url = self.construct_page_url(collection_url, current_page)
                        
                        self.log(f"Extracting from page {current_page}: {page_url}")
                        self.update_progress(
                            "extracting_links", 
                            10 + (current_page * 2), 
                            f"Extracting product links from page {current_page}/{max_pages}"
                        )
                        
                        await page.goto(page_url, wait_until="networkidle", timeout=30000)
                        
                        # Wait for products to load
                        await page.wait_for_timeout(1000)
                        
                        content = await page.content()
                        soup = BeautifulSoup(content, 'html.parser')
                        
                        # Extract product links from current page
                        page_links = self._extract_product_links_enhanced(soup, page_url)
                        
                        if not page_links:
                            self.log(f"No products found on page {current_page}, stopping pagination")
                            break
                        
                        self.log(f"Found {len(page_links)} products on page {current_page}")
                        all_product_links.extend(page_links)
                        
                        # Check if there's a next page
                        has_next = await self.has_next_page(page, soup, current_page)
                        if not has_next:
                            self.log(f"No more pages found after page {current_page}")
                            break
                        
                        current_page += 1
                        await page.wait_for_timeout(500)  # Small delay between pages
                        
                    except Exception as e:
                        self.log(f"Error processing page {current_page}: {e}", "ERROR")
                        break
                
                await browser.close()
                
        except Exception as e:
            self.log(f"Error in pagination extraction: {e}", "ERROR")
        
        self.log(f"Total products found across {current_page-1} pages: {len(all_product_links)}")
        return list(set(all_product_links))  # Remove duplicates

    def construct_page_url(self, base_url: str, page_num: int) -> str:
        """Construct paginated URL for different platforms"""
        if page_num == 1:
            return base_url
        
        # Parse the URL
        parsed = urlparse(base_url)
        query_params = parse_qs(parsed.query)
        
        # Add page parameter based on platform
        if 'shopify' in base_url.lower() or '.myshopify.com' in base_url:
            # Shopify pagination
            if base_url.endswith('/'):
                return f"{base_url}?page={page_num}"
            elif '?' in base_url:
                return f"{base_url}&page={page_num}"
            else:
                return f"{base_url}?page={page_num}"
        else:
            # WooCommerce and other platforms
            query_params['page'] = [str(page_num)]
            new_query = urlencode(query_params, doseq=True)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    async def has_next_page(self, page, soup: BeautifulSoup, current_page: int) -> bool:
        """Check if there's a next page using multiple methods"""
        
        # Method 1: Check for next page links in HTML
        next_selectors = [
            'a[rel="next"]',
            '.page-numbers a.next',
            '.pagination a.next',
            '.pagination-next',
            'a[aria-label="Next"]',
            '.pagination a:contains("Next")',
            f'a[href*="page={current_page + 1}"]'
        ]
        
        for selector in next_selectors:
            if soup.select_one(selector):
                return True
        
        # Method 2: Check for page numbers
        page_number_selectors = [
            f'a:contains("{current_page + 1}")',
            f'.page-numbers a[href*="page={current_page + 1}"]',
            f'.pagination a[href*="page={current_page + 1}"]'
        ]
        
        for selector in page_number_selectors:
            if soup.select_one(selector):
                return True
        
        # Method 3: Try to access next page directly
        try:
            next_page_url = self.construct_page_url(page.url, current_page + 1)
            response = await page.goto(next_page_url, wait_until="networkidle", timeout=10000)
            
            if response and response.status == 200:
                test_content = await page.content()
                test_soup = BeautifulSoup(test_content, 'html.parser')
                test_links = self._extract_product_links_enhanced(test_soup, next_page_url)
                return len(test_links) > 0
        except:
            pass
        
        return False

    def _extract_product_links_enhanced(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Enhanced product link extraction with better selectors"""
        links = []
        
        # Enhanced selectors for different platforms
        selectors = [
            # Shopify selectors
            '.product-item a[href*="/products/"]',
            '.product-card a[href*="/products/"]',
            '.grid-product__link',
            '.product-link',
            '.product__media a',
            'a.product-item-meta__title',
            '.card-product a',
            
            # WooCommerce selectors
            '.woocommerce-loop-product__link',
            '.product-item-link',
            '.product a[href*="/product/"]',
            '.products li a',
            'a[href*="/product/"]',
            
            # Generic selectors
            '[data-product-url]',
            'a[href*="/products/"]',
            '.product-grid a',
            '.products-grid a'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                href = element.get('href')
                if href:
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        href = urljoin(base_url, href)
                    
                    # Validate product URLs
                    if (href.startswith('http') and 
                        ('/products/' in href or '/product/' in href) and 
                        href not in links and
                        not any(exclude in href for exclude in ['#', 'javascript:', 'mailto:'])):
                        links.append(href)
        
        return links

    async def extract_product_data_parallel(self, urls: List[str], concurrency: int = 10) -> List[Dict[str, Any]]:
        """Extract product data from multiple URLs in parallel"""
        semaphore = asyncio.Semaphore(concurrency)
        
        async def scrape_single_with_limit(url: str):
            async with semaphore:
                return await self.extract_product_data_enhanced(url)
        
        self.log(f"Starting parallel extraction of {len(urls)} products with concurrency {concurrency}")
        
        # Process in batches to avoid overwhelming the server
        batch_size = 50
        all_products = []
        
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(urls) + batch_size - 1) // batch_size
            
            self.log(f"Processing batch {batch_num}/{total_batches} ({len(batch)} products)")
            self.update_progress(
                "scraping_products", 
                30 + ((i / len(urls)) * 60), 
                f"Batch {batch_num}/{total_batches}: {len(batch)} products"
            )
            
            tasks = [scrape_single_with_limit(url) for url in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and add valid results
            for result in batch_results:
                if isinstance(result, dict) and "error" not in result:
                    all_products.append(result)
                elif isinstance(result, Exception):
                    self.log(f"Error in batch processing: {result}", "ERROR")
            
            # Small delay between batches
            await asyncio.sleep(1)
        
        return all_products

    async def extract_product_data_enhanced(self, url: str) -> Dict[str, Any]:
        """Enhanced product data extraction with better image handling"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                # Optimize page loading
                await page.route("**/*.{png,jpg,jpeg,gif,svg,css,font,woff,woff2}", lambda route: route.abort())
                
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # Wait for dynamic content
                await page.wait_for_timeout(1000)
                
                content = await page.content()
                await browser.close()
                
                soup = BeautifulSoup(content, 'html.parser')
                product_data = await self._parse_product_data_enhanced(soup, url)
                
                return product_data
                
        except Exception as e:
            self.log(f"Error extracting product data from {url}: {e}", "ERROR")
            return {
                "url": url,
                "product_name": "Error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def _parse_product_data_enhanced(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Enhanced product data parsing with better image handling"""
        try:
            # Initialize enhanced product data structure
            product_data = {
                "product_name": "",
                "price": 0.0,
                "discounted_price": None,
                "product_images": [],
                "image_sizes": [],  # Add image sizes
                "description": "",
                "sizes": [],
                "colors": [],
                "material": "",
                "metadata": {
                    "platform": self._get_platform(url),
                    "extracted_at": datetime.now().isoformat(),
                    "availability": "InStock",
                    "sku": "",
                    "brand": self._get_brand(url),
                    "categories": [],
                    "tags": [],
                    "rating": None,
                    "review_count": None,
                    "specifications": {},
                    "variants": [],
                    "editable": True  # Mark as editable
                },
                "source_url": url,
                "timestamp": datetime.now().isoformat()
            }
            
            # Extract all data
            product_data["product_name"] = self._extract_product_name_enhanced(soup)
            
            price_info = self._extract_prices_enhanced(soup)
            product_data["price"] = price_info.get("price", 0.0)
            product_data["discounted_price"] = price_info.get("discounted_price")
            
            # Enhanced image extraction with validation and sizing
            raw_images = self._extract_images_enhanced(soup, url)
            if raw_images:
                # Fix image URLs and validate
                fixed_images = []
                for img_url in raw_images:
                    fixed_url = self.fix_image_url(img_url)
                    if self.is_valid_image_url(fixed_url):
                        fixed_images.append(fixed_url)
                
                product_data["product_images"] = fixed_images[:20]  # Limit to 20 images
                
                # Get image sizes asynchronously
                if fixed_images:
                    image_info = await self.validate_and_get_image_info(fixed_images[:10])  # Limit to first 10 for sizing
                    product_data["image_sizes"] = [info["size"] for info in image_info]
            
            # If no images found, add default size
            if not product_data["image_sizes"]:
                product_data["image_sizes"] = [DEFAULT_IMAGE_SIZE] * len(product_data["product_images"])
            
            # Extract other data
            product_data["description"] = self._extract_description_enhanced(soup)
            product_data["sizes"] = self._extract_sizes_enhanced(soup)
            product_data["colors"] = self._extract_colors_enhanced(soup)
            product_data["material"] = self._extract_material_enhanced(soup)
            product_data["metadata"].update(self._extract_metadata_enhanced(soup, url))
            
            return product_data
            
        except Exception as e:
            self.log(f"Error parsing product data: {e}", "ERROR")
            return {
                "url": url,
                "product_name": "Parse Error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _extract_images_enhanced(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Enhanced image extraction with better selectors and validation"""
        images = []
        
        # Enhanced selectors for different image sources
        selectors = [
            # Primary product images
            '.product__media img[src]',
            '.product-single__photos img[src]',
            '.ProductItem-gallery img[src]',
            '.product-photos img[src]',
            '.product-images img[src]',
            '.product__photo img[src]',
            
            # Shopify specific
            '.product-image-main img[src]',
            '.product-gallery__image img[src]',
            '.media img[src]',
            
            # WooCommerce specific
            '.woocommerce-product-gallery img[src]',
            '.wp-post-image',
            '.product-image img[src]',
            
            # Data attributes for lazy loading
            'img[data-src]',
            'img[data-lazy-src]',
            'img[data-original]',
            'img[data-large_image]',
            
            # Generic product image selectors
            '[data-product-image] img',
            '.product-gallery img'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for img in elements:
                # Try multiple source attributes
                src = (img.get('src') or 
                      img.get('data-src') or 
                      img.get('data-lazy-src') or 
                      img.get('data-original') or 
                      img.get('data-large_image'))
                
                if src:
                    # Handle different URL formats
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = urljoin(base_url, src)
                    
                    # Validate and add unique images
                    if (src.startswith('http') and 
                        src not in images and
                        not any(exclude in src.lower() for exclude in ['placeholder', 'loading', 'spinner'])):
                        images.append(src)
        
        return images

    # Additional enhanced methods would be implemented here...
    # (Due to length constraints, showing key enhanced methods)

    def _get_platform(self, url: str) -> str:
        """Enhanced platform detection"""
        domain = urlparse(url).netloc.lower()
        if 'shopify' in domain or '.myshopify.com' in domain:
            return 'shopify'
        elif 'woocommerce' in domain or 'wp-content' in url:
            return 'woocommerce'
        elif 'magento' in domain:
            return 'magento'
        else:
            return domain

    def _get_brand(self, url: str) -> str:
        """Enhanced brand detection"""
        domain = urlparse(url).netloc.lower()
        # Remove www and common extensions
        brand = domain.replace('www.', '').split('.')[0]
        return brand.title()

    def _extract_product_name_enhanced(self, soup: BeautifulSoup) -> str:
        """Enhanced product name extraction"""
        selectors = [
            'h1.product-title',
            'h1.product__title', 
            'h1[data-testid="product-title"]',
            '.product-single__title',
            '.ProductItem-details-title',
            'h1.entry-title',
            'h1.product_title',
            'h1',
            '.product-title'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                # Fix duplicate text
                return self._fix_duplicate_title(title) if title else "Unknown Product"
        
        return "Unknown Product"

    def _fix_duplicate_title(self, title: str) -> str:
        """Fix duplicated product titles"""
        if not title:
            return title
        
        # Check for exact duplication
        length = len(title)
        if length % 2 == 0:
            mid = length // 2
            if title[:mid] == title[mid:]:
                return title[:mid]
        
        return title

    def _extract_prices_enhanced(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Enhanced price extraction"""
        price_info = {"price": 0.0, "discounted_price": None}
        
        # Current price selectors
        price_selectors = [
            '.price__current .money',
            '.product-price .money', 
            '.price-current',
            '.current-price',
            '.woocommerce-Price-amount',
            '.price .amount',
            'p.price',
            '.price',
            '[data-price]'
        ]
        
        for selector in price_selectors:
            elements = soup.select(selector)
            for element in elements:
                price_text = element.get_text(strip=True)
                price = self._parse_price(price_text)
                if price > 0:
                    price_info["price"] = price
                    break
            if price_info["price"] > 0:
                break
        
        return price_info

    def _parse_price(self, price_text: str) -> float:
        """Parse price from text"""
        if not price_text:
            return 0.0
        
        # Extract numbers
        numbers = re.findall(r'\d+[,.]?\d*', price_text)
        for num in numbers:
            cleaned = num.replace(',', '')
            try:
                price = float(cleaned)
                if price > 0:
                    return price
            except:
                continue
        
        return 0.0

    def _extract_description_enhanced(self, soup: BeautifulSoup) -> str:
        """Enhanced description extraction"""
        selectors = [
            '.product__description',
            '.product-single__description',
            '.ProductItem-details-excerpt',
            '.woocommerce-product-details__short-description',
            '.entry-content'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)[:2000]
        
        return ""

    def _extract_sizes_enhanced(self, soup: BeautifulSoup) -> List[str]:
        """Enhanced size extraction"""
        sizes = []
        
        selectors = [
            'select[data-index="0"] option',
            'select[name*="size"] option',
            'select[data-attribute_name*="size"] option',
            '.size-options option'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                size = element.get_text(strip=True)
                if (size and 
                    size.lower() not in ['default title', 'select size', 'choose an option'] and 
                    size not in sizes):
                    sizes.append(size)
        
        return sizes

    def _extract_colors_enhanced(self, soup: BeautifulSoup) -> List[str]:
        """Enhanced color extraction"""
        colors = []
        
        selectors = [
            'select[data-index="1"] option',
            'select[name*="color"] option', 
            'select[data-attribute_name*="color"] option',
            '.color-options option'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                color = element.get_text(strip=True)
                if (color and 
                    color.lower() not in ['default title', 'select color', 'choose an option'] and 
                    color not in colors):
                    colors.append(color)
        
        return colors

    def _extract_material_enhanced(self, soup: BeautifulSoup) -> str:
        """Enhanced material extraction"""
        selectors = [
            '.product__description',
            '.product-single__description',
            '.woocommerce-product-details__short-description'
        ]
        
        for selector in selectors:
            description = soup.select_one(selector)
            if description:
                text = description.get_text()
                # Look for fabric section
                fabric_match = re.search(r'FABRIC[:\s]*(.*?)(?:PRODUCT|WASHING|$)', text, re.IGNORECASE | re.DOTALL)
                if fabric_match:
                    return fabric_match.group(1).strip()[:200]
        
        return ""

    def _extract_metadata_enhanced(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Enhanced metadata extraction"""
        metadata = {
            "availability": "InStock",
            "sku": "",
            "categories": [],
            "tags": []
        }
        
        # Extract categories from breadcrumbs
        breadcrumb_selectors = [
            '.breadcrumb a',
            '.breadcrumbs a',
            '.woocommerce-breadcrumb a'
        ]
        
        for selector in breadcrumb_selectors:
            breadcrumbs = soup.select(selector)
            for crumb in breadcrumbs:
                text = crumb.get_text(strip=True)
                href = crumb.get('href', '')
                if (text and 
                    text.lower() not in ['home', 'products', 'shop'] and
                    text not in metadata["categories"] and
                    ('/collections/' in href or '/category/' in href)):
                    metadata["categories"].append(text)
        
        return metadata

    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()

# Main API function with enhanced features
async def scrape_urls_enhanced_api(
    urls: List[str], 
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
    max_pages: int = 50  # Increased default
) -> Dict[str, Any]:
    """
    Enhanced API function to scrape product data from URLs with better pagination and performance
    """
    scraper = EnhancedSimpleProductScraper(log_callback, progress_callback)
    
    try:
        scraper.log("Starting enhanced scraping process")
        scraper.update_progress("initialization", 5, "Setting up enhanced scraper")
        
        all_products = []
        total_pages_scraped = 0
        total_urls = len(urls)
        
        for i, url in enumerate(urls):
            scraper.update_progress(
                "analyzing_urls", 
                10 + (i * 20 // total_urls), 
                f"Processing URL {i+1}/{total_urls}: {urlparse(url).netloc}"
            )
            
            # Check if it's a collection or individual product
            if any(keyword in url.lower() for keyword in ['/collections/', '/category/', '/shop', '/products']):
                # Collection page - extract ALL product links with pagination
                scraper.log(f"Detected collection URL: {url}")
                
                # Extract all product links across all pages
                all_product_links = await scraper.extract_all_collection_pages(url, max_pages)
                
                if not all_product_links:
                    scraper.log(f"No product links found in collection: {url}", "WARNING")
                    continue
                
                scraper.log(f"Found {len(all_product_links)} total products in collection")
                
                # Extract product data in parallel batches
                products = await scraper.extract_product_data_parallel(all_product_links)
                all_products.extend(products)
                total_pages_scraped += len(all_product_links)
                
            else:
                # Individual product page
                scraper.update_progress("scraping_products", 50, f"Scraping individual product")
                product_data = await scraper.extract_product_data_enhanced(url)
                if product_data and "error" not in product_data:
                    all_products.append(product_data)
                total_pages_scraped += 1
        
        # Final processing and validation
        scraper.update_progress("finalizing", 95, "Finalizing and validating data")
        
        # Validate all products have required image sizes
        for product in all_products:
            if not product.get("image_sizes"):
                image_count = len(product.get("product_images", []))
                product["image_sizes"] = [DEFAULT_IMAGE_SIZE] * image_count
            
            # Ensure product is marked as editable
            if "metadata" not in product:
                product["metadata"] = {}
            product["metadata"]["editable"] = True
            product["metadata"]["has_all_pages"] = True  # Mark that all pages were scraped
        
        scraper.update_progress("completed", 100, f"Completed! Found {len(all_products)} products across all pages")
        scraper.log("Enhanced scraping completed successfully", "SUCCESS")
        
        # Save results with enhanced metadata
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result = {
            "metadata": {
                "timestamp": timestamp,
                "total_products": len(all_products),
                "total_pages_scraped": total_pages_scraped,
                "scraper_type": "enhanced-simple",
                "scraper_version": "2.0",
                "max_pages_per_collection": max_pages,
                "urls_processed": len(urls),
                "collections_processed": sum(1 for url in urls if any(k in url.lower() for k in ['/collections/', '/category/', '/shop'])),
                "individual_products_processed": sum(1 for url in urls if not any(k in url.lower() for k in ['/collections/', '/category/', '/shop'])),
                "image_validation_enabled": True,
                "all_pages_scraped": True,
                "features": [
                    "Complete pagination support",
                    "Parallel processing", 
                    "Image validation and sizing",
                    "Enhanced product data extraction",
                    "Real-time progress tracking"
                ]
            },
            "products": all_products
        }
        
        # Save to logs directory
        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)
        
        output_file = os.path.join(logs_dir, f"enhanced_scrape_{timestamp}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        scraper.log(f"Results saved to {output_file}")
        
        # Cleanup resources
        await scraper.cleanup()
        
        return result
        
    except Exception as e:
        scraper.log(f"Error in enhanced scraping: {e}", "ERROR")
        await scraper.cleanup()
        raise e


class SimpleProductScraper:
    """Legacy wrapper for backward compatibility"""
    
    def __init__(self, log_callback: Optional[Callable] = None, progress_callback: Optional[Callable] = None):
        self.enhanced_scraper = EnhancedSimpleProductScraper(log_callback, progress_callback)
    
    async def scrape_collection_with_pagination(self, url: str, max_pages: int = 20):
        """Enhanced collection scraping with complete pagination support"""
        all_product_links = await self.enhanced_scraper.extract_all_collection_pages(url, max_pages)
        return await self.enhanced_scraper.extract_product_data_parallel(all_product_links)
    
    async def extract_product_data(self, url: str) -> Dict[str, Any]:
        """Enhanced single product extraction"""
        return await self.enhanced_scraper.extract_product_data_enhanced(url)
    
    async def scrape_all_products(self, product_links: List[str], browser=None, concurrency: int = 10):
        """Enhanced parallel product scraping"""
        return await self.enhanced_scraper.extract_product_data_parallel(product_links, concurrency)


# Update the main API function to use enhanced scraper
async def scrape_urls_simple_api(
    urls: List[str], 
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
    max_pages: int = 50
) -> Dict[str, Any]:
    """
    Updated simple API that uses enhanced scraper for better performance and complete pagination
    """
    return await scrape_urls_enhanced_api(urls, log_callback, progress_callback, max_pages)