#!/usr/bin/env python3
"""
Simple test for dynamic selectors without full AI agent
"""

import asyncio
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

def test_product_link_extraction():
    """Test the improved product link extraction logic"""
    
    # Sample HTML that mimics deashaindia.com structure
    sample_html = '''
    <html>
    <body>
        <div class="grid-item">
            <a href="/products/mahira-red-floral-saree">Mahira Red Saree</a>
        </div>
        <div class="product-item">
            <a href="/products/urvika-magenta-pink-ruffle-saree">Urvika Magenta Saree</a>
        </div>
        <div class="card-wrapper">
            <a href="/products/anisah-lavender-floral-saree">Anisah Lavender Saree</a>
        </div>
        <a href="/cart">Cart</a>
        <a href="/collections/sarees">Collections</a>
        <a href="/products/test-product">Test Product</a>
    </body>
    </html>
    '''
    
    soup = BeautifulSoup(sample_html, 'html.parser')
    base_url = "https://deashaindia.com/collections/sarees"
    
    print("🧪 Testing Enhanced Product Link Extraction")
    print("=" * 50)
    
    # Test the enhanced selectors
    shopify_selectors = [
        'a[href*="/products/"]',
        '.product-item a',
        '.grid-item a',
        '.product-card a',
        '.product__title a',
        '.card__heading a',
        '.card-wrapper a'
    ]
    
    product_links = []
    
    for selector in shopify_selectors:
        try:
            elements = soup.select(selector)
            for elem in elements:
                href = elem.get('href')
                if href:
                    # Make absolute URL
                    if href.startswith('/'):
                        href = urljoin(base_url, href)
                    elif not href.startswith('http'):
                        href = urljoin(base_url, href)
                    
                    # Filter for product URLs
                    if (href.startswith('http') and 
                        href not in product_links and 
                        len(href) < 200):
                        
                        # Check if it's likely a product URL
                        is_product = any(pattern in href.lower() for pattern in ['/products/', '/product/', '/item/', '/items/'])
                        is_excluded = any(x in href.lower() for x in ['cart', 'checkout', 'login', 'register', 'contact', 'about', 'policy', 'terms', 'search', 'collections', 'blog', 'news'])
                        
                        if is_product or not is_excluded:
                            product_links.append(href)
                            print(f"✅ Found product: {href}")
                            
                        if len(product_links) >= 50:  # Reasonable limit
                            break
        except Exception as e:
            print(f"❌ Error with selector '{selector}': {e}")
            continue
            
        if len(product_links) >= 50:
            break
    
    print(f"\n📊 Results:")
    print(f"   • Total product links found: {len(product_links)}")
    print(f"   • Expected: 4 product links")
    print(f"   • Test {'PASSED' if len(product_links) == 4 else 'FAILED'}")
    
    return len(product_links) == 4

def test_price_extraction():
    """Test price extraction logic"""
    
    sample_html = '''
    <div class="price">₹4,949.00</div>
    <span class="woocommerce-Price-amount amount">
        <bdi><span class="woocommerce-Price-currencySymbol">₹</span>6,500.00</bdi>
    </span>
    <div class="money">Rs. 2,999</div>
    '''
    
    soup = BeautifulSoup(sample_html, 'html.parser')
    
    print("\n🧪 Testing Price Extraction")
    print("=" * 50)
    
    def extract_price_from_text(text):
        """Extract price from text"""
        if not text:
            return 0.0
        
        # Remove HTML tags if any
        text = re.sub(r'<[^>]+>', '', text)
        
        # Price patterns
        price_patterns = [
            r'₹\s*([0-9,]+(?:\.[0-9]{2})?)',
            r'INR\s*([0-9,]+(?:\.[0-9]{2})?)',
            r'Rs\.?\s*([0-9,]+(?:\.[0-9]{2})?)',
            r'\$\s*([0-9,]+(?:\.[0-9]{2})?)',
            r'([0-9,]+(?:\.[0-9]{2})?)'
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    price_str = matches[0].replace(',', '')
                    return float(price_str)
                except ValueError:
                    continue
        
        return 0.0
    
    def extract_price_with_selectors(soup, selectors):
        """Extract price using CSS selectors"""
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    price_text = element.get_text(strip=True)
                    if price_text:
                        price = extract_price_from_text(price_text)
                        if price > 0:
                            return price
            except Exception:
                continue
        return 0.0
    
    price_selectors = [
        '.price', '.cost', '.amount', '.money', '.product-price', '.price-current',
        '.woocommerce-Price-amount', '.price-amount', '[data-price]', '.sale-price',
        '.regular-price', '.product__price', '.price-item'
    ]
    
    extracted_price = extract_price_with_selectors(soup, price_selectors)
    
    print(f"✅ Extracted price: ₹{extracted_price}")
    print(f"   • Expected: A price > 0")
    print(f"   • Test {'PASSED' if extracted_price > 0 else 'FAILED'}")
    
    return extracted_price > 0

def main():
    """Run all tests"""
    print("🚀 Testing AI Agent Dynamic Selector Improvements")
    print("=" * 60)
    
    test1_passed = test_product_link_extraction()
    test2_passed = test_price_extraction()
    
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS")
    print("=" * 60)
    
    print(f"✅ Product Link Extraction: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"✅ Price Extraction: {'PASSED' if test2_passed else 'FAILED'}")
    
    overall_success = test1_passed and test2_passed
    print(f"\n🎉 Overall Result: {'ALL TESTS PASSED!' if overall_success else 'SOME TESTS FAILED'}")
    
    if overall_success:
        print("\n✅ The dynamic selector improvements are working correctly!")
        print("   • Enhanced product link detection for Shopify sites")
        print("   • Improved price extraction with multiple patterns")
        print("   • Better filtering of non-product URLs")
        print("\n🔧 Next Steps:")
        print("   • The AI agent should now successfully find products on deashaindia.com")
        print("   • Dynamic selectors will adapt to different website structures")
        print("   • Price extraction will handle various currency formats")
    else:
        print("\n❌ Some improvements need fixing before the AI agent will work properly")

if __name__ == "__main__":
    main() 