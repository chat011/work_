import re
import json
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
import logging

class UniversalEcommerceExtractor:
    """Universal extractor that works with ANY e-commerce website"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_all_product_data(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract ALL product data using multiple universal methods"""
        
        # Try methods in order of reliability
        methods = [
            self._extract_from_structured_data,
            self._extract_from_meta_tags,
            self._extract_from_microdata,
            self._extract_from_javascript_variables,
            self._extract_from_dom_patterns
        ]
        
        combined_data = {}
        extraction_sources = []
        
        for method in methods:
            try:
                data = method(soup, url)
                if data:
                    # Merge data, keeping first found values
                    for key, value in data.items():
                        if value and (key not in combined_data or not combined_data[key]):
                            combined_data[key] = value
                    extraction_sources.append(method.__name__)
            except Exception as e:
                self.logger.debug(f"Method {method.__name__} failed: {e}")
                continue
        
        # Fill missing data with fallback extraction
        combined_data = self._fill_missing_data(combined_data, soup, url)
        combined_data['extraction_sources'] = extraction_sources
        combined_data['url'] = url
        
        return combined_data
    
    def _extract_from_structured_data(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract from JSON-LD structured data (most reliable)"""
        data = {}
        
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                if not script.string:
                    continue
                    
                json_data = json.loads(script.string.strip())
                if isinstance(json_data, list):
                    json_data = json_data[0]
                
                # Handle Product schema
                if json_data.get('@type') == 'Product':
                    data.update(self._parse_product_schema(json_data))
                
                # Handle nested structures
                elif isinstance(json_data, dict):
                    for key, value in json_data.items():
                        if isinstance(value, dict) and value.get('@type') == 'Product':
                            data.update(self._parse_product_schema(value))
                        elif isinstance(value, list):
                            for item in value:
                                if isinstance(item, dict) and item.get('@type') == 'Product':
                                    data.update(self._parse_product_schema(item))
                                    
            except json.JSONDecodeError:
                continue
        
        return data
    
    def _parse_product_schema(self, schema: Dict) -> Dict[str, Any]:
        """Parse Product schema from structured data"""
        data = {}
        
        # Basic product info
        data['product_name'] = schema.get('name', '')
        data['description'] = schema.get('description', '')
        data['brand'] = schema.get('brand', {}).get('name', '') if isinstance(schema.get('brand'), dict) else str(schema.get('brand', ''))
        data['sku'] = schema.get('sku', '')
        data['mpn'] = schema.get('mpn', '')
        
        # Images
        images = []
        image_data = schema.get('image', [])
        if isinstance(image_data, str):
            images.append(image_data)
        elif isinstance(image_data, list):
            images.extend([img if isinstance(img, str) else img.get('url', '') for img in image_data])
        elif isinstance(image_data, dict):
            images.append(image_data.get('url', ''))
        data['product_images'] = images
        
        # Price from offers
        offers = schema.get('offers', {})
        if isinstance(offers, list) and offers:
            offers = offers[0]
        
        if isinstance(offers, dict):
            data['price'] = self._clean_price(offers.get('price', ''))
            data['currency'] = offers.get('priceCurrency', '')
            data['availability'] = offers.get('availability', '')
            
            # Low and high prices
            low_price = offers.get('lowPrice') or offers.get('minPrice')
            high_price = offers.get('highPrice') or offers.get('maxPrice')
            if low_price:
                data['min_price'] = self._clean_price(low_price)
            if high_price:
                data['max_price'] = self._clean_price(high_price)
        
        # Categories
        category = schema.get('category', '')
        if category:
            data['categories'] = [category] if isinstance(category, str) else category
        
        return data
    
    def _extract_from_meta_tags(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract from meta tags (Open Graph, Twitter, etc.)"""
        data = {}
        
        meta_mappings = {
            # Product name
            'product_name': [
                'og:title', 'twitter:title', 'title', 
                'product:title', 'product:name'
            ],
            # Description
            'description': [
                'og:description', 'twitter:description', 'description',
                'product:description'
            ],
            # Images
            'og_image': [
                'og:image', 'twitter:image', 'product:image'
            ],
            # Price
            'price': [
                'product:price:amount', 'og:price:amount', 
                'price', 'product:price'
            ],
            # Currency
            'currency': [
                'product:price:currency', 'og:price:currency'
            ],
            # Brand
            'brand': [
                'product:brand', 'og:brand'
            ]
        }
        
        for data_key, meta_names in meta_mappings.items():
            for meta_name in meta_names:
                # Try property attribute
                meta = soup.find('meta', property=meta_name) or soup.find('meta', name=meta_name)
                if meta and meta.get('content'):
                    content = meta.get('content').strip()
                    if data_key == 'price':
                        data[data_key] = self._clean_price(content)
                    elif data_key == 'og_image':
                        data['product_images'] = data.get('product_images', []) + [content]
                    else:
                        data[data_key] = content
                    break
        
        return data
    
    def _extract_from_microdata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract from microdata attributes"""
        data = {}
        
        microdata_mappings = {
            'product_name': ['name', 'title'],
            'price': ['price', 'offers price'],
            'description': ['description'],
            'brand': ['brand'],
            'image': ['image']
        }
        
        for data_key, itemprop_values in microdata_mappings.items():
            for itemprop in itemprop_values:
                element = soup.find(attrs={'itemprop': itemprop})
                if element:
                    if data_key == 'price':
                        content = element.get('content') or element.get_text(strip=True)
                        data[data_key] = self._clean_price(content)
                    elif data_key == 'image':
                        img_src = element.get('src') or element.get('content') or element.get_text(strip=True)
                        if img_src:
                            data['product_images'] = data.get('product_images', []) + [img_src]
                    else:
                        content = element.get('content') or element.get_text(strip=True)
                        if content:
                            data[data_key] = content
                    break
        
        return data
    
    def _extract_from_javascript_variables(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract from JavaScript variables in script tags"""
        data = {}
        
        script_tags = soup.find_all('script')
        for script in script_tags:
            if not script.string:
                continue
                
            script_content = script.string
            
            # Common JS patterns for product data
            patterns = {
                'product_name': [
                    r'["\']name["\']?\s*:\s*["\']([^"\']+)["\']',
                    r'["\']title["\']?\s*:\s*["\']([^"\']+)["\']',
                    r'["\']productName["\']?\s*:\s*["\']([^"\']+)["\']'
                ],
                'price': [
                    r'["\']price["\']?\s*:\s*["\']?(\d+(?:\.\d{2})?)["\']?',
                    r'["\']regularPrice["\']?\s*:\s*["\']?(\d+(?:\.\d{2})?)["\']?',
                    r'["\']currentPrice["\']?\s*:\s*["\']?(\d+(?:\.\d{2})?)["\']?',
                    r'price["\']?\s*:\s*(\d+(?:\.\d{2})?)',
                ],
                'description': [
                    r'["\']description["\']?\s*:\s*["\']([^"\']+)["\']'
                ],
                'images': [
                    r'["\']image["\']?\s*:\s*["\']([^"\']+)["\']',
                    r'["\']images["\']?\s*:\s*\[([^\]]+)\]'
                ]
            }
            
            for data_key, pattern_list in patterns.items():
                if data_key in data and data[data_key]:  # Skip if already found
                    continue
                    
                for pattern in pattern_list:
                    matches = re.findall(pattern, script_content, re.IGNORECASE)
                    if matches:
                        if data_key == 'price':
                            data[data_key] = self._clean_price(matches[0])
                        elif data_key == 'images':
                            # Parse image array
                            images = re.findall(r'["\']([^"\']+\.(jpg|jpeg|png|webp))["\']', matches[0], re.IGNORECASE)
                            data['product_images'] = [img[0] for img in images]
                        else:
                            data[data_key] = matches[0]
                        break
        
        return data
    
    def _extract_from_dom_patterns(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract using common DOM patterns across e-commerce sites"""
        data = {}
        
        # Universal selectors for different data types
        selectors = {
            'product_name': [
                'h1', '.product-title', '.product-name', '.title', 
                '[class*="title"]', '[class*="name"]', '.product h1',
                '#product-title', '.entry-title'
            ],
            'price': [
                # WooCommerce
                '.woocommerce-Price-amount.amount bdi', '.price .amount', 
                # Shopify
                '.price', '.product-price', '.current-price',
                # Generic
                '.selling-price', '.final-price', '.regular-price',
                '[class*="price"]', '[data-price]', '[itemprop="price"]'
            ],
            'description': [
                '.product-description', '.description', '.product-details',
                '[class*="description"]', '.product-content', '.summary'
            ],
            'images': [
                '.product-image img', '.product-gallery img', '.gallery img',
                '.product img', '[class*="image"] img', '.main-image img'
            ]
        }
        
        for data_key, selector_list in selectors.items():
            if data_key in data and data[data_key]:  # Skip if already found
                continue
                
            for selector in selector_list:
                try:
                    if data_key == 'images':
                        elements = soup.select(selector)
                        images = []
                        for img in elements[:10]:  # Limit to 10 images
                            src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                            if src:
                                images.append(urljoin(url, src))
                        if images:
                            data['product_images'] = images
                            break
                    else:
                        element = soup.select_one(selector)
                        if element:
                            text = element.get_text(strip=True)
                            if text:
                                if data_key == 'price':
                                    cleaned_price = self._clean_price(text)
                                    if cleaned_price:
                                        data[data_key] = cleaned_price
                                        break
                                else:
                                    data[data_key] = text
                                    break
                except Exception as e:
                    continue
        
        return data
    
    def _fill_missing_data(self, data: Dict, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Fill any missing critical data using broad extraction methods"""
        
        # Ensure we have a product name
        if not data.get('product_name'):
            title = soup.find('title')
            if title:
                data['product_name'] = title.get_text().strip()
        
        # Ensure we have images
        if not data.get('product_images'):
            images = []
            img_tags = soup.find_all('img')
            for img in img_tags[:5]:  # Limit to first 5 images
                src = img.get('src') or img.get('data-src')
                if src and not any(skip in src.lower() for skip in ['logo', 'icon', 'banner']):
                    images.append(urljoin(url, src))
            data['product_images'] = images
        
        # Try harder for price if still missing
        if not data.get('price'):
            data['price'] = self._extract_price_aggressive(soup)
        
        # Set defaults for missing fields
        defaults = {
            'description': '',
            'brand': '',
            'categories': [],
            'stock': 100,
            'availability': 'in_stock',
            'currency': 'INR'
        }
        
        for key, default_value in defaults.items():
            if key not in data:
                data[key] = default_value
        
        return data
    
    def _extract_price_aggressive(self, soup: BeautifulSoup) -> Optional[float]:
        """Aggressive price extraction as last resort"""
        
        # Look for any text that looks like a price
        text_content = soup.get_text()
        
        # Pattern for currency + number
        patterns = [
            r'₹\s*([0-9,]+(?:\.[0-9]{1,2})?)',
            r'Rs\.?\s*([0-9,]+(?:\.[0-9]{1,2})?)',
            r'INR\s*([0-9,]+(?:\.[0-9]{1,2})?)',
            r'\$\s*([0-9,]+(?:\.[0-9]{1,2})?)',
            r'Price[:\s]*₹?\s*([0-9,]+(?:\.[0-9]{1,2})?)',
            r'Cost[:\s]*₹?\s*([0-9,]+(?:\.[0-9]{1,2})?)',
            r'MRP[:\s]*₹?\s*([0-9,]+(?:\.[0-9]{1,2})?)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for match in matches:
                price = self._clean_price(match)
                if price and 10 <= price <= 100000:  # Reasonable price range
                    return price
        
        return None
    
    def _clean_price(self, price_text: str) -> Optional[float]:
        """Universal price cleaning"""
        if not price_text:
            return None
        
        # Remove currency symbols and clean
        cleaned = re.sub(r'[₹$€£Rs\.INRUSDEURGBPinrusdeur]', '', str(price_text), flags=re.IGNORECASE)
        cleaned = re.sub(r'[^\d.,]', '', cleaned)
        
        if not cleaned:
            return None
        
        # Handle decimal formats
        if ',' in cleaned and '.' in cleaned:
            cleaned = cleaned.replace(',', '')
        elif ',' in cleaned and len(cleaned.split(',')[1]) <= 2:
            cleaned = cleaned.replace(',', '.')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '')
        
        try:
            price = float(cleaned)
            return price if 1 <= price <= 10000000 else None
        except ValueError:
            return None

# Integration with your existing scraper
def _extract_using_static_html_universal(self, url: str) -> Dict[str, Any]:
    """Universal static HTML extraction that works with ANY e-commerce site"""
    try:
        html_content = await self._fetch_page_content_requests(url)
        if not html_content:
            return None
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Use the universal extractor
        extractor = UniversalEcommerceExtractor()
        result = extractor.extract_all_product_data(soup, url)
        
        if not result.get('product_name'):
            return None
        
        # Format result to match your existing structure
        formatted_result = {
            'product_name': result.get('product_name', ''),
            'price': result.get('price', 0.0),
            'discounted_price': result.get('min_price') or result.get('discounted_price'),
            'description': result.get('description', ''),
            'product_images': result.get('product_images', []),
            'brand': result.get('brand', ''),
            'categories': result.get('categories', []),
            'stock': result.get('stock', 100),
            'availability': result.get('availability', 'in_stock'),
            'currency': result.get('currency', 'INR'),
            'sku': result.get('sku', ''),
            'url': url,
            'extraction_method': 'universal_static_html',
            'extraction_sources': result.get('extraction_sources', []),
            'timestamp': datetime.now().isoformat()
        }
        
        self.log(f"✅ Universal extraction completed for {url}: {formatted_result['product_name']} - ₹{formatted_result['price']}")
        return formatted_result
        
    except Exception as e:
        self.log(f"Universal static HTML extraction failed for {url}: {e}", "ERROR")
        return None