from flask import Blueprint, render_template, request, jsonify, session, current_app, redirect, url_for
from datetime import datetime
from bson.objectid import ObjectId
from Carely.app.utils import login_required
from Carely.mongodb_database.connection import client
from Carely.business_facing_agent.Business_Agent import BusinessAnalyticsAgent

# Create the Blueprint with the name 'business_agent'
business_bp = Blueprint('business_agent', __name__)

# Initialize Collections
documents_collection = client.Carely.Company_Documents
categories_collection = client.Carely.Company_Conversation_Categories
analytics_collection = client.Carely.Business_Analytics


@business_bp.route('/business_agent', methods=['GET'])
@login_required
def business_agent():
    """Display the Business Agent Chat Interface"""
    return render_template('business_agent.html')


# --- 1. THE API ROUTE (For Saving Data) ---
# Changed URL to /api/categories to avoid conflict
@business_bp.route('/business_agent/api/categories', methods=['GET', 'POST'])
@login_required
def manage_categories_api():
    """
    API Endpoint to Get (JSON) or Save the business tracking categories.
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not found'}), 404

    company_id = ObjectId(user_id)

    if request.method == 'GET':
        doc = categories_collection.find_one({"company_id": company_id})
        return jsonify({
            'status': 'success',
            'categories': doc.get('categories', []) if doc else []
        })

    if request.method == 'POST':
        # Used by the form in business_categories.html to save data
        # Check if the request is JSON (API call) or Form Data (HTML Form submit)
        if request.is_json:
            data = request.get_json()
            categories = data.get('categories')
        else:
            # Handle standard HTML form submission if necessary,
            # though your JS likely sends JSON.
            # For now, we assume your JS sends JSON.
            data = request.get_json(force=True, silent=True)
            categories = data.get('categories') if data else []

            # If standard form POST (not JSON), we might need to parse form fields
            # specific to how you implemented the form logic.
            # But based on previous steps, we are using JSON.

        if not categories:
            return jsonify({'error': 'Invalid data'}), 400

        try:
            categories_collection.update_one(
                {"company_id": company_id},
                {
                    "$set": {
                        "categories": categories,
                        "updated_at": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            return jsonify({'status': 'success', 'message': 'Categories saved successfully'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500


# --- 2. THE PAGE ROUTE (For Viewing HTML) ---
# This keeps the original URL you want the user to visit
@business_bp.route('/business_agent/categories')
@login_required
def category_setup():
    """
    Renders the HTML page for setting up categories.
    """
    company_id = session['user_id']

    # We check for a 'completed' document because we need text to analyze
    has_document = documents_collection.find_one({
        "company_id": ObjectId(company_id),
        "processing_status": "completed"
    })

    # If no document is found, render the "Blocker" page
    if not has_document:
        return render_template('business_no_document.html')

    settings = categories_collection.find_one({"company_id": ObjectId(company_id)})

    existing_categories = settings.get('categories') if settings else None

    suggestions = []

    # Only run Gemini analysis if no categories exist yet
    if not existing_categories:
        try:
            agent = BusinessAnalyticsAgent(
                google_api_key=current_app.config['GOOGLE_API_KEY'],
                mongodb_client=client,
                company_id=session['user_id']
            )
            suggestions = agent.generate_category_suggestions()
        except Exception as e:
            print(f"Gemini Error: {e}")
            # Fallback suggestions if API fails
            suggestions = [
                {'name': 'General', 'description': 'General inquiries'},
                {'name': 'Support', 'description': 'Technical support'}
            ]

    return render_template(
        'business_categories.html',
        existing_categories=existing_categories,
        suggestions=suggestions
    )


@business_bp.route('/business_agent/dashboard_stats', methods=['GET'])
@login_required
def dashboard_stats():
    try:
        stats = {
            "total_conversations": 0,
            "sentiment_score": "Neutral",
            "top_category": "None",
            "pending_optimizations": 0
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500