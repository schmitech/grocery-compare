import os
import warnings
import re
from dotenv import load_dotenv
import json
from collections import defaultdict
from ai_providers import get_ai_provider, OPENAI_AVAILABLE, OPENAI_API_NOT_AVAILABLE_MSG, GOOGLE_AVAILABLE, OpenAIProvider, GoogleProvider

# Control debug printing
DEBUG_PRINT = False

# Print current working directory to see where we're loading from
if DEBUG_PRINT:
    print(f"Current working directory in grocery_search.py: {os.getcwd()}")

# Load environment variables from .env file with override=True to force reload
dotenv_path = os.path.join(os.getcwd(), ".env")
if os.path.exists(dotenv_path):
    if DEBUG_PRINT:
        print(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path, override=True)
else:
    print(f"Warning: .env file not found at {dotenv_path}")

# Print the loaded environment variables for debugging
if DEBUG_PRINT:
    print(f"grocery_search.py - OPENAI_API_KEY exists: {os.getenv('OPENAI_API_KEY') is not None}")
    if os.getenv('OPENAI_API_KEY'):
        print(f"grocery_search.py - OPENAI_API_KEY last 4 chars: ...{os.getenv('OPENAI_API_KEY')[-4:]}")
    print(f"grocery_search.py - GOOGLE_API_KEY exists: {os.getenv('GOOGLE_API_KEY') is not None}")
    if os.getenv('GOOGLE_API_KEY'):
        print(f"grocery_search.py - GOOGLE_API_KEY last 4 chars: ...{os.getenv('GOOGLE_API_KEY')[-4:]}")
    print(f"grocery_search.py - DEFAULT_AI_PROVIDER: {os.getenv('DEFAULT_AI_PROVIDER', 'not set')}")

# Suppress warnings
warnings.filterwarnings("ignore", message="The installed version of bitsandbytes was compiled without GPU support")
warnings.filterwarnings("ignore", message="'NoneType' object has no attribute 'cadam32bit_grad_fp32'")

# Default to auto provider selection (will try OpenAI first, then Google)
DEFAULT_AI_PROVIDER = os.getenv("DEFAULT_AI_PROVIDER", "auto")

# Print the actual provider being used
print(f"Using DEFAULT_AI_PROVIDER: {DEFAULT_AI_PROVIDER}")

def get_openai_response(prompt, search_results=None, ai_provider_name=None):
    """
    Get a response from the specified AI provider.
    
    Args:
        prompt: The prompt to send to the AI provider
        search_results: Optional search results to include in the prompt
        ai_provider_name: Optional name of the AI provider to use (defaults to DEFAULT_AI_PROVIDER)
        
    Returns:
        str: The response from the AI provider
    """
    # Use the specified AI provider or the default
    provider_name = ai_provider_name or DEFAULT_AI_PROVIDER
    print(f"Getting response using provider: {provider_name}")
    
    # Get the AI provider
    ai_provider = get_ai_provider(provider_name)
    
    # Print which provider was actually selected
    if isinstance(ai_provider, OpenAIProvider):
        print("Selected OpenAI provider")
    elif isinstance(ai_provider, GoogleProvider):
        print("Selected Google provider")
    else:
        print(f"Selected provider type: {type(ai_provider).__name__}")
    
    return ai_provider.get_response(prompt, search_results)

def format_results_for_prompt(results):
    """
    Format search results into a string suitable for AI prompts.
    
    Args:
        results: List of search result dictionaries
        
    Returns:
        str: Formatted string of search results
    """
    if not results:
        return "No results found."
    
    # Group results by store
    stores = {}
    for item in results:
        store_name = item.get('store', 'Unknown Store')
        if store_name not in stores:
            stores[store_name] = []
        stores[store_name].append(item)
    
    # Format the results
    formatted_text = ""
    
    # Add a summary
    total_items = len(results)
    total_stores = len(stores)
    formatted_text += f"Found {total_items} items from {total_stores} stores.\n\n"
    
    # Add structured data for easier parsing by AI models
    formatted_text += "## Structured Data\n"
    formatted_text += "```\n"
    formatted_text += "{\n"
    formatted_text += '  "stores": [\n'
    
    for i, (store_name, items) in enumerate(stores.items()):
        formatted_text += '    {\n'
        formatted_text += f'      "name": "{store_name}",\n'
        formatted_text += '      "items": [\n'
        
        for j, item in enumerate(items):
            formatted_text += '        {\n'
            formatted_text += f'          "name": "{item.get("name", "Unknown Item")}",\n'
            formatted_text += f'          "price": "{item.get("price", "N/A")}",\n'
            formatted_text += f'          "description": "{item.get("description", "").replace(chr(34), chr(39))}",\n'
            formatted_text += f'          "unit": "{item.get("unit", "N/A")}",\n'
            formatted_text += f'          "unit_price": "{item.get("unit_price", "N/A")}"\n'
            formatted_text += '        }' + (',' if j < len(items) - 1 else '') + '\n'
        
        formatted_text += '      ]\n'
        formatted_text += '    }' + (',' if i < len(stores) - 1 else '') + '\n'
    
    formatted_text += '  ]\n'
    formatted_text += '}\n'
    formatted_text += '```\n\n'
    
    # Add human-readable format
    formatted_text += "## Human-Readable Format\n\n"
    
    for store_name, items in stores.items():
        formatted_text += f"### {store_name}\n"
        
        for item in items:
            name = item.get('name', 'Unknown Item')
            price = item.get('price', 'N/A')
            description = item.get('description', '')
            unit = item.get('unit', 'N/A')
            unit_price = item.get('unit_price', 'N/A')
            
            formatted_text += f"- **{name}**: {price}"
            
            if unit_price != 'N/A':
                formatted_text += f" ({unit_price})"
            
            if description:
                formatted_text += f"\n  {description}"
            
            formatted_text += "\n"
        
        formatted_text += "\n"
    
    return formatted_text

