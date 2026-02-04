import os
import time
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from bson import ObjectId

# Import your new modular components
from .document_processor import DocumentProcessor
from .vector_store import VectorStoreManager
from .history_manager import HistoryManager
from .retrieval_engine import RetrievalEngine

class CustomerSupportAgent:
    """
    Orchestrator class for Internal RAG Testing.
    Delegates logic to specialized modules.
    """

    def __init__(self, groq_api_key: str, mongodb_client, company_id: str, session_info: Optional[Dict] = None):
        self.groq_api_key = groq_api_key

        # ID Handling
        if isinstance(company_id, str):
            try:
                self.company_id = ObjectId(company_id)
            except:
                raise ValueError(f"Invalid ObjectId: {company_id}")
        else:
            self.company_id = company_id

        self.session_info = session_info or {}
        self.db = mongodb_client.Carely
        self.documents_collection = self.db.Company_Documents
        self.embeddings_collection = self.db.Company_Embeddings # Added for deletion logic

        # --- Initialize Sub-Modules ---
        self.doc_processor = DocumentProcessor()
        self.vector_manager = VectorStoreManager(self.company_id, self.db)
        self.history_manager = HistoryManager(self.company_id, self.db)
        self.retrieval_engine = RetrievalEngine(None, groq_api_key)  # Vector store set later

        # --- Load Existing Data ---
        self.history_manager.load_history()

        if self.vector_manager.load_existing():
            # If loaded successfully, inject vector store into retrieval engine
            self.retrieval_engine.vector_store = self.vector_manager.vector_store
            self.retrieval_engine.setup_retriever()
            self.retrieval_engine.initialize_chain(self._get_history_text)

    def _get_history_text(self):
        """Helper to format history for the LLM prompt."""
        if not self.history_manager.history:
            return "No previous conversation"
        return "\n".join([f"Q: {q}\nA: {a}" for q, a in self.history_manager.history[-3:]])

    def upload_file(self, pdf_path: str) -> bool:
        """Process a PDF: Load -> Split -> Embed -> Store."""
        document_id = str(ObjectId())

        # 1. Database Check
        existing = self.documents_collection.find_one({"company_id": self.company_id, "file_path": pdf_path})
        if existing:
            print("File already processed.")
            return True

        # 2. Load & Split
        docs, chunks = self.doc_processor.load_and_split(pdf_path)
        if not docs:
            return False

        # 3. Vector Store Creation
        self.vector_manager.create_from_documents(chunks)
        self.vector_manager.store_embeddings_in_mongo(chunks, document_id, pdf_path)

        # 4. Update Retrieval Engine with new Vector Store
        self.retrieval_engine.vector_store = self.vector_manager.vector_store
        self.retrieval_engine.setup_retriever()
        self.retrieval_engine.initialize_chain(self._get_history_text)

        # 5. Update Status in Mongo
        self.documents_collection.update_one(
            {"company_id": self.company_id, "file_path": pdf_path},
            {"$set": {
                "file_name": os.path.basename(pdf_path),
                "processing_status": "completed",
                "uploaded_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        return True

    def ask_question(self, question: str) -> str:
        """Main query method."""
        try:
            start = time.time()
            response = self.retrieval_engine.query(question)
            end = time.time()

            self.history_manager.add_exchange(question, response, end - start)
            self.history_manager.save(self.session_info)

            return response
        except Exception as e:
            return f"Error: {str(e)}"

    # --- RESTORED HELPER METHODS BELOW ---

    def get_company_documents(self) -> List[Dict]:
        """
        [RESTORED] Get list of processed documents for this company.
        Used by: /chat_interface, /upload, /company_documents
        """
        try:
            docs = list(self.documents_collection.find({"company_id": self.company_id}))
            return [
                {
                    "file_name": doc.get("file_name", "Unknown"),
                    "uploaded_at": doc.get("uploaded_at"),
                    "status": doc.get("processing_status", "unknown"),
                    # Add generic placeholders if modules don't track page counts yet
                    "total_pages": doc.get("total_pages", "?"),
                    "total_chunks": doc.get("total_chunks", "?")
                }
                for doc in docs
            ]
        except Exception as e:
            print(f"Error getting company documents: {str(e)}")
            return []

    def get_relevant_documents(self, question: str, k: int = 3) -> List[dict]:
        """
        [RESTORED] Get relevant docs for transparency.
        Used by: /ask_question
        """
        if not self.retrieval_engine.compression_retriever:
            return []

        try:
            # Access the retriever from the retrieval engine module
            docs = self.retrieval_engine.compression_retriever.invoke(question)
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "relevance_score": doc.metadata.get("relevance_score", "N/A")
                }
                for doc in docs[:k]
            ]
        except Exception as e:
            print(f"Error retrieving documents: {str(e)}")
            return []

    def delete_document(self, file_name: str) -> Dict[str, Any]:
        """
        [RESTORED] Delete a specific document.
        Used by: /delete_document
        """
        try:
            print(f"Attempting to delete document: {file_name}")

            # 1. Find document
            doc = self.documents_collection.find_one({
                "company_id": self.company_id,
                "file_name": file_name
            })
            if not doc:
                return {"success": False, "error": "Document not found"}

            doc_id = doc.get("_id")
            file_path = doc.get("file_path")

            # 2. Delete from MongoDB Collections
            self.documents_collection.delete_one({"_id": doc_id})
            self.embeddings_collection.delete_many({"company_id": self.company_id, "document_id": str(doc_id)})

            # 3. Rebuild Vector Store (Cleanest way to remove from Chroma)
            # We delete the folder and allow the next reload/upload to rebuild it or handle it empty
            self.vector_manager.delete_store()
            self.retrieval_engine.rag_chain = None # Reset chain

            # 4. Remove physical file
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

            return {
                "success": True,
                "message": "Document deleted. Please upload a new document to chat.",
                "deleted_items": {}
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def health_check(self) -> dict:
        """
        [RESTORED] System health check.
        Used by: /rag_status
        """
        return {
            "company_id": str(self.company_id),
            "vector_store": self.vector_manager.vector_store is not None,
            "rag_chain": self.retrieval_engine.rag_chain is not None,
            "conversation_count": len(self.history_manager.history),
            "has_documents": self.documents_collection.count_documents({"company_id": self.company_id}) > 0
        }

    def clear_conversation_history(self):
        self.history_manager.clear()

    def delete_company_data(self):
        """Cleanup method."""
        self.documents_collection.delete_many({"company_id": self.company_id})
        self.db.Internal_Test_Conversations.delete_many({"company_id": self.company_id})
        self.db.Company_Embeddings.delete_many({"company_id": self.company_id})
        self.vector_manager.delete_store()