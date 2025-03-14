# Grocery Deals Chatbot

This project scrapes weekly deals from multiple grocery stores (currently Produce Depot and Farm Boy), stores them in a vector database, and provides a chatbot interface to query and compare deals across stores.

## Components

1. **Scrapers**
   - **scrapers/produceDepot.py** - Scrapes the Produce Depot website
   - **scrapers/farmboy.py** - Loads Farm Boy deals from a JSON file
   - **scrapers/storage.py** - Common storage module for all scrapers

2. **Search and Interface**
   - **grocery_search.py** - Provides search functionality, price comparison, and OpenAI integration
   - **grocery_chatbot.py** - Streamlit web interface for the chatbot

3. **Utility Scripts**
   - **run_all_scrapers.py** - Runs all available scrapers to populate the database
   - **test_chroma_collections.py** - Tests if data was successfully loaded into ChromaDB

## Setup

1. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

2. Set up your OpenAI API key in a `.env` file in the parent directory:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

## Usage

### Step 1: Extract and Store Data

Run the data collection script to fetch and store deals from all supported grocery stores:

```
python run_all_scrapers.py
```

This only needs to be done once per week when the deals are updated.

### Step 2: Verify Data Loading (Optional)

To verify that the data was successfully loaded into the database:

```
python test_chroma_collections.py
```

This will show sample results from each store collection.

### Step 3: Run the Chatbot

Launch the Streamlit chatbot interface:

```
streamlit run grocery_chatbot.py
```

This will open a web browser with the chatbot interface where you can ask questions about the current deals across all stores.

### Alternative: Command Line Interface

If you prefer a command-line interface, you can use:

```
python grocery_search.py
```

This interactive CLI allows you to ask questions about deals and compare prices between stores.

## Example Questions

- What fruits are on sale?
- Are there any deals on vegetables under $2?
- What's the best deal in the meat section?
- Do they have any organic produce on sale?
- Which store has the better price on apples?
- Compare prices for chicken between Farm Boy and Produce Depot.
- What's on sale in the bakery section at Farm Boy?

## Price Comparison Features

The system can automatically detect comparison queries and provide detailed price comparisons between stores:

1. **Automatic Detection**: Queries containing words like "compare", "vs", "better price", or "cheaper" trigger the comparison mode.

2. **Store-Specific Queries**: You can ask about deals at a specific store by mentioning the store name in your query.

3. **Unit Price Analysis**: When comparing similar items, the system considers unit prices for more accurate comparisons.

4. **AI-Powered Analysis**: The system uses OpenAI to analyze price differences and provide insights about the best deals.

## Adding a New Store

To add a new grocery store:

1. Create a new scraper in the `scrapers` directory (use `farmboy.py` as a template)
2. Ensure it follows the standardized data format
3. Add the store to the list in `run_all_scrapers.py`
4. Add the store name to the `store_keywords` dictionary in `grocery_search.py`

## Technical Details

- The data is stored in a ChromaDB vector database with separate collections for each store
- Semantic search is used to find relevant deals
- OpenAI's API generates natural language responses and analyzes price comparisons
- Streamlit provides the web interface
- The system is designed to be modular for easy addition of new stores 