def create_grocery_search_interface():
    """
    Create a function that searches for grocery deals.
    
    Returns:
        function: A function that takes a query and returns matching deals
    """
    # Import here to avoid circular imports
    try:
        import sys
        import os
        
        # Add the current directory to the path to ensure imports work
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.append(current_dir)
            
        from scrapers.storage import GroceryDataStorage
        
        # Initialize the storage with the correct path
        storage = GroceryDataStorage(db_path="./grocery_deals_db")
        
        # Create a search function
        def search_deals(query, n=10, store=None):
            """
            Search for grocery deals matching the query.
            
            Args:
                query: The search query
                n: Number of results to return per store
                store: Optional store name to limit search to a specific store
                
            Returns:
                list: List of matching deals
            """
            try:
                if store:
                    # Search in a specific store
                    results = storage.query_store(store, query, n)
                    if not results or not results["documents"] or not results["documents"][0]:
                        return []
                    
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
                    # Search across all stores
                    return storage.query_all_stores(query, n)
            except Exception as e:
                print(f"Error in search_deals: {e}")
                return []
        
        return search_deals
    except Exception as e:
        print(f"Error creating search interface: {e}")
        
        # Return a dummy search function if there's an error
        return dummy_search

def dummy_search(query, n=5, store=None):
    """
    Dummy search function that returns no results.
    Used as a fallback if the real search can't be initialized.
    
    Args:
        query: The search query
        n: Number of results to return
        store: Optional store name to limit search to a specific store
        
    Returns:
        list: Empty list
    """
    print(f"Dummy search called with query: {query}")
    return []

def compare_prices(search_interface, item, ai_provider_name=None):
    """
    Compare prices for a specific item across different stores.
    
    Args:
        search_interface: The search interface to use
        item: The item to search for
        ai_provider_name: Optional name of the AI provider to use
        
    Returns:
        str: A comparison of prices for the item
    """
    # Search for the item
    results = search_interface(item)
    
    # Get the AI provider
    provider = get_ai_provider(ai_provider_name or DEFAULT_AI_PROVIDER)
    
    if not results:
        # If no results found, try a more general search
        print(f"No results found for '{item}'. Trying a more general search...")
        
        # Try to extract a more general term
        general_terms = {
            "carrot": "vegetables",
            "apple": "fruit",
            "banana": "fruit",
            "orange": "fruit",
            "milk": "dairy",
            "cheese": "dairy",
            "chicken": "meat",
            "beef": "meat",
            "pork": "meat",
            "bread": "bakery"
        }
        
        general_term = general_terms.get(item.lower(), None)
        
        if general_term:
            print(f"Trying more general term: {general_term}")
            results = search_interface(general_term)
            
            if results:
                prompt = f"""I was looking for information about "{item}" but couldn't find any specific deals.
                
However, I found some deals in the general category of "{general_term}" that might be of interest.

Please provide a helpful summary of these deals, and mention that specific "{item}" deals weren't found.
Focus on:
1. Which stores have deals on {general_term}
2. Price comparisons between stores
3. Any special offers or discounts
4. Recommendations for the best value

Format your response in a clear, easy-to-read way with headings and bullet points."""
                
                return provider.get_response(prompt, results)
        
        # If still no results or no general term found, return a helpful message
        return f"""I couldn't find any specific deals for '{item}' in our database.

Here are some suggestions:
1. Try searching for a more general category like "vegetables", "fruit", "meat", or "dairy"
2. Check if the item is spelled correctly
3. The item might not be on sale at the moment in our tracked stores
4. Try searching for a similar item that might be available

Would you like information about other grocery deals instead?"""
    
    # Create a structured prompt for price comparison
    prompt = f"""I want to compare prices for "{item}" across different grocery stores.

## Analysis Instructions
Please analyze these results and provide a detailed price comparison. Focus on:

1. Which store has the best deal for this item
2. Compare unit prices ($/kg, $/lb) when available for accurate comparisons
3. Highlight any significant price differences between stores
4. Consider product quality or features if mentioned in the descriptions
5. Recommend the best overall value

Format your response in a clear, easy-to-read way with headings and bullet points.
Include a "Best Deal" section at the end with your recommendation.
"""
    
    # Get the response from the AI provider
    response = provider.get_response(prompt, results)
    
    # Remove any instruction text that might have been included in the response
    response_lines = response.split('\n')
    cleaned_lines = []
    skip_line = False
    
    for line in response_lines:
        if "Analysis Instructions" in line or "instructions" in line.lower():
            skip_line = True
        elif skip_line and line.strip() == "":
            skip_line = False
        elif not skip_line:
            cleaned_lines.append(line)
    
    cleaned_response = '\n'.join(cleaned_lines)
    
    return cleaned_response

