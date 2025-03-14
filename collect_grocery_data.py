#!/usr/bin/env python3
"""
Grocery Data Collector

This script runs all available grocery store scrapers and collects data from multiple stores.
"""

import os
import sys
import importlib
import argparse
from datetime import datetime

# Add the scrapers directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scrapers'))

def get_available_scrapers():
    """
    Get a list of available scrapers in the scrapers directory.
    
    Returns:
        list: List of scraper module names (without .py extension)
    """
    scrapers_dir = os.path.join(os.path.dirname(__file__), 'scrapers')
    scrapers = []
    
    for filename in os.listdir(scrapers_dir):
        if filename.endswith('.py') and not filename.startswith('__') and filename != 'storage.py' and filename != 'scraper_template.py':
            scrapers.append(filename[:-3])  # Remove .py extension
    
    return scrapers

def run_scraper(scraper_name):
    """
    Run a specific scraper by name.
    
    Args:
        scraper_name: Name of the scraper module (without .py extension)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Import the scraper module
        scraper_module = importlib.import_module(scraper_name)
        
        # Call the main function
        if hasattr(scraper_module, 'main'):
            print(f"\n=== Running {scraper_name} scraper ===")
            scraper_module.main()
            return True
        else:
            print(f"Error: {scraper_name} does not have a main() function.")
            return False
    except Exception as e:
        print(f"Error running {scraper_name} scraper: {e}")
        return False

def main():
    """Main function to run all scrapers or specific ones."""
    parser = argparse.ArgumentParser(description='Collect grocery data from multiple stores.')
    parser.add_argument('--scrapers', nargs='+', help='Specific scrapers to run (without .py extension)')
    parser.add_argument('--list', action='store_true', help='List available scrapers')
    args = parser.parse_args()
    
    # Get available scrapers
    available_scrapers = get_available_scrapers()
    
    # List available scrapers if requested
    if args.list:
        print("Available scrapers:")
        for scraper in available_scrapers:
            print(f"  - {scraper}")
        return
    
    # Determine which scrapers to run
    scrapers_to_run = args.scrapers if args.scrapers else available_scrapers
    
    # Validate scrapers
    for scraper in scrapers_to_run:
        if scraper not in available_scrapers:
            print(f"Warning: {scraper} is not an available scraper. Skipping.")
            scrapers_to_run.remove(scraper)
    
    if not scrapers_to_run:
        print("No valid scrapers to run.")
        return
    
    # Run each scraper
    start_time = datetime.now()
    print(f"Starting data collection at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    successful = 0
    for scraper in scrapers_to_run:
        if run_scraper(scraper):
            successful += 1
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\nData collection completed at {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration}")
    print(f"Successfully ran {successful} out of {len(scrapers_to_run)} scrapers.")
    
    # Import the storage module to run a test query across all stores
    try:
        from scrapers.storage import GroceryDataStorage
        
        storage = GroceryDataStorage()
        print("\nTesting query across all stores...")
        results = storage.query_all_stores("fresh vegetables", 3)
        
        if results:
            print(f"\nFound {len(results)} results across all stores:")
            for i, item in enumerate(results):
                print(f"{i+1}. [{item['store']}] {item['name']} - {item['price']}")
                if "description" in item and item["description"]:
                    print(f"   {item['description']}")
                print(f"   Category: {item['category']}")
                if "unit" in item:
                    print(f"   Unit: {item['unit']}")
                if "unit_price" in item:
                    print(f"   Unit Price: ${item['unit_price']:.2f}")
                print()
        else:
            print("No results found across stores.")
    except Exception as e:
        print(f"Error testing query across stores: {e}")

if __name__ == "__main__":
    main() 