"""
AI-Powered Web Scraper using Google Gemini 1.5 Flash
Intelligent agent that can understand page structures, find pagination, and extract products dynamically
"""

import asyncio
import json
import logging
import os
import time
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from dataclasses import dataclass

from playwright.async_api import async_playwright
from pydantic import HttpUrl
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PaginationInfo:
    """Information about pagination found on a page"""
    has_pagination: bool
    current_page: int
    total_pages: Optional[int]
    next_page_url: Optional[str]
    page_urls: List[str]
    pagination_pattern: str

@dataclass
class PageAnalysis:
    """Analysis results from AI agent"""
    page_type: str  # 'collection', 'product', 'pagination'
    product_links: List[str]
    pagination_info: Optional[PaginationInfo]
    extraction_strategy: Dict[str, Any]
    confidence_score: float

class GeminiAIAgent:
    """AI Agent powered by Google Gemini 1.5 Flash"""
    
    def __init__(self):
        # Configure Gemini
        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable is required")
        
        genai.configure(api_key=api_key)
        
        # Initialize Gemini model
        self.model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            generation_config={
                'temperature': 0.1,  # Low temperature for consistent results
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 4096,
            }
        )
        
        logger.info("Gemini AI Agent initialized successfully")
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """Extract JSON from AI response, handling various formats"""
        if not response_text:
            raise ValueError("Empty response from AI")
        
        # Clean the response
        response_text = response_text.strip()
        
        # Try to find JSON block in markdown code blocks
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{.*?\})',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue
        
        # If no JSON found, try to parse the entire response
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Last resort: try to find key-value pairs
            logger.warning(f"Could not parse JSON from response: {response_text[:200]}...")
            raise ValueError("No valid JSON found in AI response")
    
    async def analyze_page_structure(self, html_content: str, url: str) -> PageAnalysis:
        """Analyze page structure using AI to understand layout and find pagination"""
        
        # Prepare HTML for analysis (truncate if too long)
        analyzed_html = self._prepare_html_for_analysis(html_content)
        
        prompt = f"""You are an expert web scraper analyzing an e-commerce webpage. 

URL: {url}

HTML Content (truncated):
{analyzed_html}

Analyze this page and provide a JSON response with the following exact structure:

{{
    "page_type": "collection",
    "product_links": [
        "https://example.com/product1",
        "https://example.com/product2"
    ],
    "product_link_selectors": [
        "a[href*='/products/']",
        ".product-item a",
        ".product-card a"
    ],
    "pagination_info": {{
        "has_pagination": true,
        "current_page": 1,
        "total_pages": 5,
        "next_page_url": "https://example.com/page2",
        "page_urls": ["https://example.com/page1", "https://example.com/page2"],
        "pagination_pattern": "numbered pagination"
    }},
    "extraction_strategy": {{
        "product_link_selectors": [".product-item a", ".product-card a"],
        "pagination_selectors": [".pagination a", ".page-numbers a"],
        "product_count_indicator": ".product-count",
        "load_more_button": ".load-more"
    }},
    "confidence_score": 0.8
}}

Instructions:
1. Set page_type to "collection" if this shows multiple products, "product" if single product, "unknown" otherwise
2. Extract ALL product URLs you can find (look for href="/products/..." or href="/product/..." patterns)
3. Generate optimal CSS selectors for finding product links on this specific website
4. For Shopify sites, use selectors like: a[href*="/products/"], .product-item a, .grid-item a
5. For WooCommerce sites, use: .product a, .woocommerce-LoopProduct-link, .product-item a
6. Look for pagination elements and determine if there are more pages
7. Provide CSS selectors that work best for this specific website structure
8. Rate your confidence from 0.0 to 1.0

Study the HTML structure carefully and generate selectors that are specific to this website's design patterns.
Focus on finding product links that contain "/products/" or "/product/" in the URL.

Return ONLY the JSON object, no other text."""
        
        try:
            response = await self._call_gemini_async(prompt)
            analysis_data = self._extract_json_from_response(response)
            
            # If AI didn't find product links but provided selectors, try to find them
            if not analysis_data.get('product_links') and analysis_data.get('product_link_selectors'):
                soup = BeautifulSoup(html_content, 'html.parser')
                product_links = self._extract_product_links_with_selectors(
                    soup, analysis_data['product_link_selectors'], url
                )
                analysis_data['product_links'] = product_links
            
            # Convert to PageAnalysis object
            pagination_info = None
            if analysis_data.get('pagination_info'):
                pag_data = analysis_data['pagination_info']
                pagination_info = PaginationInfo(
                    has_pagination=pag_data.get('has_pagination', False),
                    current_page=pag_data.get('current_page', 1),
                    total_pages=pag_data.get('total_pages'),
                    next_page_url=pag_data.get('next_page_url'),
                    page_urls=pag_data.get('page_urls', []),
                    pagination_pattern=pag_data.get('pagination_pattern', '')
                )
            
            return PageAnalysis(
                page_type=analysis_data.get('page_type', 'unknown'),
                product_links=analysis_data.get('product_links', []),
                pagination_info=pagination_info,
                extraction_strategy=analysis_data.get('extraction_strategy', {}),
                confidence_score=analysis_data.get('confidence_score', 0.0)
            )
            
        except Exception as e:
            logger.error(f"Error analyzing page structure: {e}")
            # Fallback analysis
            return self._fallback_analysis(html_content, url)
    
    def _extract_product_links_with_selectors(self, soup: BeautifulSoup, selectors: List[str], base_url: str) -> List[str]:
        """Extract product links using AI-generated selectors"""
        product_links = []
        
        for selector in selectors:
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
                        
                        # Filter out common non-product links but keep product URLs
                        if (href.startswith('http') and 
                            href not in product_links and
                            len(href) < 200):  # Reasonable URL length
                            
                            # Allow product URLs (common patterns)
                            is_product_url = any(pattern in href.lower() for pattern in ['/product/', '/products/', '/item/', '/items/'])
                            
                            # Exclude non-product pages
                            is_excluded = any(x in href.lower() for x in ['cart', 'checkout', 'login', 'register', 'contact', 'about', 'policy', 'terms', 'search', 'category', 'collections', 'blog', 'news', 'account', 'wishlist', 'compare'])
                            
                            if is_product_url or not is_excluded:
                                product_links.append(href)
                            
                        if len(product_links) >= 50:  # Reasonable limit
                            break
            except Exception:
                continue
                
            if len(product_links) >= 50:
                break
        
        return product_links
    
    async def extract_product_data_ai(self, html_content: str, url: str) -> Dict[str, Any]:
        """Extract product data using hybrid AI + traditional approach"""
        
        try:
            # First, try traditional extraction as it's more reliable for actual data
            traditional_data = await self._fallback_product_extraction(html_content, url)
            
            # If traditional extraction got good data, use it
            if (traditional_data.get("price", 0) > 0 or 
                traditional_data.get("product_name", "").strip() not in ["", "Unknown Product", "Extraction Failed"]):
                
                # Enhance with AI analysis for categories and additional metadata
                try:
                    ai_enhancement = await self._get_ai_enhancement(html_content, url, traditional_data)
                    traditional_data.update(ai_enhancement)
                except Exception as e:
                    logger.warning(f"AI enhancement failed, using traditional data: {e}")
                
                traditional_data["extraction_method"] = "hybrid_traditional_ai"
                return traditional_data
            
            # If traditional failed, try pure AI extraction
            return await self._pure_ai_extraction(html_content, url)
            
        except Exception as e:
            logger.error(f"Error in hybrid extraction: {e}")
            return await self._fallback_product_extraction(html_content, url)
    
    async def _pure_ai_extraction(self, html_content: str, url: str) -> Dict[str, Any]:
        """Pure AI extraction as fallback"""
        analyzed_html = self._prepare_html_for_analysis(html_content, 8000)
        
        prompt = f"""Extract product data from this e-commerce page. Return ONLY a JSON object.

URL: {url}

HTML:
{analyzed_html}

Extract these fields and return as JSON:
- product_name: The main product title
- price: Numeric price (extract numbers from price text like "₹1,999" → 1999)
- product_images: Array of image URLs (make absolute URLs)
- description: Product description text
- sizes: Array of available sizes ONLY (like ["XS", "S", "M", "L", "XL"])
- colors: Array of available colors ONLY (like ["Red", "Blue", "Green"])
- material: Material/fabric information
- categories: Array of product categories from breadcrumbs/navigation
- brand: Brand name
- availability: "InStock" or "OutOfStock"

CRITICAL INSTRUCTIONS FOR SIZES AND COLORS:
1. SIZES should contain ONLY size values: XS, S, M, L, XL, 2XL, 3XL, etc.
2. COLORS should contain ONLY color names: Red, Blue, Green, Yellow, etc.
3. If you find combined variants like "XS / Blue" or "M / Red", SEPARATE them:
   - Extract "XS", "M" for sizes array
   - Extract "Blue", "Red" for colors array
4. Look for these patterns:
   - Select dropdowns: <select><option>XS</option><option>S</option></select>
   - Variant buttons: <button data-size="M">M</button>
   - JSON data: "variants": [{{"title": "S / Red"}}, {{"title": "M / Blue"}}]
   - Option lists: <li data-variant="L">L</li>

EXAMPLES:
- If you see "XS / Blue", "S / Blue", "M / Red" → sizes: ["XS","S","M"], colors: ["Blue","Red"]
- If you see combined options, split them properly
- Ignore "Default Title", "Select Size", "Choose Color" etc.

Example response:
{{"product_name": "Red Silk Saree", "price": 2999, "product_images": ["https://example.com/img1.jpg"], "description": "Beautiful red silk saree", "sizes": ["S","M","L","XL"], "colors": ["Red","Blue","Green"], "material": "Silk", "categories": ["Sarees"], "brand": "Brand Name", "availability": "InStock"}}

Return ONLY the JSON, no other text."""
        
        try:
            response = await self._call_gemini_async(prompt)
            product_data = self._extract_json_from_response(response)
            
            # Ensure required fields
            product_data.setdefault("product_name", "AI Extracted Product")
            product_data.setdefault("price", 0.0)
            product_data.setdefault("product_images", [])
            product_data.setdefault("description", "")
            product_data.setdefault("sizes", [])
            product_data.setdefault("colors", [])
            product_data.setdefault("material", "")
            
            # Structure metadata
            if "metadata" not in product_data:
                product_data["metadata"] = {}
            
            product_data["metadata"].update({
                "availability": product_data.pop("availability", "InStock"),
                "brand": product_data.pop("brand", ""),
                "categories": product_data.pop("categories", []),
                "tags": [],
                "rating": None,
                "review_count": None,
                "specifications": {},
                "variants": []
            })
            
            product_data.update({
                "source_url": url,
                "timestamp": datetime.now().isoformat(),
                "extraction_method": "pure_ai"
            })
            
            return product_data
            
        except Exception as e:
            logger.error(f"Pure AI extraction failed: {e}")
            raise
    
    async def _get_ai_enhancement(self, html_content: str, url: str, base_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI enhancement for categories and metadata"""
        analyzed_html = self._prepare_html_for_analysis(html_content, 6000)
        
        prompt = f"""Analyze this product page and extract additional metadata. Return ONLY a JSON object.

Current product: {base_data.get('product_name', 'Unknown')}
URL: {url}

HTML:
{analyzed_html}

Extract these additional fields:
- categories: Array of product categories from breadcrumbs, navigation, or content
- tags: Array of relevant product tags/keywords
- specifications: Object with key-value pairs of product specs
- brand: Brand name if found

Example: {{"categories": ["Sarees", "Traditional Wear"], "tags": ["ethnic", "formal"], "specifications": {{"Care": "Dry clean", "Occasion": "Wedding"}}, "brand": "Brand Name"}}

Return ONLY the JSON."""
        
        try:
            response = await self._call_gemini_async(prompt)
            enhancement = self._extract_json_from_response(response)
            
            # Update metadata
            if "metadata" not in base_data:
                base_data["metadata"] = {}
            
            base_data["metadata"].update({
                "categories": enhancement.get("categories", base_data["metadata"].get("categories", [])),
                "tags": enhancement.get("tags", []),
                "specifications": enhancement.get("specifications", {}),
                "brand": enhancement.get("brand", base_data["metadata"].get("brand", ""))
            })
            
            return {"metadata": base_data["metadata"]}
            
        except Exception as e:
            logger.warning(f"AI enhancement failed: {e}")
            return {}
    
    async def _fallback_product_extraction(self, html_content: str, url: str) -> Dict[str, Any]:
        """Dynamic product extraction using AI-generated selectors for each website"""
        try:
            # First, get AI-generated selectors for this specific website
            selectors = await self._get_dynamic_selectors_for_website(html_content, url)
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract product name using AI-generated selectors
            product_name = self._extract_text_by_selectors(soup, selectors.get('name_selectors', [])) or "Unknown Product"
            
            # Extract price using AI-generated selectors
            price = self._extract_price_with_selectors(soup, selectors.get('price_selectors', []))
            
            # Extract images using AI-generated selectors
            images = self._extract_images_with_selectors(soup, selectors.get('image_selectors', []), url)
            
            # Extract description using AI-generated selectors
            description = self._extract_text_by_selectors(soup, selectors.get('description_selectors', [])) or ""
            
            # Extract sizes using AI-generated selectors
            sizes = self._extract_sizes_with_selectors(soup, selectors.get('size_selectors', []))
            
            # Extract colors using AI-generated selectors
            colors = self._extract_colors_with_selectors(soup, selectors.get('color_selectors', []))
            
            # Extract categories using AI-generated selectors
            categories = self._extract_multiple_texts(soup, selectors.get('category_selectors', []))
            
            # Extract material using AI-generated selectors + keyword detection
            material = self._extract_text_by_selectors(soup, selectors.get('material_selectors', [])) or ""
            if not material:
                material = self._detect_material_from_text(description + " " + product_name)
            
            # Check availability using AI-generated selectors
            availability = "InStock"
            if selectors.get('availability_selectors'):
                availability_text = self._extract_text_by_selectors(soup, selectors['availability_selectors'])
                if availability_text and any(word in availability_text.lower() for word in ['out', 'sold', 'unavailable']):
                    availability = "OutOfStock"
            
            product_data = {
                "product_name": product_name,
                "price": price,
                "discounted_price": None,
                "product_images": images,
                "description": description[:500] if description else "",
                "sizes": sizes,
                "colors": colors,
                "material": material,
                "metadata": {
                    "availability": availability,
                    "sku": "",
                    "brand": "",
                    "categories": categories,
                    "tags": [],
                    "rating": None,
                    "review_count": None,
                    "specifications": {},
                    "variants": [],
                    "ai_selectors_used": selectors  # Store the AI-generated selectors for debugging
                },
                "source_url": url,
                "timestamp": datetime.now().isoformat(),
                "extraction_method": "dynamic_ai_selectors"
            }
            
            return product_data
            
        except Exception as e:
            logger.error(f"Dynamic selector extraction failed: {e}")
            # Fallback to static selectors as last resort
            return await self._static_fallback_extraction(html_content, url)

    def _extract_text_by_selectors(self, soup: BeautifulSoup, selectors: List[str]) -> str:
        """Extract text using CSS selectors"""
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if text:
                        return text
            except Exception:
                continue
        return ""

    def _extract_price_with_selectors(self, soup: BeautifulSoup, selectors: List[str]) -> float:
        """Extract price using CSS selectors"""
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    price_text = element.get_text(strip=True)
                    if price_text:
                        price = self._extract_price_from_text(price_text)
                        if price > 0:
                            return price
            except Exception:
                continue
        return 0.0

    def _extract_price_from_text(self, text: str) -> float:
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

    def _extract_images_with_selectors(self, soup: BeautifulSoup, selectors: List[str], base_url: str) -> List[str]:
        """Extract product images using selectors"""
        images = []
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for img in elements:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if src:
                        # Make absolute URL
                        if src.startswith('/'):
                            src = urljoin(base_url, src)
                        elif not src.startswith('http'):
                            src = urljoin(base_url, src)
                        
                        # Filter out small images (likely icons/thumbnails)
                        if src not in images and not any(x in src.lower() for x in ['icon', 'logo', 'thumb']):
                            images.append(src)
                            
                        if len(images) >= 10:  # Reasonable limit
                            break
            except Exception:
                continue
                
            if len(images) >= 10:
                break
        
        return images

    def _extract_multiple_texts(self, soup: BeautifulSoup, selectors: List[str]) -> List[str]:
        """Extract multiple text values using selectors"""
        texts = []
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if text and text not in texts:
                        texts.append(text)
                        if len(texts) >= 5:  # Reasonable limit
                            break
            except Exception:
                continue
                
            if len(texts) >= 5:
                break
        
        return texts

    def _detect_material_from_text(self, text: str) -> str:
        """Detect material from text using keywords"""
        if not text:
            return ""
        
        material_keywords = [
            'cotton', 'silk', 'georgette', 'chiffon', 'organza', 'polyester', 
            'rayon', 'linen', 'wool', 'satin', 'velvet', 'crepe', 'net'
        ]
        
        text_lower = text.lower()
        found_materials = []
        
        for material in material_keywords:
            if material in text_lower:
                found_materials.append(material.title())
        
        return ', '.join(found_materials) if found_materials else ""

    def _extract_sizes_with_selectors(self, soup: BeautifulSoup, selectors: List[str]) -> List[str]:
        """Extract available sizes using CSS selectors with enhanced logic"""
        sizes = []
        
        # First try to get sizes from Shopify product JSON
        sizes_from_json = self._extract_variants_from_json(soup, 'size')
        if sizes_from_json:
            return sizes_from_json
        
        # Use provided selectors with enhanced extraction
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    # Get text from different sources
                    potential_sizes = []
                    
                    # Text content
                    text_content = element.get_text(strip=True)
                    if text_content:
                        potential_sizes.append(text_content)
                    
                    # Value attribute (for inputs/options)
                    if element.get('value'):
                        potential_sizes.append(element.get('value'))
                    
                    # Data attributes
                    for attr in ['data-size', 'data-value', 'data-variant', 'data-option']:
                        if element.get(attr):
                            potential_sizes.append(element.get(attr))
                    
                    # Process each potential size
                    for size_text in potential_sizes:
                        if not size_text:
                            continue
                            
                        # Handle combined variants (like "XS / Blue")
                        if ' / ' in size_text or ' \/ ' in size_text:
                            parsed_sizes = self._parse_combined_variants([size_text], 'size')
                            sizes.extend(parsed_sizes)
                        else:
                            # Check if it's a valid size
                            if self._is_size_variant(size_text) and size_text not in sizes:
                                sizes.append(size_text.strip())
                                
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        return self._clean_and_deduplicate_variants(sizes, 'size')

    def _extract_colors_with_selectors(self, soup: BeautifulSoup, selectors: List[str]) -> List[str]:
        """Extract available colors using CSS selectors with enhanced logic"""
        colors = []
        
        # First try to get colors from Shopify product JSON
        colors_from_json = self._extract_variants_from_json(soup, 'color')
        if colors_from_json:
            return colors_from_json
        
        # Use provided selectors with enhanced extraction
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    # Get text from different sources
                    potential_colors = []
                    
                    # Text content
                    text_content = element.get_text(strip=True)
                    if text_content:
                        potential_colors.append(text_content)
                    
                    # Value attribute (for inputs/options)
                    if element.get('value'):
                        potential_colors.append(element.get('value'))
                    
                    # Data attributes
                    for attr in ['data-color', 'data-value', 'data-variant', 'data-option', 'data-color-name']:
                        if element.get(attr):
                            potential_colors.append(element.get(attr))
                    
                    # Title attribute (often used for color names)
                    if element.get('title'):
                        potential_colors.append(element.get('title'))
                    
                    # Alt attribute for color images
                    if element.get('alt'):
                        potential_colors.append(element.get('alt'))
                    
                    # Process each potential color
                    for color_text in potential_colors:
                        if not color_text:
                            continue
                            
                        # Handle combined variants (like "XS / Blue")
                        if ' / ' in color_text or ' \/ ' in color_text:
                            parsed_colors = self._parse_combined_variants([color_text], 'color')
                            colors.extend(parsed_colors)
                        else:
                            # Check if it's a valid color
                            if self._is_color_variant(color_text) and color_text not in colors:
                                colors.append(color_text.strip())
                                
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        return self._clean_and_deduplicate_variants(colors, 'color')

    def _extract_variants_from_json(self, soup: BeautifulSoup, variant_type: str) -> List[str]:
        """Extract specific variant type (size/color) from Shopify product JSON with enhanced parsing"""
        variants = []
        
        # Look for Shopify product JSON in various script tags
        all_scripts = soup.find_all('script')
        for script in all_scripts:
            if script.string and ('product' in script.string.lower() and ('variants' in script.string.lower() or 'options' in script.string.lower())):
                try:
                    script_content = script.string
                    
                    # Enhanced pattern matching for variants
                    variants_patterns = [
                        r'"variants"\s*:\s*\[(.*?)\]',
                        r'"options"\s*:\s*\[(.*?)\]',
                        r'"product"\s*:\s*{[^}]*"variants"\s*:\s*\[(.*?)\]',
                    ]
                    
                    for variants_pattern in variants_patterns:
                        variants_match = re.search(variants_pattern, script_content, re.DOTALL)
                        if variants_match:
                            variants_str = variants_match.group(1)
                            
                            # Extract combined variants (like "XS / Blue", "M / Red")
                            combined_variants = []
                            combined_patterns = [
                                r'"public_title"\s*:\s*"([^"]*)"',
                                r'"title"\s*:\s*"([^"]*)"',
                                r'"option1"\s*:\s*"([^"]*)"',
                                r'"name"\s*:\s*"([^"]*)"'
                            ]
                            
                            for pattern in combined_patterns:
                                matches = re.findall(pattern, variants_str)
                                for match in matches:
                                    if match and match.strip() and match.strip() not in combined_variants:
                                        combined_variants.append(match.strip())
                            
                            # Parse combined variants to separate sizes and colors
                            parsed_variants = self._parse_combined_variants(combined_variants, variant_type)
                            if parsed_variants:
                                variants.extend(parsed_variants)
                    
                    # Also look for product data structures
                    product_patterns = [
                        r'window\.product\s*=\s*({.*?});',
                        r'var\s+product\s*=\s*({.*?});',
                        r'let\s+product\s*=\s*({.*?});',
                        r'const\s+product\s*=\s*({.*?});',
                        r'"product"\s*:\s*({.*?})',
                        r'product:\s*({.*?})',
                    ]
                    
                    for pattern in product_patterns:
                        matches = re.findall(pattern, script_content, re.DOTALL)
                        for match in matches:
                            try:
                                product_data = json.loads(match)
                                if isinstance(product_data, dict):
                                    # Extract from product options (more structured approach)
                                    extracted_variants = self._extract_from_product_options(product_data, variant_type)
                                    if extracted_variants:
                                        variants.extend(extracted_variants)
                                    
                                    # Extract from variants array with better parsing
                                    if 'variants' in product_data and isinstance(product_data['variants'], list):
                                        variant_titles = []
                                        for variant in product_data['variants']:
                                            if isinstance(variant, dict):
                                                # Try multiple fields for variant data
                                                title_fields = ['public_title', 'title', 'option1', 'option2', 'option3']
                                                for field in title_fields:
                                                    if field in variant and variant[field]:
                                                        variant_titles.append(str(variant[field]))
                                        
                                        # Parse all variant titles
                                        parsed_variants = self._parse_combined_variants(variant_titles, variant_type)
                                        if parsed_variants:
                                            variants.extend(parsed_variants)
                                
                                if variants:
                                    # Clean and deduplicate
                                    variants = self._clean_and_deduplicate_variants(variants, variant_type)
                                    return variants
                                    
                            except json.JSONDecodeError:
                                continue
                except Exception as e:
                    logger.debug(f"Error parsing variants from script: {e}")
                    continue
        
        return self._clean_and_deduplicate_variants(variants, variant_type)

    def _parse_combined_variants(self, combined_variants: List[str], variant_type: str) -> List[str]:
        """Parse combined variants like 'XS / Blue' into separate sizes and colors"""
        parsed = []
        
        for variant in combined_variants:
            if not variant or not isinstance(variant, str):
                continue
                
            variant = variant.strip()
            
            # Handle combined variants with separators
            separators = [' / ', ' \/ ', '/', ' - ', ' | ', ' : ']
            parts = [variant]  # Default to single part
            
            for sep in separators:
                if sep in variant:
                    parts = [part.strip() for part in variant.split(sep) if part.strip()]
                    break
            
            # Analyze each part to determine if it's size or color
            for part in parts:
                if self._is_size_variant(part) and variant_type.lower() == 'size':
                    if part not in parsed:
                        parsed.append(part)
                elif self._is_color_variant(part) and variant_type.lower() == 'color':
                    if part not in parsed:
                        parsed.append(part)
        
        return parsed

    def _is_size_variant(self, text: str) -> bool:
        """Determine if a text represents a size variant"""
        if not text or len(text) > 10:  # Sizes are usually short
            return False
            
        text = text.strip().upper()
        
        # Common size patterns
        size_patterns = [
            r'^(XXS|XS|S|M|L|XL|2XL|3XL|4XL|5XL|6XL)$',  # Standard sizes
            r'^\d+XL$',  # Numeric XL sizes
            r'^\d+$',  # Numeric sizes
            r'^\d+[A-Z]$',  # Like 32B, 34C
            r'^(ONE SIZE|FREE SIZE|OS)$',  # One size
            r'^\d+[\s\-]*\d+$',  # Size ranges like 32-34
        ]
        
        for pattern in size_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False

    def _is_color_variant(self, text: str) -> bool:
        """Determine if a text represents a color variant"""
        if not text or len(text) > 25:  # Colors shouldn't be too long
            return False
            
        text = text.strip()
        
        # Skip if it looks like a size
        if self._is_size_variant(text):
            return False
        
        # Common color words and patterns
        color_keywords = [
            'red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink', 'black', 'white', 'grey', 'gray',
            'brown', 'beige', 'navy', 'maroon', 'teal', 'cyan', 'magenta', 'lime', 'olive', 'silver',
            'gold', 'coral', 'salmon', 'turquoise', 'violet', 'indigo', 'cream', 'ivory', 'tan',
            'crimson', 'scarlet', 'emerald', 'sapphire', 'ruby', 'amber', 'rose', 'lavender',
            # Indian/fashion specific colors
            'mehendi', 'haldi', 'mustard', 'wine', 'burgundy', 'peach', 'mint', 'sage', 'rust',
            'copper', 'bronze', 'champagne', 'blush', 'nude', 'mocha', 'chocolate', 'camel'
        ]
        
        text_lower = text.lower()
        
        # Check if text contains color keywords
        for color in color_keywords:
            if color in text_lower:
                return True
        
        # Check for color-like patterns (not sizes)
        if len(text) >= 3 and not re.match(r'^(XXS|XS|S|M|L|XL|\d+XL|\d+)$', text, re.IGNORECASE):
            # If it's not a clear size pattern and has reasonable length, likely a color
            return True
        
        return False

    def _extract_from_product_options(self, product_data: dict, variant_type: str) -> List[str]:
        """Extract variants from structured product options"""
        variants = []
        
        if 'options' in product_data and isinstance(product_data['options'], list):
            for option in product_data['options']:
                if isinstance(option, dict):
                    option_name = str(option.get('name', '')).lower()
                    option_values = option.get('values', [])
                    
                    # Check if this option matches our variant type
                    if variant_type.lower() in option_name or (
                        variant_type.lower() == 'size' and any(keyword in option_name for keyword in ['size', 'dimension']) or
                        variant_type.lower() == 'color' and any(keyword in option_name for keyword in ['color', 'colour', 'shade'])
                    ):
                        if isinstance(option_values, list):
                            for value in option_values:
                                if value and str(value).strip():
                                    variants.append(str(value).strip())
        
        return variants

    def _clean_and_deduplicate_variants(self, variants: List[str], variant_type: str) -> List[str]:
        """Clean and deduplicate variant list"""
        if not variants:
            return []
        
        cleaned = []
        seen = set()
        
        for variant in variants:
            if not variant or not isinstance(variant, str):
                continue
                
            variant = variant.strip()
            
            # Skip common non-variant values
            skip_values = {
                'default title', 'select size', 'choose an option', 'size', 'color', 'colour',
                'select', 'choose', 'pick', 'default', 'title', '', 'null', 'undefined'
            }
            
            if variant.lower() in skip_values:
                continue
            
            # Additional validation based on variant type
            if variant_type.lower() == 'size':
                if not self._is_size_variant(variant):
                    continue
            elif variant_type.lower() == 'color':
                if not self._is_color_variant(variant):
                    continue
            
            # Deduplicate (case insensitive)
            variant_key = variant.lower()
            if variant_key not in seen:
                seen.add(variant_key)
                cleaned.append(variant)
        
        return cleaned

    async def _get_dynamic_selectors_for_website(self, html_content: str, url: str) -> Dict[str, List[str]]:
        """Generate completely dynamic selectors for any website using AI analysis"""
        
        # Prepare HTML for analysis (get relevant sections)
        analyzed_html = self._prepare_html_for_analysis(html_content, focus_on_products=True)
        
        prompt = f"""You are an expert web scraper. Analyze this HTML from {url} and generate CSS selectors for extracting product data.

HTML Content:
{analyzed_html}

Generate CSS selectors that will work for THIS specific website. Return ONLY a JSON object with these exact keys:

{{
    "name_selectors": [
        "list of CSS selectors to find product names/titles"
    ],
    "price_selectors": [
        "list of CSS selectors to find product prices"
    ],
    "image_selectors": [
        "list of CSS selectors to find product images"
    ],
    "description_selectors": [
        "list of CSS selectors to find product descriptions"
    ],
    "size_selectors": [
        "list of CSS selectors to find product sizes/variants"
    ],
    "color_selectors": [
        "list of CSS selectors to find product colors/variants"
    ],
    "category_selectors": [
        "list of CSS selectors to find product categories"
    ],
    "availability_selectors": [
        "list of CSS selectors to find stock/availability"
    ]
}}

CRITICAL SELECTOR REQUIREMENTS:

FOR SIZE SELECTORS - Look for these patterns:
- select[name*="size"] option, select[data-option="Size"] option
- .size-selector option, .variant-selector[data-type="size"] option
- input[type="radio"][name*="size"], button[data-size]
- .product-option-size .option-value, .size-variant button
- .variant-input-wrap:has(label:contains("Size")) input
- [data-variant-size], .size-option, .size-item
- For Shopify: select[data-index="0"] option, .product-form__option-value

FOR COLOR SELECTORS - Look for these patterns:
- select[name*="color"] option, select[data-option="Color"] option
- .color-selector option, .variant-selector[data-type="color"] option
- input[type="radio"][name*="color"], button[data-color]
- .product-option-color .option-value, .color-variant button
- .variant-input-wrap:has(label:contains("Color")) input
- [data-variant-color], .color-option, .color-item, .color-swatch
- For Shopify: select[data-index="1"] option, .product-form__option-value

ANALYSIS RULES:
1. Study the actual HTML structure above carefully
2. Look for form elements, select dropdowns, radio buttons, variant selectors
3. Generate 5-8 selectors per category, from most specific to general
4. Include both class-based and attribute-based selectors
5. For e-commerce platforms:
   - Shopify: .product-title, .money, .product__title, select[data-index] option
   - WooCommerce: .woocommerce-Price-amount, .product-name, .variations select option
   - Custom sites: Look for variant patterns, option selectors
6. Always include generic fallbacks: h1, h2, select option, input[type="radio"]
7. Return ONLY valid JSON, no explanations

Focus especially on finding size and color variant selectors in the HTML structure."""

        try:
            response = await self._call_gemini_async(prompt)
            
            # Clean and parse JSON
            selectors = self._extract_json_from_response(response)
            
            # Validate and enhance selectors
            enhanced_selectors = self._enhance_selectors(selectors, html_content)
            
            logger.info(f"Generated dynamic selectors for {url}: {len(enhanced_selectors)} categories")
            return enhanced_selectors
            
        except Exception as e:
            logger.warning(f"Failed to generate dynamic selectors for {url}: {e}")
            # Return comprehensive fallback selectors
            return self._get_comprehensive_fallback_selectors()

    def _prepare_html_for_analysis(self, html_content: str, focus_on_products: bool = False) -> str:
        """Prepare HTML for AI analysis with focus on product-related elements"""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unnecessary elements
        for tag in soup.find_all(['script', 'style', 'noscript', 'meta', 'link']):
            tag.decompose()
        
        if focus_on_products:
            # Focus on product-related sections
            product_sections = []
            
            # Look for common product container patterns
            product_containers = soup.find_all(class_=re.compile(r'product|item|card|grid|list', re.I))
            for container in product_containers[:10]:  # Limit to first 10 for analysis
                product_sections.append(str(container)[:1000])  # Limit each section
            
            # If no product containers found, get general content
            if not product_sections:
                main_content = soup.find('main') or soup.find('body') or soup
                product_sections.append(str(main_content)[:2000])
            
            return '\n'.join(product_sections)
        
        # General HTML preparation
        main_content = soup.find('main') or soup.find('body') or soup
        return str(main_content)[:3000]  # Limit to 3000 chars

    def _enhance_selectors(self, selectors: Dict[str, List[str]], html_content: str) -> Dict[str, List[str]]:
        """Enhance AI-generated selectors with additional fallbacks and validations"""
        
        enhanced = {}
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Base fallback selectors for each category
        fallback_selectors = {
            'name_selectors': [
                'h1', 'h2', 'h3', '.title', '.name', '.product-title', '.product-name',
                '.product__title', '[data-product-title]', '.entry-title', '.page-title'
            ],
            'price_selectors': [
                '.price', '.cost', '.amount', '.money', '.product-price', '.price-current',
                '.woocommerce-Price-amount', '.price-amount', '[data-price]', '.sale-price',
                '.regular-price', '.product__price', '.price-item'
            ],
            'image_selectors': [
                'img', '.product-image img', '.product-photo img', '.item-image img',
                '.gallery img', '.product__media img', '[data-product-image]'
            ],
            'description_selectors': [
                '.description', '.product-description', '.summary', '.product-summary',
                '.content', '.details', '.product-details', '.product__description'
            ],
            'size_selectors': [
                # Shopify variant selectors
                'select[data-index="0"] option',
                'select[name*="size"] option',
                '.variant-input-wrap:has(label:contains("Size")) input',
                '.product-form__option[data-option-name*="size"] .product-form__option-value',
                '[data-option="Size"] option',
                '.size-selector option',
                '.variant-option-size .variant-option-value',
                # WooCommerce selectors
                'select[data-attribute_name*="size"] option',
                'select[name*="attribute_pa_size"] option',
                '.variations select option',
                # Generic selectors
                '.size-options option',
                '.product-options select option',
                '.size', '.sizes', '.size-item', '.size-option'
            ],
            'color_selectors': [
                # Shopify variant selectors
                'select[data-index="1"] option',
                'select[name*="color"] option',
                '.variant-input-wrap:has(label:contains("Color")) input',
                '.product-form__option[data-option-name*="color"] .product-form__option-value',
                '[data-option="Color"] option',
                '.color-selector option',
                '.variant-option-color .variant-option-value',
                # WooCommerce selectors
                'select[data-attribute_name*="color"] option',
                'select[name*="attribute_pa_color"] option',
                '.variations select option',
                # Generic selectors
                '.color-options option',
                '.product-options select option',
                '.color', '.colors', '.color-item', '.color-option'
            ],
            'category_selectors': [
                '.category', '.categories', '.breadcrumb', '.product-category', '.tags',
                '.product-type', '.collection', '.product__tags'
            ],
            'availability_selectors': [
                '.stock', '.availability', '.in-stock', '.out-of-stock', '.inventory',
                '.product-availability', '.stock-status', '[data-stock]'
            ]
        }
        
        for key in fallback_selectors.keys():
            enhanced[key] = []
            
            # Add AI-generated selectors first
            if key in selectors and isinstance(selectors[key], list):
                enhanced[key].extend(selectors[key])
            
            # Add fallback selectors
            enhanced[key].extend(fallback_selectors[key])
            
            # Remove duplicates while preserving order
            enhanced[key] = list(dict.fromkeys(enhanced[key]))
            
            # Validate selectors by testing them
            enhanced[key] = self._validate_selectors(enhanced[key], soup)
        
        return enhanced

    def _validate_selectors(self, selectors: List[str], soup: BeautifulSoup) -> List[str]:
        """Validate CSS selectors by testing them against the HTML"""
        
        valid_selectors = []
        
        for selector in selectors:
            try:
                # Test if selector is valid and finds elements
                elements = soup.select(selector)
                if elements:  # Only include selectors that find elements
                    valid_selectors.append(selector)
                else:
                    # Still include it as it might work on product pages
                    valid_selectors.append(selector)
            except Exception:
                # Skip invalid selectors
                continue
        
        return valid_selectors

    def _get_comprehensive_fallback_selectors(self) -> Dict[str, List[str]]:
        """Get comprehensive fallback selectors for any website"""
        
        return {
            'name_selectors': [
                'h1', 'h2', 'h3', '.title', '.name', '.product-title', '.product-name',
                '.product__title', '.item-title', '.entry-title', '.page-title',
                '[data-product-title]', '.product-info h1', '.product-info h2',
                '.card-title', '.item-name', '.product-card h3', '.listing-title'
            ],
            'price_selectors': [
                '.price', '.cost', '.amount', '.money', '.product-price', '.price-current',
                '.woocommerce-Price-amount', '.price-amount', '[data-price]', '.sale-price',
                '.regular-price', '.product__price', '.price-item', '.price-box',
                '.price-current', '.current-price', '.final-price', '.special-price'
            ],
            'image_selectors': [
                'img', '.product-image img', '.product-photo img', '.item-image img',
                '.gallery img', '.product__media img', '[data-product-image]',
                '.product-card img', '.listing-image img', '.thumbnail img'
            ],
            'description_selectors': [
                '.description', '.product-description', '.summary', '.product-summary',
                '.content', '.details', '.product-details', '.product__description',
                '.short-description', '.excerpt', '.product-content'
            ],
            'size_selectors': [
                # Shopify specific selectors (most specific first)
                'select[data-index="0"] option',
                '.product-form__option[data-option-name*="size"] .product-form__option-value',
                '.product-form__option[data-option-name*="Size"] .product-form__option-value',
                'select[name*="properties[Size]"] option',
                '.variant-input-wrap:has(label:contains("Size")) input',
                '.variant-input-wrap:has(label:contains("size")) input',
                
                # WooCommerce specific selectors
                'select[data-attribute_name*="size"] option',
                'select[name*="attribute_pa_size"] option',
                '.variations select option',
                '.woocommerce-variation-selection select option',
                
                # Generic e-commerce selectors
                'select[name*="size"] option',
                'select[name*="Size"] option',
                'input[type="radio"][name*="size"]',
                'input[type="radio"][name*="Size"]',
                'button[data-size]',
                'button[data-variant-size]',
                '[data-option="Size"] option',
                '[data-option="size"] option',
                
                # Class-based selectors
                '.size-selector option',
                '.size-options option',
                '.product-options select option',
                '.variant-option-size .variant-option-value',
                '.size-variant',
                '.size-item',
                '.size-option',
                '.size',
                '.sizes',
                
                # Fallback selectors
                'select option',
                'input[type="radio"]',
                'button[data-variant]'
            ],
            'color_selectors': [
                # Shopify specific selectors (most specific first)
                'select[data-index="1"] option',
                '.product-form__option[data-option-name*="color"] .product-form__option-value',
                '.product-form__option[data-option-name*="Color"] .product-form__option-value',
                '.product-form__option[data-option-name*="colour"] .product-form__option-value',
                'select[name*="properties[Color]"] option',
                '.variant-input-wrap:has(label:contains("Color")) input',
                '.variant-input-wrap:has(label:contains("color")) input',
                
                # WooCommerce specific selectors
                'select[data-attribute_name*="color"] option',
                'select[data-attribute_name*="colour"] option',
                'select[name*="attribute_pa_color"] option',
                'select[name*="attribute_pa_colour"] option',
                '.variations select option',
                '.woocommerce-variation-selection select option',
                
                # Generic e-commerce selectors
                'select[name*="color"] option',
                'select[name*="Color"] option',
                'select[name*="colour"] option',
                'input[type="radio"][name*="color"]',
                'input[type="radio"][name*="Color"]',
                'button[data-color]',
                'button[data-colour]',
                'button[data-variant-color]',
                '[data-option="Color"] option',
                '[data-option="color"] option',
                '[data-option="Colour"] option',
                
                # Class-based selectors
                '.color-selector option',
                '.colour-selector option',
                '.color-options option',
                '.colour-options option',
                '.product-options select option',
                '.variant-option-color .variant-option-value',
                '.color-variant',
                '.colour-variant',
                '.color-item',
                '.colour-item',
                '.color-option',
                '.colour-option',
                '.color-swatch',
                '.colour-swatch',
                '.color',
                '.colors',
                '.colour',
                '.colours',
                
                # Visual color selectors
                '.swatch[data-color]',
                '.swatch[title]',
                '.color-circle[data-color]',
                '.color-square[data-color]',
                
                # Fallback selectors
                'select option',
                'input[type="radio"]',
                'button[data-variant]'
            ],
            'category_selectors': [
                '.category', '.categories', '.breadcrumb', '.product-category', '.tags',
                '.product-type', '.collection', '.product__tags', '.product-meta',
                '.product-categories', '.item-category'
            ],
            'availability_selectors': [
                '.stock', '.availability', '.in-stock', '.out-of-stock', '.inventory',
                '.product-availability', '.stock-status', '[data-stock]', '.stock-level',
                '.inventory-status', '.product-stock'
            ]
        }

    async def _static_fallback_extraction(self, html_content: str, url: str) -> Dict[str, Any]:
        """Static fallback extraction method"""
        return await self._fallback_product_extraction(html_content, url)

    async def find_pagination_urls(self, html_content: str, current_url: str, max_pages: int = 50) -> List[str]:
        """Find all pagination URLs using AI analysis"""
        
        analyzed_html = self._prepare_html_for_analysis(html_content)
        
        prompt = f"""You are analyzing an e-commerce webpage to find pagination URLs.

Current URL: {current_url}
Max pages needed: {max_pages}

HTML Content (truncated):
{analyzed_html}

Analyze pagination patterns and return a JSON response with this exact structure:

{{
    "pagination_urls": [
        "{current_url}",
        "https://example.com/page2",
        "https://example.com/page3"
    ],
    "pagination_type": "numbered",
    "total_pages_estimate": 10,
    "url_pattern": "?page=X pattern found"
}}

Instructions:
1. Look for pagination elements: .pagination, .page-numbers, .pager, numbered links (1,2,3...)
2. Check for Next/Previous buttons and their href attributes
3. Look for Shopify pagination: ?page=X patterns
4. Check for WooCommerce pagination: /page/X/ patterns  
5. Find WordPress pagination: /page/X patterns
6. Look for generic pagination: ?p=X, ?page=X patterns
7. Check HTML meta links: <link rel="next" href="...">
8. Generate complete absolute URLs starting with http/https
9. Include the current URL as page 1
10. Limit to {max_pages} URLs maximum
11. For Shopify sites (collections/): use ?page=X format
12. For WooCommerce sites (/shop/): use /page/X/ format

Website type detection:
- If URL contains "collections/" or "products/" → likely Shopify
- If URL contains "/shop/" → likely WooCommerce  
- If URL contains "/page/" → already paginated

Return ONLY the JSON object, no other text."""
        
        try:
            response = await self._call_gemini_async(prompt)
            pagination_data = self._extract_json_from_response(response)
            
            urls = pagination_data.get('pagination_urls', [current_url])
            
            # If we found a pattern but limited URLs, try to generate more
            if len(urls) < max_pages and pagination_data.get('url_pattern'):
                additional_urls = self._generate_pagination_urls(current_url, max_pages)
                urls.extend(additional_urls)
                urls = list(dict.fromkeys(urls))  # Remove duplicates while preserving order
            
            return urls[:max_pages]
            
        except Exception as e:
            logger.error(f"Error finding pagination URLs: {e}")
            # Fallback: try to generate URLs based on common patterns
            return self._generate_pagination_urls(current_url, min(max_pages, 10))
    
    def _generate_pagination_urls(self, base_url: str, max_pages: int) -> List[str]:
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
                lambda p: self._update_url_param(base_url, 'page', str(p)),
                lambda p: self._update_url_param(base_url, 'p', str(p)),
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
    
    def _update_url_param(self, url: str, param: str, value: str) -> str:
        """Update URL parameter"""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        query_params[param] = [value]
        new_query = urlencode(query_params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

    async def _call_gemini_async(self, prompt: str) -> str:
        """Make async call to Gemini API with retry logic"""
        max_retries = 3
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Use asyncio to run the synchronous call
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, 
                    lambda: self.model.generate_content(prompt)
                )
                
                if response and response.text:
                    return response.text
                else:
                    raise ValueError("Empty response from Gemini API")
                
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Gemini API call failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Gemini API call failed after {max_retries} attempts: {e}")
                    raise
    
    def _fallback_analysis(self, html_content: str, url: str) -> PageAnalysis:
        """Enhanced fallback analysis when AI fails"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Comprehensive product link detection
        product_links = []
        
        # Shopify-specific selectors
        shopify_selectors = [
            'a[href*="/products/"]',
            '.product-item a',
            '.grid-item a',
            '.product-card a',
            '.product__title a',
            '.card__heading a',
            '.card-wrapper a'
        ]
        
        # WooCommerce selectors
        woocommerce_selectors = [
            'a[href*="/product/"]',
            '.woocommerce-LoopProduct-link',
            '.product a',
            '.product-item a'
        ]
        
        # Generic selectors
        generic_selectors = [
            'a[href*="product"]',
            '.item a',
            '.listing-item a',
            '[class*="product"] a',
            '[class*="item"] a'
        ]
        
        all_selectors = shopify_selectors + woocommerce_selectors + generic_selectors
        
        for selector in all_selectors:
            try:
                elements = soup.select(selector)
                for elem in elements:
                    href = elem.get('href')
                    if href:
                        # Make absolute URL
                        if href.startswith('/'):
                            href = urljoin(url, href)
                        elif not href.startswith('http'):
                            href = urljoin(url, href)
                        
                        # Filter for product URLs
                        if (href.startswith('http') and 
                            href not in product_links and 
                            len(href) < 200):
                            
                            # Check if it's likely a product URL
                            is_product = any(pattern in href.lower() for pattern in ['/products/', '/product/', '/item/', '/items/'])
                            is_excluded = any(x in href.lower() for x in ['cart', 'checkout', 'login', 'register', 'contact', 'about', 'policy', 'terms', 'search', 'collections', 'blog', 'news'])
                            
                            if is_product or not is_excluded:
                                product_links.append(href)
                                
                            if len(product_links) >= 50:  # Reasonable limit
                                break
            except Exception:
                continue
                
            if len(product_links) >= 50:
                break
        
        # Enhanced pagination detection
        pagination_selectors = [
            '.pagination a', '.pager a', '.page-numbers a',
            '[class*="page"] a', '[class*="pagination"] a',
            '.next', '.prev', '.page-item a',
            'a[rel="next"]', 'a[rel="prev"]',
            # Shopify specific
            '.pagination__item a', '.pagination-custom a',
            # WooCommerce specific  
            '.woocommerce-pagination a', '.page-numbers',
            # Generic patterns
            'a[href*="page="]', 'a[href*="/page/"]', 'a[href*="?p="]'
        ]
        
        has_pagination = False
        next_page_url = None
        total_pages_estimate = None
        
        # Check for pagination elements
        for selector in pagination_selectors:
            elements = soup.select(selector)
            if elements:
                has_pagination = True
                
                # Try to find next page URL
                for elem in elements:
                    href = elem.get('href')
                    if href and ('next' in elem.get_text().lower() or 'page=2' in href or '/page/2' in href):
                        if href.startswith('/'):
                            next_page_url = urljoin(url, href)
                        elif href.startswith('http'):
                            next_page_url = href
                        break
                
                # Try to estimate total pages
                page_numbers = []
                for elem in elements:
                    text = elem.get_text().strip()
                    if text.isdigit():
                        page_numbers.append(int(text))
                
                if page_numbers:
                    total_pages_estimate = max(page_numbers)
                
                break
        
        # Additional check for Shopify pagination in HTML
        if not has_pagination:
            # Look for Shopify pagination indicators
            if soup.find('link', {'rel': 'next'}) or soup.find('link', {'rel': 'prev'}):
                has_pagination = True
                next_link = soup.find('link', {'rel': 'next'})
                if next_link:
                    next_page_url = urljoin(url, next_link.get('href', ''))
        
        # Generate page URLs using improved logic
        page_urls = []
        if has_pagination:
            page_urls = self._generate_pagination_urls(url, min(10, max_pages or 10))
        
        pagination_info = PaginationInfo(
            has_pagination=has_pagination,
            current_page=1,
            total_pages=total_pages_estimate,
            next_page_url=next_page_url,
            page_urls=page_urls if page_urls else [url],
            pagination_pattern="fallback_detected" if has_pagination else "none"
        )
        
        page_type = "collection" if product_links else "unknown"
        
        logger.info(f"Enhanced fallback analysis found {len(product_links)} product links, page_type: {page_type}")
        
        return PageAnalysis(
            page_type=page_type,
            product_links=product_links,
            pagination_info=pagination_info,
            extraction_strategy={
                "product_link_selectors": all_selectors[:10],  # Top selectors
                "pagination_selectors": pagination_selectors[:5]
            },
            confidence_score=0.5  # Higher confidence for enhanced fallback
        )


class AIProductScraper:
    """AI-powered product scraper using Gemini 1.5 Flash"""
    
    def __init__(self, log_callback: Optional[Callable] = None, progress_callback: Optional[Callable] = None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            self.ai_agent = GeminiAIAgent()
        except Exception as e:
            logger.error(f"Failed to initialize AI agent: {e}")
            self.ai_agent = None
        
        # Statistics
        self.stats = {
            "pages_analyzed": 0,
            "products_found": 0,
            "pagination_pages_discovered": 0,
            "ai_extraction_success": 0,
            "ai_extraction_failures": 0,
            "fallback_extractions": 0
        }
    
    def log(self, message: str, level: str = "INFO", details: Dict[str, Any] = None):
        """Enhanced logging with AI agent context"""
        timestamp = datetime.now().isoformat()
        
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "session_id": self.session_id,
            "scraper_type": "ai_agent",
            "details": details or {},
            "stats": self.stats
        }
        
        logger.info(f"[AI-AGENT] [{level}] {message}")
        
        if self.log_callback:
            try:
                self.log_callback(log_entry)
            except Exception as e:
                logger.error(f"Error in log callback: {e}")
    
    def update_progress(self, stage: str, percentage: int = None, details: str = ""):
        """Update progress with AI agent context"""
        # If percentage is None, keep the current percentage or use a default based on stage
        if percentage is None:
            if hasattr(self, '_last_percentage'):
                percentage = self._last_percentage
            else:
                # Default percentages based on stage
                stage_defaults = {
                    "initialization": 5,
                    "ai_analysis": 20,
                    "extraction": 50,
                    "completed": 100
                }
                percentage = stage_defaults.get(stage, 50)
        else:
            self._last_percentage = percentage
        
        progress_data = {
            "stage": stage,
            "percentage": percentage,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "scraper_type": "ai_agent",
            "stats": self.stats
        }
        
        self.log(f"AI Agent Progress: {stage} ({percentage}%) - {details}", "PROGRESS", progress_data)
        
        if self.progress_callback:
            try:
                # Handle both sync and async callbacks
                if asyncio.iscoroutinefunction(self.progress_callback):
                    # If we're in an async context, await the callback
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Schedule the coroutine to run
                            asyncio.create_task(self.progress_callback(progress_data))
                        else:
                            loop.run_until_complete(self.progress_callback(progress_data))
                    except Exception:
                        # Fallback: create new task
                        asyncio.create_task(self.progress_callback(progress_data))
                else:
                    # Synchronous callback
                    self.progress_callback(progress_data)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    async def scrape_with_ai_agent(self, urls: List[str], max_pages_per_url: int = 50) -> Dict[str, Any]:
        """Main scraping function using AI agent"""
        try:
            self.log("Starting AI-powered scraping process")
            self.update_progress("initialization", 5, "Initializing AI agent")
            
            if not self.ai_agent:
                self.log("AI agent not available, falling back to traditional scraping", "WARNING")
                return await self._fallback_to_simple_scraper(urls, max_pages_per_url)
            
            all_products = []
            total_pages_processed = 0
            
            for i, url in enumerate(urls):
                self.log(f"Processing URL {i+1}/{len(urls)}: {url}")
                base_progress = 15 + (i * 70 // len(urls))
                
                # Show URL being processed
                domain = url.split('/')[2] if len(url.split('/')) > 2 else url
                self.update_progress("ai_analysis", base_progress, f"🔍 Processing URL {i+1}/{len(urls)}: {domain}")
                
                # Get page content
                self.update_progress("ai_analysis", base_progress + 1, f"🌐 Fetching page content from {domain}...")
                html_content = await self._fetch_page_content(url)
                if not html_content:
                    self.log(f"Failed to fetch content from {url}", "ERROR")
                    self.update_progress("ai_analysis", base_progress + 2, f"❌ Failed to fetch content from {domain}")
                    continue
                
                self.update_progress("ai_analysis", base_progress + 2, f"🧠 AI analyzing page structure for {domain}...")
                
                # Analyze page structure with AI
                self.stats["pages_analyzed"] += 1
                analysis = await self.ai_agent.analyze_page_structure(html_content, url)
                
                self.log(f"AI Analysis - Page type: {analysis.page_type}, Confidence: {analysis.confidence_score:.2f}, Products found: {len(analysis.product_links)}")
                self.update_progress("ai_analysis", base_progress + 3, f"✅ AI Analysis complete: {analysis.page_type} page, {len(analysis.product_links)} products found")
                
                if analysis.page_type == "collection" and analysis.product_links:
                    # Handle collection page with pagination
                    self.update_progress("extraction", base_progress + 5, f"🛍️ Starting collection extraction from {domain} ({len(analysis.product_links)} products)")
                    products = await self._scrape_collection_with_pagination(url, analysis, max_pages_per_url)
                    all_products.extend(products)
                    total_pages_processed += len(analysis.pagination_info.page_urls) if analysis.pagination_info else 1
                    self.update_progress("extraction", base_progress + 15, f"✅ Collection complete: {len(products)} products extracted from {domain}")
                    
                elif analysis.page_type == "product":
                    # Handle individual product page
                    self.update_progress("extraction", base_progress + 5, f"🛍️ Extracting single product from {domain}...")
                    product = await self._scrape_single_product_ai(html_content, url)
                    if product and "error" not in product:
                        all_products.append(product)
                        self.stats["products_found"] += 1
                        product_name = product.get('product_name', 'Unknown Product')[:40]
                        self.update_progress("extraction", base_progress + 15, f"✅ Product extracted: {product_name}")
                    else:
                        self.update_progress("extraction", base_progress + 15, f"❌ Failed to extract product from {domain}")
                    total_pages_processed += 1
                
                else:
                    # Try to extract any product links found
                    if analysis.product_links:
                        self.log(f"Found {len(analysis.product_links)} product links on unknown page type")
                        self.update_progress("extraction", base_progress + 5, f"🛍️ Extracting {len(analysis.product_links)} products from {domain}...")
                        
                        products_extracted = 0
                        for j, product_url in enumerate(analysis.product_links[:max_pages_per_url]):
                            # Update progress for every product
                            product_progress = base_progress + 5 + (j * 10 // len(analysis.product_links))
                            self.update_progress("extraction", product_progress, f"🛍️ Product {j+1}/{len(analysis.product_links)} from {domain}")
                            
                            product = await self._scrape_single_product_by_url(product_url)
                            if product and "error" not in product:
                                all_products.append(product)
                                self.stats["products_found"] += 1
                                products_extracted += 1
                        
                        total_pages_processed += len(analysis.product_links[:max_pages_per_url])
                        self.update_progress("extraction", base_progress + 15, f"✅ Bulk extraction complete: {products_extracted}/{len(analysis.product_links)} products from {domain}")
                    else:
                        self.log(f"No product links found on page: {url}", "WARNING")
                        self.update_progress("extraction", base_progress + 15, f"⚠️ No products found on {domain}")
                
                # Show total progress after each URL
                self.update_progress("extraction", base_progress + 16, f"📊 Total progress: {len(all_products)} products found across {i+1}/{len(urls)} URLs")
                
                # Small delay between URLs to be respectful
                await asyncio.sleep(0.5)
            
            self.update_progress("completed", 100, f"AI scraping completed! Found {len(all_products)} products")
            self.log("AI-powered scraping completed successfully", "SUCCESS")
            
            # Prepare final result
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result = {
                "metadata": {
                    "timestamp": timestamp,
                    "total_products": len(all_products),
                    "total_pages_processed": total_pages_processed,
                    "scraper_type": "ai_agent_gemini",
                    "ai_stats": self.stats,
                    "urls_processed": len(urls)
                },
                "products": all_products
            }
            
            # Save results
            await self._save_results(result, timestamp)
            
            return result
            
        except Exception as e:
            self.log(f"Error in AI scraping: {e}", "ERROR")
            # Try fallback to simple scraper
            return await self._fallback_to_simple_scraper(urls, max_pages_per_url)
    
    async def _fallback_to_simple_scraper(self, urls: List[str], max_pages: int) -> Dict[str, Any]:
        """Fallback to simple scraper when AI fails"""
        try:
            self.log("Falling back to simple scraper", "WARNING")
            from scraper_simple import scrape_urls_simple_api
            
            result = await scrape_urls_simple_api(
                urls=urls,
                max_pages=max_pages,
                log_callback=self.log_callback,
                progress_callback=self.progress_callback
            )
            
            # Update metadata to indicate fallback
            if "metadata" in result:
                result["metadata"]["scraper_type"] = "fallback_simple"
                result["metadata"]["ai_stats"] = self.stats
            
            return result
            
        except Exception as e:
            self.log(f"Fallback scraper also failed: {e}", "ERROR")
            return {
                "metadata": {
                    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                    "total_products": 0,
                    "scraper_type": "failed",
                    "error": str(e),
                    "ai_stats": self.stats
                },
                "products": []
            }
    
    async def _scrape_collection_with_pagination(self, base_url: str, analysis: PageAnalysis, max_pages: int) -> List[Dict[str, Any]]:
        """Scrape collection with intelligent pagination handling"""
        products = []
        
        # Check if pagination is detected (either by AI or fallback)
        pagination_detected = (analysis.pagination_info and 
                             analysis.pagination_info.has_pagination and 
                             len(analysis.pagination_info.page_urls) > 1)
        
        if pagination_detected:
            # Use pagination URLs from analysis
            pagination_urls = analysis.pagination_info.page_urls[:max_pages]
            
            self.log(f"Using detected pagination: {len(pagination_urls)} pages")
            self.stats["pagination_pages_discovered"] = len(pagination_urls)
            
            # Process each pagination page
            for i, page_url in enumerate(pagination_urls):
                page_progress = 30 + (i * 50 // len(pagination_urls))
                page_display = page_url.split('/')[-1] if '/' in page_url else page_url.split('?')[-1]
                self.update_progress("extraction", page_progress, 
                                   f"📄 Processing page {i+1}/{len(pagination_urls)}: {page_display}")
                
                page_products = await self._scrape_products_from_page(page_url)
                products.extend(page_products)
                
                # Update progress with detailed results
                total_found = len(products)
                self.update_progress("extraction", page_progress + 2, 
                                   f"✅ Page {i+1}/{len(pagination_urls)} complete: {len(page_products)} products found (Total: {total_found})")
                
                # Small delay between pages
                await asyncio.sleep(0.5)
        
        elif self.ai_agent:
            # Try AI-based pagination discovery as fallback
            self.log("No pagination detected in analysis, trying AI discovery...")
            html_content = await self._fetch_page_content(base_url)
            if html_content:
                try:
                    pagination_urls = await self.ai_agent.find_pagination_urls(html_content, base_url, max_pages)
                    
                    if len(pagination_urls) > 1:
                        self.log(f"AI discovered {len(pagination_urls)} pagination pages")
                        self.stats["pagination_pages_discovered"] = len(pagination_urls)
                        
                        # Process each AI-discovered pagination page
                        for i, page_url in enumerate(pagination_urls):
                            page_progress = 30 + (i * 50 // len(pagination_urls))
                            page_display = page_url.split('/')[-1] if '/' in page_url else page_url.split('?')[-1]
                            self.update_progress("extraction", page_progress, 
                                               f"📄 AI Page {i+1}/{len(pagination_urls)}: {page_display}")
                            
                            page_products = await self._scrape_products_from_page(page_url)
                            products.extend(page_products)
                            
                            # Update progress with detailed results
                            total_found = len(products)
                            self.update_progress("extraction", page_progress + 2, 
                                               f"✅ AI Page {i+1}/{len(pagination_urls)} complete: {len(page_products)} products (Total: {total_found})")
                            
                            # Small delay between pages
                            await asyncio.sleep(0.5)
                    else:
                        # Single page collection
                        self.log("AI could not find pagination, processing single page")
                        page_products = await self._scrape_products_from_page(base_url, analysis.product_links)
                        products.extend(page_products)
                        
                except Exception as e:
                    self.log(f"AI pagination discovery failed: {e}", "ERROR")
                    # Fallback to single page
                    page_products = await self._scrape_products_from_page(base_url, analysis.product_links)
                    products.extend(page_products)
            else:
                # Could not fetch content, use known product links
                page_products = await self._scrape_products_from_page(base_url, analysis.product_links)
                products.extend(page_products)
        
        else:
            # No AI agent available, single page collection
            self.log("No AI agent available, processing single page only")
            page_products = await self._scrape_products_from_page(base_url, analysis.product_links)
            products.extend(page_products)
        
        return products
    
    async def _scrape_products_from_page(self, page_url: str, known_product_links: List[str] = None) -> List[Dict[str, Any]]:
        """Scrape all products from a single page"""
        products = []
        
        try:
            if known_product_links:
                # Use known product links
                product_links = known_product_links
            else:
                # Get page content and analyze
                self.update_progress("extraction", None, f"🔍 Analyzing page content: {page_url[:60]}...")
                html_content = await self._fetch_page_content(page_url)
                if not html_content:
                    return products
                
                if self.ai_agent:
                    analysis = await self.ai_agent.analyze_page_structure(html_content, page_url)
                    product_links = analysis.product_links
                else:
                    # Fallback product link extraction
                    soup = BeautifulSoup(html_content, 'html.parser')
                    product_links = []
                    for a in soup.select('a[href*="/products/"], a[href*="/product/"]'):
                        href = a.get('href')
                        if href:
                            if href.startswith('/'):
                                href = urljoin(page_url, href)
                            if href.startswith('http'):
                                product_links.append(href)
            
            self.log(f"Found {len(product_links)} product links on page: {page_url}")
            self.update_progress("extraction", None, f"📦 Found {len(product_links)} products on page. Starting extraction...")
            
            # Scrape each product with detailed progress
            for i, product_url in enumerate(product_links):
                # Extract product name from URL for better progress display
                product_name = product_url.split('/')[-1].replace('-', ' ').title()[:30]
                self.update_progress("extraction", None, f"🛍️ Extracting product {i+1}/{len(product_links)}: {product_name}...")
                
                product = await self._scrape_single_product_by_url(product_url)
                if product and "error" not in product:
                    products.append(product)
                    self.stats["products_found"] += 1
                    # Show success with product name
                    actual_name = product.get('product_name', product_name)[:40]
                    self.update_progress("extraction", None, f"✅ Extracted: {actual_name} (${product.get('price', 'N/A')})")
                else:
                    self.update_progress("extraction", None, f"❌ Failed to extract: {product_name}")
                
                # Small delay between products
                await asyncio.sleep(0.3)
        
        except Exception as e:
            self.log(f"Error scraping products from page {page_url}: {e}", "ERROR")
            self.update_progress("extraction", None, f"❌ Error processing page: {str(e)[:50]}...")
        
        return products
    
    async def _scrape_single_product_by_url(self, product_url: str) -> Dict[str, Any]:
        """Scrape a single product by URL"""
        try:
            # Show fetching progress
            product_name = product_url.split('/')[-1].replace('-', ' ').title()[:25]
            self.update_progress("extraction", None, f"🌐 Fetching {product_name}...")
            
            html_content = await self._fetch_page_content(product_url)
            if not html_content:
                self.update_progress("extraction", None, f"❌ Failed to fetch: {product_name}")
                return {"url": product_url, "error": "Failed to fetch content"}
            
            self.update_progress("extraction", None, f"🧠 AI processing: {product_name}...")
            result = await self._scrape_single_product_ai(html_content, product_url)
            
            if result and "error" not in result:
                self.update_progress("extraction", None, f"✅ Success: {result.get('product_name', product_name)[:30]}")
            
            return result
        
        except Exception as e:
            self.log(f"Error scraping product {product_url}: {e}", "ERROR")
            self.update_progress("extraction", None, f"❌ Error: {str(e)[:40]}...")
            return {"url": product_url, "error": str(e)}
    
    async def _scrape_single_product_ai(self, html_content: str, url: str) -> Dict[str, Any]:
        """Scrape single product using AI extraction"""
        try:
            if self.ai_agent:
                # Use AI to extract product data
                product_data = await self.ai_agent.extract_product_data_ai(html_content, url)
                
                if "error" not in product_data:
                    self.stats["ai_extraction_success"] += 1
                    self.log(f"AI successfully extracted: {product_data.get('product_name', 'Unknown')}")
                else:
                    self.stats["ai_extraction_failures"] += 1
                
                return product_data
            else:
                # Fallback to traditional extraction
                return await self.ai_agent._fallback_product_extraction(html_content, url)
            
        except Exception as e:
            self.stats["ai_extraction_failures"] += 1
            self.log(f"Error in AI product extraction: {e}", "ERROR")
            
            # Try fallback extraction
            try:
                self.stats["fallback_extractions"] += 1
                return await self._traditional_product_extraction(html_content, url)
            except Exception as fallback_error:
                self.log(f"Fallback extraction also failed: {fallback_error}", "ERROR")
                return {
                    "url": url,
                    "product_name": "Extraction Failed",
                    "price": 0.0,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "extraction_method": "failed"
                }
    
    async def _traditional_product_extraction(self, html_content: str, url: str) -> Dict[str, Any]:
        """Traditional product extraction as final fallback"""
        try:
            # Use our improved traditional extraction method
            return await self._fallback_product_extraction(html_content, url)
            
        except Exception as e:
            raise Exception(f"Traditional extraction failed: {e}")
    
    async def _fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch page content using Playwright"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Set user agent to avoid blocking
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                })
                
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Wait for dynamic content to load
                await page.wait_for_timeout(2000)
                
                content = await page.content()
                await browser.close()
                
                return content
                
        except Exception as e:
            self.log(f"Error fetching page content from {url}: {e}", "ERROR")
            return None
    
    async def _save_results(self, result: Dict[str, Any], timestamp: str):
        """Save scraping results"""
        try:
            logs_dir = "logs"
            os.makedirs(logs_dir, exist_ok=True)
            
            output_file = os.path.join(logs_dir, f"ai_agent_scrape_{timestamp}.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            self.log(f"AI scraping results saved to {output_file}")
            
        except Exception as e:
            self.log(f"Error saving results: {e}", "ERROR")


# Main API function
async def scrape_urls_ai_agent(
    urls: List[str], 
    log_callback: Optional[Callable] = None,
    progress_callback: Optional[Callable] = None,
    max_pages_per_url: int = 50
) -> Dict[str, Any]:
    """
    AI Agent API function to scrape product data from URLs using Gemini 1.5 Flash
    
    Features:
    - Intelligent page structure analysis
    - Automatic pagination discovery and navigation
    - AI-powered product data extraction
    - Adaptive to different website layouts
    - Dynamic CSS selector generation
    - Fallback to traditional scraping when AI fails
    """
    scraper = AIProductScraper(log_callback, progress_callback)
    
    try:
        return await scraper.scrape_with_ai_agent(urls, max_pages_per_url)
        
    except Exception as e:
        scraper.log(f"Error in AI agent scraping: {e}", "ERROR")
        # Try one more fallback
        try:
            return await scraper._fallback_to_simple_scraper(urls, max_pages_per_url)
        except Exception as fallback_error:
            # Final fallback result
            return {
                "metadata": {
                    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                    "total_products": 0,
                    "scraper_type": "complete_failure",
                    "error": f"AI: {e}, Fallback: {fallback_error}",
                    "ai_stats": scraper.stats if scraper else {}
                },
                "products": []
            }

if __name__ == "__main__":
    # Test the AI agent
    async def test_ai_agent():
        test_urls = [
            "https://deashaindia.com/collections/sarees",
            "https://ajmerachandanichowk.com/shop/"
        ]
        
        result = await scrape_urls_ai_agent(test_urls, max_pages_per_url=5)
        print(json.dumps(result, indent=2))
    
    asyncio.run(test_ai_agent())