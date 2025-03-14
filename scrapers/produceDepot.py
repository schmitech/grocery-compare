import json
import requests
import os
import re
import sys
import warnings
from bs4 import BeautifulSoup
import chromadb
from chromadb.utils import embedding_functions
import uuid
from dotenv import load_dotenv

# Suppress tokenizer warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Suppress bitsandbytes warnings
warnings.filterwarnings("ignore", message="The installed version of bitsandbytes was compiled without GPU support")
warnings.filterwarnings("ignore", message="'NoneType' object has no attribute 'cadam32bit_grad_fp32'")

# Suppress huggingface_hub warnings about resume_download
warnings.filterwarnings("ignore", message="`resume_download` is deprecated and will be removed in version 1.0.0")

# Load environment variables from .env file in the project root
load_dotenv(dotenv_path="../.env")

# Add parent directory to path to allow importing from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    
    # Check for explicit unit price in the description (e.g., "$13.21/kg")
    unit_price_match = re.search(r'\$(\d+\.\d+|\d+)\/(?:kg|lb)', description_text)
    if unit_price_match:
        explicit_unit_price = float(unit_price_match.group(1))
        
        # Extract the unit from the match
        unit_match = re.search(r'\/(\w+)', unit_price_match.group(0))
        if unit_match:
            explicit_unit = unit_match.group(1).lower()
            
            # If the price is per lb but the unit price is per kg (or vice versa), we need to convert
            if unit == 'lb' and explicit_unit == 'kg':
                # Convert the price from per lb to per kg
                unit_price = explicit_unit_price
                unit = 'kg'
            elif unit == 'kg' and explicit_unit == 'lb':
                # Convert the price from per kg to per lb
                unit_price = explicit_unit_price
                unit = 'lb'
            else:
                # Units match, just use the explicit unit price
                unit_price = explicit_unit_price
    
    # For multi-packs, try to extract the count and calculate per-item price
    pack_match = re.search(r'(\d+)\s*(?:pack|pk|bundle)', description_text, re.IGNORECASE)
    if pack_match and unit in ['pack', 'bundle']:
        count = int(pack_match.group(1))
        if count > 0:
            unit_price = numeric_price / count
            
    return price, unit, unit_price

def extract_produce_depot_specials():
    """
    Extract weekly specials from Produce Depot website.
    
    Returns:
        dict: Standardized grocery data
    """
    url = "https://producedepot.ca/weekly-specials/specials-list/"
    store_name = "Produce Depot"
    
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
    
    # Extract the date
    date_element = soup.select_one(".specialsdate")
    if date_element:
        structured_data["date"] = date_element.text.strip()
    
    # Find all category headers (h2) and their corresponding product lists
    h2_elements = soup.find_all('h2')
    
    for h2 in h2_elements:
        category_name = h2.text.strip()
        category = {"name": category_name, "products": []}
        
        # Find the product list that follows this h2
        product_list = h2.find_next('ul', class_='productlist')
        if product_list:
            # Extract all products in this list
            for li in product_list.find_all('li'):
                product = {}
                
                title_div = li.find('div', class_='itemtitle')
                if title_div:
                    # Get the full text first
                    full_text = title_div.get_text().strip()
                    
                    # Extract description from span
                    span = title_div.find('span')
                    description = ""
                    if span:
                        description = span.get_text().strip()
                        # Remove the span text from the full text to get just the name
                        name = full_text.replace(description, '').strip()
                    else:
                        name = full_text
                    
                    product["name"] = name
                    if description:
                        product["description"] = description
                
                price_div = li.find('div', class_='itemprice')
                if price_div:
                    # Get the full price text including any additional information
                    full_price_text = price_div.get_text().strip()
                    
                    # Extract the main price from the bold tag
                    b_tag = price_div.find('b')
                    if b_tag:
                        price_text = b_tag.get_text().strip()
                        
                        # If there's additional text in the price div (like unit prices),
                        # add it to the description
                        additional_price_info = full_price_text.replace(price_text, '').strip()
                        if additional_price_info and "description" in product:
                            product["description"] += " " + additional_price_info
                        elif additional_price_info:
                            product["description"] = additional_price_info
                        
                        # Extract price, unit, and unit_price
                        price, unit, unit_price = extract_unit_and_price(
                            price_text, 
                            product.get("description", "")
                        )
                        
                        product["price"] = price
                        product["unit"] = unit
                        product["unit_price"] = unit_price
                
                # Try to extract image URL if available
                img = li.find('img')
                if img and img.has_attr('src'):
                    product["image_url"] = img['src']
                
                if product:
                    category["products"].append(product)
        
        structured_data["categories"].append(category)
    
    # Save the structured data to a file
    output_file = "produce_depot_specials.json"
    with open(output_file, "w", encoding='utf-8') as f:
        json.dump(structured_data, f, indent=2)
    
    print(f"Data extracted and saved to {output_file}")
    print(f"Found {sum(len(cat['products']) for cat in structured_data['categories'])} products in {len(structured_data['categories'])} categories")
    
    return structured_data

def store_in_chroma(data):
    # Initialize Chroma client
    client = chromadb.PersistentClient(path="./grocery_deals_db")
    
    # Use sentence-transformers for embeddings (local model, no API key needed)
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"  # Lightweight model good for semantic search
    )
    
    # Delete the collection if it exists to reset it
    try:
        client.delete_collection(name="produce_depot_deals")
        print("Existing collection deleted.")
    except Exception as e:
        # Collection might not exist yet, which is fine
        print(f"Note: {e}")
    
    # Create a new collection
    collection = client.create_collection(
        name="produce_depot_deals",
        embedding_function=embedding_function,
        metadata={"date": data["date"]}
    )
    
    print(f"Created new collection with date: {data['date']}")
    
    # Prepare documents, metadatas, and IDs for batch addition
    documents = []
    metadatas = []
    ids = []
    
    # Process each product in each category
    for category in data["categories"]:
        category_name = category["name"]
        
        for product in category["products"]:
            # Create a searchable document text
            doc_text = f"{product['name']}"
            if "description" in product:
                doc_text += f" - {product['description']}"
            
            # Create metadata
            metadata = {
                "category": category_name,
                "price": product.get("price", ""),
                "name": product["name"],
                "description": product.get("description", ""),
                "date": data["date"],
                "unit": product.get("unit", "each"),
                "unit_price": product.get("unit_price", None)
            }
            
            # Generate a unique ID
            doc_id = str(uuid.uuid4())
            
            documents.append(doc_text)
            metadatas.append(metadata)
            ids.append(doc_id)
    
    # Add documents to the collection
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    
    print(f"Added {len(documents)} products to Chroma DB")
    return collection

def main():
    """Main function to run the scraper."""
    # Extract data
    data = extract_produce_depot_specials()
    
    if data:  # Add check in case extraction failed
        # Import the storage module here to avoid circular imports
        from scrapers.storage import GroceryDataStorage
        
        # Initialize storage and store the data
        storage = GroceryDataStorage()
        collection = storage.store_grocery_data(data, "Produce Depot")
        
        # Test a simple query
        results = storage.query_store("Produce Depot", "fresh vegetables", 3)
        
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
