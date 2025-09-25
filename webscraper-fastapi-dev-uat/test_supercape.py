import asyncio
from scraper_simple_deep import SimpleProductScraper

async def test_supercape():
    scraper = SimpleProductScraper()
    url = "https://supercape.in/product/attention-please-unisex-regular-fit-tshirt/"
    
    print(f"Testing URL: {url}")
    
    # Test the debug method directly
    await scraper.debug_price_extraction_supercape(url)
    
    print("\n" + "="*50)
    print("TESTING FULL EXTRACTION:")
    print("="*50)
    
    # Test full extraction
    result = await scraper.extract_product_data_hybrid(url)
    
    print(f"Final Result:")
    print(f"Product Name: {result.get('product_name', 'Not found')}")
    print(f"Price: {result.get('price', 'Not found')}")
    print(f"Extraction Method: {result.get('extraction_method', 'Unknown')}")
    
    return result

if __name__ == "__main__":
    asyncio.run(test_supercape())