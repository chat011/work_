#!/usr/bin/env python3
"""
Test script for AI Agent Scraper
Tests the enhanced dynamic selector generation and website-specific scraping
"""

import asyncio
import json
from datetime import datetime
from scraper_ai_agent_deep import scrape_urls_ai_agent

def progress_callback(progress_data):
    """Handle progress updates"""
    print(f"📊 Progress: {progress_data['stage']} ({progress_data['percentage']}%) - {progress_data['details']}")

def log_callback(log_entry):
    """Handle log entries"""
    level_emoji = {
        "INFO": "ℹ️",
        "SUCCESS": "✅", 
        "WARNING": "⚠️",
        "ERROR": "❌",
        "PROGRESS": "📈"
    }
    emoji = level_emoji.get(log_entry['level'], "📝")
    print(f"{emoji} {log_entry['message']}")

async def test_ai_agent():
    """Test AI agent with the deashaindia.com website that was previously failing"""
    print("🚀 Testing AI Agent with Enhanced Dynamic Selectors")
    print("=" * 60)
    
    # Test the specific website that was failing
    test_urls = [
        "https://deashaindia.com/collections/sarees"
    ]
    
    print(f"🎯 Testing URLs:")
    for url in test_urls:
        print(f"   • {url}")
    print()
    
    try:
        # Run AI agent scraper
        result = await scrape_urls_ai_agent(
            urls=test_urls,
            log_callback=log_callback,
            progress_callback=progress_callback,
            max_pages_per_url=3  # Limit to 3 pages for testing
        )
        
        # Display results
        print("\n" + "=" * 60)
        print("📊 FINAL RESULTS")
        print("=" * 60)
        
        metadata = result.get('metadata', {})
        products = result.get('products', [])
        
        print(f"✅ Total Products Found: {len(products)}")
        print(f"📄 Pages Processed: {metadata.get('total_pages_processed', 0)}")
        print(f"🤖 Scraper Type: {metadata.get('scraper_type', 'unknown')}")
        
        # Show AI statistics
        ai_stats = metadata.get('ai_stats', {})
        if ai_stats:
            print(f"\n🧠 AI Agent Statistics:")
            print(f"   • Pages Analyzed: {ai_stats.get('pages_analyzed', 0)}")
            print(f"   • AI Extractions Successful: {ai_stats.get('ai_extraction_success', 0)}")
            print(f"   • AI Extractions Failed: {ai_stats.get('ai_extraction_failures', 0)}")
            print(f"   • Fallback Extractions: {ai_stats.get('fallback_extractions', 0)}")
        
        # Show sample products
        if products:
            print(f"\n🛍️ Sample Products (showing first 3):")
            for i, product in enumerate(products[:3]):
                print(f"\n   Product {i+1}:")
                print(f"   • Name: {product.get('product_name', 'N/A')}")
                print(f"   • Price: ₹{product.get('price', 0)}")
                print(f"   • Images: {len(product.get('product_images', []))} images")
                print(f"   • Description: {product.get('description', 'N/A')[:100]}...")
                print(f"   • Categories: {product.get('categories', [])}")
                print(f"   • Material: {product.get('material', 'N/A')}")
                print(f"   • Extraction Method: {product.get('extraction_method', 'N/A')}")
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_ai_results_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Detailed results saved to: {filename}")
        
        # Test success criteria
        success = len(products) > 0
        print(f"\n{'🎉 TEST PASSED!' if success else '❌ TEST FAILED!'}")
        
        if not success:
            print("❌ No products were extracted. This indicates an issue with:")
            print("   • Dynamic selector generation")
            print("   • Product link detection")
            print("   • AI analysis of page structure")
        else:
            print("✅ AI Agent successfully extracted products with dynamic selectors!")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ai_agent()) 