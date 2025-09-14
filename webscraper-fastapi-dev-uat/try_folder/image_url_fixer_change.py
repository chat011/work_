import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import json
import os
from datetime import datetime
from PIL import Image
import requests
from io import BytesIO
import asyncio
import aiohttp
import concurrent.futures
from typing import List, Dict, Tuple, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_IMAGE_SIZE = {"width": 800, "height": 800}

class EnhancedImageURLFixer:
    """Enhanced image URL fixer with async processing and better validation"""
    
    def __init__(self, max_concurrent_requests: int = 10, timeout: int = 10):
        self.max_concurrent_requests = max_concurrent_requests
        self.timeout = timeout
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            connector=aiohttp.TCPConnector(limit=self.max_concurrent_requests)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    def fix_image_url(self, url: str) -> str:
        """
        Fix image URLs by removing placeholder parameters that make them 1x1 pixels
        Enhanced version with better URL parsing and validation
        """
        if not url or not isinstance(url, str):
            return url
        
        # Skip data URLs (base64 encoded images)
        if url.startswith('data:'):
            return url if not self.is_transparent_placeholder(url) else ""
        
        try:
            # Parse the URL
            parsed = urlparse(url)
            
            # Parse query parameters
            params = parse_qs(parsed.query, keep_blank_values=False)
            
            # Remove problematic parameters that create placeholder images
            problematic_params = ['width', 'height', 'crop', 'c', 'w', 'h']
            
            # Check if this is a 1x1 placeholder image
            is_placeholder = self._is_placeholder_image(params, url)
            
            if is_placeholder:
                # Keep only useful parameters
                useful_params = {}
                keep_params = ['v', 'version', 'quality', 'format', 'q', 'f']
                
                for param, values in params.items():
                    if param in keep_params and values:
                        useful_params[param] = values
                
                # Rebuild the URL without placeholder parameters
                new_query = urlencode(useful_params, doseq=True)
                fixed_url = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment
                ))
                
                return fixed_url
            
            return url
            
        except Exception as e:
            logger.warning(f"Error fixing URL {url}: {e}")
            return url

    def _is_placeholder_image(self, params: Dict, url: str) -> bool:
        """Enhanced placeholder detection"""
        # Method 1: Check for 1x1 dimensions in parameters
        width_vals = params.get('width', []) + params.get('w', [])
        height_vals = params.get('height', []) + params.get('h', [])
        
        has_1x1_params = (
            any(val == '1' for val in width_vals) or
            any(val == '1' for val in height_vals)
        )
        
        # Method 2: Check for 1x1 in URL string
        has_1x1_in_url = 'width=1' in url or 'height=1' in url or 'w=1' in url or 'h=1' in url
        
        # Method 3: Check for common placeholder patterns
        placeholder_patterns = [
            r'[?&]w=1[&$]',
            r'[?&]h=1[&$]',
            r'[?&]width=1[&$]',
            r'[?&]height=1[&$]',
            r'[?&]crop=center.*[?&](?:width|w)=1',
            r'[?&]crop=center.*[?&](?:height|h)=1'
        ]
        
        has_placeholder_pattern = any(re.search(pattern, url) for pattern in placeholder_patterns)
        
        return has_1x1_params or has_1x1_in_url or has_placeholder_pattern

    async def get_image_size_async(self, url: str) -> Dict[str, int]:
        """Get image size asynchronously with better error handling"""
        try:
            if not self.session:
                raise ValueError("Session not initialized. Use async context manager.")
            
            # Add headers to mimic a browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    # Read only the first chunk to get dimensions
                    chunk_size = 2048  # Read first 2KB for image header
                    content = await response.content.read(chunk_size)
                    
                    # Try to get dimensions from header without loading full image
                    try:
                        img = Image.open(BytesIO(content))
                        return {"width": img.width, "height": img.height}
                    except Exception:
                        # If header parsing fails, try to load more content
                        remaining_content = await response.content.read()
                        full_content = content + remaining_content
                        img = Image.open(BytesIO(full_content))
                        return {"width": img.width, "height": img.height}
                        
                else:
                    logger.warning(f"HTTP {response.status} for image: {url}")
                    return DEFAULT_IMAGE_SIZE
                    
        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting image size for: {url}")
            return DEFAULT_IMAGE_SIZE
        except Exception as e:
            logger.warning(f"Error getting image size for {url}: {e}")
            return DEFAULT_IMAGE_SIZE

    async def validate_image_url_async(self, url: str) -> bool:
        """Validate image URL asynchronously"""
        try:
            if not self.session:
                raise ValueError("Session not initialized")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/*,*/*;q=0.8'
            }
            
            async with self.session.head(url, headers=headers, allow_redirects=True) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    return content_type.startswith('image/')
                else:
                    return False
                    
        except Exception as e:
            logger.warning(f"Error validating image URL {url}: {e}")
            return False

    async def fix_product_images_async(self, product_images: List[str]) -> Tuple[List[str], List[Dict[str, int]]]:
        """
        Fix all image URLs in a product images array with async processing
        Returns: (fixed_images, image_sizes)
        """
        if not isinstance(product_images, list) or not product_images:
            return [], []
        
        # Step 1: Fix URLs and filter valid ones
        fixed_urls = []
        for img_url in product_images:
            fixed_url = self.fix_image_url(img_url)
            if fixed_url and self.is_valid_image_url(fixed_url):
                fixed_urls.append(fixed_url)
        
        if not fixed_urls:
            return [], []
        
        # Step 2: Validate URLs and get sizes in parallel
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        async def process_image_with_limit(url: str):
            async with semaphore:
                # First validate the URL
                is_valid = await self.validate_image_url_async(url)
                if not is_valid:
                    return None, None
                
                # Then get the size
                size = await self.get_image_size_async(url)
                return url, size
        
        # Process all images concurrently
        tasks = [process_image_with_limit(url) for url in fixed_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful results
        final_images = []
        final_sizes = []
        
        for result in results:
            if isinstance(result, tuple) and result[0] is not None:
                url, size = result
                final_images.append(url)
                final_sizes.append(size)
            elif isinstance(result, Exception):
                logger.error(f"Error processing image: {result}")
        
        return final_images, final_sizes

    def is_valid_image_url(self, url: str) -> bool:
        """Enhanced image URL validation"""
        if not url or not isinstance(url, str):
            return False
        
        # Skip data URLs and transparent placeholders
        if url.startswith('data:'):
            return not self.is_transparent_placeholder(url)
        
        # Must be HTTP/HTTPS
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Check for common image extensions or image-related paths
        image_indicators = [
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.tiff',
            'image', 'img', 'photo', 'picture', 'cdn', 'media', 'assets'
        ]
        
        url_lower = url.lower()
        has_image_indicator = any(indicator in url_lower for indicator in image_indicators)
        
        # Exclude common non-image URLs
        non_image_indicators = [
            'javascript:', 'mailto:', '#', 'tel:', 'sms:',
            'download', 'pdf', 'doc', 'zip'
        ]
        
        has_non_image = any(indicator in url_lower for indicator in non_image_indicators)
        
        return has_image_indicator and not has_non_image

    def is_transparent_placeholder(self, url: str) -> bool:
        """
        Enhanced check for transparent SVG placeholders
        """
        if not url or not url.startswith('data:image/svg+xml;base64,'):
            return False
        
        try:
            import base64
            base64_data = url.split(',')[1]
            decoded_svg = base64.b64decode(base64_data).decode('utf-8')
            
            # Check for transparent placeholder indicators
            transparent_indicators = [
                'fill="none"',
                'fill-opacity="0"',
                'opacity="0"',
                'width="1"',
                'height="1"',
                '99999',  # Common placeholder dimension
                'transparent',
                'rgba(0,0,0,0)'
            ]
            
            return any(indicator in decoded_svg for indicator in transparent_indicators)
            
        except Exception:
            return False


# Synchronous wrapper functions for backward compatibility
def fix_image_url(url: str) -> str:
    """Synchronous wrapper for fixing single image URL"""
    fixer = EnhancedImageURLFixer()
    return fixer.fix_image_url(url)

def get_image_size_sync(url: str) -> Dict[str, int]:
    """Synchronous image size getter"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            return {"width": img.width, "height": img.height}
    except Exception as e:
        logger.warning(f"Error getting image size for {url}: {e}")
    
    return DEFAULT_IMAGE_SIZE

def fix_product_images(product_images: List[str]) -> Tuple[List[str], List[Dict[str, int]]]:
    """
    Synchronous wrapper for fixing product images
    Returns: (fixed_images, image_sizes)
    """
    if not isinstance(product_images, list):
        return [], []
    
    async def process_images():
        async with EnhancedImageURLFixer() as fixer:
            return await fixer.fix_product_images_async(product_images)
    
    # Run the async function
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(process_images())
    except Exception as e:
        logger.error(f"Error in fix_product_images: {e}")
        # Fallback to synchronous processing
        return fix_product_images_sync_fallback(product_images)

def fix_product_images_sync_fallback(product_images: List[str]) -> Tuple[List[str], List[Dict[str, int]]]:
    """Fallback synchronous processing"""
    fixer = EnhancedImageURLFixer()
    fixed_images = []
    image_sizes = []
    
    for img_url in product_images:
        fixed_url = fixer.fix_image_url(img_url)
        if fixed_url and fixer.is_valid_image_url(fixed_url):
            fixed_images.append(fixed_url)
            size = get_image_size_sync(fixed_url)
            image_sizes.append(size)
    
    return fixed_images, image_sizes

async def fix_json_file_async(input_file: str, output_file: Optional[str] = None) -> Dict:
    """
    Fix image URLs in a JSON file containing scraped products (async version)
    """
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    # Read the JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if 'products' not in data:
        logger.warning("No products found in JSON file")
        return data
    
    total_products = len(data['products'])
    total_images_before = 0
    total_images_after = 0
    fixed_count = 0
    
    logger.info(f"Starting async image fixing for {total_products} products...")
    
    # Process products in batches to avoid overwhelming the server
    batch_size = 10
    
    async with EnhancedImageURLFixer(max_concurrent_requests=5) as fixer:
        for i in range(0, total_products, batch_size):
            batch = data['products'][i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_products + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches}")
            
            # Process batch concurrently
            batch_tasks = []
            for product in batch:
                if 'product_images' in product:
                    original_count = len(product['product_images'])
                    total_images_before += original_count
                    batch_tasks.append(fixer.fix_product_images_async(product['product_images']))
                else:
                    batch_tasks.append(asyncio.coroutine(lambda: ([], []))())
            
            batch_results = await asyncio.gather(*batch_tasks)
            
            # Update products with results
            for j, (product, (fixed_images, sizes)) in enumerate(zip(batch, batch_results)):
                if 'product_images' in product:
                    original_count = len(product['product_images'])
                    product['product_images'] = fixed_images
                    product['image_sizes'] = sizes
                    
                    new_count = len(fixed_images)
                    total_images_after += new_count
                    
                    if original_count != new_count:
                        fixed_count += 1
                        product_name = product.get('product_name', 'Unknown')[:40]
                        logger.info(f"Fixed '{product_name}': {original_count} -> {new_count} images")
            
            # Small delay between batches
            await asyncio.sleep(0.5)
    
    # Calculate statistics
    images_removed = total_images_before - total_images_after
    fix_percentage = (fixed_count / total_products * 100) if total_products > 0 else 0
    
    # Update metadata
    if 'metadata' not in data:
        data['metadata'] = {}
        
    data['metadata'].update({
        'image_urls_fixed': True,
        'products_with_fixed_images': fixed_count,
        'total_images_before_fix': total_images_before,
        'total_images_after_fix': total_images_after,
        'images_removed': images_removed,
        'fix_percentage': round(fix_percentage, 1),
        'image_fix_timestamp': datetime.now().isoformat(),
        'async_processing': True
    })
    
    logger.info(f"Async image fixing complete:")
    logger.info(f"   Products processed: {total_products}")
    logger.info(f"   Products with fixed images: {fixed_count} ({fix_percentage:.1f}%)")
    logger.info(f"   Images: {total_images_before} -> {total_images_after} (removed {images_removed} invalid)")
    
    # Save to output file
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Fixed JSON saved to: {output_file}")
    
    return data

def fix_json_file(input_file: str, output_file: Optional[str] = None) -> Dict:
    """
    Synchronous wrapper for fix_json_file_async
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(fix_json_file_async(input_file, output_file))

def test_enhanced_url_fixing():
    """Test the enhanced URL fixing function"""
    test_urls = [
        "https://poshique.in/cdn/shop/collections/Dresses.jpg?crop=center&height=1&v=1732876930&width=1",
        "https://poshique.in/cdn/shop/files/product.jpg?width=800&height=600&v=123456",
        "https://example.com/image.jpg?width=1&height=1&crop=center",
        "https://example.com/normal-image.jpg",
        "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMSIgaGVpZ2h0PSIxIj4KPC9zdmc+",
        "https://cdn.shopify.com/s/files/1/0001/2345/products/dress.jpg?v=1234567890&width=1&height=1",
        "invalid-url",
        "",
        None
    ]
    
    print("Enhanced URL Fixing Test:")
    print("=" * 80)
    
    fixer = EnhancedImageURLFixer()
    
    for i, url in enumerate(test_urls, 1):
        try:
            fixed = fixer.fix_image_url(url)
            is_valid = fixer.is_valid_image_url(fixed) if fixed else False
            
            status = "✅ FIXED & VALID" if url != fixed and is_valid else \
                    "✅ VALID" if is_valid else \
                    "❌ INVALID" if fixed else \
                    "⚠️ SKIPPED"
                    
            print(f"{i:2d}. {status}")
            print(f"    Original: {str(url)[:70]}...")
            print(f"    Fixed:    {str(fixed)[:70]}...")
            print(f"    Valid:    {is_valid}")
            print()
        except Exception as e:
            print(f"{i:2d}. ❌ ERROR: {e}")
            print(f"    URL: {url}")
            print()

async def test_async_processing():
    """Test async image processing"""
    test_images = [
        "https://via.placeholder.com/300x300.jpg",
        "https://via.placeholder.com/400x400.png",
        "https://httpbin.org/image/jpeg",
        "https://invalid-url-test.com/image.jpg"
    ]
    
    print("Async Processing Test:")
    print("=" * 40)
    
    async with EnhancedImageURLFixer() as fixer:
        fixed_images, sizes = await fixer.fix_product_images_async(test_images)
        
        print(f"Original count: {len(test_images)}")
        print(f"Fixed count: {len(fixed_images)}")
        print(f"Sizes: {sizes}")
        print("Fixed images:")
        for i, (img, size) in enumerate(zip(fixed_images, sizes)):
            print(f"  {i+1}. {img[:50]}... ({size['width']}x{size['height']})")

if __name__ == "__main__":
    # Run tests
    test_enhanced_url_fixing()
    
    # Test async processing
    try:
        asyncio.run(test_async_processing())
    except Exception as e:
        print(f"Async test failed: {e}")
    
    print("\nFor JSON file processing, use:")
    print("fix_json_file('input.json', 'output_fixed.json')")