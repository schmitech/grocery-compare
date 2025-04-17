#!/usr/bin/env python3
"""
Test script to verify that grocery data was successfully loaded into a unified Chroma collection.
This script queries the collection and displays sample results for each store and across all stores.

Note: You must run the scrapers first to populate the database:
- python grocery_specials.py "Metro Market" ./weekly-specials/metromarket.json
- python grocery_specials.py "SunnySide Foods" ./weekly-specials/sunnyside.json

This script assumes the remote Chroma server is configured in config.yaml
"""

import os
import sys
import json
from pprint import pprint

# Import the storage module
from storage import GroceryDataStorage

def test_store_query(storage, store_name, query="fresh", num_results=3):
    """
    Test querying products from a specific store.
    
    Args:
        storage: GroceryDataStorage instance
        store_name: Name of the store to query
        query: Search query to use
        num_results: Number of results to display
    
    Returns:
        bool: True if the query returns results, False otherwise
    """
    print(f"\n{'='*50}")
    print(f"Testing query for store: {store_name}")
    print(f"{'='*50}")
    
    try:
        results = storage.query_store(store_name, query, num_results)
        
        if not results or 'documents' not in results or not results["documents"] or not results["documents"][0]:
            print(f"No results found for '{query}' in {store_name}.")
            return False
        
        print(f"Found {len(results['documents'][0])} results for '{query}' in {store_name}:")
        
        for i, (doc, metadata, distance) in enumerate(zip(
            results["documents"][0], 
            results["metadatas"][0],
            results["distances"][0] if "distances" in results and results["distances"] else [0] * len(results["metadatas"][0])
        )):
            similarity = 1 - distance
            print(f"\n{i+1}. {metadata['name']} - {metadata['price']} ({store_name})")
            print(f"   Similarity: {similarity:.4f}")
            if "description" in metadata and metadata["description"]:
                print(f"   {metadata['description']}")
            print(f"   Category: {metadata['category']}")
            if "unit" in metadata:
                print(f"   Unit: {metadata['unit']}")
            if "unit_price" in metadata and metadata["unit_price"] is not None:
                if isinstance(metadata["unit_price"], (int, float)):
                    print(f"   Unit Price: ${metadata['unit_price']:.2f}")
                else:
                    print(f"   Unit Price: {metadata['unit_price']}")
        
        return True
    
    except Exception as e:
        print(f"Error querying {store_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function to test the Chroma collection."""
    print("=" * 70)
    print("GROCERY DEALS DATABASE TEST (SINGLE COLLECTION)")
    print("=" * 70)
    print("Testing connection to remote Chroma server...")
    print("This script tests if data has been successfully loaded into the unified Chroma collection.")
    print("If no data is found, please run the scrapers first:")
    print("  python grocery_specials.py \"Metro Market\" ./weekly-specials/metromarket.json")
    print("  python grocery_specials.py \"SunnySide Foods\" ./weekly-specials/sunnyside.json")
    print("=" * 70)
    
    # Get query from command line arguments, default to "fresh" if not provided
    query = "fresh"  # default query
    config_path = "config.yaml"  # default config path
    
    if len(sys.argv) > 1:
        query = sys.argv[1]
    if len(sys.argv) > 2:
        config_path = sys.argv[2]
    
    try:
        # Initialize storage with the config path
        print(f"Initializing storage with config from: {config_path}")
        storage = GroceryDataStorage(config_path=config_path)
        
        # Print connection information
        print(f"Connected to Chroma server at: {storage.chroma_host}:{storage.chroma_port}")
        print(f"Using Ollama embedding model: {storage.model}")
        print(f"Using collection: {storage.collection_name}")
        print(f"Using search query: '{query}'")
        
        # Get list of all stores in the database
        stores = storage.get_all_stores()
        print(f"\nFound {len(stores)} stores in the database: {', '.join(stores)}")
        
        if not stores:
            print("\nNo stores found in the database. Please run the scrapers first to populate the database.")
            print("  python grocery_specials.py \"Metro Market\" ./weekly-specials/metromarket.json")
            print("  python grocery_specials.py \"SunnySide Foods\" ./weekly-specials/sunnyside.json")
            return
        
        # Test store-specific queries
        successful_stores = []
        for store in stores:
            if test_store_query(storage, store, query=query):
                successful_stores.append(store)
        
        # Summary
        print("\n" + "="*50)
        print("Test Summary")
        print("="*50)
        print(f"Successfully tested {len(successful_stores)} out of {len(stores)} stores.")
        if successful_stores:
            print("Successful stores:")
            for store in successful_stores:
                print(f"- {store}")
        else:
            print("\nNo store queries were successful.")
            print("Please make sure you've run the scrapers to populate the database:")
            print("  python grocery_specials.py \"Metro Market\" ./weekly-specials/metromarket.json")
            print("  python grocery_specials.py \"SunnySide Foods\" ./weekly-specials/sunnyside.json")
        
        # Test a cross-store query
        if len(successful_stores) > 0:
            print("\n" + "="*50)
            print("Testing Cross-Store Query")
            print("="*50)
            
            try:
                print(f"Searching for '{query}' across all stores...")
                results = storage.query_all_stores(query, 5)
                
                if results:
                    print(f"\nFound {len(results)} results for '{query}' across all stores:")
                    for i, item in enumerate(results):
                        print(f"\n{i+1}. {item['name']} - {item['price']} ({item['store']})")
                        if "similarity" in item:
                            print(f"   Similarity: {item['similarity']}")
                        if "description" in item and item["description"]:
                            print(f"   {item['description']}")
                        print(f"   Category: {item['category']}")
                        if "unit" in item:
                            print(f"   Unit: {item['unit']}")
                        if "unit_price" in item and item["unit_price"] is not None:
                            if isinstance(item["unit_price"], (int, float)):
                                print(f"   Unit Price: ${item['unit_price']:.2f}")
                            else:
                                print(f"   Unit Price: {item['unit_price']}")
                else:
                    print(f"No results found for '{query}' across all stores.")
            except Exception as e:
                print(f"Error in cross-store query: {e}")
                import traceback
                traceback.print_exc()
    
    except Exception as e:
        print(f"Error initializing storage: {e}")
        import traceback
        traceback.print_exc()
        print("\nPlease check your configuration file and ensure the Chroma and Ollama servers are running.")

if __name__ == "__main__":
    main()