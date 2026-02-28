import os
import time
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from bson import ObjectId
from groq import Groq

# Import your modular components
from .document_processor import DocumentProcessor
from .vector_store import VectorStoreManager
from .history_manager import HistoryManager
from .retrieval_engine import RetrievalEngine


class CustomerSupportAgent:
    """
    Orchestrator for Carely AI.
    Handles RAG-based answering, Sentiment Analysis, and Category Classification.
    """

    def __init__(self, groq_api_key: str, mongodb_client, company_id: str, session_info: Optional[Dict] = None):
        self.groq_api_key = groq_api_key
        self.groq_client = Groq(api_key=groq_api_key)

        # ID Handling
        if isinstance(company_id, str):
            self.company_id = ObjectId(company_id)
        else:
            self.company_id = company_id

        self.db = mongodb_client.Carely
        self.categories_collection = self.db.Company_Conversation_Categories
        self.documents_collection = self.db.Company_Documents
        self.embeddings_collection = self.db.Company_Embeddings

        # Models
        self.reasoning_model = "llama-3.3-70b-versatile"  # For RAG
        self.fast_model = "llama-3.1-8b-instant"  # For Classification

        # Initialize Sub-Modules
        self.doc_processor = DocumentProcessor()
        self.vector_manager = VectorStoreManager(self.company_id, self.db)
        self.history_manager = HistoryManager(self.company_id, self.db)
        self.retrieval_engine = RetrievalEngine(
            vector_store=None,
            groq_api_key=groq_api_key,
            model_name=self.reasoning_model
        )

        # Load Existing Data
        self.history_manager.load_history()
        if self.vector_manager.load_existing():
            self.retrieval_engine.vector_store = self.vector_manager.vector_store
            self.retrieval_engine.setup_retriever()
            self.retrieval_engine.initialize_chain(self._get_history_text)

    def _get_history_text(self):
        if not self.history_manager.history:
            return "No previous conversation"
        return "\n".join([f"Q: {q}\nA: {a}" for q, a in self.history_manager.history[-3:]])

    def classify_and_analyze(self, text: str) -> Dict[str, Any]:
        """
        Internal method to categorize the message based on user-defined categories.
        """
        try:
            # 1. Fetch company-specific categories
            category_doc = self.categories_collection.find_one({"company_id": self.company_id})
            user_categories = [cat['name'] for cat in category_doc.get('categories', [])] if category_doc else []

            # If the user hasn't set categories, we use a default list or "Uncategorized"
            category_list_str = ", ".join(user_categories) if user_categories else "None (Use 'Uncategorized')"

            prompt = f"""
            Analyze the following customer message and provide classification.

            Customer Message: "{text}"
            Available Categories: [{category_list_str}]

            Instructions:
            1. Select the most relevant category from the list. 
            2. If no categories are provided or the message doesn't fit, use "Uncategorized".
            3. Provide a sentiment score between -1.0 (very negative) and 1.0 (very positive).

            Respond ONLY in valid JSON:
            {{
                "category": "Selected Category",
                "sentiment_score": 0.0
            }}
            """

            response = self.groq_client.chat.completions.create(
                model=self.fast_model,
                messages=[{"role": "system", "content": "You are a precise data classifier."},
                          {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )

            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Classification Error: {e}")
            return {"category": "Uncategorized", "sentiment_score": 0.0}

    def process_message(self, question: str) -> Dict[str, Any]:
        """
        The master method for the Webhook.
        Returns the answer, the category, and the sentiment in one go.
        """
        start_time = time.time()

        # 1. Classification & Sentiment (Async-ready if needed)
        analysis = self.classify_and_analyze(question)

        # 2. RAG Answer Generation
        try:
            answer = self.retrieval_engine.query(question)
        except Exception as e:
            answer = "I'm sorry, I encountered an error processing your request."
            print(f"RAG Error: {e}")

        # 3. Update internal history
        duration = time.time() - start_time
        self.history_manager.add_exchange(question, answer, duration)

        return {
            "answer": answer,
            "category": analysis.get("category", "Uncategorized"),
            "sentiment_score": analysis.get("sentiment_score", 0.0),
            "timestamp": datetime.now(timezone.utc)
        }

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
            # The retrieval_engine now uses llama-3.3-70b-versatile
            response = self.retrieval_engine.query(question)
            end = time.time()

            self.history_manager.add_exchange(question, response, end - start)
            self.history_manager.save(self.session_info)

            return response
        except Exception as e:
            return f"Error: {str(e)}"

    def get_company_documents(self) -> List[Dict]:
        """Get list of processed documents for this company."""
        try:
            docs = list(self.documents_collection.find({"company_id": self.company_id}))
            return [
                {
                    "file_name": doc.get("file_name", "Unknown"),
                    "uploaded_at": doc.get("uploaded_at"),
                    "status": doc.get("processing_status", "unknown"),
                    "total_pages": doc.get("total_pages", "?"),
                    "total_chunks": doc.get("total_chunks", "?")
                }
                for doc in docs
            ]
        except Exception as e:
            print(f"Error getting company documents: {str(e)}")
            return []

    def get_relevant_documents(self, question: str, k: int = 3) -> List[dict]:
        """Get relevant docs for transparency."""
        if not self.retrieval_engine.compression_retriever:
            return []

        try:
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
        """Delete a specific document."""
        try:
            doc = self.documents_collection.find_one({
                "company_id": self.company_id,
                "file_name": file_name
            })
            if not doc:
                return {"success": False, "error": "Document not found"}

            doc_id = doc.get("_id")
            file_path = doc.get("file_path")

            self.documents_collection.delete_one({"_id": doc_id})
            self.embeddings_collection.delete_many({"company_id": self.company_id, "document_id": str(doc_id)})

            self.vector_manager.delete_store()
            self.retrieval_engine.rag_chain = None

            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

            return {
                "success": True,
                "message": "Document deleted. Please upload a new document to chat."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def health_check(self) -> dict:
        """System health check."""
        return {
            "company_id": str(self.company_id),
            "model_in_use": self.model_name,
            "vector_store_active": self.vector_manager.vector_store is not None,
            "rag_chain_active": self.retrieval_engine.rag_chain is not None,
            "history_depth": len(self.history_manager.history)
        }

    def clear_conversation_history(self):
        self.history_manager.clear()

    def delete_company_data(self):
        """Full cleanup."""
        self.documents_collection.delete_many({"company_id": self.company_id})
        self.db.Internal_Test_Conversations.delete_many({"company_id": self.company_id})
        self.db.Company_Embeddings.delete_many({"company_id": self.company_id})
        self.vector_manager.delete_store()