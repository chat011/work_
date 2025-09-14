import re
import json
from bs4 import BeautifulSoup

# Sample HTML with Shopify variants (similar to what we found on deashaindia.com)
sample_html = '''
<script>
"variants":[{"id":50472020541751,"price":494900,"name":"MAHIRA RED FLORAL SAREE - XS","public_title":"XS","sku":"BKLMAH06XS"},{"id":50472020574519,"price":494900,"name":"MAHIRA RED FLORAL SAREE - XXS","public_title":"XXS","sku":"BKLMAH06XXS"},{"id":50472020607287,"price":494900,"name":"MAHIRA RED FLORAL SAREE - S","public_title":"S","sku":"BKLMAH06S"},{"id":50472020640055,"price":494900,"name":"MAHIRA RED FLORAL SAREE - M","public_title":"M","sku":"BKLMAH06M"},{"id":50472020672823,"price":494900,"name":"MAHIRA RED FLORAL SAREE - L","public_title":"L","sku":"BKLMAH06L"},{"id":50472020705591,"price":494900,"name":"MAHIRA RED FLORAL SAREE - XL","public_title":"XL","sku":"BKLMAH06XL"},{"id":50472020738359,"price":494900,"name":"MAHIRA RED FLORAL SAREE - 2XL","public_title":"2XL","sku":"BKLMAH062XL"},{"id":50472020771127,"price":514900,"name":"MAHIRA RED FLORAL SAREE - 3XL","public_title":"3XL","sku":"BKLMAH063XL"}]
</script>
'''

def test_variant_extraction():
    print("Testing improved variant extraction...")
    
    soup = BeautifulSoup(sample_html, 'html.parser')
    variants = []
    variant_type = 'size'
    
    # Look for Shopify product JSON in script tags
    all_scripts = soup.find_all('script')
    for script in all_scripts:
        if script.string and ('variants' in script.string.lower()):
            try:
                script_content = script.string
                
                # Look for variants array directly
                variants_pattern = r'"variants"\s*:\s*\[(.*?)\]'
                variants_match = re.search(variants_pattern, script_content, re.DOTALL)
                if variants_match:
                    variants_str = variants_match.group(1)
                    print(f"Found variants string: {variants_str[:100]}...")
                    
                    # Extract public_title values from variants
                    if variant_type.lower() == 'size':
                        size_patterns = [
                            r'"public_title"\s*:\s*"([^"]*)"',
                            r'"title"\s*:\s*"([^"]*)"',
                            r'"option1"\s*:\s*"([^"]*)"'
                        ]
                        for pattern in size_patterns:
                            size_matches = re.findall(pattern, variants_str)
                            print(f"Pattern {pattern} found: {size_matches}")
                            for size in size_matches:
                                # Check if it looks like a size
                                if re.match(r'^(XXS|XS|S|M|L|XL|\d*XL|\d+)$', size.strip(), re.IGNORECASE):
                                    if size.strip() not in variants:
                                        variants.append(size.strip())
                        
                        print(f"✅ Extracted sizes: {variants}")
                        return variants
                        
            except Exception as e:
                print(f"Error: {e}")
                continue
    
    print("❌ No variants found")
    return []

if __name__ == "__main__":
    sizes = test_variant_extraction()
    if sizes:
        print(f"SUCCESS: Found {len(sizes)} sizes: {sizes}")
    else:
        print("FAILED: No sizes extracted") 