def process_query(query, ai_provider_name=None):
    """
    Process a user query and return a response.
    
    Args:
        query: The user's query
        ai_provider_name: Optional name of the AI provider to use
        
    Returns:
        str: The response to the query
    """
    try:
        # Print the AI provider being used
        print(f"Processing query with AI provider: {ai_provider_name or DEFAULT_AI_PROVIDER}")
        
        # Create the search interface
        search_deals = create_grocery_search_interface()
        
        # Clean up the query
        clean_query = query.strip().rstrip('?').lower()
        
        # Check if it's a comparison query
        comparison_keywords = ["compare", "comparison", "versus", "vs", "better price", "cheaper", "best deal", "better deal"]
        is_comparison = any(keyword in clean_query for keyword in comparison_keywords)
        
        # Check if it's a store-specific query
        store_keywords = {
            "produce depot": "Produce Depot",
            "farm boy": "Farm Boy"
        }
        specific_store = None
        for keyword, store in store_keywords.items():
            if keyword in clean_query:
                specific_store = store
                break
        
        # Check if it's a query about a specific product
        # Common product categories
        product_categories = [
            "chicken", "beef", "pork", "meat", "fish", "seafood",
            "fruit", "apple", "orange", "banana", "berry", "berries",
            "vegetable", "broccoli", "carrot", "potato", "tomato",
            "dairy", "milk", "cheese", "yogurt", "egg",
            "bread", "bakery", "pastry"
        ]
        
        specific_product = None
        for category in product_categories:
            if category in clean_query:
                specific_product = category
                break
        
        # Use the specified AI provider or the default
        provider = get_ai_provider(ai_provider_name or DEFAULT_AI_PROVIDER)
        
        # Process the query
        if is_comparison and specific_product:
            # Comparison of a specific product
            print(f"Comparing prices for {specific_product}")
            return compare_prices(search_deals, specific_product, ai_provider_name=ai_provider_name)
        
        elif is_comparison:
            # Extract the item to compare
            # This is a simple approach - in a real system, you might use NLP to extract the item
            extracted_item = None
            for keyword in comparison_keywords:
                if keyword in clean_query:
                    parts = clean_query.split(keyword)
                    if len(parts) > 1:
                        extracted_item = parts[1].strip()
                        if not extracted_item:
                            extracted_item = parts[0].strip()
                        break
            
            if extracted_item:
                print(f"Comparing prices for extracted item: {extracted_item}")
                return compare_prices(search_deals, extracted_item, ai_provider_name=ai_provider_name)
            
            # If we can't extract a specific item, just search for the query
            print(f"Could not extract specific item from comparison query, searching for: {query}")
            results = search_deals(query)
            
            if not results:
                return handle_no_results(query, provider)
            
            # Create a more structured prompt for the AI
            prompt = f"""I want to compare prices for grocery items matching: "{query}"

Please analyze these results and provide a clear comparison of prices. Focus on:
1. Which store has the better deal for similar items
2. Consider unit prices ($/kg, $/lb) for accurate comparisons
3. Highlight any significant price differences
4. Recommend the best overall value

Format your response in a clear, easy-to-read way with headings and bullet points."""
            
            return provider.get_response(prompt, results)
        
        elif specific_store and specific_product:
            # Search for a specific product in a specific store
            print(f"Searching for {specific_product} at {specific_store}")
            results = search_deals(specific_product, store=specific_store)
            
            if not results:
                return f"I couldn't find any deals for {specific_product} at {specific_store}. Would you like to search for {specific_product} at other stores instead?"
            
            # Create a more structured prompt for the AI
            prompt = f"""Tell me about {specific_product} at {specific_store}.

Please provide a helpful summary of these deals. Focus on:
1. The best deals available
2. Any special offers or discounts
3. Unit prices where available
4. Any other relevant information for the shopper

Format your response in a clear, easy-to-read way."""
            
            return provider.get_response(prompt, results)
        
        elif specific_store:
            # Search in the specific store
            print(f"Searching in {specific_store} for: {query}")
            results = search_deals(query, store=specific_store)
            
            if not results:
                return f"I couldn't find any deals matching '{query}' at {specific_store}. Would you like to search for deals at other stores instead?"
            
            # Create a more structured prompt for the AI
            prompt = f"""I'm looking for information about grocery deals at {specific_store} matching: "{query}"

Please provide a helpful summary of these deals. Focus on:
1. The best deals available
2. Any special offers or discounts
3. Unit prices where available
4. Any other relevant information for the shopper

Format your response in a clear, easy-to-read way."""
            
            return provider.get_response(prompt, results)
        
        elif specific_product:
            # Search for a specific product across all stores
            print(f"Searching for {specific_product} across all stores")
            results = search_deals(specific_product)
            
            # If it's a "best deal" query, use the compare_prices function
            if "best" in clean_query or "cheapest" in clean_query or "deal" in clean_query:
                print(f"Finding best deals for {specific_product}")
                return compare_prices(search_deals, specific_product, ai_provider_name=ai_provider_name)
            else:
                if not results:
                    return handle_no_results(specific_product, provider)
                
                # Create a more structured prompt for the AI
                prompt = f"""I'm looking for information about {specific_product} deals across different stores.

Please provide a helpful summary of these deals. Focus on:
1. Which stores have the best deals
2. Price comparisons between stores
3. Unit prices where available
4. Any special offers or discounts
5. Recommendations for the best value

Format your response in a clear, easy-to-read way with headings and bullet points."""
                
                return provider.get_response(prompt, results)
        
        else:
            # General query across all stores
            print(f"General search for: {query}")
            results = search_deals(query)
            
            if not results:
                return handle_no_results(query, provider)
            
            # Create a more structured prompt for the AI
            prompt = f"""I'm looking for information about grocery deals matching: "{query}"

Please provide a helpful summary of these deals. Focus on:
1. Which stores have the best deals
2. Price comparisons between stores
3. Unit prices where available
4. Any special offers or discounts
5. Recommendations for the best value

Format your response in a clear, easy-to-read way with headings and bullet points."""
            
            return provider.get_response(prompt, results)
    except Exception as e:
        # Handle any errors gracefully
        error_message = f"Sorry, I encountered an error while processing your query: {str(e)}"
        print(f"Error in process_query: {e}")
        return error_message

