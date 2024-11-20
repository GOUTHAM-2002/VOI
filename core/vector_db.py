import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import os
import logging
import json
from .models import Product

logger = logging.getLogger(__name__)


class ChromaDBSingleton:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChromaDBSingleton, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            try:
                logger.setLevel(logging.DEBUG)

                persist_directory = os.path.join("vector_db")
                os.makedirs(persist_directory, exist_ok=True)

                logger.debug(
                    f"Initializing ChromaDB with directory: {persist_directory}"
                )

                self.client = chromadb.PersistentClient(path=persist_directory)
                self.encoder = SentenceTransformer(
                    "sentence-transformers/all-MiniLM-L6-v2"
                )

                self.collection = self.client.get_or_create_collection(
                    name="products", metadata={"hnsw:space": "cosine"}
                )

                products = list(Product.objects.all())

                if products and isinstance(products, list):
                    self.add_products_to_vectordb(products)
                else:
                    logger.warning("No products found in database")

                self._initialized = True
                logger.info("ChromaDB initialization completed")

            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON: {e}")
            except Exception as e:
                logger.error(f"Error during ChromaDB initialization: {str(e)}")
                raise

    def add_products_to_vectordb(self, products=None):
        """
        Add multiple products to vector database with Django ORM integration
        """
        try:
            if products is None:
                from .models import Product

                products = Product.objects.all()

            existing_collection = self.collection.get()
            existing_ids = set(existing_collection.get("ids", []))
            logger.debug(f"Found {len(existing_ids)} existing products in vector DB")

            ids = []
            embeddings = []
            documents = []
            metadatas = []

            for product in products:
                try:
                    # Use the product's ID as a string
                    product_id = str(product.id)

                    # Skip if product already exists in vector DB
                    if product_id in existing_ids:
                        logger.debug(
                            f"Product {product_id} already exists in vector DB"
                        )
                        continue

                    # Generate embedding from description
                    description = product.name + product.description
                    embedding = self.encoder.encode(description).tolist()

                    # Create document text
                    document_text = f"{description}"

                    ids.append(product_id)
                    embeddings.append(embedding)
                    documents.append(document_text)

                    # Prepare metadata
                    metadata = {
                        "name": product.name,
                        "price": str(product.price),
                    }
                    metadatas.append(metadata)

                except Exception as e:
                    logger.error(f"Error processing product {product.id}: {str(e)}")

            # Batch upsert products
            if ids:
                self.collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )
                logger.info(f"Successfully added {len(ids)} new products to vector DB")
            else:
                logger.info("No new products to add to vector DB")

        except Exception as e:
            logger.error(f"Error in batch upload to vector DB: {str(e)}")
            raise

    def search_similar(self, query_text, n_results=5, similarity_threshold=0.75):
        """Search for similar products"""
        try:
            # Encode the query
            query_embedding = self.encoder.encode(query_text).tolist()

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=5,
                include=["distances", "metadatas", "documents"],
            )
            return results
        except Exception as e:
            logger.error(f"Error in similarity search: {str(e)}")
            return {"ids": [], "distances": [], "documents": [], "metadatas": []}


def vector_search(query):
    try:
        db = ChromaDBSingleton()
        logger.info(f"Received query: {query}")

        formatted_results = []
        if query:
            results = db.search_similar(query, 10, 0.75)
            ids = results.get("ids", [[]])[0]
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for id_, doc, metadata, distance in zip(
                ids, documents, metadatas, distances
            ):
                if distance < 0.55:
                    formatted_results.append(
                        {
                            "ID": id_,
                            "NAME": metadata.get("name", "Unknown"),
                            "PRICE": metadata.get("price", "100.00"),
                            "DESCRIPTION": doc,
                            "DISTANCE": distance,
                        }
                    )
            sorted_formatted_list = sorted(
                formatted_results, key=lambda k: k["DISTANCE"]
            )
            print("------------------------------\n\n")
            print(sorted_formatted_list)
            print("------------------------------\n\n")
            # if len(sorted_formatted_list) > 2:
            #     sorted_formatted_list = sorted_formatted_list[:2]
        return sorted_formatted_list
    except Exception as e:
        logger.error(f"Error in vector search: {str(e)}")
        return []
