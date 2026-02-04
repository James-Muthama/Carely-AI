import os

from flask import Blueprint, render_template, request, jsonify, session, current_app
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
        if request.is_json:
            data = request.get_json()
            categories = data.get('categories')
        else:
            data = request.get_json(force=True, silent=True)
            categories = data.get('categories') if data else []

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


@business_bp.route('/business_agent/categories')
@login_required
def category_setup():
    """
    Renders the HTML page for setting up categories.
    """
    company_id = session['user_id']

    # Check for 'completed' document
    has_document = documents_collection.find_one({
        "company_id": ObjectId(company_id),
        "processing_status": "completed"
    })

    if not has_document:
        return render_template('business_no_document.html')

    settings = categories_collection.find_one({"company_id": ObjectId(company_id)})
    existing_categories = settings.get('categories') if settings else None

    suggestions = []

    # Only run Gemini if no categories exist
    if not existing_categories:
        try:
            # Instantiate the internal class we defined above
            agent = BusinessAnalyticsAgent(
                google_api_key=os.environ.get('GOOGLE_API_KEY'), # Better than config for now
                mongodb_client=client,
                company_id=session['user_id']
            )
            suggestions = agent.generate_category_suggestions()
        except Exception as e:
            print(f"Gemini Error: {e}")
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