def handle_no_results(query, provider):
    """
    Handle the case when no results are found for a query.
    
    Args:
        query: The user's query
        provider: The AI provider to use
        
    Returns:
        str: A helpful message
    """
    # Try to suggest alternative searches
    alternative_terms = {
        "carrot": ["vegetables", "produce"],
        "apple": ["fruit", "produce"],
        "banana": ["fruit", "produce"],
        "orange": ["fruit", "produce"],
        "milk": ["dairy"],
        "cheese": ["dairy"],
        "chicken": ["meat", "poultry"],
        "beef": ["meat"],
        "pork": ["meat"],
        "bread": ["bakery"]
    }
    
    # Check if we have alternative terms for this query
    for term, alternatives in alternative_terms.items():
        if term in query.lower():
            alternatives_str = ", ".join([f"'{alt}'" for alt in alternatives])
            return f"""I couldn't find any specific deals for '{query}' in our database.

Here are some suggestions:
1. Try searching for more general categories like {alternatives_str}
2. Check if the item is spelled correctly
3. The item might not be on sale at the moment in our tracked stores
4. Try searching for a similar item that might be available

Would you like information about other grocery deals instead?"""
    
    # Generic message if no specific alternatives
    return f"""I couldn't find any deals matching '{query}' in our database.

Here are some suggestions:
1. Try searching for a more general category like "vegetables", "fruit", "meat", or "dairy"
2. Check if the item is spelled correctly
3. Try searching for a similar item that might be available
4. You can also try searching for deals at a specific store like "Farm Boy" or "Produce Depot"

Would you like information about other grocery deals instead?"""

if __name__ == "__main__":
    # Interactive command-line interface
    print("Grocery Deals Search")
    print("Type 'exit' to quit")
    print()
    
    while True:
        query = input("What would you like to know about grocery deals? ")
        if query.lower() in ['exit', 'quit', 'q']:
            break
        
        response = process_query(query)
        print("\n" + response + "\n") 