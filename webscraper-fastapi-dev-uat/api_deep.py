from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Any, Optional
import asyncio
import json
import os
from datetime import datetime
import logging
import time
from scraper_simple_deep import scrape_urls_simple_api, SimpleProductScraper
from scraper_ai_agent_deep import scrape_urls_ai_agent
from image_url_fixer_deep import fix_product_images
import glob
import hashlib
from cachetools import TTLCache
from datetime import timedelta
import tenacity
import aiohttp
from aiohttp import TCPConnector, ClientSession
from urllib.parse import urlparse
import re
import concurrent.futures
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import httpx
from selectolax.parser import HTMLParser
from playwright.async_api import async_playwright


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI-Powered Web Scraper API", version="2.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="./static/"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Configure cache
url_cache = TTLCache(maxsize=1000, ttl=timedelta(hours=24).total_seconds())
product_cache = TTLCache(maxsize=5000, ttl=timedelta(hours=12).total_seconds())

class ScrapeRequest(BaseModel):
    """Model for scrape request data"""
    urls: List[HttpUrl]
    max_pages: int = 20

class AIAgentScrapeRequest(BaseModel):
    """Model for AI agent scrape request data"""
    urls: List[HttpUrl]
    max_pages_per_url: int = 50
    use_ai_pagination: bool = True
    ai_extraction_mode: bool = True

class ScrapeResponse(BaseModel):
    """Model for scrape response data"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Store active tasks and WebSocket connections
active_tasks: Dict[str, Dict[str, Any]] = {}

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
        logger.info(f"WebSocket connection established for task {task_id}")

    def disconnect(self, websocket: WebSocket, task_id: str):
        if task_id in self.active_connections:
            self.active_connections[task_id].remove(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
        logger.info(f"WebSocket connection closed for task {task_id}")

    async def send_progress_update(self, task_id: str, message: dict):
        if task_id in self.active_connections and self.active_connections[task_id]:
            logger.info(f"Sending WebSocket message to {len(self.active_connections[task_id])} connections for task {task_id}: {message}")
            disconnected_connections = []
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                    logger.debug(f"Successfully sent message to WebSocket connection")
                except Exception as e:
                    logger.error(f"Failed to send WebSocket message: {e}")
                    disconnected_connections.append(connection)
            
            # Clean up disconnected connections
            for connection in disconnected_connections:
                self.disconnect(connection, task_id)
        else:
            # This is normal - client may have disconnected or not established connection yet
            logger.debug(f"No active WebSocket connections for task {task_id} - continuing task in background")

    async def close_task_connections(self, task_id: str):
        """Close all WebSocket connections for a specific task"""
        if task_id in self.active_connections:
            disconnected_connections = []
            for connection in self.active_connections[task_id]:
                try:
                    await connection.close()
                    disconnected_connections.append(connection)
                except Exception as e:
                    logger.error(f"Error closing WebSocket connection: {e}")
            
            # Clean up the connections
            del self.active_connections[task_id]
            logger.info(f"🔌 Closed {len(disconnected_connections)} WebSocket connections for task {task_id}")
        else:
            logger.info(f"ℹ️ No active WebSocket connections found for task {task_id}")

manager = ConnectionManager()

# Retry decorator with exponential backoff
def retry_with_exponential_backoff():
    """Retry decorator with exponential backoff"""
    return tenacity.retry(
        wait=tenacity.wait_exponential(multiplier=1, min=2, max=30),
        stop=tenacity.stop_after_attempt(3),
        retry=tenacity.retry_if_exception_type(Exception),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )

# Caching functions
def get_url_hash(url):
    """Generate hash for URL caching"""
    return hashlib.md5(url.encode()).hexdigest()

async def get_cached_or_scrape(url, scraper, is_collection=False, max_pages=20):
    """Get data from cache or scrape if not available"""
    url_hash = get_url_hash(url)
    
    # Check cache first
    if url_hash in url_cache:
        logger.info(f"Using cached data for {url}")
        return url_cache[url_hash]
    
    # Scrape fresh data
    if is_collection:
        data = await scraper.scrape_collection_with_pagination(url, max_pages=max_pages)
    else:
        data = await scraper.extract_product_data(url)
        data = [data] if data and "error" not in data else []
    
    # Cache the results
    url_cache[url_hash] = data
    return data

def post_process_scraped_data_sync(result):
    """
    Synchronous post-processing of scraped data to fix image URLs
    
    Args:
        result (dict): Raw scraped data
        
    Returns:
        dict: Processed data with fixed image URLs
    """
    logger.info("🔧 Starting post-processing of scraped data...")
    
    if not result or 'products' not in result:
        logger.warning("⚠️ No products found in result, skipping post-processing")
        return result
    
    total_products = len(result['products'])
    fixed_count = 0
    total_images_before = 0
    total_images_after = 0
    
    for product in result['products']:
        if 'product_images' in product:
            original_count = len(product['product_images'])
            total_images_before += original_count
            
            # Fix the product images
            fixed, sizes = fix_product_images(product['product_images'])
            product['product_images'] = fixed
            product['image_sizes'] = sizes
            new_count = len(product['product_images'])
            total_images_after += new_count
            
            if original_count != new_count:
                fixed_count += 1
                product_name = product.get('product_name', 'Unknown')[:40]
                logger.info(f"🔧 Fixed '{product_name}': {original_count} -> {new_count} images")

    # Calculate statistics
    images_removed = total_images_before - total_images_after
    fix_percentage = (fixed_count / total_products * 100) if total_products > 0 else 0
    
    # Update metadata
    if 'metadata' in result:
        result['metadata']['image_urls_fixed'] = True
        result['metadata']['products_with_fixed_images'] = fixed_count
        result['metadata']['total_images_before_fix'] = total_images_before
        result['metadata']['total_images_after_fix'] = total_images_after
        result['metadata']['images_removed'] = images_removed
        result['metadata']['fix_percentage'] = round(fix_percentage, 1)
        result['metadata']['image_fix_timestamp'] = datetime.now().isoformat()
    
    logger.info(f"🎉 Post-processing complete:")
    logger.info(f"   📊 Products processed: {total_products}")
    logger.info(f"   🔧 Products with fixed images: {fixed_count} ({fix_percentage:.1f}%)")
    logger.info(f"   🖼️ Images: {total_images_before} -> {total_images_after} (removed {images_removed} placeholders)")
    
    return result

async def post_process_scraped_data(result):
    """Async wrapper for post-processing"""
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, post_process_scraped_data_sync, result)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main GUI interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/edit-products", response_class=HTMLResponse)
async def edit_products(request: Request, task_id: Optional[str] = None):
    """Serve the product editing interface"""
    return templates.TemplateResponse("edit_products.html", {"request": request, "task_id": task_id})

@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time progress updates"""
    await manager.connect(websocket, task_id)
    try:
        # Send current task status if available
        if task_id in active_tasks:
            await websocket.send_json({
                "type": "status_update",
                "data": active_tasks[task_id]
            })
        
        while True:
            # Keep connection alive
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id)

