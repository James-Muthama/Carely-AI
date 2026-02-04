import os
import json
import time
import pypdf
from typing import List, Dict, Optional
from bson import ObjectId
from google import genai
from google.genai import types
from flask import current_app
from pydantic import BaseModel, Field


class BusinessAnalyticsAgent:
    """
    Business Analytics Agent using Gemini 2.5 Flash Lite.
    FINAL HACKATHON CONFIG:
    - Uses 'gemini-2.5-flash-lite' for speed and free-tier access.
    - Aggregates text from ALL uploaded company documents.
    - Extracts text locally to prevent token limit errors.
    """

    def __init__(self, google_api_key: str, mongodb_client, company_id: str):
        self.google_api_key = google_api_key
        self.mongodb_client = mongodb_client

        # Ensure company_id is an ObjectId
        if isinstance(company_id, str):
            self.company_id = ObjectId(company_id)
        else:
            self.company_id = company_id

        self.db = mongodb_client.Carely
        self.documents_collection = self.db.Company_Documents

        # Initialize Gemini Client
        self.client = genai.Client(api_key=self.google_api_key)

        # --- MODEL CONFIGURATION ---
        # Using Gemini 2.5 Flash Lite (Best balance of speed/cost/quality)
        self.model_name = "gemini-2.5-flash-lite"

    def _get_all_document_paths(self) -> List[str]:
        """
        Finds absolute paths for ALL completed documents for this company.
        """
        # Find all documents marked as 'completed'
        docs = self.documents_collection.find(
            {"company_id": self.company_id, "processing_status": "completed"}
        )

        valid_paths = []

        for doc in docs:
            stored_path = doc.get('file_path')
            if not stored_path:
                continue

            actual_filename = os.path.basename(stored_path)

            # Check standard upload locations to handle different environments
            potential_paths = []
            if current_app:
                potential_paths.append(os.path.join(current_app.config['UPLOAD_FOLDER'], actual_filename))

            potential_paths.append(os.path.abspath(stored_path))
            potential_paths.append(os.path.join(os.getcwd(), 'app', 'uploads', actual_filename))
            potential_paths.append(os.path.join(os.getcwd(), 'uploads', actual_filename))

            for path in potential_paths:
                if os.path.exists(path):
                    valid_paths.append(path)
                    print(f"DEBUG: ✅ Found file: {actual_filename}")
                    break

        if not valid_paths:
            print("DEBUG: ❌ No valid document files found on disk.")

        return valid_paths

    def _extract_text_from_pdf(self, file_path: str, max_pages: int = 5) -> str:
        """
        Extracts text from a single PDF (first N pages to save tokens).
        """
        try:
            reader = pypdf.PdfReader(file_path)
            text_content = []

            # Read first N pages to get the "gist" without hitting limits
            pages_to_read = min(len(reader.pages), max_pages)

            for i in range(pages_to_read):
                page_text = reader.pages[i].extract_text()
                if page_text:
                    text_content.append(page_text)

            return "\n".join(text_content)
        except Exception as e:
            print(f"DEBUG: Error reading PDF {file_path}: {e}")
            return ""

    def generate_category_suggestions(self) -> List[Dict[str, str]]:
        # 1. Get ALL file paths
        file_paths = self._get_all_document_paths()

        if not file_paths:
            return []

        # 2. Extract and Aggregate Text
        full_context = ""
        for path in file_paths:
            file_text = self._extract_text_from_pdf(path)
            if file_text:
                full_context += f"\n--- DOCUMENT START: {os.path.basename(path)} ---\n"
                full_context += file_text
                full_context += "\n--- DOCUMENT END ---\n"

        # Safety Truncate to ~40k characters to stay safe within quotas
        if len(full_context) > 40000:
            full_context = full_context[:40000] + "... [TRUNCATED]"

        print(f"Analyzing {len(full_context)} chars from {len(file_paths)} docs with {self.model_name}...")

        try:
            # 3. Define Schema (Pydantic) for structured JSON output
            class Category(BaseModel):
                name: str = Field(description="Short category name (e.g. 'Pricing')")
                description: str = Field(description="Simple description of what this tracks")

            class CategoryList(BaseModel):
                categories: List[Category]

            # 4. Prompt
            prompt = f"""
            You are setting up a Customer Support AI.
            Review the business documents below.
            Identify the **5 most important categories** of questions customers will ask this specific business.

            BUSINESS CONTEXT:
            {full_context}
            """

            # 5. Generate with Gemini
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CategoryList
                )
            )

            # 6. Parse Response
            try:
                # Try standard JSON parsing first
                result = json.loads(response.text)
                return result.get("categories", [])
            except:
                # Fallback to parsed object if SDK returns it directly
                if hasattr(response, 'parsed') and response.parsed:
                    return [cat.model_dump() for cat in response.parsed.categories]
                else:
                    return []

        except Exception as e:
            print(f"DEBUG: Gemini Error: {str(e)}")
            # Robust Fallback to prevent crashes
            return [
                {'name': 'General Inquiry', 'description': 'General questions about the business'},
                {'name': 'Support', 'description': 'Technical support requests'},
                {'name': 'Sales', 'description': 'Product inquiries and sales'}
            ]