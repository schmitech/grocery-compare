import json
import os
import re
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file in the project root
load_dotenv(dotenv_path=".env")

def extract_unit_and_price(price_text, price_tag="", description_text=""):
    """
    Extract unit and calculate unit price from price text.
    
    Args:
        price_text: The price text (e.g., "2.99")
        price_tag: The unit tag (e.g., "lb", "ea")
        description_text: Additional description text that might contain unit info
        
    Returns:
        tuple: (price, unit, unit_price)
    """
    # Default values
    unit = "each"  # Default unit if none specified
    unit_price = None
    
    # Format price with dollar sign
    price = f"${price_text}"
    
    try:
        numeric_price = float(price_text)
    except (ValueError, TypeError):
        return price, unit, unit_price
    
    # Map price_tag to standardized unit
    unit_mapping = {
        "ea": "each",
        "lb": "lb",
        "kg": "kg",
        "100g": "100g",
        "pkg": "pack",
        "Bag": "bag",
        "dozen": "dozen"
    }
    
    # Set unit based on price_tag
    if price_tag in unit_mapping:
        unit = unit_mapping[price_tag]
    
    # Calculate unit price based on the unit
    unit_price = numeric_price
    
    # For multi-packs, try to extract the count and calculate per-item price
    pack_match = re.search(r'(\d+)\s*(?:pack|pk|bundle)', description_text, re.IGNORECASE)
    if pack_match and unit in ['pack', 'bundle']:
        count = int(pack_match.group(1))
        if count > 0:
            unit_price = numeric_price / count
            
    return price, unit, unit_price

def extract_specials(store_name, json_file_path):
    """
    Extract weekly specials from a store's JSON file.
    
    Args:
        store_name: Name of the store
        json_file_path: Path to the JSON file containing the specials
        
    Returns:
        dict: Standardized grocery data
    """
    # Clean store name to prevent double underscores
    store_name = store_name.strip()
    
    # Check if the file exists
    if not os.path.exists(json_file_path):
        print(f"Error: File {json_file_path} not found.")
        return None
    
    # Load the JSON data
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON data: {e}")
        return None
    
    # Get the date range from the data
    # Use the first item's validfrom and validto dates
    if raw_data and len(raw_data) > 0:
        try:
            from_date = datetime.fromisoformat(raw_data[0]["validfrom"]).strftime("%b %d")
            to_date = datetime.fromisoformat(raw_data[0]["validto"]).strftime("%b %d, %Y")
            date_range = f"{from_date} - {to_date}"
        except (ValueError, KeyError):
            date_range = "Current Flyer"
    else:
        date_range = "Current Flyer"
    
    structured_data = {
        "store": store_name,
        "date": date_range,
        "categories": []
    }
    
    # Group products by department
    departments = {}
    
    # Filter to only include "Flyer Version 1" items to avoid duplicates
    filtered_data = [item for item in raw_data if item.get("version") == "Flyer Version 1"]
    
    for item in filtered_data:
        department = item.get("department", "Other")
        if department not in departments:
            departments[department] = []
        departments[department].append(item)
    
    # Convert departments to categories
    for department, products in departments.items():
        category = {"name": department, "products": []}
        
        for product in products:
            # Extract product details
            name = product.get("name", "")
            brand = product.get("brand", "")
            sub_text = product.get("sub_text", "")
            size = product.get("size", "")
            per_text = product.get("per_text", "")
            price_text = product.get("price", "")
            price_tag = product.get("price_tag", "")
            location = product.get("location", "")
            
            # Build description
            description_parts = []
            if brand:
                description_parts.append(brand)
            if sub_text:
                description_parts.append(sub_text)
            if size:
                description_parts.append(size)
            if per_text:
                description_parts.append(per_text)
            if location:
                description_parts.append(f"Origin: {location}")
            
            description = ", ".join(filter(None, description_parts))
            
            # Extract price, unit, and unit_price
            price, unit, unit_price = extract_unit_and_price(
                price_text, 
                price_tag,
                description
            )
            
            # Create product object
            product_obj = {
                "name": name,
                "description": description,
                "price": price,
                "unit": unit,
                "unit_price": unit_price
            }
            
            # Add to category
            category["products"].append(product_obj)
        
        # Only add categories with products
        if category["products"]:
            structured_data["categories"].append(category)
    
    # Save the structured data to a file
    # output_file = f"{store_name.lower().replace(' ', '_')}_specials_processed.json"
    # with open(output_file, "w", encoding='utf-8') as f:
    #     json.dump(structured_data, f, indent=2)
    
    # print(f"Data extracted and saved to {output_file}")
    print(f"Found {sum(len(cat['products']) for cat in structured_data['categories'])} products in {len(structured_data['categories'])} categories")
    
    return structured_data

def main():
    """Main function to run the scraper."""
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Extract and process grocery store specials from JSON files.')
    parser.add_argument('store_name', help='Name of the store (e.g., "Metro Market")')
    parser.add_argument('json_file', help='Path to the JSON file containing the specials')
    args = parser.parse_args()
    
    # Clean store name to prevent double underscores
    store_name = args.store_name.strip()
    
    # Extract data
    data = extract_specials(store_name, args.json_file)
    
    if data:  # Add check in case extraction failed
        # Import the storage module
        from storage import GroceryDataStorage
        
        # Initialize storage and store the data
        storage = GroceryDataStorage()
        collection = storage.store_grocery_data(data, store_name)
        
        # Test a simple query
        results = storage.query_store(store_name, "fresh vegetables", 3)
        
        if results:
            print(f"\nSample Query Results for 'fresh vegetables' at {store_name}:")
            for i, (doc, metadata) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
                print(f"{i+1}. {metadata['name']} - {metadata['price']}")
                if "description" in metadata and metadata["description"]:
                    print(f"   {metadata['description']}")
                print(f"   Category: {metadata['category']}")
                if "unit" in metadata:
                    print(f"   Unit: {metadata['unit']}")
                if "unit_price" in metadata and metadata["unit_price"] is not None:
                    print(f"   Unit Price: ${metadata['unit_price']:.2f}")
                print()
        
        print("\nData extraction and storage complete!")
        print("You can now use the GroceryDataStorage class to search and query the data.")

if __name__ == "__main__":
    main() 