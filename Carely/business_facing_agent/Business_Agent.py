import os
import json
import time
from typing import List, Dict, Optional
from bson import ObjectId
from google import genai
from google.genai import types
from flask import current_app
from pydantic import BaseModel, Field


class BusinessAnalyticsAgent:
    """
    Business Analytics Agent using Gemini 1.5 Flash.
    Fixed: Uses the most reliable Free Tier model to avoid 'Quota Exceeded / Limit 0' errors.
    """

    def __init__(self, google_api_key: str, mongodb_client, company_id: str):
        self.google_api_key = google_api_key
        self.mongodb_client = mongodb_client

        if isinstance(company_id, str):
            self.company_id = ObjectId(company_id)
        else:
            self.company_id = company_id

        self.db = mongodb_client.Carely
        self.documents_collection = self.db.Company_Documents

        self.client = genai.Client(api_key=self.google_api_key)

        # --- FIX IS HERE ---
        # Switched to 1.5 Flash. This model has the most stable/generous free tier
        # (15 RPM) and supports PDFs natively.
        self.model_name = "gemini-1.5-flash"

    def _get_document_path(self) -> Optional[str]:
        """Robustly finds the absolute path of the document."""
        doc = self.documents_collection.find_one(
            {"company_id": self.company_id, "processing_status": "completed"},
            sort=[("uploaded_at", -1)]
        )

        if not doc:
            print("DEBUG: ❌ No completed document found in database.")
            return None

        stored_path = doc.get('file_path')
        actual_filename = os.path.basename(stored_path)

        print(f"DEBUG: Looking for file: {actual_filename}")

        potential_paths = []
        if current_app:
            potential_paths.append(os.path.join(current_app.config['UPLOAD_FOLDER'], actual_filename))

        potential_paths.append(os.path.abspath(stored_path))
        potential_paths.append(os.path.join(os.getcwd(), 'app', 'uploads', actual_filename))
        potential_paths.append(os.path.join(os.getcwd(), 'uploads', actual_filename))

        for path in potential_paths:
            if os.path.exists(path):
                print(f"DEBUG: ✅ Found file at: {path}")
                return path

        print("DEBUG: ❌ File could not be found in any standard location.")
        return None

    def generate_category_suggestions(self) -> List[Dict[str, str]]:
        file_path = self._get_document_path()

        if not file_path:
            return []

        print(f"Analyzing document with {self.model_name}: {file_path}")

        try:
            # 1. Upload to Gemini
            with open(file_path, "rb") as f:
                file_upload = self.client.files.upload(
                    file=f,
                    config=types.UploadFileConfig(mime_type='application/pdf')
                )

            # 2. Wait for Processing
            while file_upload.state.name == "PROCESSING":
                time.sleep(1)
                file_upload = self.client.files.get(name=file_upload.name)

            if file_upload.state.name == "FAILED":
                raise ValueError(f"Gemini failed to process file. Error: {file_upload.error.message}")

            # 3. Define Schema using Pydantic
            class Category(BaseModel):
                name: str = Field(description="Short name of the category (e.g. 'Pricing')")
                description: str = Field(description="What this category tracks")

            class CategoryList(BaseModel):
                categories: List[Category]

            prompt = """
            You are an expert Business Analyst for a hackathon project.
            Analyze the attached business document deeply. 
            Identify the top 5 most critical categories for tracking customer conversations.
            Be specific to the business domain found in the document.
            """

            # 4. Generate Content
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[file_upload, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CategoryList
                )
            )

            # 5. Parse Response
            try:
                result = json.loads(response.text)
                categories = result.get("categories", [])
            except:
                if hasattr(response, 'parsed') and response.parsed:
                    categories = [cat.model_dump() for cat in response.parsed.categories]
                else:
                    categories = []

            print(f"DEBUG: ✅ Successfully generated {len(categories)} categories.")
            return categories

        except Exception as e:
            print(f"DEBUG: ❌ Gemini Analysis Error: {str(e)}")
            # Fallback
            return [
                {"name": "General Inquiry", "description": "General questions about the business"},
                {"name": "Pricing", "description": "Questions regarding costs and payments"},
                {"name": "Support", "description": "Technical or service-related assistance"}
            ]