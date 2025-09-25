import asyncio
import httpx
from bs4 import BeautifulSoup

async def simple_test():
    url = "https://supercape.in/product/attention-please-unisex-regular-fit-tshirt/"
    
    print(f"Testing URL: {url}")
    
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Test the exact selector we expect
            print("\n1. Testing exact selector:")
            elements = soup.select('.price .woocommerce-Price-amount.amount bdi')
            print(f"Found {len(elements)} elements with exact selector")
            
            for i, element in enumerate(elements):
                text = element.get_text(strip=True)
                print(f"  Element {i+1}: '{text}'")
                
                # Simple price extraction
                import re
                numbers = re.findall(r'[\d,]+\.?\d*', text)
                if numbers:
                    try:
                        price_str = numbers[0].replace(',', '')
                        price = float(price_str)
                        print(f"  -> Extracted price: {price}")
                    except ValueError as e:
                        print(f"  -> Could not parse: {e}")
            
            # Test broader selector
            print("\n2. Testing broader selector:")
            elements = soup.select('.price')
            print(f"Found {len(elements)} .price elements")
            
            for i, element in enumerate(elements[:2]):
                text = element.get_text(strip=True)
                print(f"  Price element {i+1}: '{text[:100]}'")
                
                # Look for rupee symbol
                import re
                matches = re.findall(r'₹\s*([0-9,]+(?:\.[0-9]{2})?)', text)
                if matches:
                    print(f"  -> Found rupee price: {matches[0]}")
                
        else:
            print(f"Failed to fetch: {response.status_code}")

asyncio.run(simple_test())