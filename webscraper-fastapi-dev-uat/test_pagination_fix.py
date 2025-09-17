#!/usr/bin/env python3
"""
Test script to verify pagination fixes
"""

import asyncio
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_pagination_fix():
    """Test the pagination fixes on the provided URLs"""
    
    # Import here to avoid import issues
    try:
        from scraper_ai_agent_deep import scrape_urls_ai_agent
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all dependencies are installed")
        return
    
    test_urls = [
        "https://deashaindia.com/collections/banno-ke-libaas",
        "https://kajrakh.com/collections/cotton-bra", 
        "https://ajmerachandanichowk.com/shop/page/1/",
        "https://tajiri.in/collections/all-products"
    ]
    
    def log_callback(message, level="INFO", details=None):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        if details and level == "ERROR":
            print(f"    Details: {json.dumps(details, indent=2)}")
    
    def progress_callback(progress_data):
        stage = progress_data.get('stage', 'unknown')
        percentage = progress_data.get('percentage', 0)
        details = progress_data.get('details', '')
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Progress [{stage}] {percentage}%: {details}")
    
    print("🧪 Testing Pagination Fixes")
    print("="*80)
    
    for i, url in enumerate(test_urls):
        print(f"\n🔍 Testing URL {i+1}/{len(test_urls)}: {url}")
        print("-" * 60)
        
        try:
            start_time = datetime.now()
            
            result = await scrape_urls_ai_agent(
                urls=[url],
                max_pages_per_url=3,  # Limit to 3 pages for testing
                log_callback=log_callback,
                progress_callback=progress_callback
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"\n📊 RESULTS FOR {url}")
            print(f"   Duration: {duration:.1f} seconds")
            print(f"   Total products: {result.get('metadata', {}).get('total_products', 0)}")
            print(f"   Pages processed: {result.get('metadata', {}).get('total_pages_processed', 0)}")
            
            # AI Stats
            ai_stats = result.get('metadata', {}).get('ai_stats', {})
            if ai_stats:
                print(f"   Pagination pages discovered: {ai_stats.get('pagination_pages_discovered', 0)}")
                print(f"   AI extraction success: {ai_stats.get('ai_extraction_success', 0)}")
                print(f"   AI extraction failures: {ai_stats.get('ai_extraction_failures', 0)}")
            
            # Show first few products
            products = result.get('products', [])
            if products:
                print(f"\n   First 3 products:")
                for j, product in enumerate(products[:3]):
                    name = product.get('product_name', 'N/A')[:40]
                    price = product.get('price', 'N/A')
                    print(f"   {j+1}. {name} - ${price}")
                    
                # Check if we got products from multiple pages (indication of pagination working)
                unique_domains = set()
                for product in products:
                    url_parts = product.get('url', '').split('/')
                    if len(url_parts) > 2:
                        unique_domains.add(url_parts[2])
                
                if len(products) > 16:  # Most pages have ~16 products per page
                    print(f"   ✅ Likely multiple pages scraped ({len(products)} products)")
                elif ai_stats.get('pagination_pages_discovered', 0) > 1:
                    print(f"   ✅ Pagination detected ({ai_stats.get('pagination_pages_discovered')} pages)")
                else:
                    print(f"   ⚠️  Only single page scraped ({len(products)} products)")
            else:
                print(f"   ❌ No products found")
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        print("-" * 60)
    
    print("\n" + "="*80)
    print("🏁 Pagination testing completed!")

if __name__ == "__main__":
    asyncio.run(test_pagination_fix()) 