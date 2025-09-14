# Scheduled Product Scraper Solution

4. Setup Instructions

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

2. **Set up environment variables**:
   Create a `.env` file:
   ```
   API_ENDPOINT=https://your-api-endpoint.com/products
   API_KEY=your_api_key_here
   GEMINI_API_KEY=your_gemini_api_key_here  # If using AI features
   ```

3. **Run the scraper manually first**:
   ```bash
   python scheduled_scraper.py
   ```

## 5. Schedule the Script to Run Every 10 Days

### On Linux/macOS (using cron):

1. Open the crontab editor:
   ```bash
   crontab -e
   ```

2. Add this line to run every 10 days at 2 AM:
   ```
   0 2 */10 * * cd /path/to/your/project && /path/to/python /path/to/project/scheduled_scraper.py >> /path/to/project/scraper.log 2>&1
   ```

### On Windows (using Task Scheduler):

1. Open Task Scheduler
2. Create a new task
3. Set the trigger to "Daily" and recurrence to 10 days
4. Set the action to start a program:
   - Program: `C:\Path\To\Python\python.exe`
   - Arguments: `C:\Path\To\Project\scheduled_scraper.py`
5. Set the working directory to your project folder

### Using a Python scheduler (alternative approach):

Create a separate scheduler script `run_scheduler.py`:

```python
import asyncio
import time
from scheduled_scraper import ScheduledScraper

async def run_scraper():
    API_ENDPOINT = "https://your-api-endpoint.com/products"
    API_KEY = "your_api_key_here"
    
    scraper = ScheduledScraper(API_ENDPOINT, API_KEY)
    await scraper.run()

async def main():
    # Run immediately on startup
    await run_scraper()
    
    # Then run every 10 days
    while True:
        await asyncio.sleep(10 * 24 * 60 * 60)  # 10 days in seconds
        await run_scraper()

if __name__ == "__main__":
    asyncio.run(main())
```

## 6. API Data Format

The scraper will send data to your API in this format:

```json
{
  "products": [
    {
      "product_name": "Product Name",
      "price": 99.99,
      "discounted_price": null,
      "product_images": ["https://example.com/image1.jpg"],
      "description": "Product description",
      "sizes": ["S", "M", "L"],
      "colors": ["Red", "Blue"],
      "material": "Cotton",
      "metadata": {
        "availability": "InStock",
        "sku": "ABC123",
        "brand": "Brand Name",
        "categories": ["Category1", "Category2"]
      },
      "source_url": "https://example.com/product",
      "timestamp": "2023-11-07T12:00:00.000000"
    }
  ],
  "metadata": {
    "scraped_at": "2023-11-07T12:00:00.000000",
    "total_products": 1,
    "scraper_type": "AI"
  }
}
```

## 7. Monitoring and Logs

The script will create:
- `scheduled_scraper.log` - Detailed logs of each run
- `last_run.txt` - Timestamp of the last successful run
- `scraper.log` - If using cron, output will be appended here

## 8. Error Handling

The script includes comprehensive error handling:
- Continues if individual URLs fail
- Falls back to simple scraper if AI scraper fails
- Logs all errors for debugging
- Doesn't update the last run time if API call fails

This solution provides a robust, scheduled scraping system that will run every 10 days, scrape product and stock details from your URLs, and send the data to your API endpoint.