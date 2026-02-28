import os
from datetime import datetime
from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, jsonify, session, current_app, redirect, url_for
from Carely.app.utils import login_required
from Carely.mongodb_database.connection import client

from Carely.business_facing_agent.Business_Agent import BusinessAnalyticsAgent

# Create the Blueprint
business_bp = Blueprint('business_agent', __name__)

# Initialize Collections
documents_collection = client.Carely.Company_Documents
categories_collection = client.Carely.Company_Conversation_Categories
analytics_collection = client.Carely.Business_Analytics


@business_bp.route('/business_agent', methods=['GET'])
@login_required
def business_agent():
    """Display the Business Agent Chat Interface/Dashboard"""
    return render_template('business_agent.html')


@business_bp.route('/business_agent/api/categories', methods=['GET', 'POST'])
@login_required
def manage_categories_api():
    """
    API Endpoint called by the 'Save & Activate' button in the HTML.
    Handles JSON data to save categories to MongoDB.
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'User not found'}), 404

    company_id = ObjectId(user_id)

    # GET: Retrieve current categories (if needed for frontend loading)
    if request.method == 'GET':
        doc = categories_collection.find_one({"company_id": company_id})
        return jsonify({
            'status': 'success',
            'categories': doc.get('categories', []) if doc else []
        })

    # POST: Save new categories
    if request.method == 'POST':
        # The HTML JavaScript sends strictly JSON
        if request.is_json:
            data = request.get_json()
            categories = data.get('categories')
        else:
            # Fallback for safety
            data = request.get_json(force=True, silent=True)
            categories = data.get('categories') if data else []

        if not categories:
            return jsonify({'status': 'error', 'message': 'No categories provided'}), 400

        try:
            # Save to MongoDB
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
            print(f"Database Error: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500


@business_bp.route('/business_agent/categories')
@login_required
def category_setup():
    """
    Renders the setup page (business_categories.html).
    - Checks if a PDF exists.
    - If no categories exist yet, runs the Agent to generate suggestions.
    """
    company_id = session.get('user_id')
    if not company_id:
        return redirect(url_for('auth.login'))

    # 1. Check if the user has ANY completed document
    has_document = documents_collection.find_one({
        "company_id": ObjectId(company_id),
        "processing_status": "completed"
    })

    # If no document is uploaded yet, block access or show warning
    if not has_document:
        return render_template('business_no_document.html')

    # 2. Check for existing categories
    settings = categories_collection.find_one({"company_id": ObjectId(company_id)})
    existing_categories = settings.get('categories') if settings else None

    suggestions = []

    # 3. If no categories exist, run the Agent to get suggestions
    if not existing_categories:
        try:
            # Initialize the Agent using GROQ_API_KEY
            agent = BusinessAnalyticsAgent(
                groq_api_key=os.environ.get('GROQ_API_KEY'),
                mongodb_client=client,
                company_id=str(company_id)
            )
            # Run the analysis
            suggestions = agent.generate_category_suggestions()

        except Exception as e:
            print(f"Agent Analysis Error: {e}")
            # Fallback suggestions so the page doesn't crash
            suggestions = [
                {'name': 'General Inquiry', 'description': 'General questions about business hours or location.'},
                {'name': 'Support Request', 'description': 'Technical issues or help needed with a product.'}
            ]

    return render_template(
        'business_categories.html',
        existing_categories=existing_categories,
        suggestions=suggestions
    )


@business_bp.route('/business_agent/manage_categories')
@login_required
def manage_categories():
    """
    Renders the Management Dashboard (business_manage_categories.html).
    This allows the user to Add/Delete categories using the Table view.
    """
    company_id = session.get('user_id')
    if not company_id:
        return redirect(url_for('auth.login'))

    # Fetch existing categories to populate the 'Current List' table
    settings = categories_collection.find_one({"company_id": ObjectId(company_id)})
    existing_categories = settings.get('categories') if settings else []

    return render_template(
        'business_manage_categories.html', # Make sure your new HTML file is named this
        existing_categories=existing_categories
    )


@business_bp.route('/business_agent/dashboard_stats', methods=['GET'])
@login_required
def dashboard_stats():
    """
    Endpoint for future dashboard statistics (placeholder).
    """
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