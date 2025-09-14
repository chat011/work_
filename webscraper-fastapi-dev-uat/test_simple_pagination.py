#!/usr/bin/env python3
"""
Simple test to debug pagination detection
"""

import asyncio
from scraper_ai_agent import GeminiAIAgent, AIProductScraper
from playwright.async_api import async_playwright

async def test_single_url_pagination():
    """Test pagination detection on a single URL"""
    
    test_url = "https://deashaindia.com/collections/banno-ke-libaas"
    
    print(f"Testing pagination detection for: {test_url}")
    print("="*60)
    
    # Initialize AI agent
    try:
        ai_agent = GeminiAIAgent()
        print("✅ AI Agent initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize AI Agent: {e}")
        return
    
    # Fetch page content
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(test_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)
            html_content = await page.content()
            await browser.close()
        
        print(f"✅ Page content fetched ({len(html_content)} characters)")
        
    except Exception as e:
        print(f"❌ Failed to fetch page content: {e}")
        return
    
    # Analyze page structure
    try:
        print("\n🧠 Analyzing page structure with AI...")
        analysis = await ai_agent.analyze_page_structure(html_content, test_url)
        
        print(f"Page Type: {analysis.page_type}")
        print(f"Confidence Score: {analysis.confidence_score}")
        print(f"Product Links Found: {len(analysis.product_links)}")
        
        if analysis.pagination_info:
            print(f"Has Pagination: {analysis.pagination_info.has_pagination}")
            print(f"Current Page: {analysis.pagination_info.current_page}")
            print(f"Total Pages: {analysis.pagination_info.total_pages}")
            print(f"Next Page URL: {analysis.pagination_info.next_page_url}")
            print(f"Page URLs: {len(analysis.pagination_info.page_urls)}")
            print(f"Pagination Pattern: {analysis.pagination_info.pagination_pattern}")
        else:
            print("❌ No pagination info detected")
        
        # Show first few product links
        if analysis.product_links:
            print(f"\nFirst 5 product links:")
            for i, link in enumerate(analysis.product_links[:5]):
                print(f"{i+1}. {link}")
        
    except Exception as e:
        print(f"❌ Failed to analyze page structure: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test pagination URL discovery
    if analysis.pagination_info and analysis.pagination_info.has_pagination:
        try:
            print(f"\n🔍 Discovering pagination URLs...")
            pagination_urls = await ai_agent.find_pagination_urls(html_content, test_url, 5)
            print(f"Pagination URLs discovered: {len(pagination_urls)}")
            for i, url in enumerate(pagination_urls):
                print(f"{i+1}. {url}")
                
        except Exception as e:
            print(f"❌ Failed to discover pagination URLs: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test_single_url_pagination()) 