@app.get("/api")
async def api_info():
    """API information endpoint"""
    return {
        "message": "AI-Powered Web Scraper API",
        "version": "2.0.0",
        "scraper_types": {
            "simple": "Direct HTML parsing scraper",
            "ai_agent": "AI-powered intelligent scraper using Gemini 1.5 Flash"
        },
        "endpoints": {
            "gui": "GET / - Web GUI interface",
            "scrape": "POST /scrape - Simple scraping with direct HTML parsing",
            "scrape/ai": "POST /scrape/ai - AI-powered intelligent scraping",
            "status": "GET /status/{task_id} - Get scraping task status",
            "websocket": "WS /ws/{task_id} - Real-time progress updates",
            "health": "GET /health - API health check"
        },
        "features": {
            "ai_agent": [
                "Intelligent page structure analysis",
                "Automatic pagination discovery",
                "Dynamic product extraction",
                "Adaptive to different website layouts",
                "AI-powered data extraction using Gemini 1.5 Flash",
                "Real-time WebSocket progress updates"
            ]
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_tasks": len(active_tasks),
        "active_websockets": sum(len(connections) for connections in manager.active_connections.values()),
        "scraper_types": ["simple", "ai_agent"],
        "timestamp": datetime.now().isoformat()
    }

@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_products(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Scrape products using simple direct HTML parsing
    
    - **urls**: List of URLs to scrape (collections or individual products)
    - **max_pages**: Maximum number of pages/products to scrape per URL (default: 20)
    """
    task_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
    
    logger.info(f"Starting simple scrape task {task_id} with {len(request.urls)} URLs")
    
    # Store task info
    active_tasks[task_id] = {
        "task_id": task_id,
        "status": "started",
        "scraper_type": "simple",
        "start_time": datetime.now().isoformat(),
        "urls": [str(url) for url in request.urls],
        "max_pages": request.max_pages,
        "result": None,
        "error": None,
        "end_time": None,
        "processing_time": None,
        "current_progress": {
            "stage": "initializing",
            "percentage": 0,
            "details": "Starting simple scraping...",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    # Start scraping in background
    background_tasks.add_task(run_simple_scrape_task, task_id, [str(url) for url in request.urls], request.max_pages)
    
    return ScrapeResponse(
        success=True,
        message=f"Simple scraping task started with ID: {task_id}",
        data={
            "task_id": task_id,
            "status": "started",
            "scraper_type": "simple",
            "urls_count": len(request.urls),
            "max_pages": request.max_pages
        }
    )

@app.post("/scrape/ai", response_model=ScrapeResponse)
async def scrape_products_ai(request: AIAgentScrapeRequest, background_tasks: BackgroundTasks):
    """
    Scrape products using AI-powered intelligent agent (Gemini 1.5 Flash)
    
    Features:
    - **Intelligent page analysis**: AI understands page structure and layout
    - **Automatic pagination discovery**: Finds and navigates all pages automatically
    - **Dynamic product extraction**: Adapts to different website designs
    - **Smart data extraction**: AI-powered product data extraction
    - **Real-time WebSocket updates**: Live progress tracking
    
    Parameters:
    - **urls**: List of URLs to scrape (collections or individual products)
    - **max_pages_per_url**: Maximum pages to scrape per URL (default: 50)
    - **use_ai_pagination**: Enable AI-powered pagination discovery (default: true)
    - **ai_extraction_mode**: Use AI for product data extraction (default: true)
    """
    task_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
    
    logger.info(f"Starting AI agent scrape task {task_id} with {len(request.urls)} URLs")
    
    # Store task info
    active_tasks[task_id] = {
        "task_id": task_id,
        "status": "started",
        "scraper_type": "ai_agent",
        "start_time": datetime.now().isoformat(),
        "urls": [str(url) for url in request.urls],
        "max_pages_per_url": request.max_pages_per_url,
        "use_ai_pagination": request.use_ai_pagination,
        "ai_extraction_mode": request.ai_extraction_mode,
        "result": None,
        "error": None,
        "end_time": None,
        "processing_time": None,
        "ai_stats": None,
        "current_progress": {
            "stage": "initializing",
            "percentage": 0,
            "details": "🧠 AI agent initializing...",
            "timestamp": datetime.now().isoformat()
        }
    }
    
    # Start AI scraping in background
    background_tasks.add_task(run_ai_scrape_task, task_id, [str(url) for url in request.urls], request.max_pages_per_url)
    
    return ScrapeResponse(
        success=True,
        message=f"AI agent scraping task started with ID: {task_id}",
        data={
            "task_id": task_id,
            "status": "started",
            "scraper_type": "ai_agent",
            "urls_count": len(request.urls),
            "max_pages_per_url": request.max_pages_per_url,
            "features": [
                "AI page structure analysis",
                "Automatic pagination discovery",
                "Dynamic product extraction",
                "Gemini 1.5 Flash powered",
                "Real-time WebSocket updates"
            ]
        }
    )

@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a scraping task (both simple and AI agent)"""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return active_tasks[task_id]

@app.get("/api/tasks")
async def list_available_tasks():
    """List all available scraping tasks, prioritizing FIXED versions"""
    try:
        logs_dir = "logs"
        if not os.path.exists(logs_dir):
            return {
                "success": True,
                "tasks": [],
                "message": "No logs directory found"
            }
        
        # Get all JSON files
        json_files = glob.glob(os.path.join(logs_dir, "*.json"))
        
        # Group files by task ID
        tasks = {}
        
        for file_path in json_files:
            filename = os.path.basename(file_path)
            
            # Extract task ID from filename
            if filename.startswith('ai_agent_scrape_'):
                # Remove prefix and extension
                task_part = filename.replace('ai_agent_scrape_', '').replace('.json', '')
                
                # Check if it's a FIXED version
                is_fixed = task_part.endswith('_FIXED')
                if is_fixed:
                    task_id = task_part.replace('_FIXED', '')
                else:
                    task_id = task_part
                
                # Read file metadata
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    metadata = data.get('metadata', {})
                    products_count = len(data.get('products', []))
                    
                    if task_id not in tasks:
                        tasks[task_id] = {
                            'task_id': task_id,
                            'has_original': False,
                            'has_fixed': False,
                            'original_file': None,
                            'fixed_file': None,
                            'products_count': 0,
                            'timestamp': metadata.get('timestamp', ''),
                            'scraper_type': metadata.get('scraper_type', 'unknown'),
                            'ai_stats': metadata.get('ai_stats', {}),
                            'urls_processed': metadata.get('urls_processed', 0)
                        }
                    
                    if is_fixed:
                        tasks[task_id]['has_fixed'] = True
                        tasks[task_id]['fixed_file'] = filename
                    else:
                        tasks[task_id]['has_original'] = True
                        tasks[task_id]['original_file'] = filename
                    
                    # Use the count from the FIXED version if available, otherwise original
                    if is_fixed or not tasks[task_id]['has_fixed']:
                        tasks[task_id]['products_count'] = products_count
                        
                except Exception as e:
                    logger.warning(f"Error reading file {filename}: {e}")
                    continue
        
        # Convert to list and sort by timestamp (newest first)
        tasks_list = list(tasks.values())
        tasks_list.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Add preferred file information
        for task in tasks_list:
            task['preferred_file'] = task['fixed_file'] if task['has_fixed'] else task['original_file']
            task['preferred_version'] = 'FIXED' if task['has_fixed'] else 'ORIGINAL'
        
        return {
            "success": True,
            "tasks": tasks_list,
            "total_tasks": len(tasks_list),
            "message": f"Found {len(tasks_list)} scraping tasks"
        }
        
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing tasks: {str(e)}")

@app.get("/api/products/{task_id}")
async def get_products_by_task_id(task_id: str):
    """Get products from a specific task, prioritizing FIXED.json files"""
    try:
        logs_dir = "logs"
        
        # First try to find the FIXED version
        fixed_file_patterns = [
            f"ai_agent_scrape_{task_id}_FIXED.json",
            f"ai_agent_scrape_{task_id.replace('_', '')}_FIXED.json",
            f"*{task_id}*_FIXED.json"
        ]
        
        # Then try original versions as fallback
        original_file_patterns = [
            f"ai_agent_scrape_{task_id}.json",
            f"ai_agent_scrape_{task_id.replace('_', '')}.json", 
            f"*{task_id}*.json"
        ]
        
        found_file = None
        is_fixed_version = False
        
        # Look for FIXED version first
        for pattern in fixed_file_patterns:
            matching_files = glob.glob(os.path.join(logs_dir, pattern))
            if matching_files:
                found_file = matching_files[0]  # Take the first match
                is_fixed_version = True
                logger.info(f"🔧 Found FIXED version: {found_file}")
                break
        
        # If no FIXED version found, look for original
        if not found_file:
            for pattern in original_file_patterns:
                matching_files = glob.glob(os.path.join(logs_dir, pattern))
                if matching_files:
                    found_file = matching_files[0]
                    logger.info(f"📄 Found original version: {found_file}")
                    break
        
        if not found_file:
            # List available files for debugging
            available_files = glob.glob(os.path.join(logs_dir, "*.json"))
            logger.warning(f"No file found for task_id: {task_id}")
            logger.info(f"Available files: {[os.path.basename(f) for f in available_files]}")
            
            raise HTTPException(
                status_code=404, 
                detail=f"No scraping results found for task ID: {task_id}. Available files: {[os.path.basename(f) for f in available_files]}"
            )
        
        # Load and return the file
        with open(found_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        products = data.get('products', [])
        metadata = data.get('metadata', {})
        
        # Add information about which version was loaded
        metadata['loaded_from_fixed'] = is_fixed_version
        metadata['loaded_file'] = os.path.basename(found_file)
        
        # Determine scraper type
        scraper_type = metadata.get('scraper_type', 'unknown')
        if 'ai_agent' in scraper_type or 'ai_stats' in metadata:
            scraper_type = 'ai_agent'
        elif 'simple' in scraper_type:
            scraper_type = 'simple'
        
        return {
            "success": True,
            "task_id": task_id,
            "products": products,
            "metadata": metadata,
            "scraper_type": scraper_type,
            "total_products": len(products),
            "is_fixed_version": is_fixed_version,
            "loaded_file": os.path.basename(found_file),
            "message": f"Loaded {len(products)} products from {'FIXED' if is_fixed_version else 'original'} version"
        }
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"No scraping results found for task ID: {task_id}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Invalid JSON data for task ID: {task_id}")
    except Exception as e:
        logger.error(f"Error retrieving products for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving products: {str(e)}")

class UploadProductsRequest(BaseModel):
    """Model for upload products request"""
    products: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None
    send_to_external: bool = False  # Add this field

@app.post("/api/upload-products")
async def upload_products(request: UploadProductsRequest):
    """Upload edited products and optionally send to external API"""
    try:
        products = request.products
        metadata = request.metadata or {}
        send_to_external = request.send_to_external
        
        if not products:
            raise HTTPException(status_code=400, detail="No products provided")
        
        # Transform products to external API format
        transformed_data = transform_to_external_format(products)
        logger.info(transformed_data)
        # Create timestamp for this upload
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Prepare the upload data
        upload_data = {
            "metadata": {
                "timestamp": timestamp,
                "total_products": len(products),
                "upload_type": "manual_edit",
                "source": metadata.get("source", "edit_interface"),
                "sent_to_external": send_to_external,
                **metadata
            },
            "products": products,
            "transformed_data": transformed_data if send_to_external else None
        }
        
        # Save to upload_data directory
        upload_dir = "upload_data"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Create a filename with timestamp
        filename = f"products_{timestamp}.json"
        upload_file = os.path.join(upload_dir, filename)
        
        with open(upload_file, 'w', encoding='utf-8') as f:
            json.dump(upload_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully saved {len(products)} products to {upload_file}")
        
        # Send to external API if requested
        external_response = None
        if send_to_external:
            external_response = await send_to_external_api(transformed_data)
            logger.info(f"Sent {len(products)} products to external API")
        
        return {
            "success": True,
            "message": f"Successfully uploaded {len(products)} products" + 
                      (" and sent to external API" if send_to_external else ""),
            "data": {
                "products_count": len(products),
                "upload_file": upload_file,
                "timestamp": timestamp,
                "sent_to_external": send_to_external,
                "external_response": external_response
            }
        }
        
    except Exception as e:
        logger.error(f"Error uploading products: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


def transform_to_external_format(products):
    """Transform products to external API format"""
    transformed_products = []
    
    for product in products:
        # Skip products with "Error" in the name or no images
        if (product.get("product_name") == "Error" or 
            not product.get("product_images") or 
            len(product.get("product_images", [])) == 0):
            continue
        
        # Handle categories - extract category names if they're dictionaries
        categories = product.get("categories", [])
        category_labels = []
        
        for category in categories:
            if isinstance(category, dict):
                # Extract name from category dictionary if available
                category_labels.append(category.get("name", ""))
            else:
                category_labels.append(str(category))
        
        # Basic product information
        transformed = {
            "product_name": product.get("product_name", ""),
            "category_name": {
                "label": " > ".join(category_labels) if category_labels else "Uncategorized",
                "value": " > ".join([str(i) for i in range(len(category_labels))]) if category_labels else ""
            },
            "description": product.get("description", ""),
            "status": "1",
            "product_image": {
                "uploaded_image_url": product.get("product_images", [""])[0] if product.get("product_images") else "",
                "uploaded_image_key": "",
                "media_type": "image"
            },
            "product_video": {},
            "product_media": [],
            "meta_tag_title": product.get("meta_title", ""),
            "meta_tag_description": product.get("meta_description", ""),
            "seo_url": product.get("slug", product.get("url", "")),
            "variantPrices": [],
            "isPremium": False,
            "is_customize": 0,
            "variant_gender": "",
            "approximate_delivery_days": "",
            "selectedCustomizationFields": [],
            "pickupAddressId": '',
            "packageInfo": {
                "weight": product.get("weight", 0.5),
                "dimensions": {
                    "length": "35",
                    "width": "24",
                    "height": "5"
                }
            },
            "isReturnable": False,
            "maxDaysToReturn": None
        }
        
        # Add product media (all images)
        for img_url in product.get("product_images", []):
            transformed["product_media"].append({
                "uploaded_image_url": img_url,
                "uploaded_image_key": "",
                "media_type": "image"
            })
        
        # Create variant structure
        variant_price = {
            "rowId": 0,
            "variants": [],
            "quantity": str(product.get("stock", 100)),
            "regularPrice": str(product.get("price", 0)),
            "discountedPrice": str(product.get("discounted_price", product.get("price", 0)))
        }
        
        # Add color variants if available
        if "colors" in product and product["colors"]:
            color_variant = {
                "optionId": "",
                "optionName": "Color",
                "optionValues": []
            }
            for color in product["colors"]:
                color_variant["optionValues"].append({
                    "code": color.get("color_code", ""),
                    "value": color.get("id", ""),
                    "label": color.get("option_value_name", "")
                })
            variant_price["variants"].append(color_variant)
        
        # Add size variants if available
        if "sizes" in product and product["sizes"]:
            size_variant = {
                "optionId": "",
                "optionName": "Size",
                "optionValues": []
            }
            for size in product["sizes"]:
                size_variant["optionValues"].append({
                    "code": "",
                    "value": size.get("_id", ""),
                    "label": size.get("option_value_name", "")
                })
            variant_price["variants"].append(size_variant)
        
        # Add material variants if available
        if "material" in product and product["material"]:
            material_variant = {
                "optionId": "601a6a544e966936d4f475e2",
                "optionName": "Materials",
                "optionValues": []
            }
            # Handle material data - it might be a string or object
            material_data = product["material"]
            if isinstance(material_data, dict) and "_id" in material_data:
                # Extract material info from the _id field
                material_text = material_data["_id"]
                material_variant["optionValues"].append({
                    "code": "",
                    "value": material_text,  # Using the text as value
                    "label": material_text   # Using the text as label
                })
            elif isinstance(material_data, str):
                material_variant["optionValues"].append({
                    "code": "",
                    "value": material_data,
                    "label": material_data
                })
            
            variant_price["variants"].append(material_variant)
        
        transformed["variantPrices"].append(variant_price)
        transformed_products.append(transformed)
    
    return {"products": transformed_products}
async def send_to_external_api(transformed_data):
    """Send transformed data to external API"""
    try:
        external_api_url = "https://www.rte.in/api/product/upload-scraped-product-to-particular-sellers-dashboard"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                external_api_url, 
                json=transformed_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                return {
                    "status": response.status,
                    "response": result
                }
    except Exception as e:
        logger.error(f"Error sending to external API: {e}")
        return {"error": str(e)}

@app.get("/results/{task_id}")
async def get_results(task_id: str):
    if task_id not in active_tasks:
        return {"success": False, "error": "Invalid task ID"}

    task = active_tasks[task_id]
    if task["status"] != "completed":
        return {
            "success": False,
            "status": task["status"],
            "progress": task.get("current_progress")
        }

    return {
        "success": True,
        "task_id": task_id,
        "products": task["result"]["products"]
    }

async def run_simple_scrape_task(task_id: str, urls: List[str], max_pages: int):
    """Run the simple scraping task in the background with enhanced pagination"""
    start_time = time.time()
    
    try:
        active_tasks[task_id]["status"] = "running"
        
        async def progress_callback(progress_data):
            if task_id in active_tasks:
                active_tasks[task_id]["current_progress"] = {
                    **progress_data,
                    "timestamp": datetime.now().isoformat()
                }
                await manager.send_progress_update(task_id, {
                    "type": "progress_update",
                    "data": progress_data
                })
        
        # Initialize scraper with enhanced pagination
        scraper = SimpleProductScraper()
        all_products = []
        
        for i, url in enumerate(urls):
            progress = 10 + (i * 70 // len(urls))
            domain = urlparse(url).netloc
            await progress_callback({
                "stage": "scraping",
                "percentage": progress,
                "details": f"Processing {domain}"
            })
            
            # Check if it's a collection URL
            if "/collection" in url or "/category" in url or "/shop" in url:
                # Use enhanced pagination scraping
                products = await scraper.scrape_collection_with_pagination(
                    url, max_pages=max_pages, progress_callback=progress_callback
                )
                all_products.extend(products)
            else:
                # Single product
                product = await scraper.extract_product_data(url)
                if product and "error" not in product:
                    all_products.append(product)
        
        # Wrap in result structure
        result = {
            "products": all_products,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_products": len(all_products),
                "scraper_type": "simple",
                "urls_processed": len(urls)
            }
        }
        
        # Post-process the scraped data
        await progress_callback({
            "stage": "post_processing",
            "percentage": 95,
            "details": "🔧 Post-processing and fixing image URLs..."
        })
        
        result = await post_process_scraped_data(result)
        
        # Save the fixed results automatically
        timestamp = result["metadata"]["timestamp"]
        await save_fixed_results(result, timestamp, task_id)
        
        # Update task with results
        active_tasks[task_id].update({
            "status": "completed",
            "result": result,
            "end_time": datetime.now().isoformat(),
            "processing_time": round(time.time() - start_time, 2)
        })
        
        # Send completion update via WebSocket
        await manager.send_progress_update(task_id, {
            "type": "task_completed",
            "data": active_tasks[task_id]
        })
        
    except Exception as e:
        logger.error(f"Simple scrape task {task_id} failed: {e}")
        active_tasks[task_id].update({
            "status": "failed",
            "error": str(e),
            "end_time": datetime.now().isoformat(),
            "processing_time": round(time.time() - start_time, 2)
        })
        
        # Send error update via WebSocket
        await manager.send_progress_update(task_id, {
            "type": "task_failed",
            "data": active_tasks[task_id]
        })

async def run_ai_scrape_task(task_id: str, urls: List[str], max_pages_per_url: int):
    """Run the AI scraping task in the background with enhanced progress tracking"""
    start_time = time.time()
    
    try:
        active_tasks[task_id]["status"] = "running"
        
        # Enhanced progress callback with more granular updates
        async def detailed_progress_callback(stage, sub_stage, progress, details=""):
            progress_data = {
                "stage": stage,
                "sub_stage": sub_stage,
                "percentage": progress,
                "details": details,
                "timestamp": datetime.now().isoformat()
            }
            
            if task_id in active_tasks:
                active_tasks[task_id]["current_progress"] = progress_data
                await manager.send_progress_update(task_id, {
                    "type": "progress_update",
                    "data": progress_data
                })
        
        await detailed_progress_callback("initialization", "ai_agent", 5, "Initializing AI agent")
        
        # Initialize AI agent
        from scraper_ai_agent_deep import AIProductScraper
        scraper = AIProductScraper()
        
        if not scraper.ai_agent:
            await detailed_progress_callback("error", "ai_agent", 0, "AI agent not available")
            # Fallback to simple scraping
            return await run_simple_scrape_task(task_id, urls, max_pages_per_url)
        
        all_products = []
        total_pages_processed = 0
        
        for i, url in enumerate(urls):
            base_progress = 10 + (i * 70 // len(urls))
            domain = urlparse(url).netloc
            
            await detailed_progress_callback(
                "url_processing", f"url_{i}", base_progress, 
                f"Processing URL {i+1}/{len(urls)}: {domain}"
            )
            
            # Get page content with progress updates
            await detailed_progress_callback(
                "fetching", "page_content", base_progress + 2,
                f"Fetching page content from {domain}"
            )
            
            html_content = await scraper._fetch_page_content(url)
            if not html_content:
                await detailed_progress_callback(
                    "error", "fetch_failed", base_progress + 3,
                    f"Failed to fetch content from {domain}"
                )
                continue
            
            # Analyze page structure
            await detailed_progress_callback(
                "analysis", "page_structure", base_progress + 5,
                f"Analyzing page structure for {domain}"
            )
            
            analysis = await scraper.ai_agent.analyze_page_structure(html_content, url)
            
            await detailed_progress_callback(
                "analysis", "complete", base_progress + 10,
                f"Page type: {analysis.page_type}, Found {len(analysis.product_links)} products"
            )
            
            if analysis.page_type == "collection" and analysis.product_links:
                # Handle collection page with pagination
                await detailed_progress_callback(
                    "scraping", "collection", base_progress + 15,
                    f"Scraping collection with {len(analysis.product_links)} products"
                )
                
                products = await scraper._scrape_collection_with_pagination(
                    url, analysis, max_pages_per_url, detailed_progress_callback, base_progress + 15
                )
                all_products.extend(products)
                total_pages_processed += len(analysis.pagination_info.page_urls) if analysis.pagination_info else 1
                
            elif analysis.page_type == "product":
                # Handle individual product page
                await detailed_progress_callback(
                    "scraping", "product", base_progress + 15,
                    "Scraping single product"
                )
                
                product = await scraper._scrape_single_product_ai(html_content, url)
                if product and "error" not in product:
                    all_products.append(product)
                    scraper.stats["products_found"] += 1
                total_pages_processed += 1
            
            else:
                # Try to extract any product links found
                if analysis.product_links:
                    await detailed_progress_callback(
                        "scraping", "products", base_progress + 15,
                        f"Scraping {len(analysis.product_links)} products from unknown page type"
                    )
                    
                    for j, product_url in enumerate(analysis.product_links[:max_pages_per_url]):
                        product_progress = base_progress + 15 + (j * 10 // len(analysis.product_links))
                        await detailed_progress_callback(
                            "scraping", f"product_{j}", product_progress,
                            f"Product {j+1}/{len(analysis.product_links)}"
                        )
                        
                        product = await scraper._scrape_single_product_by_url(product_url)
                        if product and "error" not in product:
                            all_products.append(product)
                            scraper.stats["products_found"] += 1
                    
                    total_pages_processed += len(analysis.product_links[:max_pages_per_url])
        
        # Post-process the scraped data
        await detailed_progress_callback(
            "post_processing", "image_fixing", 95,
            "Fixing image URLs and sizes"
        )
        
        result = {
            "products": all_products,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_products": len(all_products),
                "total_pages_processed": total_pages_processed,
                "scraper_type": "ai_agent",
                "ai_stats": scraper.stats,
                "urls_processed": len(urls)
            }
        }
        
        result = await post_process_scraped_data(result)
        
        # Save the fixed results automatically
        timestamp = result["metadata"]["timestamp"]
        await save_fixed_results(result, timestamp, task_id)
        
        # Update task with results
        active_tasks[task_id].update({
            "status": "completed",
            "result": result,
            "ai_stats": scraper.stats,
            "end_time": datetime.now().isoformat(),
            "processing_time": round(time.time() - start_time, 2),
            "current_progress": {
                "stage": "completed",
                "sub_stage": "finished",
                "percentage": 100,
                "details": f"✅ AI scraping completed! Found {len(all_products)} products with fixed image URLs",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        # Send completion update via WebSocket
        await manager.send_progress_update(task_id, {
            "type": "task_completed",
            "data": active_tasks[task_id]
        })
        
    except Exception as e:
        logger.error(f"AI scrape task {task_id} failed: {e}")
        active_tasks[task_id].update({
            "status": "failed",
            "error": str(e),
            "end_time": datetime.now().isoformat(),
            "processing_time": round(time.time() - start_time, 2),
            "current_progress": {
                "stage": "failed",
                "sub_stage": "error",
                "percentage": 0,
                "details": f"❌ AI scraping failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        # Send error update via WebSocket
        await manager.send_progress_update(task_id, {
            "type": "task_failed",
            "data": active_tasks[task_id]
        })
# In api.py, update the startup_event function
@app.on_event("startup")
async def startup_event():
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check if Gemini API key is available
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        logger.warning("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not found. AI features will be disabled.")
    else:
        logger.info("Gemini API key found. AI features are enabled.")
    
    logger.info("🚀 AI-Powered Web Scraper API started successfully!")
    logger.info("📊 Available scrapers: Simple Parser, AI Agent (Gemini 1.5 Flash)")
    logger.info("🌐 GUI available at: http://localhost:8000/")
    logger.info("📚 API docs available at: http://localhost:8000/docs")
    logger.info("🔌 WebSocket support enabled for real-time updates")
    
    # Create upload_data directory if it doesn't exist
    upload_dir = "upload_data"
    os.makedirs(upload_dir, exist_ok=True)
    logger.info(f"Ensured upload directory exists: {upload_dir}")
    # Create shared HTTP session with throttling
    app.state.http_session = ClientSession(
        connector=TCPConnector(limit_per_host=2),
        timeout=aiohttp.ClientTimeout(total=30)
    )
# Another option - use a simpler timestamp format
async def save_fixed_results(result: Dict[str, Any], timestamp: str, task_id: str):
    """Save the fixed scraping results automatically"""
    try:
        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)
        
        # Use a simpler timestamp format without colons or periods
        simple_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save the fixed version
        fixed_file = os.path.join(logs_dir, f"ai_agent_scrape_{simple_timestamp}_FIXED.json")
        
        with open(fixed_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        # Log the successful save
        logger.info(f"✅ Fixed results saved automatically to: {fixed_file}")
        
        # Update metadata to indicate this is the auto-fixed version
        if 'metadata' in result:
            result['metadata']['auto_fixed'] = True
            result['metadata']['fixed_file'] = fixed_file
            result['metadata']['task_id'] = task_id
        
    except Exception as e:
        logger.error(f"❌ Error saving fixed results: {e}")

# Create a shared HTTP session for all requests
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 AI-Powered Web Scraper API started successfully!")
    logger.info("📊 Available scrapers: Simple Parser, AI Agent (Gemini 1.5 Flash)")
    logger.info("🌐 GUI available at: http://localhost:8000/")
    logger.info("📚 API docs available at: http://localhost:8000/docs")
    logger.info("🔌 WebSocket support enabled for real-time updates")
    
    # Create shared HTTP session with throttling
    app.state.http_session = ClientSession(
        connector=TCPConnector(limit_per_host=2),
        timeout=aiohttp.ClientTimeout(total=30)
    )

@app.on_event("shutdown")
async def shutdown_event():
    # Close HTTP session
    await app.state.http_session.close()

class TaskTerminationRequest(BaseModel):
    """Model for task termination request"""
    task_ids: List[str]
    reason: Optional[str] = "User requested termination"

@app.post("/api/terminate-tasks")
async def terminate_tasks(request: TaskTerminationRequest):
    """Terminate active scraping tasks and close WebSocket connections"""
    try:
        terminated_tasks = []
        failed_terminations = []
        
        for task_id in request.task_ids:
            try:
                # Check if task exists and is active
                if task_id not in active_tasks:
                    failed_terminations.append({
                        "task_id": task_id,
                        "reason": "Task not found"
                    })
                    continue
                
                # Update task status to terminated
                if active_tasks[task_id]["status"] in ["running", "started"]:
                    active_tasks[task_id]["status"] = "terminated"
                    active_tasks[task_id]["end_time"] = datetime.now().isoformat()
                    active_tasks[task_id]["termination_reason"] = request.reason
                    
                    # Send termination message to WebSocket connections
                    await manager.send_progress_update(task_id, {
                        "type": "task_terminated",
                        "data": {
                            "task_id": task_id,
                            "reason": request.reason,
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                    
                    # Close WebSocket connections for this task
                    await manager.close_task_connections(task_id)
                    
                    terminated_tasks.append(task_id)
                    logger.info(f"✅ Task {task_id} terminated successfully")
                    
                else:
                    failed_terminations.append({
                        "task_id": task_id,
                        "reason": f"Task status is '{active_tasks[task_id]['status']}', cannot terminate"
                    })
                    
            except Exception as e:
                failed_terminations.append({
                    "task_id": task_id,
                    "reason": f"Error terminating task: {str(e)}"
                })
                logger.error(f"❌ Error terminating task {task_id}: {e}")
        
        # Clean up terminated tasks from memory after a delay
        if terminated_tasks:
            asyncio.create_task(cleanup_terminated_tasks(terminated_tasks))
        
        return {
            "success": True,
            "message": f"Terminated {len(terminated_tasks)} tasks successfully",
            "terminated_tasks": terminated_tasks,
            "failed_terminations": failed_terminations,
            "total_requested": len(request.task_ids),
            "total_terminated": len(terminated_tasks),
            "total_failed": len(failed_terminations)
        }
        
    except Exception as e:
        logger.error(f"Error in terminate_tasks endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error terminating tasks: {str(e)}")

@app.get("/api/active-tasks")
async def get_active_tasks():
    """Get list of currently active tasks"""
    try:
        active_task_list = []
        
        for task_id, task_data in active_tasks.items():
            if task_data["status"] in ["started", "running"]:
                active_task_list.append({
                    "task_id": task_id,
                    "status": task_data["status"],
                    "scraper_type": task_data["scraper_type"],
                    "start_time": task_data["start_time"],
                    "urls_count": len(task_data.get("urls", [])),
                    "current_progress": task_data.get("current_progress", {})
                })
        
        return {
            "success": True,
            "active_tasks": active_task_list,
            "total_active": len(active_task_list),
            "all_tasks_count": len(active_tasks)
        }
        
    except Exception as e:
        logger.error(f"Error getting active tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting active tasks: {str(e)}")


# Request body model
class UrlRequest(BaseModel):
    base_url: str

# @app.post("/api/get-domain-urls")
# async def get_domain_urls(req: UrlRequest):
#     try:
#         base_url = req.base_url.strip()
#         if not base_url.startswith(("http://", "https://")):
#             base_url = "https://" + base_url

#         headers = {"User-Agent": "Mozilla/5.0"}

#         async with httpx.AsyncClient(
#             timeout=httpx.Timeout(10.0, connect=5.0),
#             verify=False,
#             follow_redirects=True,
#             headers=headers
#         ) as client:
#             resp = await client.get(base_url)
            
#             if resp.status_code >= 400:
#                 raise HTTPException(status_code=400, detail=f"Unable to fetch (status {resp.status_code})")

#             tree = HTMLParser(resp.text)
#             sublinks = set()
#             for a in tree.css("a[href]"):
#                 href = a.attributes.get("href")
#                 if not href:
#                     continue
#                 full_url = urljoin(base_url, href)
#                 if urlparse(full_url).netloc == urlparse(base_url).netloc:
#                     sublinks.add(full_url)

#             sublinks = sorted(list(sublinks)) # smaller MAX_LINKS

#             semaphore = asyncio.Semaphore(5)
#             async def fetch(url):
#                 async with semaphore:
#                     try:
#                         return url, await client.get(url)
#                     except Exception:
#                         return url, None

#             responses = await asyncio.gather(*[fetch(u) for u in sublinks])

#             collections_with_products, product_urls, urls_array = [], set(), set()
#             for url, res in responses:
#                 if not res or res.status_code != 200:
#                     continue
#                 tree = HTMLParser(res.text)
#                 product_links = [
#                     urljoin(base_url, a.attributes.get("href"))
#                     for a in tree.css("a[href*='/products/']")
#                 ]
#                 if product_links:
#                     collections_with_products.append(url)
#                     product_urls.update(product_links)
#                 urls_array.add(url)

#             return {
#                 "success": True,
#                 "base_url": base_url,
#                 "collections_count": len(collections_with_products),
#                 "collections_with_products": sorted(collections_with_products),
#                 "total_products": len(product_urls),
#                 "all_product_urls": sorted(product_urls),
#                 "urls_array": sorted(urls_array)
#             }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error scraping: {str(e)}")

async def fetch_html(client, url):
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        return None
    return None

@app.post("/api/get-domain-urls")
async def get_domain_urls(req: UrlRequest):
    try:
        base_url = req.base_url.strip()
        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url  # default try https

        headers = {"User-Agent": "Mozilla/5.0"}

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            verify=False,
            follow_redirects=True,
            headers=headers
        ) as client:
            # Try HTTPS first, fallback to HTTP if fails
            html = await fetch_html(client, base_url)
            if not html and base_url.startswith("https://"):
                base_url = base_url.replace("https://", "http://", 1)
                html = await fetch_html(client, base_url)
            if not html:
                raise HTTPException(status_code=400, detail="Unable to fetch the site")

            tree = HTMLParser(html)
            sublinks = set()
            for a in tree.css("a[href]"):
                href = a.attributes.get("href")
                if not href:
                    continue
                full_url = urljoin(base_url, href)
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    sublinks.add(full_url)

            # limit crawling
            sublinks = sorted(list(sublinks))

            semaphore = asyncio.Semaphore(5)
            async def fetch(url):
                async with semaphore:
                    try:
                        return url, await client.get(url)
                    except Exception:
                        return url, None

            responses = await asyncio.gather(*[fetch(u) for u in sublinks])

            collections_with_products, product_urls, urls_array = [], set(), set()
            for url, res in responses:
                if not res or res.status_code != 200:
                    continue
                tree = HTMLParser(res.text)

                # Detect Shopify (/products/) and WooCommerce (/product/)
                product_links = [
                    urljoin(base_url, a.attributes.get("href"))
                    for a in tree.css("a[href]")
                    if a.attributes.get("href") and (
                        "/products/" in a.attributes["href"] or "/product/" in a.attributes["href"]
                    )
                ]

                if product_links:
                    collections_with_products.append(url)
                    product_urls.update(product_links)

                urls_array.add(url)

            return {
                "success": True,
                "base_url": base_url,
                "collections_count": len(collections_with_products),
                "collections_with_products": sorted(collections_with_products),
                "total_products": len(product_urls),
                "all_product_urls": sorted(product_urls),
                "urls_array": sorted(urls_array)
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scraping: {str(e)}")

async def cleanup_terminated_tasks(task_ids: List[str], delay_seconds: int = 30):
    """Clean up terminated tasks from memory after a delay"""
    try:
        await asyncio.sleep(delay_seconds)
        
        for task_id in task_ids:
            if task_id in active_tasks and active_tasks[task_id]["status"] == "terminated":
                del active_tasks[task_id]
                logger.info(f"🗑️ Cleaned up terminated task {task_id} from memory")
                
    except Exception as e:
        logger.error(f"Error cleaning up terminated tasks: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)