#!/usr/bin/env python3
"""
Script to fix image URLs in existing scraping log files
"""

import os
import glob
from image_url_fixer import fix_json_file

def fix_all_logs(logs_dir='logs'):
    """
    Fix image URLs in all JSON log files in the logs directory
    
    Args:
        logs_dir (str): Directory containing log files
    """
    if not os.path.exists(logs_dir):
        print(f"❌ Logs directory not found: {logs_dir}")
        return
    
    # Find all JSON log files
    json_files = glob.glob(os.path.join(logs_dir, "*.json"))
    
    if not json_files:
        print(f"❌ No JSON files found in {logs_dir}")
        return
    
    print(f"🔍 Found {len(json_files)} JSON files to process:")
    
    for json_file in json_files:
        print(f"\n📂 Processing: {os.path.basename(json_file)}")
        
        try:
            # Create output filename
            base_name = os.path.splitext(json_file)[0]
            output_file = f"{base_name}_FIXED.json"
            
            # Skip if already processed
            if "_FIXED" in json_file:
                print(f"   ⚪ Skipping (already fixed)")
                continue
            
            # Fix the file
            data = fix_json_file(json_file, output_file)
            
            if data and 'products' in data:
                products_count = len(data['products'])
                fixed_count = data.get('metadata', {}).get('products_with_fixed_images', 0)
                print(f"   ✅ Success: {products_count} products, {fixed_count} had image URLs fixed")
            else:
                print(f"   ⚠️ Warning: No products found in file")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def main():
    print("🔧 Image URL Fixer for Existing Log Files")
    print("=" * 50)
    
    # Fix all logs in the logs directory
    fix_all_logs()
    
    print("\n🎉 Processing complete!")
    print("\nFixed files are saved with '_FIXED' suffix")
    print("You can now use these files in your product editor.")

if __name__ == "__main__":
    main() 