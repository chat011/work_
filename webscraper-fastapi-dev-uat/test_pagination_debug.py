#!/usr/bin/env python3
"""
Debug script to test pagination detection and scraping
"""

import asyncio
import json
import logging
from datetime import datetime
from scraper_ai_agent_deep import scrape_urls_ai_agent

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_pagination_urls():
    """Test the provided URLs for pagination detection"""
    
    test_urls = [
        "https://deashaindia.com/collections/banno-ke-libaas",
        "https://kajrakh.com/collections/cotton-bra", 
        "https://ajmerachandanichowk.com/shop/page/1/",
        "https://tajiri.in/collections/all-products"
    ]
    
    def log_callback(message, level="INFO", details=None):
        print(f"[{level}] {message}")
        if details:
            print(f"Details: {json.dumps(details, indent=2)}")
    
    def progress_callback(progress_data):
        stage = progress_data.get('stage', 'unknown')
        percentage = progress_data.get('percentage', 0)
        details = progress_data.get('details', '')
        print(f"Progress [{stage}] {percentage}%: {details}")
    
    for i, url in enumerate(test_urls):
        print(f"\n{'='*80}")
        print(f"Testing URL {i+1}/{len(test_urls)}: {url}")
        print(f"{'='*80}")
        
        try:
            result = await scrape_urls_ai_agent(
                urls=[url],
                max_pages_per_url=5,  # Limit to 5 pages for testing
                log_callback=log_callback,
                progress_callback=progress_callback
            )
            
            print(f"\n--- RESULTS FOR {url} ---")
            print(f"Total products found: {result.get('metadata', {}).get('total_products', 0)}")
            print(f"Pages processed: {result.get('metadata', {}).get('total_pages_processed', 0)}")
            print(f"AI Stats: {json.dumps(result.get('metadata', {}).get('ai_stats', {}), indent=2)}")
            
            # Show first few products
            products = result.get('products', [])
            if products:
                print(f"\nFirst 3 products:")
                for j, product in enumerate(products[:3]):
                    print(f"{j+1}. {product.get('product_name', 'N/A')} - ${product.get('price', 'N/A')}")
                    print(f"   URL: {product.get('url', 'N/A')}")
            
        except Exception as e:
            print(f"ERROR testing {url}: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"\n{'='*80}\n")

if __name__ == "__main__":
    asyncio.run(test_pagination_urls()) 