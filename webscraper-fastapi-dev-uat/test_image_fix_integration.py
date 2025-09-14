#!/usr/bin/env python3
"""
Test script to verify image fixing integration works in the API
"""

import requests
import json
import time

def test_api_integration():
    """Test that the API properly fixes image URLs during scraping"""
    
    print("🧪 Testing Image URL Fixing Integration")
    print("=" * 50)
    
    # Test URL - this should trigger the image fixing
    test_url = "https://poshique.in/collections/tops"
    
    print(f"🔍 Testing with URL: {test_url}")
    
    # Start a scraping task
    payload = {
        "urls": [test_url],
        "max_pages_per_url": 2,
        "use_ai_pagination": True,
        "ai_extraction_mode": True
    }
    
    try:
        print("🚀 Starting AI scrape task...")
        response = requests.post("http://localhost:8000/scrape/ai", json=payload)
        
        if response.status_code != 200:
            print(f"❌ Failed to start scrape: {response.status_code}")
            return
        
        result = response.json()
        task_id = result['data']['task_id']
        
        print(f"✅ Task started: {task_id}")
        print("⏳ Waiting for completion...")
        
        # Poll for completion
        for i in range(60):  # Wait up to 60 seconds
            time.sleep(1)
            
            status_response = requests.get(f"http://localhost:8000/status/{task_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                current_status = status_data.get('status')
                
                print(f"📊 Status: {current_status}", end='\r')
                
                if current_status == 'completed':
                    print("\n✅ Task completed!")
                    
                    # Check if image URLs were fixed
                    result_data = status_data.get('result', {})
                    products = result_data.get('products', [])
                    metadata = result_data.get('metadata', {})
                    
                    print(f"📈 Results:")
                    print(f"  - Products found: {len(products)}")
                    print(f"  - Image URLs fixed: {metadata.get('image_urls_fixed', False)}")
                    print(f"  - Products with fixed images: {metadata.get('products_with_fixed_images', 0)}")
                    print(f"  - Images before fix: {metadata.get('total_images_before_fix', 0)}")
                    print(f"  - Images after fix: {metadata.get('total_images_after_fix', 0)}")
                    
                    if products:
                        sample_product = products[0]
                        sample_images = sample_product.get('product_images', [])
                        print(f"\n🔍 Sample product '{sample_product.get('product_name', 'Unknown')}':")
                        print(f"  - Image count: {len(sample_images)}")
                        
                        if sample_images:
                            for i, img in enumerate(sample_images[:3]):
                                is_clean = not ('width=1' in img or 'height=1' in img or img.startswith('data:image/svg'))
                                status = "✅ CLEAN" if is_clean else "❌ PLACEHOLDER"
                                print(f"  - Image {i+1}: {status}")
                                print(f"    {img[:80]}...")
                    
                    return True
                
                elif current_status == 'failed':
                    error = status_data.get('error', 'Unknown error')
                    print(f"\n❌ Task failed: {error}")
                    return False
        
        print("\n⏰ Task timed out")
        return False
        
    except Exception as e:
        print(f"❌ Error testing integration: {e}")
        return False

if __name__ == "__main__":
    success = test_api_integration()
    if success:
        print("\n🎉 Integration test PASSED!")
        print("Image URL fixing is working correctly in the API")
    else:
        print("\n💥 Integration test FAILED!")
        print("There may be an issue with the image fixing integration") 