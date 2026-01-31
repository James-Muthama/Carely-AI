from flask import Blueprint, render_template, request, jsonify, session, current_app
from datetime import datetime
from bson.objectid import ObjectId
from Carely.app.utils import login_required
from Carely.mongodb_database.connection import client

# Create the Blueprint
business_bp = Blueprint('business_agent', __name__)

# Initialize Collections
# (Assuming you created this collection using the validator script provided earlier)
categories_collection = client.Carely.Company_Conversation_Categories
analytics_collection = client.Carely.Business_Analytics


@business_bp.route('/business_agent', methods=['GET'])
@login_required
def business_agent():
    """Display the Business Agent Chat Interface"""
    return render_template('business_agent.html')


# --- NEW ROUTES FOR BUSINESS ANALYTICS FEATURES ---

@business_bp.route('/business_agent/categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    """
    API Endpoint to Get or Save the business tracking categories.
    This connects to the 'Company_Conversation_Categories' collection.
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not found'}), 404

    company_id = ObjectId(user_id)

    if request.method == 'GET':
        # Retrieve existing categories for this company
        doc = categories_collection.find_one({"company_id": company_id})
        if doc:
            return jsonify({
                'status': 'success',
                'categories': doc.get('categories', [])
            })
        else:
            return jsonify({'status': 'success', 'categories': []})

    if request.method == 'POST':
        # Save or Update categories
        data = request.get_json()
        if not data or 'categories' not in data:
            return jsonify({'error': 'Invalid data'}), 400

        categories = data['categories']

        # Validates against the schema you created earlier automatically
        # (if validator is active on MongoDB)
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


@business_bp.route('/business_agent/dashboard_stats', methods=['GET'])
@login_required
def dashboard_stats():
    """
    API to fetch real-time stats for the Business Analytics Dashboard.
    (This is a placeholder for where your aggregation logic will go)
    """
    try:
        # Example: Fetching simple counts (You will expand this with real RAG analytics later)
        stats = {
            "total_conversations": 0,
            "sentiment_score": "Neutral",
            "top_category": "None",
            "pending_optimizations": 0
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500