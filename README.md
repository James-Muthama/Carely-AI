# Carely AI 🚀

[![GitHub Repo](https://img.shields.io/badge/GitHub-Repository-181717?logo=github)](https://github.com/James-Muthama/Carely-AI)

**Carely AI** is an advanced, dual-agent Customer Relationship Management (CRM) platform. Originally conceptualized as an agentic-powered CRM solution for a hackathon, Carely bridges the gap between automated customer support and actionable business intelligence.

By leveraging Retrieval-Augmented Generation (RAG) and high-speed LLM classification, Carely not only answers customer queries based on uploaded company documents but also continuously analyzes conversation logs to visually report on sentiments, categorize inquiries, and autonomously identify gaps in a business's knowledge base.

---

## ✨ Key Features

### 1. Customer Support Agent (RAG)
- **Context-Aware Responses:** Automatically answers customer inquiries (via WhatsApp integration) using semantic search against uploaded business PDFs.
- **Smart Fallbacks:** If a customer asks a question outside the scope of the uploaded documents, the agent gracefully handles it and tags the conversation for review.
- **Persistent Memory:** Maintains conversation history for context-aware, multi-turn interactions.

### 2. Business Analytics Agent & Dashboard
- **Real-Time KPI Tracking:** Tracks total conversations, message volume, overall customer sentiment, and top interaction categories.
- **Dynamic Data Visualization:** Utilizes Chart.js for real-time line charts, doughnut charts, and bar charts.
- **Category Management:** Tracks specific types of inquiries (e.g., *Pricing Inquiries, Technical Support, Complaints*).

### 3. AI-Driven Knowledge Gap Discovery
- **Insight Generation:** Scans recent "Uncategorized" customer chats and cross-references them against the existing PDF knowledge base to identify missing information.
- **Actionable Recommendations:** Automatically suggests new tracking categories and specific FAQ documents the business should create to improve the RAG agent's accuracy.
- **Background Re-categorization:** When a new category is approved, a background thread seamlessly scans historical unmapped messages and re-categorizes them without freezing the UI.

---

## 🛠️ Tech Stack & Architecture

### Backend & Core Logic
- **Framework:** Python / Flask
- **LLM Provider:** [Groq](https://groq.com/) (Ultra-fast inference)
- **Models Used:**
  - `llama-3.3-70b-versatile`: Utilized by the Customer Support Agent for deep reasoning and accurate RAG formulation.
  - `llama-3.1-8b-instant`: Utilized by the Business Analytics Agent for lightning-fast JSON classification, sentiment scoring, and gap analysis across large context windows.
- **Vector Store:** ChromaDB for local embedding storage and retrieval.
- **Document Processing:** `pypdf` for text extraction.

### Database (MongoDB)
- **Company_Documents:** Stores metadata and paths to uploaded PDFs.
- **Company_Conversation_Categories:** Stores active tracking categories defined by the business or suggested by AI.
- **Customer_Live_Conversations:** Stores chronological arrays of chat messages per customer, tracking roles, content, timestamps, status, categories, and sentiment scores.

### Frontend
- **UI/UX:** HTML5, CSS3, JavaScript
- **Libraries:** Chart.js

---

## 📂 Project Structure

```text
Carely/
├── app/
│   ├── routes/
│   │   ├── auth_routes.py                 # Authentication and session handling
│   │   ├── business_agent_routes.py       # Analytics dashboard and gap analysis endpoints
│   │   ├── main_routes.py                 # Core navigation and landing pages
│   │   ├── rag_agent_routes.py            # Customer support RAG interface
│   │   └── whatsapp_integration_routes.py # Webhooks for WhatsApp messaging
│   ├── static/                            # CSS, images, and frontend assets
│   ├── templates/                         # HTML templates (Dashboards, Modals)
│   ├── config.py                          # Application configuration variables
│   ├── services.py                        # Shared business logic
│   └── utils.py                           # Helper functions and decorators (e.g., @login_required)
├── business_facing_agent/
│   └── Business_Agent.py                  # Gap analysis, PDF extraction, and recategorizer logic
├── chroma_db_<company_id>/                # Local vector store directories per company
├── customer_facing_agent/
│   ├── Customer_Agent.py                  # Orchestrator for RAG answering and fast classification
│   ├── document_processor.py             # PDF chunking and embedding generation
│   ├── history_manager.py                # Chat history context window management
│   ├── retrieval_engine.py               # LLM Chain execution and prompt formatting
│   └── vector_store.py                   # ChromaDB manager
├── mongodb_database/
│   ├── company_documents_db/             # Modular DB operations
│   ├── company_embeddings_db/
│   ├── company_info_db/
│   ├── company_whatsapp_config_db/
│   ├── conversation_categories_db/
│   ├── customer_live_conversations_db/
│   ├── internal_test_conversations_db/
│   └── connection.py                     # PyMongo client initialization
├── uploads/                              # Secure storage for uploaded company PDFs
├── .env                                  # Environment variables (API keys, URIs)
└── run.py                                # Application entry point
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.9+
- MongoDB URI (Local or Atlas)
- Groq API Key

### 1. Clone the Repository
```bash
git clone https://github.com/James-Muthama/Carely-AI.git
cd Carely-AI
```

### 2. Set Up Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Variables
Create a `.env` file in the root directory and add your credentials:

```env
# Flask Configuration
FLASK_APP=run.py
FLASK_ENV=development
app.secret_key=your_secure_flask_secret_key

# MongoDB
MONGO_URI=mongodb+srv://<username>:<password>@cluster.mongodb.net/Carely
MONGO_PWD="your_mongo_password"

# Model API Keys
GROQ_API_KEY="gsk_your_groq_api_key_here"

# Encryption
ENCRYPTION_KEY=your_encryption_key_here

# reCAPTCHA Keys
RECAPTCHA_SITE_KEY=your_recaptcha_site_key
RECAPTCHA_SECRET_KEY=your_recaptcha_secret_key

# Email Configuration
EMAIL_ADDRESS="your_email@gmail.com"
EMAIL_PASSWORD="your_gmail_app_password"

# Google OAuth Configuration
GOOGLE_OAUTH_CLIENT_ID=your_google_oauth_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your_google_oauth_client_secret
GOOGLE_PROJECT_ID=your_google_project_id

# OAuth Configuration
OAUTHLIB_INSECURE_TRANSPORT=1

# MCP Server Configuration
MCP_SERVER_URL=http://127.0.0.1:8000
```

### 5. Run the Application
```bash
flask run --port=5000
```

Navigate to `http://127.0.0.1:5000` in your browser.

---

## 💡 Usage Workflow

1. **Upload Knowledge:** The business uploads their operating procedures, pricing, and FAQ PDFs. The system chunks and embeds these documents into ChromaDB.
2. **Setup Categories:** The AI reads the PDFs and suggests initial categories. The business activates them to start tracking.
3. **Handle Chats:** As customers send messages, the Customer Support Agent answers via RAG. Concurrently, the Fast LLM tags the message with a Category and Sentiment Score (-1.0 to 1.0).
4. **Monitor:** The business reviews the Analytics Dashboard to see volume trends and overall satisfaction.
5. **Improve:** The business visits Agent Insights. The AI reviews messages tagged as "Uncategorized" and suggests new documents to write to fill the knowledge gaps, creating a continuous improvement loop.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/James-Muthama/Carely-AI/issues).

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).