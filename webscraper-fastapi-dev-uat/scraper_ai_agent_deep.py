
"""
AI-Powered Web Scraper using Google Gemini 1.5 Flash
Intelligent agent that can understand page structures, find pagination, and extract products dynamically
"""
import tenacity
from cachetools import TTLCache
import hashlib
import asyncio
import json
import logging
import os
import time
import re

from datetime import datetime,timedelta
from typing import List, Dict, Any, Optional, Callable, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from dataclasses import dataclass

from playwright.async_api import async_playwright
from pydantic import HttpUrl
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PaginationInfo:
    """Information about pagination found on a page"""
    has_pagination: bool
    current_page: int
    total_pages: Optional[int]
    next_page_url: Optional[str]
    page_urls: List[str]
    pagination_pattern: str

@dataclass
class PageAnalysis:
    """Analysis results from AI agent"""
    page_type: str  # 'collection', 'product', 'pagination'
    product_links: List[str]
    pagination_info: Optional[PaginationInfo]
    extraction_strategy: Dict[str, Any]
    confidence_score: float

# In scraper_ai_agent.py, add debug logging to the AI agent initialization
def __init__(self):

    # Load environment variables directly
    from dotenv import load_dotenv
    load_dotenv()  # This ensures .env is loaded
    
    # Debug: Check if .env file was loaded
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    logger.info(f"Looking for .env file at: {env_path}")
    logger.info(f".env file exists: {os.path.exists(env_path)}")
    
    # Debug: Check all environment variables
    all_env_vars = dict(os.environ)
    logger.info(f"Available environment variables: {list(all_env_vars.keys())}")
    
    # Configure Gemini
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    logger.info(f"API key found: {bool(api_key)}")
    
    if not api_key:
        raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required")
    
    # Rest of the initialization code...
    # Rest of the initialization code...z
# Add caching and retry to the AIAgent class
class GeminiAIAgent:
    """AI Agent powered by Google Gemini 1.5 Flash with enhanced features"""
    
    
    # In scraper_ai_agent.py, update the GeminiAIAgent __init__ method
    def __init__(self):
        # Load environment variables directly
        from dotenv import load_dotenv
        load_dotenv()  # This ensures .env is loaded
        
        # Configure Gemini
        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required")
        
        genai.configure(api_key=api_key)
        
        # Initialize Gemini model
        self.model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            generation_config={
                'temperature': 0.1,  # Low temperature for consistent results
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 4096,
            }
        )
        
        logger.info("Gemini AI Agent initialized successfully")
        
    # Add retry to API calls
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
        retry=tenacity.retry_if_exception_type(Exception)
    )
    async def analyze_page_structure(self, html_content: str, url: str) -> PageAnalysis:
        """Analyze page structure using AI to understand layout and find pagination"""
        
        # Check cache first
        url_hash = hashlib.md5(url.encode()).hexdigest()
        if url_hash in self.analysis_cache:
            logger.info(f"Using cached analysis for {url}")
            return self.analysis_cache[url_hash]
        
        # ... existing analysis code ...
        
        # Cache the result
        self.analysis_cache[url_hash] = analysis
        return analysis
    
    # Add similar caching and retry to other methods
  

