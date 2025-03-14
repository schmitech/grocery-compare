import streamlit as st
import os
import warnings
import json
import re
import requests
import pandas as pd
import altair as alt
import chromadb

# Set page configuration
st.set_page_config(
    page_title="Grocery Deals Comparison",
    page_icon="🛒",
    layout="wide"
)

# Custom CSS for better appearance and JavaScript for auto-focus
st.markdown("""
<style>
    .main {
        background-color: #f5f5f5;
    }
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: row;
        align-items: flex-start;
    }
    .chat-message.user {
        background-color: #e6f7ff;
    }
    .chat-message.assistant {
        background-color: #f0f0f0;
    }
    .chat-message .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        object-fit: cover;
        margin-right: 1rem;
    }
    .chat-message .message {
        flex-grow: 1;
    }
    /* Make the input field more prominent */
    [data-testid="stFormTextInput"] input {
        border: 2px solid #4CAF50 !important;
        padding: 10px !important;
        font-size: 16px !important;
    }
    /* Style for store badges */
    .store-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
        margin-right: 5px;
        color: white;
    }
    /* Store-specific colors */
    .store-badge.produce-depot {
        background-color: #4CAF50;
    }
    .store-badge.farm-boy {
        background-color: #2196F3;
    }
    .store-badge.loblaws {
        background-color: #F44336;
    }
    .store-badge.metro {
        background-color: #FF9800;
    }
    .store-badge.food-basics {
        background-color: #9C27B0;
    }
    .store-badge.walmart {
        background-color: #3F51B5;
    }
    .store-badge.other {
        background-color: #607D8B;
    }
    /* Comparison table styling */
    .comparison-table {
        width: 100%;
        border-collapse: collapse;
    }
    .comparison-table th, .comparison-table td {
        padding: 8px;
        text-align: left;
        border-bottom: 1px solid #ddd;
    }
    .comparison-table th {
        background-color: #f2f2f2;
    }
    .comparison-table tr:hover {
        background-color: #f5f5f5;
    }
    .best-price {
        font-weight: bold;
        color: #4CAF50;
    }
    /* AI provider badges */
    .ai-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
        margin-right: 5px;
        color: white;
    }
    .ai-badge.openai {
        background-color: #10a37f;
    }
    .ai-badge.google {
        background-color: #4285F4;
    }
    .ai-badge.auto {
        background-color: #9E9E9E;
    }
</style>

<script>
    // More aggressive approach to focus the input field
    function focusInputField() {
        // Try different selectors to find the input field
        const selectors = [
            'input[data-testid="stFormTextInput"]',
            'input[type="text"]',
            '.stTextInput input',
            'form input'
        ];
        
        for (const selector of selectors) {
            const inputs = document.querySelectorAll(selector);
            for (const input of inputs) {
                try {
                    input.focus();
                    input.click();
                    console.log("Focus applied to:", selector);
                    return true;
                } catch (e) {
                    console.error("Error focusing:", e);
                }
            }
        }
        return false;
    }

    // Run focus attempts with increasing delays
    const delays = [100, 300, 500, 1000, 2000, 3000];
    for (const delay of delays) {
        setTimeout(() => {
            console.log(`Attempting focus after ${delay}ms`);
            focusInputField();
        }, delay);
    }
    
    // Also try on various events
    window.addEventListener('load', () => {
        console.log("Window loaded");
        focusInputField();
    });
    
    document.addEventListener('DOMContentLoaded', () => {
        console.log("DOM content loaded");
        focusInputField();
    });
    
    // Continuously attempt to focus for the first 10 seconds
    let startTime = Date.now();
    const focusInterval = setInterval(() => {
        if (Date.now() - startTime > 10000) {
            clearInterval(focusInterval);
            return;
        }
        focusInputField();
    }, 500);
</script>
""", unsafe_allow_html=True)

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize a flag to track if we need to clear the input
if "should_clear" not in st.session_state:
    st.session_state.should_clear = False

# Initialize selected stores in session state
if "selected_stores" not in st.session_state:
    st.session_state.selected_stores = []

# Initialize AI provider in session state
if "ai_provider" not in st.session_state:
    st.session_state.ai_provider = "auto"

# API configuration
API_BASE_URL = "http://localhost:8000"  # Change this to your API server address

def get_store_badge(store_name):
    """Generate HTML for a store badge with appropriate styling."""
    store_class = store_name.lower().replace(' ', '-')
    return f'<span class="store-badge {store_class}">{store_name}</span>'

def get_ai_badge(provider_name):
    """Generate HTML for an AI provider badge with appropriate styling."""
    provider_class = provider_name.lower()
    return f'<span class="ai-badge {provider_class}">{provider_name.upper()}</span>'

