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
live_conversations_collection = client.Carely.Customer_Live_Conversations


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


@business_bp.route('/business_agent/analytics_dashboard', methods=['GET'])
@login_required
def analytics_dashboard():
    """Display the Chart.js Analytics Dashboard"""
    return render_template('analytics_dashboard.html')


@business_bp.route('/business_agent/api/dashboard_stats', methods=['GET'])
@login_required
def dashboard_stats():
    """
    In-depth real-time aggregation of WhatsApp messages.
    Provides Categories, Sentiment, Volume over time, and Recent Messages.
    """
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        company_id = ObjectId(user_id)

        # 1. Fetch tracked categories
        category_doc = categories_collection.find_one({"company_id": company_id})
        tracked_categories = [cat['name'] for cat in category_doc.get('categories', [])] if category_doc else []

        # 2. Get all user messages (flattened) sorted by newest first
        pipeline = [
            {"$match": {"company_id": company_id}},
            {"$unwind": "$messages"},
            {"$match": {"messages.role": "user"}},
            {"$project": {
                "phone": "$customer_phone",
                "name": "$customer_name",  # <--- NEW: Pulling the customer name
                "content": "$messages.content",
                "category": "$messages.category",
                "sentiment": "$messages.sentiment_score",
                "timestamp": "$messages.timestamp"
            }},
            {"$sort": {"timestamp": -1}}
        ]

        user_messages = list(live_conversations_collection.aggregate(pipeline))

        # 3. Process Data for the Dashboard
        total_messages = len(user_messages)
        total_conversations = live_conversations_collection.count_documents({"company_id": company_id})

        category_counts = {cat: 0 for cat in tracked_categories}
        category_counts["Uncategorized"] = 0

        sentiment_counts = {"Positive": 0, "Neutral": 0, "Negative": 0}
        total_sentiment_score = 0
        valid_sentiment_count = 0

        # For Volume over time (last 7 days)
        from collections import defaultdict
        daily_volume = defaultdict(int)

        recent_messages = []

        for idx, msg in enumerate(user_messages):
            # A. Categories
            cat = msg.get("category")
            if cat in category_counts:
                category_counts[cat] += 1
            elif cat:
                category_counts[cat] = category_counts.get(cat, 0) + 1
            else:
                category_counts["Uncategorized"] += 1

            # B. Sentiment (Thresholds: > 0.25 is Positive, < -0.25 is Negative)
            sentiment = msg.get("sentiment")
            if sentiment is not None:
                total_sentiment_score += sentiment
                valid_sentiment_count += 1
                if sentiment > 0.25:
                    sentiment_counts["Positive"] += 1
                elif sentiment < -0.25:
                    sentiment_counts["Negative"] += 1
                else:
                    sentiment_counts["Neutral"] += 1
            else:
                sentiment_counts["Neutral"] += 1

            # C. Daily Volume
            timestamp = msg.get("timestamp")
            if timestamp:
                date_str = timestamp.strftime('%Y-%m-%d')
                daily_volume[date_str] += 1

            # D. Recent Messages (Grab the top 5)
            if idx < 5:
                phone = msg.get("phone", "")
                masked_phone = f"...{phone[-4:]}" if len(phone) >= 4 else phone

                # Format the display name cleanly
                raw_name = msg.get("name")
                display_name = raw_name if raw_name and raw_name != "Unknown" else "WhatsApp User"

                recent_messages.append({
                    "customer_name": display_name,  # <--- NEW: Sending to frontend
                    "phone": masked_phone,
                    "content": msg.get("content", ""),
                    "category": cat or "Uncategorized",
                    "sentiment": sentiment if sentiment is not None else 0,
                    "time": timestamp.strftime('%I:%M %p, %b %d') if timestamp else "Unknown"
                })

        # Calculate Averages & Top Metrics
        top_category = "None"
        if total_messages > 0:
            top_category = max(category_counts, key=category_counts.get)

        avg_sentiment = (total_sentiment_score / valid_sentiment_count) if valid_sentiment_count > 0 else 0
        overall_sentiment_label = "Neutral 😐"
        if avg_sentiment > 0.25:
            overall_sentiment_label = "Positive 😃"
        elif avg_sentiment < -0.25:
            overall_sentiment_label = "Negative 😠"

        # Sort daily volume chronologically
        sorted_dates = sorted(daily_volume.keys())[-7:]
        volume_data = [daily_volume[date] for date in sorted_dates]
        formatted_dates = [datetime.strptime(d, '%Y-%m-%d').strftime('%b %d') for d in sorted_dates]

        return jsonify({
            "status": "success",
            "kpis": {
                "total_conversations": total_conversations,
                "total_messages_analyzed": total_messages,
                "top_category": top_category,
                "overall_sentiment": overall_sentiment_label
            },
            "charts": {
                "categories": {
                    "labels": list(category_counts.keys()),
                    "data": list(category_counts.values())
                },
                "sentiment": {
                    "labels": ["Positive", "Neutral", "Negative"],
                    "data": [sentiment_counts["Positive"], sentiment_counts["Neutral"], sentiment_counts["Negative"]]
                },
                "volume": {
                    "labels": formatted_dates if formatted_dates else ["No Data"],
                    "data": volume_data if volume_data else [0]
                }
            },
            "recent_messages": recent_messages
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': str(e)}), 500