from flask import session, current_app
from ..customer_facing_agent.Customer_Agent import CustomerSupportAgent
from ..mongodb_database.connection import client


def get_or_create_rag_system():
    company_id = session.get('user_id')
    if not company_id:
        return None

    rag_key = f'RAG_SYSTEM_{company_id}'

    # Access the app config via current_app proxy
    if rag_key not in current_app.config:
        try:
            rag_system = CustomerSupportAgent(
                groq_api_key=current_app.config['GROQ_API_KEY'],
                mongodb_client=client,
                company_id=company_id
            )
            current_app.config[rag_key] = rag_system
            session['rag_system_initialized'] = True
            return rag_system
        except Exception as e:
            print(f"Error: {str(e)}")
            return None
    return current_app.config.get(rag_key)