# Enhance the AIProductScraper class
class AIProductScraper:
    """AI-powered product scraper using Gemini 1.5 Flash with enhanced features"""
    
    # In scraper_ai_agent.py, update the __init__ method of AIProductScraper
    def __init__(self, log_callback: Optional[Callable] = None, progress_callback: Optional[Callable] = None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize AI agent with better error handling
        self.ai_agent = None
        try:
            self.ai_agent = GeminiAIAgent()
            logger.info("AI Agent initialized successfully")
        except Exception as e:
            logger.warning(f"AI Agent initialization failed: {e}")
            # Don't raise an exception, just continue without AI capabilities
    
    async def scrape_products_concurrently(self, product_urls, max_concurrent=5):
        """Scrape multiple products concurrently with semaphore"""
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []
        
        async def limited_scrape(url):
            async with semaphore:
                # Check cache first
                url_hash = hashlib.md5(url.encode()).hexdigest()
                if url_hash in self.product_cache:
                    return self.product_cache[url_hash]
                
                result = await self._scrape_single_product_by_url(url)
                
                # Cache the result
                self.product_cache[url_hash] = result
                return result
        
        tasks = [limited_scrape(url) for url in product_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        return [r for r in results if not isinstance(r, Exception)]
    
    async def _scrape_collection_with_pagination(self, base_url: str, analysis: PageAnalysis, max_pages: int, progress_callback: Optional[Callable] = None, base_progress: int = 0) -> List[Dict[str, Any]]:

        """Scrape collection with intelligent pagination handling and progress updates"""
        products = []
        
        # Check if pagination is detected
        pagination_detected = (analysis.pagination_info and 
                             analysis.pagination_info.has_pagination and 
                             len(analysis.pagination_info.page_urls) > 1)
        
        if pagination_detected:
            # Use pagination URLs from analysis
            pagination_urls = analysis.pagination_info.page_urls[:max_pages]
            
            self.log(f"Using detected pagination: {len(pagination_urls)} pages")
            self.stats["pagination_pages_discovered"] = len(pagination_urls)
            
            # Process each pagination page
            for i, page_url in enumerate(pagination_urls):
                if progress_callback:
                    page_progress = base_progress + (i * 50 // len(pagination_urls))
                    page_display = page_url.split('/')[-1] if '/' in page_url else page_url.split('?')[-1]
                    await progress_callback(
                        "scraping", f"page_{i}", page_progress,
                        f"Processing page {i+1}/{len(pagination_urls)}: {page_display}"
                    )
                
                page_products = await self._scrape_products_from_page(page_url)
                products.extend(page_products)
                
                if progress_callback:
                    await progress_callback(
                        "scraping", f"page_{i}_complete", page_progress + 2,
                        f"Page {i+1}/{len(pagination_urls)} complete: {len(page_products)} products found"
                    )
                
                # Small delay between pages
                await asyncio.sleep(0.5)
        
        elif self.ai_agent:
            # Try AI-based pagination discovery as fallback
            self.log("No pagination detected in analysis, trying AI discovery...")
            html_content = await self._fetch_page_content(base_url)
            if html_content:
                try:
                    pagination_urls = await self.ai_agent.find_pagination_urls(html_content, base_url, max_pages)
                    
                    if len(pagination_urls) > 1:
                        self.log(f"AI discovered {len(pagination_urls)} pagination pages")
                        self.stats["pagination_pages_discovered"] = len(pagination_urls)
                        
                        # Process each AI-discovered pagination page
                        for i, page_url in enumerate(pagination_urls):
                            if progress_callback:
                                page_progress = base_progress + (i * 50 // len(pagination_urls))
                                page_display = page_url.split('/')[-1] if '/' in page_url else page_url.split('?')[-1]
                                await progress_callback(
                                    "scraping", f"ai_page_{i}", page_progress,
                                    f"Processing AI page {i+1}/{len(pagination_urls)}: {page_display}"
                                )
                            
                            page_products = await self._scrape_products_from_page(page_url)
                            products.extend(page_products)
                            
                            if progress_callback:
                                await progress_callback(
                                    "scraping", f"ai_page_{i}_complete", page_progress + 2,
                                    f"AI page {i+1}/{len(pagination_urls)} complete: {len(page_products)} products"
                                )
                            
                            # Small delay between pages
                            await asyncio.sleep(0.5)
                    else:
                        # Single page collection
                        self.log("AI could not find pagination, processing single page")
                        page_products = await self._scrape_products_from_page(base_url, analysis.product_links)
                        products.extend(page_products)
                        
                except Exception as e:
                    self.log(f"AI pagination discovery failed: {e}", "ERROR")
                    # Fallback to single page
                    page_products = await self._scrape_products_from_page(base_url, analysis.product_links)
                    products.extend(page_products)
            else:
                # Could not fetch content, use known product links
                page_products = await self._scrape_products_from_page(base_url, analysis.product_links)
                products.extend(page_products)
        
        else:
            # No AI agent available, single page collection
            self.log("No AI agent available, processing single page only")
            page_products = await self._scrape_products_from_page(base_url, analysis.product_links)
            products.extend(page_products)
        
        return products
    

# Main API function
async def scrape_urls_ai_agent(
    urls: List[str], 
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
    max_pages_per_url: int = 50
) -> Dict[str, Any]:
    """
    AI Agent API function to scrape product data from URLs using Gemini 1.5 Flash
    
    Features:
    - Intelligent page structure analysis
    - Automatic pagination discovery and navigation
    - AI-powered product data extraction
    - Adaptive to different website layouts
    - Dynamic CSS selector generation
    - Fallback to traditional scraping when AI fails
    """
    scraper = AIProductScraper(log_callback, progress_callback)
    
    try:
        return await scraper.scrape_with_ai_agent(urls, max_pages_per_url)
        
    except Exception as e:
        scraper.log(f"Error in AI agent scraping: {e}", "ERROR")
        # Try one more fallback
        try:
            return await scraper._fallback_to_simple_scraper(urls, max_pages_per_url)
        except Exception as fallback_error:
            # Final fallback result
            return {
                "metadata": {
                    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                    "total_products": 0,
                    "scraper_type": "complete_failure",
                    "error": f"AI: {e}, Fallback: {fallback_error}",
                    "ai_stats": scraper.stats if scraper else {}
                },
                "products": []
            }

if __name__ == "__main__":
    # Test the AI agent
    async def test_ai_agent():
        test_urls = [
            "https://deashaindia.com/collections/sarees",
            "https://ajmerachandanichowk.com/shop/"
        ]
        
        result = await scrape_urls_ai_agent(test_urls, max_pages_per_url=5)
        print(json.dumps(result, indent=2))
    
    asyncio.run(test_ai_agent())