import os
import warnings
import uuid
import chromadb
from chromadb.utils import embedding_functions

# Suppress tokenizer warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Suppress bitsandbytes warnings
warnings.filterwarnings("ignore", message="The installed version of bitsandbytes was compiled without GPU support")
warnings.filterwarnings("ignore", message="'NoneType' object has no attribute 'cadam32bit_grad_fp32'")

# Suppress huggingface_hub warnings about resume_download
warnings.filterwarnings("ignore", message="`resume_download` is deprecated and will be removed in version 1.0.0")

class GroceryDataStorage:
    def __init__(self, db_path="./grocery_deals_db"):
        """Initialize the storage with the path to the ChromaDB database."""
        self.db_path = db_path
        self.client = chromadb.PersistentClient(path=db_path)
        
        # Use sentence-transformers for embeddings (local model, no API key needed)
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"  # Lightweight model good for semantic search
        )
    
    def _get_collection_name(self, store_name):
        """
        Get the standardized collection name for a store.
        
        Args:
            store_name: Name of the grocery store
            
        Returns:
            str: Standardized collection name
        """
        # Clean store name and ensure consistent format
        store_name = store_name.strip()
        return f"{store_name.lower().replace(' ', '_')}_deals"
    
    def store_grocery_data(self, data, store_name):
        """
        Store grocery data in ChromaDB.
        
        Args:
            data: The standardized grocery data dictionary
            store_name: Name of the grocery store
        
        Returns:
            The ChromaDB collection
        """
        # Get standardized collection name
        collection_name = self._get_collection_name(store_name)
        
        # Delete the collection if it exists to reset it
        try:
            self.client.delete_collection(name=collection_name)
            print(f"Existing collection for {store_name} deleted.")
        except Exception as e:
            # Collection might not exist yet, which is fine
            print(f"Note: {e}")
        
        # Create a new collection
        collection = self.client.create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"store": store_name, "date": data["date"]}
        )
        
        print(f"Created new collection for {store_name} with date: {data['date']}")
        
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
                    "store": store_name,
                    "category": category_name,
                    "price": product.get("price", ""),
                    "name": product["name"],
                    "description": product.get("description", ""),
                    "date": data["date"]
                }
                
                # Add unit and unit_price if available
                if "unit" in product:
                    metadata["unit"] = product["unit"]
                
                if "unit_price" in product:
                    metadata["unit_price"] = product["unit_price"]
                
                if "image_url" in product:
                    metadata["image_url"] = product["image_url"]
                
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
        
        print(f"Added {len(documents)} products from {store_name} to Chroma DB")
        return collection
    
    def query_store(self, store_name, query_text, n_results=5):
        """
        Query a specific store's collection.
        
        Args:
            store_name: Name of the grocery store
            query_text: The search query
            n_results: Number of results to return
            
        Returns:
            Query results
        """
        collection_name = self._get_collection_name(store_name)
        
        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            return results
        except Exception as e:
            print(f"Error querying {store_name}: {e}")
            return None
    
    def query_all_stores(self, query_text, n_results=5):
        """
        Query all store collections.
        
        Args:
            query_text: The search query
            n_results: Number of results to return per store
            
        Returns:
            Combined results from all stores
        """
        all_items = []
        
        try:
            # Get all collection names
            collection_names = self.client.list_collections()
            print(f"Debug - Collection names: {collection_names}")
            
            # Filter for only deal collections
            deal_collections = [name for name in collection_names if isinstance(name, str) and name.endswith("_deals")]
            print(f"Debug - Deal collections: {deal_collections}")
            
            for collection_name in deal_collections:
                try:
                    # Extract store name from collection name
                    store_name = collection_name.replace("_deals", "").replace("_", " ").title()
                    
                    # Query this store
                    results = self.query_store(store_name, query_text, n_results)
                    
                    if results and results["documents"] and results["documents"][0]:
                        # Convert to a list of items
                        for i, (doc, metadata) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
                            item = {
                                "name": metadata["name"],
                                "price": metadata["price"],
                                "category": metadata["category"],
                                "store": store_name,
                                "date": metadata.get("date", "Unknown")
                            }
                            
                            if "description" in metadata and metadata["description"]:
                                item["description"] = metadata["description"]
                            
                            if "unit" in metadata:
                                item["unit"] = metadata["unit"]
                            
                            if "unit_price" in metadata:
                                item["unit_price"] = metadata["unit_price"]
                            
                            all_items.append(item)
                except Exception as e:
                    print(f"Error querying {collection_name}: {e}")
                    continue
        except Exception as e:
            print(f"Error in query_all_stores: {e}")
        
        return all_items 