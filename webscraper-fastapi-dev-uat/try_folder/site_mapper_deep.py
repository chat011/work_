# site_mapper_deep.py
"""
Site Mapper for discovering all URLs on a website
"""
import asyncio
import logging
from urllib.parse import urlparse, urljoin, urlunparse
from typing import List, Set, Dict, Any
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SiteMapper:
    """Discovers all URLs on a website with intelligent filtering"""
    
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.visited_urls: Set[str] = set()
        self.all_urls: Set[str] = set()
        self.discovered_collections: Set[str] = set()
        self.discovered_products: Set[str] = set()
        self.discovered_pages: Set[str] = set()
    
    def log(self, message: str, level: str = "INFO"):
        """Log messages with callback support"""
        if self.log_callback:
            self.log_callback({"message": message, "level": level})
        logger.log(getattr(logging, level), message)
    
    def normalize_url(self, url: str, base_url: str) -> str:
        """Normalize URL to a standard form"""
        parsed = urlparse(url)
        base_parsed = urlparse(base_url)
        
        # Handle relative URLs
        if not parsed.netloc:
            url = urljoin(base_url, url)
            parsed = urlparse(url)
        
        # Remove fragments and query parameters for normalization
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            '',  # params
            '',  # query
            ''   # fragment
        ))
        
        # Ensure URL ends with slash for root paths
        if not parsed.path:
            normalized = normalized.rstrip('/') + '/'
        
        return normalized
    
    def is_same_domain(self, url: str, base_url: str) -> bool:
        """Check if URL is from the same domain"""
        parsed_url = urlparse(url)
        parsed_base = urlparse(base_url)
        return parsed_url.netloc == parsed_base.netloc
    
    def should_crawl(self, url: str, base_url: str) -> bool:
        """Determine if a URL should be crawled"""
        # Check if same domain
        if not self.is_same_domain(url, base_url):
            return False
        
        # Check if already visited
        normalized = self.normalize_url(url, base_url)
        if normalized in self.visited_urls:
            return False
        
        # Check for common exclusions
        excluded_patterns = [
            r'\.(pdf|jpg|jpeg|png|gif|css|js|zip|rar|tar|gz)$',
            r'/cdn-cgi/',
            r'/wp-admin/',
            r'/wp-includes/',
            r'/checkout/',
            r'/cart/',
            r'/account/',
            r'/login/',
            r'/register/',
            r'/search/',
            r'/api/',
            r'/ajax/',
        ]
        
        for pattern in excluded_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        return True
    
    def categorize_url(self, url: str) -> str:
        """Categorize URL type"""
        url_lower = url.lower()
        
        # Product patterns
        product_patterns = [
            r'/product/',
            r'/products/',
            r'/item/',
            r'/p/',
            r'\.html.*product',
            r'-product-',
        ]
        
        # Collection patterns
        collection_patterns = [
            r'/collection/',
            r'/collections/',
            r'/category/',
            r'/categories/',
            r'/shop/',
            r'/browse/',
        ]
        
        for pattern in product_patterns:
            if re.search(pattern, url_lower):
                return "product"
        
        for pattern in collection_patterns:
            if re.search(pattern, url_lower):
                return "collection"
        
        return "page"
    
    async def extract_links_from_page(self, url: str) -> List[str]:
        """Extract all links from a page"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Set longer timeout for comprehensive crawling
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Wait for page to fully load
                await page.wait_for_load_state("networkidle")
                
                # Extract all links
                links = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('a[href]')).map(a => a.href);
                }''')
                
                await browser.close()
                return links
                
        except Exception as e:
            self.log(f"Error extracting links from {url}: {e}", "ERROR")
            return []
    
    async def crawl_site(self, base_url: str, max_pages: int = 100) -> Dict[str, Any]:
        """Crawl the entire site starting from base URL"""
        self.log(f"Starting site crawl for: {base_url}")
        
        # Ensure base URL ends with slash
        if not base_url.endswith('/'):
            base_url += '/'
        
        # Initialize queue with base URL
        queue = [base_url]
        self.visited_urls.add(self.normalize_url(base_url, base_url))
        
        page_count = 0
        
        while queue and page_count < max_pages:
            current_url = queue.pop(0)
            page_count += 1
            
            self.log(f"Crawling page {page_count}: {current_url}")
            
            # Extract links from current page
            links = await self.extract_links_from_page(current_url)
            
            # Process each link
            for link in links:
                if not link or not isinstance(link, str):
                    continue
                
                # Normalize and check if we should crawl
                normalized = self.normalize_url(link, base_url)
                
                if self.should_crawl(normalized, base_url):
                    # Add to visited URLs
                    self.visited_urls.add(normalized)
                    self.all_urls.add(normalized)
                    
                    # Categorize URL
                    url_type = self.categorize_url(normalized)
                    
                    if url_type == "product":
                        self.discovered_products.add(normalized)
                    elif url_type == "collection":
                        self.discovered_collections.add(normalized)
                        # Add collection to queue for further crawling
                        queue.append(normalized)
                    else:
                        self.discovered_pages.add(normalized)
                        # Add regular page to queue
                        queue.append(normalized)
            
            # Add a small delay to be respectful
            await asyncio.sleep(0.5)
        
        self.log(f"Site crawl completed. Found {len(self.all_urls)} URLs total")
        
        return {
            "base_url": base_url,
            "total_urls": len(self.all_urls),
            "products": list(self.discovered_products),
            "collections": list(self.discovered_collections),
            "pages": list(self.discovered_pages),
            "all_urls": list(self.all_urls)
        }