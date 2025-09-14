import asyncio
import json
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import aiohttp
from scraper_simple import SimpleProductScraper
from scraper_ai_agent import AIProductScraper
from image_url_fixer import fix_product_images

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduled_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ScheduledScraper:
    def __init__(self, api_endpoint: str, api_key: str = None):
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.last_run_file = "last_run.txt"
        
    async def load_urls(self, urls_file: str = "urls.txt") -> List[str]:
        """Load URLs from a text file"""
        try:
            with open(urls_file, 'r') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            logger.info(f"Loaded {len(urls)} URLs from {urls_file}")
            return urls
        except FileNotFoundError:
            logger.error(f"URLs file {urls_file} not found")
            return []
    
    def should_run(self) -> bool:
        """Check if it's time to run the scraper (every 10 days)"""
        try:
            if not os.path.exists(self.last_run_file):
                return True
                
            with open(self.last_run_file, 'r') as f:
                last_run_str = f.read().strip()
                
            if not last_run_str:
                return True
                
            last_run = datetime.fromisoformat(last_run_str)
            next_run = last_run + timedelta(days=10)
            
            if datetime.now() >= next_run:
                return True
            else:
                logger.info(f"Next run scheduled for: {next_run}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking last run: {e}")
            return True
    
    def update_last_run(self):
        """Update the last run timestamp"""
        try:
            with open(self.last_run_file, 'w') as f:
                f.write(datetime.now().isoformat())
            logger.info("Updated last run timestamp")
        except Exception as e:
            logger.error(f"Error updating last run: {e}")
    
    async def scrape_urls(self, urls: List[str]) -> Dict[str, Any]:
        """Scrape all URLs and return the results"""
        # Try AI scraper first, fall back to simple scraper
        try:
            scraper = AIProductScraper()
            if scraper.ai_agent:
                logger.info("Using AI scraper")
                result = await scraper.scrape_with_ai_agent(urls, max_pages_per_url=50)
            else:
                raise Exception("AI agent not available")
        except Exception as e:
            logger.warning(f"AI scraper failed, using simple scraper: {e}")
            scraper = SimpleProductScraper()
            result = {"products": []}
            
            for url in urls:
                try:
                    if "/collection" in url or "/category" in url or "/shop" in url:
                        products = await scraper.scrape_collection_with_pagination(url, max_pages=20)
                        result["products"].extend(products)
                    else:
                        product = await scraper.extract_product_data(url)
                        if product and "error" not in product:
                            result["products"].append(product)
                except Exception as url_error:
                    logger.error(f"Error scraping {url}: {url_error}")
        
        # Add metadata
        result["metadata"] = {
            "scraped_at": datetime.now().isoformat(),
            "total_products": len(result.get("products", [])),
            "scraper_type": "AI" if isinstance(scraper, AIProductScraper) else "Simple"
        }
        
        return result
    
    async def send_to_api(self, data: Dict[str, Any]) -> bool:
        """Send scraped data to the API endpoint"""
        try:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "ScheduledScraper/1.0"
            }
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_endpoint,
                    json=data,
                    headers=headers,
                    timeout=60
                ) as response:
                    if response.status == 200:
                        logger.info(f"Successfully sent data to API")
                        return True
                    else:
                        logger.error(f"API returned error status: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Error sending data to API: {e}")
            return False
    
    async def run(self):
        """Main method to run the scheduled scraping"""
        if not self.should_run():
            logger.info("Not time to run yet")
            return
        
        logger.info("Starting scheduled scraping run")
        
        # Load URLs
        urls = await self.load_urls()
        if not urls:
            logger.error("No URLs to scrape")
            return
        
        # Scrape data
        scraped_data = await self.scrape_urls(urls)
        
        # Fix image URLs
        if "products" in scraped_data:
            fixed_images, image_sizes = fix_product_images(
                [img for product in scraped_data["products"] for img in product.get("product_images", [])]
            )
            # Update products with fixed images (this is a simplified approach)
            # In a real implementation, you'd want to update each product individually
        
        # Send to API
        success = await self.send_to_api(scraped_data)
        
        if success:
            # Update last run time
            self.update_last_run()
            logger.info("Scheduled scraping completed successfully")
        else:
            logger.error("Scheduled scraping failed - API call unsuccessful")

async def main():
    # Configuration - update these values as needed
    API_ENDPOINT = os.getenv("API_ENDPOINT", "https://your-api-endpoint.com/products")
    API_KEY = os.getenv("API_KEY", None)
    
    scraper = ScheduledScraper(API_ENDPOINT, API_KEY)
    await scraper.run()

if __name__ == "__main__":
    asyncio.run(main())