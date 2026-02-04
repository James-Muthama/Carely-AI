import os
from datetime import datetime, timezone
from langchain_community.document_loaders import PyPDFLoader, OnlinePDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


class DocumentProcessor:
    def __init__(self, chunk_size=1000, chunk_overlap=200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_and_split(self, pdf_path: str):
        """Loads a PDF and splits it into chunks."""
        try:
            print(f"Loading PDF from: {pdf_path}")
            if pdf_path.startswith('http'):
                try:
                    loader = OnlinePDFLoader(pdf_path)
                except ImportError:
                    loader = PyPDFLoader(pdf_path)
            else:
                loader = PyPDFLoader(pdf_path)

            documents = loader.load()
            if not documents:
                return None, None

            print(f"Loaded {len(documents)} pages.")

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
            chunks = text_splitter.split_documents(documents)
            print(f"Split into {len(chunks)} chunks.")

            return documents, chunks
        except Exception as e:
            print(f"Error processing document: {e}")
            raise e