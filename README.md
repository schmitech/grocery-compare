# Grocery Deals Chatbot

A simple AI chatbot to compare and price-match weekly specials from multiple grocery stores.

## Components

1. **Scrapers**
   - **grocery_specials.py** - Generic scraper for processing store specials from JSON files
   - **storage.py** - Common storage module for all scrapers

2. **Search and Interface**
   - **grocery_search.py** - Provides search functionality, price comparison, and AI integration
   - **grocery_chatbot.py** - Streamlit web interface for the chatbot
   - **grocery_api.py** - FastAPI backend for the chatbot

3. **Utility Scripts**
   - **test_chroma_collections.py** - Tests if data was successfully loaded into ChromaDB

## Setup

1. Set environment
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your OpenAI API key in a `.env` file (copy from .env.example)
   ```bash
   OPENAI_API_KEY=your_api_key_here
   ```

## Usage

### Load data into Chroma DB
```bash
python grocery_specials.py "True North Grocers" ./weekly-specials/true-north-grocers.json
```

### Verify Data Loading

To verify that the data was successfully loaded into the database:
```bash
python test_chroma_collections.py "organic milk"
```

This will show sample results from each store collection.

### Start chat service

```bash
uvicorn grocery_api:app --host 0.0.0.0 --port 8000 --reload
```

### Run streamlit chatbot app

```bash
streamlit run grocery_chatbot.py
```

This will open a web browser with the chatbot interface where you can ask questions about the current deals across all stores.

You can also try the  CLI version:
```
python grocery_search.py
```

## Example Questions

- What fruits are on sale?
- Are there any deals on vegetables under $2?
- What's the best deal in the meat section?
- Do they have any organic produce on sale?
- Which store has the better price on apples?
- Compare prices for chicken between SunnySide Foods and Metro Market.
- What's on sale in the bakery section at SunnySide Foods?

## Adding a New Store

To add a new grocery store, you have two options:

```bash
python grocery_specials.py "Store Name" path/to/specials.json

#Example
python grocery_specials.py "True North Grocers" ./weekly-specials/true-north-grocers.json
```

Ensure it follows the standardized data format:
   ```python
   {
       "store": "Store Name",
       "date": "Date Range",
       "categories": [
           {
               "name": "Category Name",
               "products": [
                   {
                       "name": "Product Name",
                       "description": "Product Description",
                       "price": "$Price",
                       "unit": "Unit Type",
                       "unit_price": UnitPrice
                   }
               ]
           }
       ]
   }
   ```

## Technical Details

- The data is stored in a ChromaDB vector database with separate collections for each store
- Semantic search is used to find relevant deals
- Google or OpenAI's API generates natural language responses and analyzes price comparisons
- Streamlit provides the web interface

## License
Apache 2.0 (LICENSE file)