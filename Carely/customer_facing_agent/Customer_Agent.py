import os
import pickle
from typing import List, Optional, Dict, Any
import warnings
from datetime import datetime, timezone
import time
import numpy as np

warnings.filterwarnings("ignore")

# Required imports
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from langchain_community.document_loaders import OnlinePDFLoader

# MongoDB imports
from bson import Binary, ObjectId


class CustomerSupportAgent:
    """
    A RAG-based customer support system with MongoDB persistence that can process business documents
    and provide conversational answers to customer queries using Groq Llama model.
    Now fully compliant with MongoDB validator schemas.
    """

    def __init__(self, groq_api_key: str, mongodb_client, company_id: str, session_info: Optional[Dict] = None):
        """
        Initialize the RAG system with Groq API key and MongoDB connection.

        Args:
            groq_api_key: Groq API key
            mongodb_client: MongoDB client instance
            company_id: Unique company/customer ID for data isolation (will be converted to ObjectId)
            session_info: Optional session information (session_id, user_agent, ip_address)
        """
        self.groq_api_key = groq_api_key
        self.mongodb_client = mongodb_client

        # Convert company_id to ObjectId for validator compliance
        if isinstance(company_id, str):
            try:
                # Try to convert existing ObjectId string
                self.company_id = ObjectId(company_id)
            except:
                # If not valid ObjectId, create new one (you might want to handle this differently)
                raise ValueError(f"Invalid ObjectId format: {company_id}")
        else:
            self.company_id = company_id

        # Store session info for conversation tracking
        self.session_info = session_info or {}

        # MongoDB collections
        self.db = mongodb_client.Carely
        self.documents_collection = self.db.Company_Documents
        self.embeddings_collection = self.db.Company_Embeddings
        self.conversations_collection = self.db.Company_Conversations

        # Set environment variables
        os.environ["GROQ_API_KEY"] = groq_api_key

        # Initialize components
        self.embedding_model = None
        self.vector_store = None
        self.rag_chain = None
        self.conversation_history = []
        self.conversation_start_time = datetime.now(timezone.utc)
        self.response_times = []

        # Persistent storage path for Chroma
        self.persist_directory = f"./chroma_db_{str(self.company_id)}"

        # Initialize embedding model
        self._initialize_embeddings()

        # Load existing data if available
        self._load_existing_data()

    def _initialize_embeddings(self):
        """Initialize the embedding model."""
        print("Initializing embedding model...")
        try:
            self.embedding_model = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
        except ImportError:
            print("Using deprecated HuggingFaceEmbeddings. Consider upgrading to langchain-huggingface")
            self.embedding_model = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
        print("Embedding model initialized successfully!")

    def _load_existing_data(self):
        """Load existing vector database and conversation history for this company."""
        try:
            # Check if company has existing documents
            existing_docs = self.documents_collection.find_one({"company_id": self.company_id})

            if existing_docs:
                print(f"Found existing documents for company {self.company_id}")

                # Load Chroma vector store from persistent directory
                if os.path.exists(self.persist_directory):
                    print("Loading existing Chroma vector store...")
                    self.vector_store = Chroma(
                        persist_directory=self.persist_directory,
                        embedding_function=self.embedding_model
                    )

                    # Set up retriever and RAG chain
                    self._setup_retriever()
                    self._initialize_rag_chain()

                    print("Existing vector store loaded successfully!")

                # Load conversation history
                self._load_conversation_history()

        except Exception as e:
            print(f"Error loading existing data: {str(e)}")

    def _load_conversation_history(self):
        """Load conversation history from MongoDB."""
        try:
            conversation_doc = self.conversations_collection.find_one({"company_id": self.company_id})
            if conversation_doc and 'history' in conversation_doc:
                self.conversation_history = conversation_doc['history'][-10:]  # Load last 10 exchanges
                print(f"Loaded {len(self.conversation_history)} conversation exchanges")
        except Exception as e:
            print(f"Error loading conversation history: {str(e)}")

    def _extract_topics_from_conversation(self) -> List[str]:
        """Extract topics from conversation history using simple keyword extraction."""
        topics = set()
        common_words = {'what', 'how', 'when', 'where', 'why', 'the', 'is', 'are', 'can', 'do', 'does', 'will', 'would',
                        'could', 'should', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
                        'by'}

        for question, answer in self.conversation_history:
            # Simple keyword extraction from questions
            words = question.lower().split()
            for word in words:
                word = word.strip('.,!?()[]{}":;')
                if len(word) > 3 and word not in common_words:
                    topics.add(word)

        return list(topics)[:10]  # Limit to 10 topics

    def _save_conversation_history(self):
        """Save conversation history to MongoDB with full validator compliance."""
        try:
            # Calculate conversation metadata
            total_questions = len(self.conversation_history)
            average_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else None
            topics_discussed = self._extract_topics_from_conversation()

            conversation_doc = {
                "company_id": self.company_id,
                "history": self.conversation_history,
                "session_info": {
                    "session_id": self.session_info.get("session_id"),
                    "user_agent": self.session_info.get("user_agent"),
                    "ip_address": self.session_info.get("ip_address")
                },
                "conversation_metadata": {
                    "total_questions": total_questions,
                    "average_response_time": average_response_time,
                    "topics_discussed": topics_discussed
                },
                "updated_at": datetime.now(timezone.utc)
            }

            # Check if this is a new conversation to set created_at
            existing_conversation = self.conversations_collection.find_one({"company_id": self.company_id})
            if not existing_conversation:
                conversation_doc["created_at"] = self.conversation_start_time

            self.conversations_collection.update_one(
                {"company_id": self.company_id},
                {"$set": conversation_doc},
                upsert=True
            )
        except Exception as e:
            print(f"Error saving conversation history: {str(e)}")

    def _store_embeddings_in_mongodb(self, docs: List, document_id: str, file_path: str):
        """Store individual chunks and embeddings in MongoDB according to validator schema."""
        try:
            print(f"Storing {len(docs)} embeddings in MongoDB...")
            embedding_docs = []

            for i, doc in enumerate(docs):
                # Generate embedding for the chunk
                embedding_vector = self.embedding_model.embed_query(doc.page_content)

                embedding_doc = {
                    "company_id": self.company_id,

                    # FIX: Remove ObjectId() wrapper. The validator expects a String.
                    "document_id": str(document_id),

                    "chunk_id": f"{document_id}_chunk_{i}",
                    "chunk_text": doc.page_content,
                    "embedding_vector": Binary(pickle.dumps(np.array(embedding_vector))),
                    "page_number": doc.metadata.get('page', None) if isinstance(doc.metadata.get('page'),
                                                                                int) else None,
                    "chunk_index": i,
                    "metadata": {
                        "source": doc.metadata.get('source', file_path),
                        "page": doc.metadata.get('page', None) if isinstance(doc.metadata.get('page'), int) else None
                    },
                    "created_at": datetime.now(timezone.utc)
                }
                embedding_docs.append(embedding_doc)

            # Batch insert embeddings
            if embedding_docs:
                self.embeddings_collection.insert_many(embedding_docs)
                print(f"Successfully stored {len(embedding_docs)} embeddings in MongoDB")

        except Exception as e:
            print(f"Error storing embeddings in MongoDB: {str(e)}")

    def upload_file(self, pdf_path: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> bool:
        """
        Upload and process a PDF file for the RAG system with full validator compliance.

        Args:
            pdf_path: Path to the PDF file
            chunk_size: Size of text chunks for splitting
            chunk_overlap: Overlap between chunks

        Returns:
            bool: True if successful, False otherwise
        """
        document_id = str(ObjectId())  # Generate unique document ID

        try:
            print(f"Loading PDF from: {pdf_path}")

            # Check if this file was already processed for this company
            existing_doc = self.documents_collection.find_one({
                "company_id": self.company_id,
                "file_path": pdf_path
            })

            if existing_doc:
                print("File already processed. Loading existing vector store...")
                if os.path.exists(self.persist_directory):
                    self.vector_store = Chroma(
                        persist_directory=self.persist_directory,
                        embedding_function=self.embedding_model
                    )
                    self._setup_retriever()
                    self._initialize_rag_chain()
                    return True

                # Initialize document metadata with required fields
            doc_metadata = {
                "company_id": self.company_id,
                "file_path": pdf_path,
                "file_name": os.path.basename(pdf_path),
                "uploaded_at": datetime.now(timezone.utc),
                "processing_status": "processing"  # Set to processing initially
            }

            # Insert initial document record
            self.documents_collection.update_one(
                {"company_id": self.company_id, "file_path": pdf_path},
                {"$set": doc_metadata},
                upsert=True
            )

            # Load PDF
            if pdf_path.startswith('http'):
                try:
                    loader = OnlinePDFLoader(pdf_path)
                except ImportError:
                    loader = PyPDFLoader(pdf_path)
            else:
                loader = PyPDFLoader(pdf_path)

            documents = loader.load()
            print(f"Loaded {len(documents)} pages from PDF")

            if not documents:
                print("No content found in the PDF file.")
                # Update status as failed
                self.documents_collection.update_one(
                    {"company_id": self.company_id, "file_path": pdf_path},
                    {
                        "$set": {
                            "processing_status": "failed",
                            "error_message": "No content found in PDF file",
                            "failed_at": datetime.now(timezone.utc)
                        }
                    }
                )
                return False

            # Split documents into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
            docs = text_splitter.split_documents(documents)
            print(f"Split into {len(docs)} chunks")

            # Create persistent vector store
            print("Creating persistent vector store...")
            self.vector_store = Chroma.from_documents(
                docs,
                self.embedding_model,
                persist_directory=self.persist_directory
            )

            # Persist the vector store
            self.vector_store.persist()

            # Store embeddings in MongoDB
            self._store_embeddings_in_mongodb(docs, document_id, pdf_path)

            # Update document metadata with completion info - ensure all types are correct
            completed_metadata = {
                "total_pages": int(len(documents)),
                "total_chunks": int(len(docs)),
                "chunk_size": int(chunk_size),
                "chunk_overlap": int(chunk_overlap),
                "processing_status": "completed"
            }

            self.documents_collection.update_one(
                {"company_id": self.company_id, "file_path": pdf_path},
                {"$set": completed_metadata}
            )

            # Set up retriever with reranking
            self._setup_retriever()

            # Initialize RAG chain
            self._initialize_rag_chain()

            print("File uploaded and processed successfully with full MongoDB compliance!")
            return True

        except Exception as e:
            print(f"Error uploading file: {str(e)}")
            # Update status as failed in MongoDB with proper error handling
            try:
                error_metadata = {
                    "file_name": os.path.basename(pdf_path),
                    "processing_status": "failed",
                    "error_message": str(e),
                    "failed_at": datetime.now(timezone.utc),
                    "uploaded_at": datetime.now(timezone.utc)
                }

                self.documents_collection.update_one(
                    {"company_id": self.company_id, "file_path": pdf_path},
                    {"$set": error_metadata},
                    upsert=True
                )
            except Exception as db_error:
                print(f"Error saving failure status to database: {str(db_error)}")
            return False

    def _setup_retriever(self):
        """Set up the retriever with reranking."""
        print("Setting up retriever with reranking...")

        try:
            # Base retriever
            base_retriever = self.vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 10}
            )

            # Cross-encoder reranker
            model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
            compressor = CrossEncoderReranker(model=model, top_n=5)

            # Contextual compression retriever
            self.compression_retriever = ContextualCompressionRetriever(
                base_compressor=compressor,
                base_retriever=base_retriever
            )
        except Exception as e:
            print(f"Warning: Could not set up reranking ({str(e)}). Using basic retriever...")
            # Fallback to basic retriever
            self.compression_retriever = self.vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 5}
            )

    def _initialize_rag_chain(self):
        """Initialize the RAG chain with the Groq Llama model."""
        print("Initializing RAG chain with Groq Llama model...")

        try:
            # Initialize Groq LLM
            llm = ChatGroq(
                model_name="llama-3.1-8b-instant",
                temperature=0.1,
                api_key=self.groq_api_key
            )

            # Create prompt template for customer support
            prompt_template = ChatPromptTemplate.from_template("""
You are a helpful customer support assistant. Use the provided context to answer the customer's question accurately and professionally.

Context from business documents:
{context}

Previous conversation:
{conversation_history}

Customer Question: {question}

Instructions:
- Answer based primarily on the provided context
- Be friendly, professional, and helpful
- If the information isn't in the context, politely say so and offer to help with other questions
- Keep responses concise but complete
- Use a conversational tone appropriate for customer support

Answer:""")

            def format_docs(docs):
                return "\n\n".join(doc.page_content for doc in docs)

            def format_conversation_history():
                if not self.conversation_history:
                    return "No previous conversation"

                formatted = []
                for i, (q, a) in enumerate(self.conversation_history[-3:]):  # Last 3 exchanges
                    formatted.append(f"Q{i + 1}: {q}")
                    formatted.append(f"A{i + 1}: {a}")
                return "\n".join(formatted)

            # Build RAG chain
            self.rag_chain = (
                    {
                        "context": self.compression_retriever | format_docs,
                        "question": RunnablePassthrough(),
                        "conversation_history": lambda x: format_conversation_history()
                    }
                    | prompt_template
                    | llm
                    | StrOutputParser()
            )

            print("RAG chain initialized successfully!")

        except Exception as e:
            print(f"Error initializing RAG chain: {str(e)}")
            raise

    def ask_question(self, question: str) -> str:
        """
        Ask a question to the customer support RAG system.

        Args:
            question: Customer's question

        Returns:
            str: AI-generated response
        """
        if not self.rag_chain:
            return "Please upload a business document first using the upload_file() method."

        try:
            print(f"Processing question: {question}")

            # Track response time
            start_time = time.time()
            response = self.rag_chain.invoke(question)
            end_time = time.time()

            response_time = end_time - start_time
            self.response_times.append(response_time)

            # Store in conversation history
            self.conversation_history.append((question, response))

            # Keep only last 10 exchanges to manage memory
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
                # Also keep only last 10 response times
                self.response_times = self.response_times[-10:]

            # Save conversation history to MongoDB with enhanced metadata
            self._save_conversation_history()

            return response

        except Exception as e:
            error_msg = f"Sorry, I encountered an error while processing your question: {str(e)}"
            print(error_msg)
            return error_msg

    def get_relevant_documents(self, question: str, k: int = 3) -> List[dict]:
        """
        Get the most relevant documents for a question (for debugging/transparency).

        Args:
            question: The question to search for
            k: Number of documents to return

        Returns:
            List of dictionaries with document content and metadata
        """
        if not self.compression_retriever:
            return []

        try:
            docs = self.compression_retriever.invoke(question)
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

    def clear_conversation_history(self):
        """Clear the conversation history."""
        self.conversation_history = []
        self.response_times = []
        self._save_conversation_history()
        print("Conversation history cleared.")

    def delete_company_data(self):
        """Delete all data for this company (for cleanup/testing)."""
        try:
            # Delete from MongoDB collections
            self.documents_collection.delete_many({"company_id": self.company_id})
            self.embeddings_collection.delete_many({"company_id": self.company_id})
            self.conversations_collection.delete_many({"company_id": self.company_id})

            # Delete Chroma persistence directory
            import shutil
            if os.path.exists(self.persist_directory):
                shutil.rmtree(self.persist_directory)

            print(f"All data deleted for company {self.company_id}")

        except Exception as e:
            print(f"Error deleting company data: {str(e)}")

    def get_company_documents(self) -> List[Dict]:
        """Get list of processed documents for this company."""
        try:
            docs = list(self.documents_collection.find({"company_id": self.company_id}))
            return [
                {
                    "file_name": doc.get("file_name", "Unknown"),
                    "uploaded_at": doc.get("uploaded_at"),
                    "status": doc.get("processing_status", "unknown"),
                    "total_pages": doc.get("total_pages", 0),
                    "total_chunks": doc.get("total_chunks", 0)
                }
                for doc in docs
            ]
        except Exception as e:
            print(f"Error getting company documents: {str(e)}")
            return []

    def get_company_embeddings_stats(self) -> Dict:
        """Get statistics about stored embeddings for this company."""
        try:
            total_embeddings = self.embeddings_collection.count_documents({"company_id": self.company_id})

            # Get unique document count
            unique_docs = len(list(self.embeddings_collection.distinct("document_id", {"company_id": self.company_id})))

            return {
                "total_embeddings": total_embeddings,
                "unique_documents": unique_docs,
                "company_id": str(self.company_id)
            }
        except Exception as e:
            print(f"Error getting embeddings stats: {str(e)}")
            return {"error": str(e)}

    def health_check(self) -> dict:
        """Check the health status of all components with enhanced information."""
        try:
            company_docs = self.get_company_documents()
            embeddings_stats = self.get_company_embeddings_stats()
            has_documents = len(company_docs) > 0

            status = {
                "company_id": str(self.company_id),
                "embedding_model": self.embedding_model is not None,
                "vector_store": self.vector_store is not None,
                "rag_chain": self.rag_chain is not None,
                "conversation_history_count": len(self.conversation_history),
                "llm_provider": "groq",
                "has_processed_documents": has_documents,
                "processed_documents_count": len(company_docs),
                "persistent_storage": os.path.exists(self.persist_directory),
                "documents": company_docs,
                "embeddings_stats": embeddings_stats,
                "session_info": self.session_info,
                "mongodb_collections": {
                    "documents_connected": self.documents_collection is not None,
                    "embeddings_connected": self.embeddings_collection is not None,
                    "conversations_connected": self.conversations_collection is not None
                }
            }
            return status
        except Exception as e:
            return {"error": str(e), "company_id": str(self.company_id)}

    def update_session_info(self, session_info: Dict):
        """Update session information for better tracking."""
        self.session_info.update(session_info)
        # Save updated session info with conversation
        self._save_conversation_history()

    def delete_document(self, file_name: str) -> Dict[str, Any]:
        """
        Delete a document and all its associated data from both MongoDB and vector store.

        Args:
            file_name: Name of the file to delete

        Returns:
            Dict with status and details of the deletion
        """
        try:
            print(f"Attempting to delete document: {file_name} for company: {self.company_id}")

            # Step 1: Find the document in Company_Documents collection
            document_record = self.documents_collection.find_one({
                "company_id": self.company_id,
                "file_name": file_name
            })

            if not document_record:
                return {
                    "success": False,
                    "error": f"Document '{file_name}' not found for this company",
                    "deleted_items": {}
                }

            # Get document details for response
            document_id = document_record.get("_id")
            file_path = document_record.get("file_path")

            print(f"Found document record with ID: {document_id}")

            # Step 2: Delete from Company_Embeddings collection using document_id
            # Note: In embeddings, document_id is stored as string, not ObjectId
            embeddings_result = self.embeddings_collection.delete_many({
                "company_id": self.company_id,
                "document_id": str(document_id)  # Convert ObjectId to string for matching
            })

            deleted_embeddings = embeddings_result.deleted_count
            print(f"Deleted {deleted_embeddings} embeddings")

            # Step 3: Delete from Company_Documents collection
            documents_result = self.documents_collection.delete_one({
                "company_id": self.company_id,
                "file_name": file_name
            })

            deleted_documents = documents_result.deleted_count
            print(f"Deleted {deleted_documents} document records")

            # Step 4: Update vector store by recreating it without the deleted document
            # This is necessary because Chroma doesn't have easy document-level deletion
            try:
                remaining_embeddings = list(self.embeddings_collection.find({
                    "company_id": self.company_id
                }))

                if remaining_embeddings:
                    print(f"Recreating vector store with {len(remaining_embeddings)} remaining embeddings")

                    # Clear current vector store
                    if os.path.exists(self.persist_directory):
                        import shutil
                        shutil.rmtree(self.persist_directory)

                    # Recreate vector store with remaining embeddings
                    remaining_docs = []
                    remaining_embeddings_vectors = []

                    for embedding_record in remaining_embeddings:
                        chunk_text = embedding_record.get("chunk_text", "")
                        if chunk_text:
                            # Create document object
                            from langchain.schema import Document
                            doc = Document(
                                page_content=chunk_text,
                                metadata=embedding_record.get("metadata", {})
                            )
                            remaining_docs.append(doc)

                    if remaining_docs:
                        # Recreate vector store
                        self.vector_store = Chroma.from_documents(
                            remaining_docs,
                            self.embedding_model,
                            persist_directory=self.persist_directory
                        )
                        self.vector_store.persist()

                        # Reinitialize retriever and RAG chain
                        self._setup_retriever()
                        self._initialize_rag_chain()
                        print("Vector store recreated successfully")
                    else:
                        # No documents left, clear everything
                        self.vector_store = None
                        self.compression_retriever = None
                        self.rag_chain = None
                        print("No documents remaining, cleared vector store")
                else:
                    # No embeddings left, clear everything
                    if os.path.exists(self.persist_directory):
                        import shutil
                        shutil.rmtree(self.persist_directory)

                    self.vector_store = None
                    self.compression_retriever = None
                    self.rag_chain = None
                    print("No embeddings remaining, cleared all vector store data")

            except Exception as vector_error:
                print(f"Warning: Error updating vector store after deletion: {str(vector_error)}")
                # Continue even if vector store update fails

            # Step 5: Clean up physical file if it still exists
            file_deleted = False
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    file_deleted = True
                    print(f"Deleted physical file: {file_path}")
                except Exception as file_error:
                    print(f"Warning: Could not delete physical file {file_path}: {str(file_error)}")

            return {
                "success": True,
                "message": f"Document '{file_name}' deleted successfully",
                "deleted_items": {
                    "document_records": deleted_documents,
                    "embedding_records": deleted_embeddings,
                    "physical_file": file_deleted,
                    "vector_store_updated": True
                }
            }

        except Exception as e:
            error_msg = f"Error deleting document '{file_name}': {str(e)}"
            print(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "deleted_items": {}
            }

    @classmethod
    def create_with_new_company(cls, groq_api_key: str, mongodb_client, session_info: Optional[Dict] = None):
        """
        Create a new RAG instance with a fresh company ID.

        Args:
            groq_api_key: Groq API key
            mongodb_client: MongoDB client instance
            session_info: Optional session information

        Returns:
            CustomerSupportRAG instance with new company ID
        """
        new_company_id = str(ObjectId())
        return cls(groq_api_key, mongodb_client, new_company_id, session_info)