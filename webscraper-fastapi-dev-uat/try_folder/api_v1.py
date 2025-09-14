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
from scraper_simple import EnhancedSimpleProductScraper, scrape_urls_enhanced_api
from scraper_ai_agent import scrape_urls_ai_agent
from image_url_fixer import EnhancedImageURLFixer, fix_product_images
import glob

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Enhanced AI-Powered Web Scraper API", version="3.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Setup templates
templates = Jinja2Templates(directory="templates")

class ScrapeRequest(BaseModel):
    """Model for scrape request data"""
    urls: List[HttpUrl]
    max_pages: int = 50  # Increased default for complete pagination

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
websocket_connections: Dict[str, List[WebSocket]] = {}

class EnhancedConnectionManager:
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
            try:
                self.active_connections[task_id].remove(websocket)
                if not self.active_connections[task_id]:
                    del self.active_connections[task_id]
            except ValueError:
                pass  # Connection already removed
        logger.info(f"WebSocket connection closed for task {task_id}")

    async def send_progress_update(self, task_id: str, message: dict):
        if task_id in self.active_connections and self.active_connections[task_id]:
            logger.info(f"Sending WebSocket message to {len(self.active_connections[task_id])} connections for task {task_id}")
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
            logger.debug(f"No active WebSocket connections for task {task_id}")

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
            
            del self.active_connections[task_id]
            logger.info(f"Closed {len(disconnected_connections)} WebSocket connections for task {task_id}")
        else:
            logger.info(f"No active WebSocket connections found for task {task_id}")

manager = EnhancedConnectionManager()

async def enhanced_post_process_scraped_data(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced post-processing with async image fixing and better performance
    """
    logger.info("Starting enhanced post-processing of scraped data...")
    
    if not result or 'products' not in result:
        logger.warning("No products found in result, skipping post-processing")
        return result
    
    total_products = len(result['products'])
    if total_products == 0:
        return result
    
    fixed_count = 0
    total_images_before = 0
    total_images_after = 0
    
    # Process in batches for better performance
    batch_size = 10
    logger.info(f"Processing {total_products} products in batches of {batch_size}")
    
    async with EnhancedImageURLFixer(max_concurrent_requests=5) as fixer:
        for i in range(0, total_products, batch_size):
            batch = result['products'][i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_products + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches}")
            
            # Process batch concurrently
            batch_tasks = []
            for product in batch:
                if 'product_images' in product and product['product_images']:
                    original_count = len(product['product_images'])
                    total_images_before += original_count
                    batch_tasks.append(fixer.fix_product_images_async(product['product_images']))
                else:
                    batch_tasks.append(asyncio.coroutine(lambda: ([], []))())
            
            if batch_tasks:
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Update products with results
                for product, result_item in zip(batch, batch_results):
                    if isinstance(result_item, tuple):
                        fixed_images, sizes = result_item
                        if 'product_images' in product:
                            original_count = len(product['product_images'])
                            product['product_images'] = fixed_images
                            product['image_sizes'] = sizes
                            
                            new_count = len(fixed_images)
                            total_images_after += new_count
                            
                            if original_count != new_count:
                                fixed_count += 1
                    elif isinstance(result_item, Exception):
                        logger.error(f"Error processing product images: {result_item}")
            
            # Small delay between batches
            await asyncio.sleep(0.1)
    
    # Calculate statistics
    images_removed = total_images_before - total_images_after
    fix_percentage = (fixed_count / total_products * 100) if total_products > 0 else 0
    
    # Update metadata
    if 'metadata' not in result:
        result['metadata'] = {}
        
    result['metadata'].update({
        'image_urls_fixed': True,
        'products_with_fixed_images': fixed_count,
        'total_images_before_fix': total_images_before,
        'total_images_after_fix': total_images_after,
        'images_removed': images_removed,
        'fix_percentage': round(fix_percentage, 1),
        'image_fix_timestamp': datetime.now().isoformat(),
        'enhanced_processing': True,
        'async_image_processing': True
    })
    
    logger.info(f"Enhanced post-processing complete:")
    logger.info(f"   Products processed: {total_products}")
    logger.info(f"   Products with fixed images: {fixed_count} ({fix_percentage:.1f}%)")
    logger.info(f"   Images: {total_images_before} -> {total_images_after} (removed {images_removed} invalid)")
    
    return result

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main GUI interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/edit-products", response_class=HTMLResponse)
async def edit_products(request: Request, task_id: Optional[str] = None):
    """Serve the enhanced product editing interface"""
    return templates.TemplateResponse("edit_products.html", {"request": request, "task_id": task_id})

@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """Enhanced WebSocket endpoint for real-time progress updates"""
    await manager.connect(websocket, task_id)
    try:
        # Send current task status if available
        if task_id in active_tasks:
            await websocket.send_json({
                "type": "status_update",
                "data": active_tasks[task_id]
            })
        
        while True:
            # Keep connection alive and handle ping/pong
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send keep-alive ping
                await websocket.send_json({"type": "keep_alive", "timestamp": datetime.now().isoformat()})
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id)
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
        manager.disconnect(websocket, task_id)

@app.get("/api")
async def api_info():
    """Enhanced API information endpoint"""
    return {
        "message": "Enhanced AI-Powered Web Scraper API",
        "version": "3.0.0",
        "scraper_types": {
            "enhanced_simple": "High-performance direct HTML parsing with complete pagination",
            "ai_agent": "AI-powered intelligent scraper using Gemini 1.5 Flash"
        },
        "endpoints": {
            "gui": "GET / - Web GUI interface",
            "scrape": "POST /scrape - Enhanced scraping with complete pagination support",
            "scrape/ai": "POST /scrape/ai - AI-powered intelligent scraping",
            "status": "GET /status/{task_id} - Get scraping task status",
            "websocket": "WS /ws/{task_id} - Real-time progress updates",
            "health": "GET /health - API health check",
            "tasks": "GET /api/tasks - List available tasks",
            "products": "GET /api/products/{task_id} - Get products by task ID"
        },
        "new_features": {
            "v3.0": [
                "Complete pagination support - scrapes ALL pages",
                "Async image processing for 10x faster image validation",
                "Enhanced product editor with image management",
                "Individual image removal and validation",
                "Image size detection and display",
                "Real-time image URL validation",
                "Batch processing for improved performance",
                "Enhanced error handling and recovery",
                "Better progress tracking and WebSocket updates"
            ]
        },
        "performance_improvements": [
            "Parallel image processing",
            "Async HTTP requests",
            "Batch processing",
            "Optimized pagination detection",
            "Faster URL validation",
            "Concurrent scraping with rate limiting"
        ],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Enhanced health check endpoint"""
    return {
        "status": "healthy",
        "version": "3.0.0",
        "active_tasks": len(active_tasks),
        "active_websockets": sum(len(connections) for connections in manager.active_connections.values()),
        "scraper_types": ["enhanced_simple", "ai_agent"],
        "features": {
            "complete_pagination": True,
            "async_image_processing": True,
            "enhanced_editor": True,
            "real_time_updates": True
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_products_enhanced(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Enhanced scraping with complete pagination support and async image processing
    
    NEW FEATURES:
    - **Complete Pagination**: Scrapes ALL pages of collections automatically
    - **Async Image Processing**: 10x faster image validation and sizing
    - **Enhanced Performance**: Parallel processing and optimized requests
    - **Better Error Handling**: Robust error recovery and logging
    
    Parameters:
    - **urls**: List of URLs to scrape (collections or individual products)
    - **max_pages**: