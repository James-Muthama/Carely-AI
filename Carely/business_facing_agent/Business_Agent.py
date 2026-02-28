import os
import json
import pypdf
from typing import List, Dict, Optional
from bson import ObjectId
from flask import current_app

from groq import Groq


class BusinessAnalyticsAgent:
    """
    Business Analytics Agent using Groq.
    - Uses 'llama-3.1-8b-instant' for blazing fast inference and massive context.
    - Aggregates text from ALL uploaded company documents.
    """

    def __init__(self, groq_api_key: str, mongodb_client, company_id: str):
        self.groq_api_key = groq_api_key
        self.mongodb_client = mongodb_client

        if isinstance(company_id, str):
            self.company_id = ObjectId(company_id)
        else:
            self.company_id = company_id

        self.db = mongodb_client.Carely
        self.documents_collection = self.db.Company_Documents
        self.client = Groq(api_key=self.groq_api_key)

        # --- UPDATED MODEL ---
        # The new 8B model with a 128k context window
        self.model_name = "llama-3.1-8b-instant"

    def _get_all_document_paths(self) -> List[str]:
        docs = self.documents_collection.find(
            {"company_id": self.company_id, "processing_status": "completed"}
        )

        valid_paths = []
        for doc in docs:
            stored_path = doc.get('file_path')
            if not stored_path:
                continue

            actual_filename = os.path.basename(stored_path)
            potential_paths = []

            if current_app:
                potential_paths.append(os.path.join(current_app.config['UPLOAD_FOLDER'], actual_filename))

            potential_paths.append(os.path.abspath(stored_path))
            potential_paths.append(os.path.join(os.getcwd(), 'app', 'uploads', actual_filename))
            potential_paths.append(os.path.join(os.getcwd(), 'uploads', actual_filename))

            for path in potential_paths:
                if os.path.exists(path):
                    valid_paths.append(path)
                    break

        return valid_paths

    def _extract_text_from_pdf(self, file_path: str, max_pages: int = 15) -> str:
        """
        Extracts text from a single PDF.
        Increased max_pages to 15 since we now have a 128k context window.
        """
        try:
            reader = pypdf.PdfReader(file_path)
            text_content = []
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
        file_paths = self._get_all_document_paths()

        if not file_paths:
            return []

        full_context = ""
        for path in file_paths:
            file_text = self._extract_text_from_pdf(path)
            if file_text:
                full_context += f"\n--- DOCUMENT START: {os.path.basename(path)} ---\n"
                full_context += file_text
                full_context += "\n--- DOCUMENT END ---\n"

        # Expanded Safety Truncate: Now allows ~100,000 characters (approx 25k tokens)
        # safely well within the 128k limit of Llama 3.1
        if len(full_context) > 100000:
            full_context = full_context[:100000] + "... [TRUNCATED]"

        print(f"Analyzing {len(full_context)} chars from {len(file_paths)} docs with {self.model_name}...")

        try:
            prompt = f"""
            You are setting up a Customer Support AI.
            Review the business documents below.
            Identify the 5 most important categories of questions customers will ask this specific business.

            You MUST respond in valid JSON format exactly matching this structure:
            {{
                "categories": [
                    {{"name": "Category Name", "description": "Short description of what this tracks"}}
                ]
            }}

            BUSINESS CONTEXT:
            {full_context}
            """

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            try:
                result = json.loads(response.choices[0].message.content)
                return result.get("categories", [])
            except json.JSONDecodeError as e:
                print(f"DEBUG: JSON Parse Error: {e}")
                return []

        except Exception as e:
            print(f"DEBUG: Groq Error: {str(e)}")
            return [
                {'name': 'General Inquiry', 'description': 'General questions about the business'},
                {'name': 'Support', 'description': 'Technical support requests'},
                {'name': 'Sales', 'description': 'Product inquiries and sales'}
            ]