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
    - Aggregates text from ALL uploaded company documents and cross-references them with live chats.
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
        self.live_conversations_collection = self.db.Customer_Live_Conversations
        self.categories_collection = self.db.Company_Conversation_Categories  # NEW
        self.client = Groq(api_key=self.groq_api_key)

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

        if len(full_context) > 100000:
            full_context = full_context[:100000] + "... [TRUNCATED]"

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
                {'name': 'Support', 'description': 'Technical support requests'}
            ]

    def generate_improvement_suggestions(self) -> dict:
        """
        Cross-references uploaded documents against unmapped chats to find knowledge gaps.
        """
        try:
            # 1. Fetch up to 50 recent Uncategorized messages
            pipeline = [
                {"$match": {"company_id": self.company_id}},
                {"$unwind": "$messages"},
                {"$match": {
                    "messages.role": "user",
                    "messages.category": {"$in": ["Uncategorized", None, ""]}
                }},
                {"$project": {"content": "$messages.content"}},
                {"$limit": 50}
            ]

            results = list(self.live_conversations_collection.aggregate(pipeline))

            if not results:
                return {
                    "new_categories": [{"name": "All Caught Up", "description": "Your agent is currently categorizing all interactions successfully."}],
                    "suggested_documents": [{"title": "Knowledge Base is Solid", "description": "No new unmapped questions detected in recent chats."}]
                }

            messages_text = "\n- ".join([r['content'] for r in results])

            # 2. Fetch the current business documents
            file_paths = self._get_all_document_paths()
            full_context = ""
            for path in file_paths:
                file_text = self._extract_text_from_pdf(path)
                if file_text:
                    full_context += f"\n--- DOCUMENT START: {os.path.basename(path)} ---\n"
                    full_context += file_text
                    full_context += "\n--- DOCUMENT END ---\n"

            if len(full_context) > 80000:
                full_context = full_context[:80000] + "... [TRUNCATED]"
            elif not full_context:
                full_context = "No business documents currently uploaded."

            # 3. Prompt the AI with strict instructions
            prompt = f"""
            You are a Business Intelligence Analyst. Your task is to identify knowledge gaps in an AI Customer Support Agent.

            STEP 1: Review the current Business Knowledge Base:
            {full_context}

            STEP 2: Review these recent customer messages that our AI failed to categorize:
            {messages_text}

            STEP 3: Compare them. What are customers asking about in the messages that is completely MISSING or insufficiently covered in the Business Knowledge Base?

            Respond EXACTLY in this JSON format. If you cannot find any suggestions, return empty arrays ([]), NEVER return null:
            {{
                "new_categories": [
                    {{"name": "Category Name", "description": "Why this category is needed based on what was talked about in the unmapped messages."}}
                ],
                "suggested_documents": [
                    {{"title": "Document Title", "description": "What specific information this document must contain to fill the knowledge gap."}}
                ]
            }}
            """

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant that outputs strictly valid JSON. Never output null."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            content = response.choices[0].message.content
            parsed_data = json.loads(content)

            if not parsed_data:
                return {
                    "new_categories": [],
                    "suggested_documents": [{"title": "No Clear Insights", "description": "The AI reviewed the messages but could not generate specific missing documents."}]
                }

            return parsed_data

        except Exception as e:
            print(f"DEBUG: Improvement Suggestion Error: {str(e)}")
            return {
                "new_categories": [],
                "suggested_documents": [{"title": "Error generating insights", "description": str(e)}]
            }

    def recategorize_unmapped_messages(self):
        """
        Scans all user messages that are currently 'Uncategorized' and
        attempts to classify them into the newly updated active categories.
        """
        print("DEBUG: Starting background recategorization process...")
        try:
            category_doc = self.categories_collection.find_one({"company_id": self.company_id})
            user_categories = [cat['name'] for cat in category_doc.get('categories', [])] if category_doc else []

            if not user_categories:
                return 0

            category_list_str = ", ".join(user_categories)

            query = {
                "company_id": self.company_id,
                "messages": {
                    "$elemMatch": {
                        "role": "user",
                        "category": {"$in": ["Uncategorized", None, ""]}
                    }
                }
            }

            docs = self.live_conversations_collection.find(query)
            updated_count = 0

            for doc in docs:
                messages = doc.get("messages", [])
                needs_db_update = False

                for msg in messages:
                    if msg.get("role") == "user" and msg.get("category") in ["Uncategorized", None, ""]:
                        text = msg.get("content", "")

                        prompt = f"""
                        Analyze the following customer message and provide classification.

                        Customer Message: "{text}"
                        Available Categories: [{category_list_str}]

                        Instructions:
                        1. Select the most relevant category from the list. 
                        2. If no categories are provided or the message doesn't fit, use "Uncategorized".

                        Respond ONLY in valid JSON:
                        {{
                            "category": "Selected Category"
                        }}
                        """
                        try:
                            response = self.client.chat.completions.create(
                                model=self.model_name,
                                messages=[
                                    {"role": "system",
                                     "content": "You are a precise data classifier that outputs only valid JSON."},
                                    {"role": "user", "content": prompt}
                                ],
                                response_format={"type": "json_object"},
                                temperature=0.1
                            )
                            result = json.loads(response.choices[0].message.content)
                            new_category = result.get("category")

                            if new_category and new_category in user_categories:
                                msg["category"] = new_category
                                needs_db_update = True
                                updated_count += 1

                        except Exception as parse_e:
                            print(f"DEBUG: Failed to classify msg: {parse_e}")

                if needs_db_update:
                    self.live_conversations_collection.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"messages": messages}}
                    )

            print(f"DEBUG: Recategorization complete. Successfully remapped {updated_count} messages.")
            return updated_count

        except Exception as e:
            print(f"DEBUG: Recategorization Critical Error: {str(e)}")
            return 0