def display_chat_message(role, content, avatar, ai_provider=None):
    """Display a chat message with the given role and content."""
    with st.container():
        col1, col2 = st.columns([1, 9])
        with col1:
            st.image(avatar, width=50)
        with col2:
            if role == "Assistant" and ai_provider:
                st.markdown(f"**{role}** {get_ai_badge(ai_provider)}", unsafe_allow_html=True)
            else:
                st.markdown(f"**{role}**")
            
            # Apply minimal formatting to the content
            if role == "Assistant":
                # Just ensure proper markdown spacing
                formatted_content = format_markdown(content)
            else:
                formatted_content = content
            
            # Use Streamlit's native markdown rendering
            st.markdown(formatted_content)
        st.markdown("---")

def get_available_stores():
    """Get a list of available stores from the API."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/stores")
        if response.status_code == 200:
            return response.json()["stores"]
        else:
            print(f"Error getting stores: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Error getting available stores: {e}")
        return []

def filter_results_by_stores(results, selected_stores):
    """Filter results by selected stores."""
    filtered_results = []
    
    for item in results:
        # Skip if store not selected
        if selected_stores:
            # Convert both to lowercase for case-insensitive comparison
            item_store = item["store"].lower()
            selected_store_matches = [s.lower() for s in selected_stores]
            if not any(item_store == s.lower() for s in selected_stores):
                continue
        
        filtered_results.append(item)
    
    return filtered_results

def group_similar_items(results):
    """Group similar items across different stores for comparison."""
    # This is a simple grouping based on exact name matches
    # In a real app, you might want to use fuzzy matching or NLP
    similar_items = {}
    
    for item in results:
        name = item["name"].lower()
        if name not in similar_items:
            similar_items[name] = []
        similar_items[name].append(item)
    
    # Only keep groups with items from multiple stores
    return {name: items for name, items in similar_items.items() if len(items) > 1}

def create_comparison_chart(similar_items):
    """Create a comparison chart for similar items across stores."""
    chart_data = []
    
    for name, items in similar_items.items():
        for item in items:
            try:
                price = float(item["price"].replace('$', '').strip())
                chart_data.append({
                    "Item": name,
                    "Store": item["store"],
                    "Price": price
                })
            except (ValueError, TypeError):
                # Skip items with unparseable prices
                pass
    
    if not chart_data:
        return None
    
    df = pd.DataFrame(chart_data)
    
    # Create a bar chart with Altair
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X('Store:N', title='Store'),
        y=alt.Y('Price:Q', title='Price ($)'),
        color=alt.Color('Store:N', legend=None),
        column=alt.Column('Item:N', title='Item')
    ).properties(
        width=100
    )
    
    return chart

def create_comparison_table_html(similar_items):
    """Create an HTML table for comparing similar items across stores."""
    html = '<table class="comparison-table">'
    html += '<tr><th>Item</th><th>Store</th><th>Price</th><th>Unit</th><th>Unit Price</th><th>Description</th></tr>'
    
    for name, items in similar_items.items():
        # Sort items by unit price if available, otherwise by price
        try:
            # First try to sort by unit price
            items_with_unit_price = [item for item in items if "unit_price" in item and item["unit_price"] is not None]
            if items_with_unit_price:
                items_with_unit_price.sort(key=lambda x: float(x["unit_price"]))
                items_without_unit_price = [item for item in items if "unit_price" not in item or item["unit_price"] is None]
                items = items_with_unit_price + items_without_unit_price
            else:
                # Fall back to sorting by price
                items.sort(key=lambda x: float(x["price"].replace('$', '').strip()))
        except (ValueError, TypeError):
            # If we can't sort, just use the original order
            pass
        
        # Flag for the first (best) price
        first_item = True
        
        for item in items:
            price_class = "best-price" if first_item else ""
            first_item = False
            
            html += f'<tr>'
            html += f'<td>{item["name"]}</td>'
            html += f'<td>{get_store_badge(item["store"])}</td>'
            html += f'<td class="{price_class}">{item["price"]}</td>'
            html += f'<td>{item.get("unit", "each")}</td>'
            
            if "unit_price" in item and item["unit_price"] is not None:
                html += f'<td class="{price_class}">${item["unit_price"]:.2f}/{item.get("unit", "each")}</td>'
            else:
                # Check if there's a unit price in the description
                unit_price_match = None
                if "description" in item and item["description"]:
                    unit_price_match = re.search(r'\$(\d+\.\d+|\d+)\/(?:kg|lb)', item["description"])
                
                if unit_price_match:
                    html += f'<td class="{price_class}">{unit_price_match.group(0)}</td>'
                else:
                    html += '<td>-</td>'
            
            # Add description, highlighting any unit prices
            if "description" in item and item["description"]:
                desc = item["description"]
                # Highlight unit prices in the description
                desc = highlight_unit_prices(desc)
                html += f'<td>{desc}</td>'
            else:
                html += '<td>-</td>'
            
            html += '</tr>'
    
    html += '</table>'
    return html

def process_query(query):
    """Process a user query and generate a response using the API."""
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": query})
    
    try:
        # Call the API to process the query
        payload = {
            "query": query,
            "ai_provider": st.session_state.ai_provider,
            "selected_stores": st.session_state.selected_stores
        }
        
        # Determine if it's a comparison query
        comparison_keywords = ["compare", "comparison", "versus", "vs", "better price", "cheaper", "best deal", "better deal"]
        is_comparison = any(keyword in query.lower() for keyword in comparison_keywords)
        
        if is_comparison:
            # Use the compare endpoint
            response = requests.post(f"{API_BASE_URL}/api/compare", json=payload)
        else:
            # Use the chat endpoint
            response = requests.post(f"{API_BASE_URL}/api/chat", json=payload)
        
        if response.status_code == 200:
            # Extract the text response
            response_data = response.json()
            response_text = response_data.get("text", "")
            
            # Get search results for visualization
            search_response = requests.get(
                f"{API_BASE_URL}/api/search",
                params={"query": query}
            )
            
            if search_response.status_code == 200:
                results = search_response.json()
                
                # Filter results by selected stores
                if st.session_state.selected_stores:
                    results = filter_results_by_stores(results, st.session_state.selected_stores)
            else:
                print(f"Error getting search results: {search_response.status_code}")
                results = []
        else:
            print(f"Error from API: {response.status_code} - {response.text}")
            response_text = f"Sorry, I encountered an error while processing your query. Status code: {response.status_code}"
            results = []
    except Exception as e:
        # Handle any errors gracefully
        print(f"Error in process_query: {e}")
        response_text = f"Sorry, I encountered an error while processing your query: {str(e)}"
        results = []
    
    # Add assistant response to chat history
    st.session_state.messages.append({
        "role": "assistant", 
        "content": response_text, 
        "results": results,
        "ai_provider": st.session_state.ai_provider
    })
    
    # Set the flag to clear the input on next render
    st.session_state.should_clear = True
    
    return response_text, results

def highlight_unit_prices(text):
    """Highlight unit prices in text for better visibility."""
    # We'll use pure markdown for this now
    return text

def format_markdown(text):
    """
    Format markdown text to improve readability in Streamlit.
    
    This function ensures proper markdown formatting without using HTML.
    """
    if not text:
        return text
    
    # Clean up any HTML tags that might be in the text
    text = re.sub(r'<[^>]*>', '', text)
    
    # Fix spacing issues around prices and units
    # Add space between price and unit (e.g., "$0.99each" -> "$0.99 each")
    text = re.sub(r'(\$\d+\.\d+)([a-zA-Z])', r'\1 \2', text)
    
    # Add space between number and unit (e.g., "2kg" -> "2 kg")
    text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
    
    # Fix spacing around store names
    for store in ["Farm Boy", "Produce Depot", "Loblaws", "Metro", "Food Basics", "Walmart"]:
        # Fix cases like "atFarm Boy" -> "at Farm Boy"
        text = re.sub(f'([a-z])({store})', f'\\1 {store}', text)
        # Fix cases like "Farm Boyhas" -> "Farm Boy has"
        text = re.sub(f'({store})([a-z])', f'{store} \\2', text)
    
    # Ensure proper spacing after headings
    text = re.sub(r'(#{1,6}.*?)(\n)(?!\n)', r'\1\n\n', text)
    
    # Ensure proper spacing for list items
    text = re.sub(r'(\n- .*?)(\n)(?![\n-])', r'\1\n\n', text)
    
    # Ensure proper spacing after paragraphs
    text = re.sub(r'(\n\n)(\n+)', r'\n\n', text)
    
    return text

def main():
    # Header
    st.title("🛒 Grocery Deals Comparison")
    st.markdown("""
    Ask me about current deals at various grocery stores! I can help you find the best prices on fruits, vegetables, 
    meat, and more. Try asking questions like:
    - What fruits are on sale?
    - Where can I find the cheapest vegetables?
    - Which store has the best deals on meat?
    - Compare chicken prices between stores
    """)
    
    # Sidebar with filters and information
    with st.sidebar:
        st.header("Filters")
        
        # Get available stores from API
        available_stores = get_available_stores()
        
        # Store selection
        st.session_state.selected_stores = st.multiselect(
            "Select stores to include:",
            options=available_stores,
            default=st.session_state.selected_stores if st.session_state.selected_stores else available_stores
        )
        
        # AI provider selection
        ai_options = ["openai", "google", "auto"]  # We don't know what's available on the server
        
        # Get the current default provider
        default_provider = os.getenv("DEFAULT_AI_PROVIDER", "auto")
        
        # Initialize AI provider in session state if not already set
        if "ai_provider" not in st.session_state:
            st.session_state.ai_provider = default_provider
        
        # Allow user to override the default provider
        st.session_state.ai_provider = st.selectbox(
            "Select AI provider:",
            options=ai_options,
            index=ai_options.index(st.session_state.ai_provider) if st.session_state.ai_provider in ai_options else ai_options.index("auto")
        )
        
        st.header("About")
        st.markdown("""
        This chatbot compares grocery deals across multiple stores.
        
        The data is scraped from each store's weekly specials and stored in a vector database (ChromaDB) for semantic search.
        
        Responses are generated using either OpenAI's GPT-4 model or Google's Gemini model.
        """)
    
    # Display chat history
    for message in st.session_state.messages:
        if message["role"] == "user":
            display_chat_message("You", message["content"], "https://api.dicebear.com/7.x/personas/svg?seed=user")
        else:
            display_chat_message(
                "Assistant", 
                message["content"], 
                "https://api.dicebear.com/7.x/bottts/svg?seed=assistant",
                message.get("ai_provider", "auto")
            )
            
            # If this message has results and contains similar items, show comparison
            if "results" in message and len(message["results"]) > 0:
                similar_items = group_similar_items(message["results"])
                if similar_items:
                    st.subheader("Price Comparison")
                    
                    # Display comparison table
                    st.markdown(create_comparison_table_html(similar_items), unsafe_allow_html=True)
                    
                    # Display comparison chart
                    chart = create_comparison_chart(similar_items)
                    if chart:
                        st.altair_chart(chart, use_container_width=True)
    
    # Add a key to force re-rendering of the form
    form_key = f"query_form_{len(st.session_state.messages)}"
    
    # Wrap the input in a form to handle Enter key submission
    with st.form(key=form_key, clear_on_submit=True):
        # If should_clear is True, use an empty string as the default value
        default_value = "" if st.session_state.should_clear else st.session_state.get("user_query", "")
        
        # Use autofocus=True to try to focus the input field
        user_query = st.text_input(
            "Ask about grocery deals...", 
            value=default_value, 
            key="user_query",
            # This is the key - use autofocus attribute
            help="Press Enter to submit your question",
            # Add a placeholder to make it more obvious
            placeholder="Type your question here...",
            # Add label visibility to make it cleaner
            label_visibility="visible",
            # Add a max chars to prevent very long queries
            max_chars=200
        )
        
        # Hidden submit button that will be triggered by Enter key
        submit_button = st.form_submit_button("Submit", type="primary")
        
        # Reset the should_clear flag after rendering the input
        if st.session_state.should_clear:
            st.session_state.should_clear = False
    
    # Add JavaScript to focus the input field right after the form is rendered
    st.markdown("""
    <script>
        // Immediate focus attempt
        (function() {
            setTimeout(function() {
                const inputs = document.querySelectorAll('input[type="text"]');
                if (inputs.length > 0) {
                    for (let i = 0; i < inputs.length; i++) {
                        try {
                            inputs[i].focus();
                            inputs[i].click();
                            console.log("Focus applied to input", i);
                        } catch (e) {
                            console.error("Error focusing input", i, e);
                        }
                    }
                } else {
                    console.log("No text inputs found");
                }
            }, 100);
        })();
    </script>
    """, unsafe_allow_html=True)
    
    # Process the query if submitted
    if submit_button and user_query:
        # Process the query
        process_query(user_query)
        # Rerun to update the UI
        st.rerun()
    
    # Example query buttons (outside the form)
    st.markdown("### Try these examples:")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("What fruits are on sale?"):
            process_query("What fruits are on sale?")
            st.rerun()
    with col2:
        if st.button("Where are the cheapest vegetables?"):
            process_query("Where can I find the cheapest vegetables?")
            st.rerun()
    with col3:
        if st.button("Best meat deals?"):
            process_query("Which store has the best deals on meat?")
            st.rerun()
    with col4:
        if st.button("Compare chicken prices"):
            process_query("Compare chicken prices between stores")
            st.rerun()

if __name__ == "__main__":
    main() 