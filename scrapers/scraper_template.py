import json
import requests
import os
import re
import sys
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables from .env file in the project root
load_dotenv(dotenv_path=".env")

def extract_unit_and_price(price_text, description_text=""):
    """
    Extract unit and calculate unit price from price text.
    
    Args:
        price_text: The price text (e.g., "$2.99/lb", "$5.99 each")
        description_text: Additional description text that might contain unit info
        
    Returns:
        tuple: (price, unit, unit_price)
    """
    # Remove the dollar sign and any spaces
    price_text = price_text.strip()
    
    # Default values
    unit = "each"  # Default unit if none specified
    unit_price = None
    
    # Extract the numeric price
    price_match = re.search(r'\$?(\d+\.\d+|\d+)', price_text)
    if not price_match:
        return price_text, unit, unit_price
    
    price = price_match.group(0)
    numeric_price = float(price.replace('$', ''))
    
    # Check for common units in the price text
    unit_patterns = {
        r'\/lb': 'lb',
        r'\/kg': 'kg',
        r'\/100g': '100g',
        r'\/each': 'each',
        r'each': 'each',
        r'\/pack': 'pack',
        r'\/bundle': 'bundle'
    }
    
    # Look for units in price text
    for pattern, unit_value in unit_patterns.items():
        if re.search(pattern, price_text, re.IGNORECASE):
            unit = unit_value
            break
    
    # If no unit found in price text, check description
    if unit == "each" and description_text:
        for pattern, unit_value in unit_patterns.items():
            if re.search(pattern, description_text, re.IGNORECASE):
                unit = unit_value
                break
    
    # Calculate unit price based on the unit
    unit_price = numeric_price
    
    # For multi-packs, try to extract the count and calculate per-item price
    pack_match = re.search(r'(\d+)\s*(?:pack|pk|bundle)', description_text, re.IGNORECASE)
    if pack_match and unit in ['pack', 'bundle']:
        count = int(pack_match.group(1))
        if count > 0:
            unit_price = numeric_price / count
            
    return price, unit, unit_price

def extract_store_specials():
    """
    Extract weekly specials from [STORE NAME] website.
    
    Returns:
        dict: Standardized grocery data
    """
    url = "https://example.com/weekly-specials"  # Replace with actual URL
    store_name = "Store Name"  # Replace with actual store name
    
    # Create a structured data object with the standardized schema
    structured_data = {
        "store": store_name,
        "date": "",
        "categories": []
    }
    
    # Fetch the webpage content using requests
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error: Failed to fetch the webpage. Status code: {response.status_code}")
        return None
        
    html_content = response.text
    
    # Parse the HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract the date (modify this based on the website structure)
    date_element = soup.select_one(".date-selector")  # Replace with actual selector
    if date_element:
        structured_data["date"] = date_element.text.strip()
    
    # Find all categories and products (modify this based on the website structure)
    # This is just a template - you'll need to adapt it to the specific HTML structure
    category_elements = soup.find_all('div', class_='category')  # Replace with actual selector
    
    for category_element in category_elements:
        category_name = category_element.find('h2').text.strip()  # Replace with actual selector
        category = {"name": category_name, "products": []}
        
        # Find all products in this category
        product_elements = category_element.find_all('div', class_='product')  # Replace with actual selector
        
        for product_element in product_elements:
            product = {}
            
            # Extract product name
            name_element = product_element.find('div', class_='product-name')  # Replace with actual selector
            if name_element:
                product["name"] = name_element.text.strip()
            
            # Extract product description
            desc_element = product_element.find('div', class_='product-desc')  # Replace with actual selector
            if desc_element:
                product["description"] = desc_element.text.strip()
            
            # Extract product price
            price_element = product_element.find('div', class_='product-price')  # Replace with actual selector
            if price_element:
                price_text = price_element.text.strip()
                
                # Extract price, unit, and unit_price
                price, unit, unit_price = extract_unit_and_price(
                    price_text, 
                    product.get("description", "")
                )
                
                product["price"] = price
                product["unit"] = unit
                product["unit_price"] = unit_price
            
            # Extract product image
            img_element = product_element.find('img')  # Replace with actual selector
            if img_element and img_element.has_attr('src'):
                product["image_url"] = img_element['src']
            
            if product and "name" in product and "price" in product:
                category["products"].append(product)
        
        if category["products"]:
            structured_data["categories"].append(category)
    
    # Save the structured data to a file
    output_file = f"{store_name.lower().replace(' ', '_')}_specials.json"
    with open(output_file, "w", encoding='utf-8') as f:
        json.dump(structured_data, f, indent=2)
    
    print(f"Data extracted and saved to {output_file}")
    print(f"Found {sum(len(cat['products']) for cat in structured_data['categories'])} products in {len(structured_data['categories'])} categories")
    
    return structured_data

def main():
    """Main function to run the scraper."""
    # Extract data
    data = extract_store_specials()
    
    if data:  # Add check in case extraction failed
        # Import the storage module here to avoid circular imports
        from storage import GroceryDataStorage
        
        # Initialize storage and store the data
        storage = GroceryDataStorage()
        collection = storage.store_grocery_data(data, data["store"])
        
        # Test a simple query
        results = storage.query_store(data["store"], "fresh vegetables", 3)
        
        if results:
            print("\nSample Query Results for 'fresh vegetables':")
            for i, (doc, metadata) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
                print(f"{i+1}. {metadata['name']} - {metadata['price']}")
                if "description" in metadata and metadata["description"]:
                    print(f"   {metadata['description']}")
                print(f"   Category: {metadata['category']}")
                if "unit" in metadata:
                    print(f"   Unit: {metadata['unit']}")
                if "unit_price" in metadata:
                    print(f"   Unit Price: ${metadata['unit_price']:.2f}")
                print()
        
        print("\nData extraction and storage complete!")
        print("You can now use the GroceryDataStorage class to search and query the data.")

if __name__ == "__main__":
    main() 