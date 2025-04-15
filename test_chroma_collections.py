#!/usr/bin/env python3
"""
Test script to verify that grocery data was successfully loaded into ChromaDB collections.
This script queries each store collection and displays sample results.

Note: You must run the scrapers first to populate the database:
- python grocery_specials.py "Metro Market" ./weekly-specials/metromarket.json
- python grocery_specials.py "SunnySide Foods" ./weekly-specials/sunnyside.json
"""

import os
import sys
import json
from pprint import pprint

# Import the storage module
from storage import GroceryDataStorage

def get_collection_name(store_name):
    """Convert store name to collection name format."""
    return f"{store_name.lower().replace(' ', '_')}_deals"

def test_collection(storage, store_name, query="fresh", num_results=3):
    """
    Test a specific store collection by running a query and displaying results.
    
    Args:
        storage: GroceryDataStorage instance
        store_name: Name of the store to query
        query: Search query to use
        num_results: Number of results to display
    
    Returns:
        bool: True if the collection exists and returns results, False otherwise
    """
    print(f"\n{'='*50}")
    print(f"Testing collection for: {store_name}")
    print(f"Collection name: {get_collection_name(store_name)}")
    print(f"{'='*50}")
    
    try:
        results = storage.query_store(store_name, query, num_results)
        
        if not results or not results["documents"] or not results["documents"][0]:
            print(f"No results found for '{query}' in {store_name} collection.")
            return False
        
        print(f"Found {len(results['documents'][0])} results for '{query}':")
        
        for i, (doc, metadata) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
            print(f"\n{i+1}. {metadata['name']} - {metadata['price']}")
            if "description" in metadata and metadata["description"]:
                print(f"   {metadata['description']}")
            print(f"   Category: {metadata['category']}")
            if "unit" in metadata:
                print(f"   Unit: {metadata['unit']}")
            if "unit_price" in metadata and metadata["unit_price"] is not None:
                print(f"   Unit Price: ${metadata['unit_price']:.2f}")
        
        return True
    
    except Exception as e:
        print(f"Error querying {store_name} collection: {e}")
        return False

def list_all_collections(storage):
    """
    List all available collections in ChromaDB.
    
    Args:
        storage: GroceryDataStorage instance
    """
    try:
        # In ChromaDB v0.6.0, list_collections only returns collection names
        collection_names = storage.client.list_collections()
        
        print("\nAvailable collections in ChromaDB:")
        if not collection_names:
            print("No collections found. Please run the scrapers first to populate the database.")
            print("Run: python grocery_specials.py \"Metro Market\" ./weekly-specials/metromarket.json")
            print("Run: python grocery_specials.py \"SunnySide Foods\" ./weekly-specials/sunnyside.json")
            return
            
        for i, name in enumerate(collection_names):
            print(f"{i+1}. {name}")
        print()
    except Exception as e:
        print(f"Error listing collections: {e}")
        print("If you're seeing API compatibility errors, make sure you're using the correct version of ChromaDB.")

def main():
    """Main function to test ChromaDB collections."""
    print("=" * 70)
    print("GROCERY DEALS DATABASE TEST")
    print("=" * 70)
    print("This script tests if data has been successfully loaded into ChromaDB.")
    print("If no collections are found, please run the scrapers first:")
    print("  python grocery_specials.py \"Metro Market\" ./weekly-specials/metromarket.json")
    print("  python grocery_specials.py \"SunnySide Foods\" ./weekly-specials/sunnyside.json")
    print("=" * 70)
    
    # Initialize storage
    storage = GroceryDataStorage()
    
    # List all available collections
    list_all_collections(storage)
    
    # Define stores to test
    stores = ["Metro Market", "SunnySide Foods", "Maple Leaf Market", "True North Grocers", "Fresh Value Market"]
    
    # Test each store collection
    successful_stores = []
    for store in stores:
        if test_collection(storage, store):
            successful_stores.append(store)
    
    # Summary
    print("\n" + "="*50)
    print("Test Summary")
    print("="*50)
    print(f"Successfully tested {len(successful_stores)} out of {len(stores)} store collections.")
    if successful_stores:
        print("Successful stores:")
        for store in successful_stores:
            print(f"- {store}")
    else:
        print("\nNo store collections were successfully tested.")
        print("Please make sure you've run the scrapers to populate the database:")
        print("  python grocery_specials.py \"Metro Market\" ./weekly-specials/metromarket.json")
        print("  python grocery_specials.py \"SunnySide Foods\" ./weekly-specials/sunnyside.json")
    
    # Test a multi-store query
    if len(successful_stores) > 1:
        print("\n" + "="*50)
        print("Testing Multi-Store Query")
        print("="*50)
        
        try:
            query = "apples"
            results = storage.query_all_stores(query, 2)
            
            if results:
                print(f"\nResults for '{query}' across all stores:")
                for i, item in enumerate(results):
                    print(f"\n{i+1}. {item['name']} - {item['price']} ({item['store']})")
                    if "description" in item and item["description"]:
                        print(f"   {item['description']}")
                    print(f"   Category: {item['category']}")
                    if "unit" in item:
                        print(f"   Unit: {item['unit']}")
                    if "unit_price" in item and item["unit_price"] is not None:
                        print(f"   Unit Price: ${item['unit_price']:.2f}")
            else:
                print(f"No results found for '{query}' across all stores.")
        except Exception as e:
            print(f"Error in multi-store query: {e}")

if __name__ == "__main__":
    main() 