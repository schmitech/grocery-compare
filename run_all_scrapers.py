#!/usr/bin/env python3
"""
Run all available grocery store scrapers to populate the ChromaDB database.
This script will run each scraper in sequence and report the results.
"""

import os
import sys
import importlib
import time
from datetime import datetime

# Add the project root to the path to allow importing modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def run_scraper(scraper_name):
    """
    Run a specific scraper module.
    
    Args:
        scraper_name: Name of the scraper module (without the .py extension)
    
    Returns:
        bool: True if the scraper ran successfully, False otherwise
    """
    print(f"\n{'='*70}")
    print(f"Running {scraper_name} scraper")
    print(f"{'='*70}")
    
    try:
        # Import the scraper module
        module_path = f"scrapers.{scraper_name}"
        scraper_module = importlib.import_module(module_path)
        
        # Run the main function
        if hasattr(scraper_module, 'main'):
            scraper_module.main()
            print(f"\n{scraper_name} scraper completed successfully!")
            return True
        else:
            print(f"Error: {scraper_name} does not have a main() function.")
            return False
    
    except Exception as e:
        print(f"Error running {scraper_name} scraper: {e}")
        return False

def main():
    """Main function to run all scrapers."""
    start_time = time.time()
    
    print(f"{'='*70}")
    print(f"RUNNING ALL GROCERY SCRAPERS")
    print(f"{'='*70}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"This script will run all available scrapers to populate the database.")
    
    # List of available scrapers (without the .py extension)
    scrapers = [
        "produceDepot",
        "farmboy"
    ]
    
    # Run each scraper and track results
    successful_scrapers = []
    failed_scrapers = []
    
    for scraper in scrapers:
        if run_scraper(scraper):
            successful_scrapers.append(scraper)
        else:
            failed_scrapers.append(scraper)
    
    # Print summary
    elapsed_time = time.time() - start_time
    
    print(f"\n{'='*70}")
    print(f"SCRAPER RUN SUMMARY")
    print(f"{'='*70}")
    print(f"Total scrapers: {len(scrapers)}")
    print(f"Successful: {len(successful_scrapers)}")
    print(f"Failed: {len(failed_scrapers)}")
    print(f"Elapsed time: {elapsed_time:.2f} seconds")
    
    if successful_scrapers:
        print("\nSuccessful scrapers:")
        for scraper in successful_scrapers:
            print(f"- {scraper}")
    
    if failed_scrapers:
        print("\nFailed scrapers:")
        for scraper in failed_scrapers:
            print(f"- {scraper}")
    
    print(f"\n{'='*70}")
    print("Next steps:")
    print("1. Run the test script to verify data was loaded correctly:")
    print("   python test_chroma_collections.py")
    print("2. Run the chatbot to interact with the data:")
    print("   streamlit run grocery_chatbot.py")
    print(f"{'='*70}")

if __name__ == "__main__":
    main() 