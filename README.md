# Carely AI

**Intelligent Customer Engagement & Business Intelligence Platform**

Carely AI is a dual-agent system designed to help small and medium-sized businesses (SMBs) automate customer support while deriving actionable insights from every interaction. Built on **Google’s Gemini Large Language Model (LLM)**, it combines real-time automated support with deep business analytics to create a continuous feedback loop that improves customer service over time.

---

## 🚀 About the Project

Carely AI solves the disconnect between customer inquiries and business knowledge. Instead of static chatbots, Carely AI uses **Retrieval-Augmented Generation (RAG)** to "read" your internal business documents—FAQs, pricing sheets, policies, and operating hours—to generate accurate, brand-aligned responses.

But it goes beyond just answering questions. Carely AI listens. Its **Business Analytics Agent** analyzes conversation logs to categorize topics, detect gaps in knowledge, and identify high-priority customer concerns, allowing businesses to make data-driven decisions.

### Core Philosophy
* **Automate:** Reduce response times with a context-aware AI support agent.
* **Analyze:** Uncover hidden patterns in customer conversations.
* **Improve:** Receive data-driven recommendations to refine your knowledge base.

---

## ✨ Key Features

### 🤖 Customer Support Agent (RAG-Powered)
* **Context-Aware Responses:** Indexes uploaded business documents (PDFs, text files) to provide factual answers using Google Gemini.
* **Brand Alignment:** Ensures responses are consistent with your company's tone and policies.
* **24/7 Availability:** Handles inquiries instantly, reducing human workload.

### 📊 Business Analytics Agent
* **Topic Modeling:** Automatically categorizes customer messages into meaningful business topics (e.g., "Pricing," "Technical Issues," "Availability").
* **Gap Analysis:** Detects questions where the AI had low confidence or lacked information, highlighting areas where your documentation needs improvement.
* **Insight Dashboard:** Visualizes frequently asked questions and emerging trends.

### 🔄 Continuous Learning Loop
* **Smart Recommendations:** Suggests specific content updates based on "failed" or low-confidence interactions.
* **Dynamic Knowledge Base:** Easily update your documents to instantly improve the AI's future performance.

---

## 🛠️ Tech Stack

* **LLM:** Google Gemini (via Google AI Studio)
* **Backend:** Python (Flask)
* **Vector Database:** ChromaDB (for document indexing and retrieval)
* **Primary Database:** MongoDB (for storing conversation logs and analytics)
* **Frontend:** HTML/CSS/JavaScript

---

## 📂 Project Structure

```bash
Carely/
├── business_facing_agent/   # Logic for analytics and insights generation
├── customer_facing_agent/   # Logic for RAG and handling customer queries
├── chroma_db/               # Local vector storage for business documents
├── mongodb_database/        # Database connection and models
├── static/                  # CSS, Images, and JavaScript files
├── templates/               # HTML templates for the web interface
├── uploads/                 # Storage for uploaded business documents
├── app.py                   # Main Flask application entry point
└── .env                     # API keys and configuration secrets