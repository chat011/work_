import re
from urllib.parse import urlparse, parse_qs, urlencode
import json
import os
from datetime import datetime
from PIL import Image
import requests
from io import BytesIO
import concurrent.futures
import asyncio

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
        print(f"Could not get image size for {url}: {e}")
        return DEFAULT_IMAGE_SIZE

def fix_product_images(product_images):
    """Fix all image URLs in a product images array and get their sizes"""
    fixed_images = []
    image_sizes = []
    
    # Use thread pool for concurrent image processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Process images concurrently
        future_to_url = {
            executor.submit(process_image, img_url): img_url 
            for img_url in product_images
        }
        
        for future in concurrent.futures.as_completed(future_to_url):
            img_url = future_to_url[future]
            try:
                fixed_url, size = future.result()
                if fixed_url:
                    fixed_images.append(fixed_url)
                    image_sizes.append(size)
            except Exception as e:
                print(f"Error processing image {img_url}: {e}")
    
    return fixed_images, image_sizes

def process_image(img_url):
    """Process a single image URL"""
    fixed_url = fix_image_url(img_url)
    if fixed_url and not is_transparent_placeholder(fixed_url):
        size = get_image_size(fixed_url)
        return fixed_url, size
    return None, None

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

# Rest of the file remains the same...