import os
import warnings
import uuid
import yaml
import chromadb
from langchain_ollama import OllamaEmbeddings

# Suppress tokenizer warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Suppress warnings
warnings.filterwarnings("ignore", message="The installed version of bitsandbytes was compiled without GPU support")
warnings.filterwarnings("ignore", message="'NoneType' object has no attribute 'cadam32bit_grad_fp32'")
warnings.filterwarnings("ignore", message="`resume_download` is deprecated and will be removed in version 1.0.0")

class GroceryDataStorage:
    def __init__(self, config_path="config.yaml"):
        """
        Initialize the storage with connection to a remote Chroma server.
        
        Args:
            config_path: Path to the configuration file
        """
        # Load configuration
        self.config = self.load_config(config_path)
        
        # Initialize Chroma client with HTTP connection to remote server
        self.chroma_host = self.config['chroma']['host']
        self.chroma_port = int(self.config['chroma']['port'])
        self.client = chromadb.HttpClient(host=self.chroma_host, port=self.chroma_port)
        print(f"Connected to Chroma server at {self.chroma_host}:{self.chroma_port}")
        
        # Initialize Ollama embeddings
        self.ollama_base_url = self.config['ollama']['base_url']
        self.model = self.config['ollama']['embed_model']
        
        if not self.model:
            raise ValueError("Embedding model is not specified in the configuration file.")
        
        self.embeddings = OllamaEmbeddings(
            model=self.model,
            base_url=self.ollama_base_url,
            client_kwargs={"timeout": 60.0}  # Increased timeout for larger embeddings
        )
        
        # Verify Ollama connection and get embedding dimensions
        try:
            test_embedding = self.embeddings.embed_query("test connection")
            self.embedding_dim = len(test_embedding)
            print("Successfully connected to Ollama server")
            print(f"Embedding dimensions: {self.embedding_dim}")
        except Exception as e:
            print(f"Failed to connect to Ollama server at {self.ollama_base_url}")
            print(f"Error: {str(e)}")
            raise
            
        # Collection name for all grocery deals
        self.collection_name = "grocery-deals"
    
    def load_config(self, config_path):
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            dict: Configuration dictionary
        """
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except Exception as e:
            print(f"Error loading configuration from {config_path}: {str(e)}")
            # Provide default configuration
            return {
                "ollama": {
                    "base_url": "http://localhost:11434",
                    "embed_model": "nomic-embed-text"
                },
                "chroma": {
                    "host": "localhost", 
                    "port": "8000"
                }
            }
    
    def get_or_create_collection(self, recreate=False):
        """
        Get the grocery deals collection or create it if it doesn't exist.
        
        Args:
            recreate: If True, delete and recreate the collection
            
        Returns:
            ChromaDB collection
        """
        try:
            # Check if collection exists
            collections = self.client.list_collections()
            collection_names = [c.name for c in collections]
            
            # If recreate=True or embedding dimension issues, delete existing collection
            if recreate and self.collection_name in collection_names:
                self.client.delete_collection(self.collection_name)
                print(f"Deleted existing collection: {self.collection_name}")
                collection_exists = False
            else:
                collection_exists = self.collection_name in collection_names
            
            if collection_exists:
                # Try to get the collection
                try:
                    collection = self.client.get_collection(name=self.collection_name)
                    print(f"Using existing collection: {self.collection_name}")
                    return collection
                except Exception as e:
                    # If there's an error (like dimension mismatch), recreate the collection
                    print(f"Error accessing collection: {e}")
                    print("Recreating collection due to compatibility issues...")
                    self.client.delete_collection(self.collection_name)
                    collection_exists = False
            
            if not collection_exists:
                # Create a new collection with cosine similarity
                collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={
                        "hnsw:space": "cosine",
                        "description": "Unified grocery deals collection",
                        "embedding_dim": self.embedding_dim,
                        "embedding_model": self.model
                    }
                )
                print(f"Created new collection: {self.collection_name}")
                return collection
            
        except Exception as e:
            print(f"Error in get_or_create_collection: {e}")
            # As a last resort, try to create a new collection
            print("Attempting to create new collection as fallback...")
            collection = self.client.create_collection(
                name=self.collection_name,
                metadata={
                    "hnsw:space": "cosine",
                    "description": "Unified grocery deals collection",
                    "embedding_dim": self.embedding_dim,
                    "embedding_model": self.model
                }
            )
            return collection
            
    def delete_store_records(self, collection, store_name):
        """
        Delete all records for a specific store.
        
        Args:
            collection: ChromaDB collection
            store_name: Name of the store
            
        Returns:
            int: Number of records deleted
        """
        deleted_count = 0
        
        try:
            # Get all IDs for the store
            print(f"Searching for existing records from {store_name}...")
            
            try:
                # Try using a direct get with where filter
                store_data = collection.get(
                    where={"store": store_name},
                    include=["metadatas", "documents"]
                )
                
                if store_data and 'ids' in store_data and store_data['ids']:
                    store_ids = store_data['ids']
                    if store_ids:
                        # Delete in batches to avoid overwhelming the server
                        batch_size = 100
                        for i in range(0, len(store_ids), batch_size):
                            batch_ids = store_ids[i:i+batch_size]
                            collection.delete(ids=batch_ids)
                        
                        deleted_count = len(store_ids)
                        print(f"Deleted {deleted_count} existing records for {store_name}")
                
            except Exception as e:
                print(f"Direct deletion failed: {str(e)}")
                print("Trying alternate approach...")
                
                # Fallback: Get all records and filter manually
                try:
                    all_data = collection.get(include=["metadatas", "documents"])
                    
                    if all_data and 'ids' in all_data and all_data['ids']:
                        store_ids = []
                        
                        # Find all IDs belonging to the store
                        for i, metadata in enumerate(all_data['metadatas']):
                            if metadata.get('store') == store_name:
                                store_ids.append(all_data['ids'][i])
                        
                        if store_ids:
                            # Delete in batches to avoid overwhelming the server
                            batch_size = 100
                            for i in range(0, len(store_ids), batch_size):
                                batch_ids = store_ids[i:i+batch_size]
                                collection.delete(ids=batch_ids)
                            
                            deleted_count = len(store_ids)
                            print(f"Deleted {deleted_count} existing records for {store_name}")
                
                except Exception as e2:
                    print(f"Alternate deletion approach also failed: {str(e2)}")
                    
                    # Last resort: check if IDs follow a predictable pattern
                    try:
                        print("Attempting pattern-based deletion...")
                        prefix = f"product_{store_name.lower().replace(' ', '_')}_"
                        
                        # Get all IDs
                        all_ids = collection.get(include=[])['ids']
                        store_ids = [id for id in all_ids if id.startswith(prefix)]
                        
                        if store_ids:
                            # Delete in batches
                            batch_size = 100
                            for i in range(0, len(store_ids), batch_size):
                                batch_ids = store_ids[i:i+batch_size]
                                collection.delete(ids=batch_ids)
                            
                            deleted_count = len(store_ids)
                            print(f"Deleted {deleted_count} existing records for {store_name}")
                    
                    except Exception as e3:
                        print(f"Pattern-based deletion also failed: {str(e3)}")
        
        except Exception as e:
            print(f"Error deleting records for {store_name}: {e}")
        
        return deleted_count
    
    def store_grocery_data(self, data, store_name):
        """
        Store grocery data in the unified Chroma collection.
        
        Args:
            data: The standardized grocery data dictionary
            store_name: Name of the grocery store
        
        Returns:
            The ChromaDB collection
        """
        # Get or create the collection - ensure it matches our current embedding model
        collection = self.get_or_create_collection(recreate=False)
        
        # Delete existing data for this store
        deleted_count = self.delete_store_records(collection, store_name)
        
        # If deletion completely failed and we want to ensure clean data, we can recreate
        if deleted_count == 0:
            try:
                # Use a different query approach to check if records exist
                query_results = self.query_store(store_name, "test", 1)
                if query_results and 'metadatas' in query_results and query_results['metadatas'] and query_results['metadatas'][0]:
                    # Records exist but couldn't be deleted, recreate collection as last resort
                    print("Warning: Store records exist but couldn't be deleted")
                    print("Consider manually recreating the collection if you encounter issues")
            except Exception:
                # Ignore errors in this check
                pass
        
        print(f"Adding data for {store_name} with date: {data['date']}")
        
        # Prepare data for batch processing
        batch_ids = []
        batch_embeddings = []
        batch_metadatas = []
        batch_documents = []
        batch_size = 50  # Process in batches of 50 to avoid overwhelming the server
        
        # Process each product in each category
        idx = 0
        for category in data["categories"]:
            category_name = category["name"]
            
            for product in category["products"]:
                # Create a searchable document text that includes store name
                doc_text = f"{store_name} {category_name} {product['name']}"
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
                
                try:
                    # Generate embedding
                    embedding = self.embeddings.embed_query(doc_text)
                    
                    # Generate a unique ID that includes store name
                    doc_id = f"product_{store_name.lower().replace(' ', '_')}_{idx}"
                    idx += 1
                    
                    batch_ids.append(doc_id)
                    batch_embeddings.append(embedding)
                    batch_metadatas.append(metadata)
                    batch_documents.append(doc_text)
                    
                    # Process in batches to avoid overwhelming the server
                    if len(batch_ids) >= batch_size:
                        self._add_batch_to_collection(
                            collection, 
                            batch_ids, 
                            batch_embeddings, 
                            batch_metadatas, 
                            batch_documents
                        )
                        # Reset batches
                        batch_ids = []
                        batch_embeddings = []
                        batch_metadatas = []
                        batch_documents = []
                        
                except Exception as e:
                    print(f"Error processing product {product['name']}: {str(e)}")
                    continue
        
        # Add any remaining items
        if batch_ids:
            self._add_batch_to_collection(
                collection, 
                batch_ids, 
                batch_embeddings, 
                batch_metadatas, 
                batch_documents
            )
        
        print(f"Added {idx} products from {store_name} to Chroma DB")
        return collection
    
    def _add_batch_to_collection(self, collection, ids, embeddings, metadatas, documents):
        """Helper method to add a batch of items to a collection."""
        try:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
            print(f"Uploaded batch of {len(ids)} vectors")
        except Exception as e:
            print(f"Error uploading batch: {str(e)}")
            
            # Try smaller batches if the main batch fails
            if len(ids) > 10:
                print("Trying with smaller batches...")
                mid = len(ids) // 2
                self._add_batch_to_collection(collection, ids[:mid], embeddings[:mid], metadatas[:mid], documents[:mid])
                self._add_batch_to_collection(collection, ids[mid:], embeddings[mid:], metadatas[mid:], documents[mid:])
            else:
                # Try one by one as a last resort
                for i in range(len(ids)):
                    try:
                        collection.upsert(
                            ids=[ids[i]],
                            embeddings=[embeddings[i]],
                            metadatas=[metadatas[i]],
                            documents=[documents[i]]
                        )
                        print(f"Uploaded single vector {ids[i]}")
                    except Exception as e2:
                        print(f"Failed to upload {ids[i]}: {str(e2)}")
    
    def query_store(self, store_name, query_text, n_results=5):
        """
        Query products from a specific store.
        
        Args:
            store_name: Name of the grocery store
            query_text: The search query
            n_results: Number of results to return
            
        Returns:
            Query results
        """
        try:
            # Get the collection
            collection = self.get_or_create_collection()
            
            # Generate embedding for query - pass the raw query
            query_embedding = self.embeddings.embed_query(query_text)
            
            # Perform query using embeddings and where filter
            results = collection.query(
                query_embeddings=[query_embedding],
                where={"store": store_name},
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            return results
        except Exception as e:
            print(f"Error querying {store_name}: {e}")
            try:
                # Alternative query approach - use without the where filter
                print(f"Trying alternative query approach for {store_name}...")
                query_embedding = self.embeddings.embed_query(query_text)
                
                # Use the API without the where filter
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results * 3,  # Get more results since we'll filter afterward
                    include=["documents", "metadatas", "distances"]
                )
                
                # Filter results manually
                if results and 'metadatas' in results and results['metadatas'] and results['metadatas'][0]:
                    filtered_metadatas = []
                    filtered_documents = []
                    filtered_distances = []
                    filtered_ids = []
                    
                    for i, metadata in enumerate(results['metadatas'][0]):
                        if metadata.get('store') == store_name:
                            filtered_metadatas.append(metadata)
                            filtered_documents.append(results['documents'][0][i])
                            filtered_distances.append(results['distances'][0][i])
                            filtered_ids.append(results['ids'][0][i] if 'ids' in results and results['ids'] and results['ids'][0] else f"result_{i}")
                            
                            # Stop once we have enough results
                            if len(filtered_metadatas) >= n_results:
                                break
                    
                    # Create a new results dictionary with only filtered items
                    filtered_results = {
                        'ids': [filtered_ids],
                        'metadatas': [filtered_metadatas],
                        'documents': [filtered_documents],
                        'distances': [filtered_distances]
                    }
                    
                    return filtered_results
                
                return results
            except Exception as e2:
                print(f"Alternative approach also failed: {str(e2)}")
                return None
    
    def query_all_stores(self, query_text, n_results=5):
        """
        Query products across all stores.
        
        Args:
            query_text: The search query
            n_results: Number of results to return
            
        Returns:
            Combined results from all stores
        """
        all_items = []
        
        try:
            # Get the collection
            collection = self.get_or_create_collection()
            
            # Generate embedding for query
            query_embedding = self.embeddings.embed_query(query_text)
            
            # Perform query using embeddings (no store filter)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results * 5,  # Get more results to account for multiple stores
                include=["documents", "metadatas", "distances"]
            )
            
            if results and 'metadatas' in results and results["metadatas"] and results["metadatas"][0]:
                # Convert to a list of items
                for i, metadata in enumerate(results["metadatas"][0]):
                    distance = results["distances"][0][i] if "distances" in results and results["distances"] and results["distances"][0] else 1.0
                    similarity = 1 - distance
                    
                    store_name = metadata.get("store", "Unknown Store")
                    
                    item = {
                        "name": metadata["name"],
                        "price": metadata["price"],
                        "category": metadata["category"],
                        "store": store_name,
                        "date": metadata.get("date", "Unknown"),
                        "similarity": f"{similarity:.4f}"
                    }
                    
                    if "description" in metadata and metadata["description"]:
                        item["description"] = metadata["description"]
                    
                    if "unit" in metadata:
                        item["unit"] = metadata["unit"]
                    
                    if "unit_price" in metadata:
                        item["unit_price"] = metadata["unit_price"]
                    
                    if "image_url" in metadata:
                        item["image_url"] = metadata["image_url"]
                    
                    all_items.append(item)
                    
                # Sort items by similarity (highest first)
                all_items.sort(key=lambda x: float(x.get("similarity", "0")), reverse=True)
                
                # Limit to requested number of results
                all_items = all_items[:n_results]
            
        except Exception as e:
            print(f"Error in query_all_stores: {e}")
        
        return all_items
        
    def get_all_stores(self):
        """
        Get a list of all store names in the database.
        
        Returns:
            list: List of store names
        """
        try:
            # Get the collection
            collection = self.get_or_create_collection()
            
            # Use get instead of query to avoid embedding dimension issues
            all_data = collection.get(
                include=["metadatas"],
                limit=1000  # Limit to 1000 records
            )
            
            # Extract unique store names from metadata
            stores = set()
            if all_data and 'metadatas' in all_data and all_data['metadatas']:
                for metadata in all_data['metadatas']:
                    if 'store' in metadata:
                        stores.add(metadata['store'])
            
            return sorted(list(stores))
            
        except Exception as e:
            print(f"Error getting stores: {e}")
            
            # Try an alternate approach if the first one fails
            try:
                print("Trying alternate approach to get stores...")
                # List all collections to check if our collection exists
                collections = self.client.list_collections()
                collection_names = [c.name for c in collections]
                
                if self.collection_name not in collection_names:
                    print(f"Collection '{self.collection_name}' does not exist yet.")
                    return []
                
                # Try to use raw API to get stores
                store_counts = {}
                
                # If we've gotten this far, there's likely a dimension mismatch
                # Recreate the collection with the current embedding dimensions
                print("Previous collection exists but may have incompatible dimensions.")
                print(f"Using search query: 'milk'")
                
                # Try a direct query as a last resort
                query_result = self.query_all_stores("milk", 100)
                
                # Extract store names from the query result
                stores = set()
                for item in query_result:
                    stores.add(item.get("store", ""))
                
                return sorted(list(filter(None, stores)))
                
            except Exception as e2:
                print(f"Alternate approach also failed: {str(e2)}")
                return []