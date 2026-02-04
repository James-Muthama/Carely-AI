import os
import pickle
import numpy as np
from datetime import datetime, timezone
from bson import Binary
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings


class VectorStoreManager:
    def __init__(self, company_id, mongodb_db):
        self.company_id = company_id
        self.db = mongodb_db
        self.embeddings_collection = self.db.Company_Embeddings
        self.persist_directory = f"./chroma_db_{str(self.company_id)}"

        # Initialize Embeddings
        print("Initializing embedding model...")
        self.embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.vector_store = None

    def load_existing(self):
        """Loads existing ChromaDB if it exists."""
        if os.path.exists(self.persist_directory):
            print("Loading existing Chroma vector store...")
            self.vector_store = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embedding_model
            )
            return True
        return False

    def create_from_documents(self, docs):
        """Creates a new ChromaDB from documents."""
        print("Creating persistent vector store...")
        self.vector_store = Chroma.from_documents(
            docs,
            self.embedding_model,
            persist_directory=self.persist_directory
        )
        self.vector_store.persist()

    def store_embeddings_in_mongo(self, docs, document_id, file_path):
        """Backs up embeddings to MongoDB."""
        try:
            print(f"Storing {len(docs)} embeddings in MongoDB...")
            embedding_docs = []

            for i, doc in enumerate(docs):
                embedding_vector = self.embedding_model.embed_query(doc.page_content)

                embedding_docs.append({
                    "company_id": self.company_id,
                    "document_id": str(document_id),
                    "chunk_id": f"{document_id}_chunk_{i}",
                    "chunk_text": doc.page_content,
                    "embedding_vector": Binary(pickle.dumps(np.array(embedding_vector))),
                    "chunk_index": i,
                    "metadata": {
                        "source": doc.metadata.get('source', file_path),
                        "page": doc.metadata.get('page')
                    },
                    "created_at": datetime.now(timezone.utc)
                })

            if embedding_docs:
                self.embeddings_collection.insert_many(embedding_docs)
        except Exception as e:
            print(f"Error storing embeddings in MongoDB: {str(e)}")

    def delete_store(self):
        """Deletes the physical ChromaDB folder."""
        import shutil
        if os.path.exists(self.persist_directory):
            shutil.rmtree(self.persist_directory)