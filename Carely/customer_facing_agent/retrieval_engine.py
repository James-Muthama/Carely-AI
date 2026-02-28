from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser


class RetrievalEngine:
    def __init__(self, vector_store, groq_api_key, model_name="llama-3.1-8b-instant"):
        self.vector_store = vector_store
        self.groq_api_key = groq_api_key
        self.model_name = model_name  # Store the model name
        self.rag_chain = None
        self.compression_retriever = None

    def setup_retriever(self):
        """Sets up retriever with Re-ranking."""
        print("Setting up retriever...")
        try:
            base_retriever = self.vector_store.as_retriever(search_kwargs={"k": 10})
            # Re-ranking remains the same
            model = HuggingFaceCrossEncoder(model_name="BAAI/bge-reranker-base")
            compressor = CrossEncoderReranker(model=model, top_n=5)
            self.compression_retriever = ContextualCompressionRetriever(
                base_compressor=compressor, base_retriever=base_retriever
            )
        except Exception as e:
            print(f"Reranking failed ({e}), using basic retriever.")
            self.compression_retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})

    def initialize_chain(self, history_getter_func):
        """Initializes the RAG chain."""
        # UPDATED: Now uses the model_name passed during initialization
        llm = ChatGroq(
            model_name=self.model_name,
            temperature=0.1,
            api_key=self.groq_api_key
        )

        prompt = ChatPromptTemplate.from_template("""
        You are a helpful customer support assistant.
        Context: {context}
        History: {conversation_history}
        Question: {question}
        Answer:""")

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        self.rag_chain = (
                {
                    "context": self.compression_retriever | format_docs,
                    "question": RunnablePassthrough(),
                    "conversation_history": lambda x: history_getter_func()
                }
                | prompt
                | llm
                | StrOutputParser()
        )

    def query(self, question):
        if not self.rag_chain:
            raise ValueError("RAG Chain not initialized. Upload a document first.")
        return self.rag_chain.invoke(question)