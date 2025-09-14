import re
from urllib.parse import urlparse, parse_qs, urlencode
import json
import os
from datetime import datetime
from PIL import Image
import requests
from io import BytesIO

DEFAULT_IMAGE_SIZE = {"width": 800, "height": 800}

def fix_image_url(url):
    """
    Fix image URLs by removing placeholder parameters that make them 1x1 pixels
    
    Args:
        url (str): Original image URL
        
    Returns:
        str: Fixed URL with full-size image parameters
    """
    if not url or not isinstance(url, str):
        return url
    
    # Skip data URLs (base64 encoded images)
    if url.startswith('data:'):
        return url
    
    try:
        # Parse the URL
        parsed = urlparse(url)
        
        # Parse query parameters
        params = parse_qs(parsed.query)
        
        # Remove problematic parameters that create placeholder images
        problematic_params = ['width', 'height', 'crop']
        
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
            
            # Rebuild the URL without placeholder parameters
            new_query = urlencode(useful_params, doseq=True)
            fixed_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            
            if new_query:
                fixed_url += f"?{new_query}"
            
            return fixed_url
        
        return url
        
    except Exception as e:
        print(f"Error fixing URL {url}: {e}")
        return url


# Update the image_url_fixer.py to include size detection
def get_image_size(url):
    """Get image dimensions with timeout and error handling"""
    try:
        # Skip data URLs
        if url.startswith('data:'):
            return DEFAULT_IMAGE_SIZE
            
        # Set timeout to avoid blocking
        response = requests.get(url, timeout=5, stream=True)
        response.raise_for_status()
        
        # Only download first few bytes to get dimensions
        img_data = response.content[:1024]  # First 1KB should be enough for headers
        
        # Try to get image size without downloading entire file
        img = Image.open(BytesIO(img_data))
        return {"width": img.width, "height": img.height}
    except Exception as e:
        logger.warning(f"Could not get image size for {url}: {e}")
        return DEFAULT_IMAGE_SIZE

# Update the fix_product_images function
def fix_product_images(product_images):
    fixed_images = []
    image_sizes = []
    for img_url in product_images:
        fixed_url = fix_image_url(img_url)
        if fixed_url and not is_transparent_placeholder(fixed_url):
            fixed_images.append(fixed_url)
            image_sizes.append(get_image_size(fixed_url))
    return fixed_images, image_sizes


# def fix_product_images(product_images):
#     """
#     Fix all image URLs in a product images array
    
#     Args:
#         product_images (list): List of image URLs
        
#     Returns:
#         list: List of fixed image URLs
#     """
#     if not isinstance(product_images, list):
#         return product_images
    
#     fixed_images = []
#     for img_url in product_images:
#         fixed_url = fix_image_url(img_url)
        
#         # Skip transparent SVG placeholders
#         if fixed_url and not is_transparent_placeholder(fixed_url):
#             fixed_images.append(fixed_url)
    
#     return fixed_images

def is_transparent_placeholder(url):
    """
    Check if URL is a transparent SVG placeholder
    
    Args:
        url (str): Image URL
        
    Returns:
        bool: True if it's a transparent placeholder
    """
    if not url or not url.startswith('data:image/svg+xml;base64,'):
        return False
    
    try:
        import base64
        base64_data = url.split(',')[1]
        decoded_svg = base64.b64decode(base64_data).decode('utf-8')
        
        # Check if it's a transparent placeholder
        return (
            'fill="none"' in decoded_svg and 
            'fill-opacity="0"' in decoded_svg and 
            '99999' in decoded_svg
        )
    except:
        return False

def fix_json_file(input_file, output_file=None):
    """
    Fix image URLs in a JSON file containing scraped products
    
    Args:
        input_file (str): Path to input JSON file
        output_file (str): Path to output JSON file (optional)
        
    Returns:
        dict: Fixed data
    """
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    # Read the JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Fix product images
    if 'products' in data:
        for product in data['products']:
            if 'product_images' in product:
                original_count = len(product['product_images'])
                product['product_images'] = fix_product_images(product['product_images'])
                fixed_count = len(product['product_images'])
                
                if original_count != fixed_count:
                    print(f"Product '{product.get('product_name', 'Unknown')}': {original_count} -> {fixed_count} images")
    
    # Update metadata
    if 'metadata' in data:
        data['metadata']['image_urls_fixed'] = True
        data['metadata']['fixed_timestamp'] = str(datetime.now())
    
    # Save to output file
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Fixed JSON saved to: {output_file}")
    
    return data

def test_url_fixing():
    """Test the URL fixing function with examples"""
    test_urls = [
        "https://poshique.in/cdn/shop/collections/Dresses.jpg?crop=center&height=1&v=1732876930&width=1",
        "https://poshique.in/cdn/shop/files/product.jpg?width=800&height=600&v=123456",
        "https://example.com/image.jpg?width=1&height=1&crop=center",
        "https://example.com/normal-image.jpg",
        "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iOTk5..."
    ]
    
    print("🔧 Testing URL Fixing:")
    print("=" * 60)
    
    for url in test_urls:
        fixed = fix_image_url(url)
        status = "✅ FIXED" if url != fixed else "⚪ NO CHANGE"
        print(f"{status}")
        print(f"  Original: {url[:80]}...")
        print(f"  Fixed:    {fixed[:80]}...")
        print()

if __name__ == "__main__":
    # Run tests
    test_url_fixing()
    
    # Example usage with a JSON file
    # fix_json_file('logs/ai_agent_scrape_20250619_112440.json', 'logs/fixed_images.json') 