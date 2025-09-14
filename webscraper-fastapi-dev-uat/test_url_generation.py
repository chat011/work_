#!/usr/bin/env python3
"""
Test URL generation logic for pagination
"""

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def _update_url_param(url: str, param: str, value: str) -> str:
    """Update URL parameter"""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    query_params[param] = [value]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))

def _generate_pagination_urls(base_url: str, max_pages: int) -> list:
    """Generate pagination URLs based on common patterns"""
    urls = [base_url]  # Always include the base URL
    parsed_url = urlparse(base_url)
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    # Detect website type and use appropriate patterns
    if 'shopify' in base_url.lower() or any(shopify_indicator in base_url.lower() for shopify_indicator in ['collections/', '/products/']):
        # Shopify pagination pattern
        for page in range(2, max_pages + 1):
            if '?' in base_url:
                page_url = f"{base_url}&page={page}"
            else:
                page_url = f"{base_url}?page={page}"
            urls.append(page_url)
    
    elif '/shop/' in base_url.lower() and '/page/' in base_url.lower():
        # WordPress/WooCommerce pattern like /shop/page/1/
        base_path = base_url.rsplit('/page/', 1)[0]
        for page in range(2, max_pages + 1):
            page_url = f"{base_path}/page/{page}/"
            urls.append(page_url)
    
    elif '/shop/' in base_url.lower():
        # WooCommerce without existing page structure
        for page in range(2, max_pages + 1):
            if base_url.endswith('/'):
                page_url = f"{base_url}page/{page}/"
            else:
                page_url = f"{base_url}/page/{page}/"
            urls.append(page_url)
    
    else:
        # Generic patterns - try multiple approaches
        patterns_to_try = [
            # Query parameter patterns
            lambda p: _update_url_param(base_url, 'page', str(p)),
            lambda p: _update_url_param(base_url, 'p', str(p)),
            lambda p: f"{base_url}{'&' if '?' in base_url else '?'}page={p}",
            # Path-based patterns
            lambda p: f"{base_url.rstrip('/')}/page/{p}",
            lambda p: f"{base_url.rstrip('/')}/page/{p}/",
            lambda p: f"{base_url}/{p}" if base_url.endswith('/') else f"{base_url}/{p}",
        ]
        
        # Try each pattern and use the first one that seems reasonable
        for pattern_func in patterns_to_try:
            try:
                test_url = pattern_func(2)
                # Basic validation - URL should be well-formed
                if test_url.startswith('http') and domain in test_url:
                    for page in range(2, max_pages + 1):
                        urls.append(pattern_func(page))
                    break
            except Exception:
                continue
    
    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    return unique_urls[:max_pages]

def test_url_generation():
    """Test URL generation for the provided URLs"""
    
    test_cases = [
        {
            "url": "https://deashaindia.com/collections/banno-ke-libaas",
            "expected_pattern": "?page=",
            "type": "Shopify"
        },
        {
            "url": "https://kajrakh.com/collections/cotton-bra",
            "expected_pattern": "?page=",
            "type": "Shopify"
        },
        {
            "url": "https://ajmerachandanichowk.com/shop/page/1/",
            "expected_pattern": "/page/",
            "type": "WooCommerce with page"
        },
        {
            "url": "https://tajiri.in/collections/all-products",
            "expected_pattern": "?page=",
            "type": "Shopify"
        }
    ]
    
    print("🔗 Testing URL Generation Logic")
    print("="*60)
    
    for i, test_case in enumerate(test_cases):
        url = test_case["url"]
        expected_pattern = test_case["expected_pattern"]
        site_type = test_case["type"]
        
        print(f"\n{i+1}. Testing {site_type}: {url}")
        print("-" * 40)
        
        generated_urls = _generate_pagination_urls(url, 5)
        
        print(f"Generated {len(generated_urls)} URLs:")
        for j, gen_url in enumerate(generated_urls):
            print(f"   {j+1}. {gen_url}")
        
        # Check if expected pattern is present
        pattern_found = any(expected_pattern in gen_url for gen_url in generated_urls[1:])  # Skip first URL
        
        if pattern_found:
            print(f"   ✅ Pattern '{expected_pattern}' found in generated URLs")
        else:
            print(f"   ❌ Pattern '{expected_pattern}' NOT found in generated URLs")
        
        # Basic validation
        all_valid = all(gen_url.startswith('http') for gen_url in generated_urls)
        if all_valid:
            print(f"   ✅ All URLs are well-formed")
        else:
            print(f"   ❌ Some URLs are malformed")
    
    print("\n" + "="*60)
    print("🏁 URL generation test completed!")

if __name__ == "__main__":
    test_url_generation() 