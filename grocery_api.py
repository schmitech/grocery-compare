from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
import sys
import traceback
from fastapi.responses import PlainTextResponse

# Import your existing functionality
from grocery_search import (
    create_grocery_search_interface, 
    process_query as process_search_query,
    compare_prices,
    get_openai_response
)
import chromadb

# Define data models
class SearchRequest(BaseModel):
    query: str
    ai_provider: Optional[str] = "auto"
    selected_stores: Optional[List[str]] = []

class ComparisonRequest(BaseModel):
    item: str
    ai_provider: Optional[str] = "auto"

class ChatResponse(BaseModel):
    response: str
    results: List[Dict[Any, Any]] = []

class StoreResponse(BaseModel):
    stores: List[str]

# Add a new response model for text-only responses
class TextResponse(BaseModel):
    response: str

# Define a simple text-only response model
class TextOnlyResponse(BaseModel):
    text: str

# Initialize FastAPI app
app = FastAPI(
    title="Grocery Comparison API",
    description="API for comparing grocery deals across multiple stores",
    version="1.0.0"
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Get absolute path to the database
current_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(current_dir, "grocery_deals_db")
print(f"Using database path: {DB_PATH}")

# Initialize search interface at startup
search_interface = None

@app.on_event("startup")
async def startup_event():
    global search_interface
    try:
        # Add the current directory to the path to ensure imports work
        if current_dir not in sys.path:
            sys.path.append(current_dir)
            
        # Check if the database directory exists
        if not os.path.exists(DB_PATH):
            print(f"WARNING: Database directory does not exist: {DB_PATH}")
            os.makedirs(DB_PATH, exist_ok=True)
            print(f"Created database directory: {DB_PATH}")
        
        # List collections to verify database connection
        client = chromadb.PersistentClient(path=DB_PATH)
        collections = client.list_collections()
        print(f"Found {len(collections)} collections in database")
        for collection_name in collections:
            print(f"  - Collection: {collection_name}")
        
        # Create the search interface using the existing function but with our path
        from scrapers.storage import GroceryDataStorage
        
        # Initialize the storage with the absolute path
        storage = GroceryDataStorage(db_path=DB_PATH)
        
        # Create a search function that uses our storage
        def custom_search_deals(query, n=10, store=None):
            print(f"Searching for: '{query}' in store: {store}")
            try:
                if store:
                    # Search in a specific store
                    results = storage.query_store(store, query, n)
                    if results and results["documents"] and results["documents"][0]:
                        print(f"Store search returned: {len(results['documents'][0])} results")
                        
                        # Convert to the same format as query_all_stores
                        items = []
                        for i, (doc, metadata) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
                            item = {
                                "name": metadata["name"],
                                "price": metadata["price"],
                                "category": metadata["category"],
                                "store": store,
                                "date": metadata.get("date", "Unknown")
                            }
                            
                            if "description" in metadata and metadata["description"]:
                                item["description"] = metadata["description"]
                            
                            if "unit" in metadata:
                                item["unit"] = metadata["unit"]
                            
                            if "unit_price" in metadata:
                                item["unit_price"] = metadata["unit_price"]
                            
                            items.append(item)
                        
                        return items
                    else:
                        print("Store search returned no results")
                        return []
                else:
                    # Search across all stores
                    results = storage.query_all_stores(query, n)
                    print(f"All stores search returned: {len(results) if results else 0} results")
                    return results
                
            except Exception as e:
                print(f"Error in custom_search_deals: {e}")
                traceback.print_exc()
                return []
        
        search_interface = custom_search_deals
        print("Search interface initialized successfully")
    except Exception as e:
        print(f"Error initializing search interface: {e}")
        traceback.print_exc()
        # Create a dummy search function that returns an error message
        def dummy_search(query, n=10, store=None):
            print(f"Dummy search called with query: {query}")
            return []
        search_interface = dummy_search

# Define API endpoints
@app.post("/api/chat", response_model=TextOnlyResponse)
async def chat(request: SearchRequest):
    """
    Process a natural language query about grocery deals and return only the text response.
    """
    try:
        print(f"Processing chat request: {request.query}")
        
        # Extract category from query
        query = request.query.lower()
        category = None
        
        # Define category mappings
        category_mappings = {
            "fruit": ["fruit", "apple", "orange", "banana", "pear", "berry", "berries", "pineapple", "melon"],
            "vegetable": ["vegetable", "vegetables", "veggie", "veggies", "carrot", "potato", "tomato", "lettuce", "onion"],
            "meat": ["meat", "chicken", "beef", "pork", "steak", "ground", "turkey", "lamb"],
            "dairy": ["dairy", "milk", "cheese", "yogurt", "butter", "cream"],
            "bakery": ["bakery", "bread", "bun", "roll", "pastry", "cake"]
        }
        
        # Check if query contains category keywords
        for cat, keywords in category_mappings.items():
            if any(keyword in query for keyword in keywords):
                category = cat
                print(f"Detected category: {category}")
                break
        
        # Get search results
        results = search_interface(request.query)
        print(f"Search returned {len(results)} results")
        
        # Filter results by category if detected
        if category:
            filtered_results = []
            for item in results:
                item_name = item.get("name", "").lower()
                item_category = item.get("category", "").lower()
                item_description = item.get("description", "").lower()
                
                # Check if item matches the detected category
                if category == "fruit":
                    fruit_keywords = category_mappings["fruit"]
                    if (any(keyword in item_name for keyword in fruit_keywords) or 
                        "fruit" in item_category or 
                        any(keyword in item_description for keyword in fruit_keywords)):
                        filtered_results.append(item)
                
                elif category == "vegetable":
                    veg_keywords = category_mappings["vegetable"]
                    if (any(keyword in item_name for keyword in veg_keywords) or 
                        "vegetable" in item_category or 
                        "produce" in item_category or
                        any(keyword in item_description for keyword in veg_keywords)):
                        filtered_results.append(item)
                
                elif category == "meat":
                    meat_keywords = category_mappings["meat"]
                    if (any(keyword in item_name for keyword in meat_keywords) or 
                        "meat" in item_category or 
                        any(keyword in item_description for keyword in meat_keywords)):
                        filtered_results.append(item)
                
                elif category == "dairy":
                    dairy_keywords = category_mappings["dairy"]
                    if (any(keyword in item_name for keyword in dairy_keywords) or 
                        "dairy" in item_category or 
                        any(keyword in item_description for keyword in dairy_keywords)):
                        filtered_results.append(item)
                
                elif category == "bakery":
                    bakery_keywords = category_mappings["bakery"]
                    if (any(keyword in item_name for keyword in bakery_keywords) or 
                        "bakery" in item_category or 
                        any(keyword in item_description for keyword in bakery_keywords)):
                        filtered_results.append(item)
            
            if filtered_results:
                print(f"Filtered to {len(filtered_results)} {category} items")
                results = filtered_results
        
        # Filter results by selected stores if provided
        if request.selected_stores:
            results = [
                item for item in results 
                if item.get("store", "").lower() in [s.lower() for s in request.selected_stores]
            ]
            print(f"After filtering by stores: {len(results)} results")
        
        # Clean the data
        results = clean_product_data(results)
        
        # Get the AI provider
        from ai_providers import get_ai_provider
        provider = get_ai_provider(request.ai_provider)
        
        if not results:
            # Handle no results case
            response_text = f"""I couldn't find any specific deals for '{request.query}' in our database.

Here are some suggestions:
1. Try searching for a more general category like "vegetables", "fruit", "meat", or "dairy"
2. Check if the item is spelled correctly
3. The item might not be on sale at the moment in our tracked stores
4. Try searching for a similar item that might be available

Would you like information about other grocery deals instead?"""
        else:
            # Check if it's a comparison query
            comparison_keywords = ["compare", "comparison", "versus", "vs", "better price", "cheaper", "best deal", "better deal"]
            is_comparison = any(keyword in query for keyword in comparison_keywords)
            
            if is_comparison:
                # Create a structured prompt for price comparison
                prompt = f"""I want to compare prices for grocery items matching: "{request.query}"

Please analyze these results and provide a clear comparison of prices. Focus on:
1. Which store has the better deal for similar items
2. Consider unit prices ($/kg, $/lb) for accurate comparisons
3. Highlight any significant price differences
4. Recommend the best overall value

Format your response in a clear, easy-to-read way with headings and bullet points."""
            else:
                # Create a prompt for the AI based on the query and results
                prompt = f"""I'm looking for information about grocery deals matching: "{request.query}"

Please provide a helpful summary of these deals. Focus on:
1. Which stores have the best deals
2. Price comparisons between stores
3. Unit prices where available
4. Any special offers or discounts
5. Recommendations for the best value

Format your response in a clear, easy-to-read way with headings and bullet points."""
            
            # Get response from the AI provider using our results
            response_text = provider.get_response(prompt, results)
            
        # Return only the text response
        return TextOnlyResponse(text=response_text)
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.post("/api/compare", response_model=TextOnlyResponse)
async def compare(request: ComparisonRequest):
    """
    Compare prices for a specific item across different stores and return only the text response.
    """
    try:
        print(f"Processing compare request for item: {request.item}")
        
        # Get the search results for the item
        results = search_interface(request.item)
        print(f"Compare search returned {len(results)} results")
        
        # Filter results to only include items that match the requested item
        item_keywords = request.item.lower().split()
        filtered_results = []
        
        for item in results:
            item_name = item.get("name", "").lower()
            item_description = item.get("description", "").lower()
            
            # Check if the item name or description contains all the keywords
            if all(keyword in item_name or keyword in item_description for keyword in item_keywords):
                filtered_results.append(item)
        
        if filtered_results:
            print(f"Filtered to {len(filtered_results)} items matching '{request.item}'")
            results = filtered_results
        
        # Clean the data
        results = clean_product_data(results)
        
        # Get the AI provider
        from ai_providers import get_ai_provider
        provider = get_ai_provider(request.ai_provider)
        
        if not results:
            # Handle no results case
            response_text = f"""I couldn't find any specific deals for '{request.item}' in our database.

Here are some suggestions:
1. Try searching for a more general category like "vegetables", "fruit", "meat", or "dairy"
2. Check if the item is spelled correctly
3. The item might not be on sale at the moment in our tracked stores
4. Try searching for a similar item that might be available

Would you like information about other grocery deals instead?"""
        else:
            # Create a structured prompt for price comparison
            prompt = f"""I want to compare prices for "{request.item}" across different grocery stores.

Please analyze these results and provide a detailed price comparison. Focus on:
1. Which store has the best deal for this item
2. Compare unit prices ($/kg, $/lb) when available for accurate comparisons
3. Highlight any significant price differences between stores
4. Consider product quality or features if mentioned in the descriptions
5. Recommend the best overall value

Format your response in a clear, easy-to-read way with headings and bullet points.
Include a "Best Deal" section at the end with your recommendation."""
            
            # Get response from the AI provider using our results
            response_text = provider.get_response(prompt, results)
        
        # Return only the text response
        return TextOnlyResponse(text=response_text)
    except Exception as e:
        print(f"Error in compare endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error comparing prices: {str(e)}")

@app.get("/api/search", response_model=List[Dict[str, Any]])
async def search(
    query: str = Query(..., description="Search query"),
    store: Optional[str] = Query(None, description="Filter by store name")
):
    """
    Search for grocery deals matching the query
    """
    try:
        print(f"Processing search request: {query}, store: {store}")
        if store:
            results = search_interface(query, store=store)
        else:
            results = search_interface(query)
            
        print(f"Search returned {len(results)} results")
        
        # Clean the data before returning
        results = clean_product_data(results)
        
        return results
    except Exception as e:
        print(f"Error in search endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error searching: {str(e)}")

@app.get("/api/stores", response_model=StoreResponse)
async def get_stores():
    """
    Get a list of available stores
    """
    try:
        available_stores = []
        client = chromadb.PersistentClient(path=DB_PATH)
        
        # Get all collections - in ChromaDB v0.6.0, these are just strings
        collection_names = client.list_collections()
        
        # Extract store names from collections
        for name in collection_names:
            if isinstance(name, str) and name.endswith("_deals"):
                store_name = name.replace("_deals", "").replace("_", " ").title()
                available_stores.append(store_name)
                
        return StoreResponse(stores=available_stores)
    except Exception as e:
        print(f"Error in get_stores endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting stores: {str(e)}")

# Add a debug endpoint to check database status
@app.get("/api/debug")
async def debug_info():
    """
    Get debug information about the database and search functionality
    """
    try:
        info = {
            "database_path": DB_PATH,
            "database_exists": os.path.exists(DB_PATH),
            "current_directory": os.getcwd(),
            "script_directory": current_dir,
        }
        
        # Check database collections
        try:
            client = chromadb.PersistentClient(path=DB_PATH)
            collections = client.list_collections()
            info["collections"] = collections
            info["collection_count"] = len(collections)
            
            # Try to get collection counts
            for collection_name in collections:
                try:
                    collection = client.get_collection(collection_name)
                    count = collection.count()
                    info[f"{collection_name}_count"] = count
                except Exception as e:
                    info[f"{collection_name}_error"] = str(e)
        except Exception as e:
            info["database_error"] = str(e)
        
        # Try a simple search
        try:
            results = search_interface("fruit")
            info["test_search_results"] = len(results)
            if results:
                info["sample_result"] = results[0]
        except Exception as e:
            info["search_error"] = str(e)
            
        return info
    except Exception as e:
        return {"error": str(e)}

# Add this function to your code
def clean_product_data(results):
    """Clean product data to fix common typos and formatting issues."""
    cleaned_results = []
    
    # Common typo corrections
    typo_corrections = {
        "Boold": "Blood",
        "Lemos": "Lemons",
        "Honycrisp": "Honeycrisp",
        "Pineaple": "Pineapple",
        "Tomatoe": "Tomato",
        "Potatoe": "Potato",
        "Brocoli": "Broccoli",
        "Cauliflour": "Cauliflower"
    }
    
    for item in results:
        # Create a copy of the item to modify
        cleaned_item = item.copy()
        
        # Fix typos in name
        if "name" in cleaned_item:
            name = cleaned_item["name"]
            for typo, correction in typo_corrections.items():
                name = name.replace(typo, correction)
            cleaned_item["name"] = name
        
        # Fix typos in description
        if "description" in cleaned_item and cleaned_item["description"]:
            description = cleaned_item["description"]
            for typo, correction in typo_corrections.items():
                description = description.replace(typo, correction)
            cleaned_item["description"] = description
        
        # Fix price formatting
        if "price" in cleaned_item:
            price = cleaned_item["price"]
            # Make sure price has a dollar sign if it's just a number
            if price and price.isdigit():
                cleaned_item["price"] = f"${price}"
        
        # Fix unit price formatting
        if "unit_price" in cleaned_item and cleaned_item["unit_price"] is not None:
            # Make sure unit_price is a float
            try:
                unit_price = float(cleaned_item["unit_price"])
                cleaned_item["unit_price"] = unit_price
            except (ValueError, TypeError):
                # If conversion fails, leave it as is
                pass
        
        cleaned_results.append(cleaned_item)
    
    return cleaned_results

@app.post("/api/plaintext", response_class=PlainTextResponse)
async def plain_text_response(request: SearchRequest):
    """
    Process a query and return only the text response as plain text.
    """
    try:
        # ... same processing code as before ...
        
        # Return the text directly as plain text
        return response_text
    except Exception as e:
        print(f"Error in plain_text_response endpoint: {e}")
        traceback.print_exc()
        return f"Error processing query: {str(e)}"

# Run the API server
if __name__ == "__main__":
    uvicorn.run("grocery_api:app", host="0.0.0.0", port=8000, reload=True) 