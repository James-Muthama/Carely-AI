import os
from datetime import datetime, timezone
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, session, current_app
from Carely.app.utils import login_required
from Carely.mongodb_database.connection import client

# Create the Blueprint
whatsapp_bp = Blueprint('whatsapp_integration', __name__)

# Collection Reference
whatsapp_config_collection = client.Carely.Company_WhatsApp_Config


@whatsapp_bp.route('/whatsapp_integration', methods=['GET'])
@login_required
def whatsapp_integration_page():
    """
    Renders the WhatsApp Integration dashboard.
    Fetches existing config to show status/details if already connected.
    """
    company_id = session.get('user_id')

    # Check if config exists
    config = whatsapp_config_collection.find_one({"company_id": ObjectId(company_id)})

    context = {
        "status": config.get("status", "disconnected") if config else "disconnected",
        "phone_number": config.get("phone_number", "") if config else "",
        "waba_id": config.get("waba_id", "") if config else "",
        # Don't send the full access token back to UI for security
        "has_token": bool(config.get("access_token")) if config else False
    }

    return render_template('whatsapp_integration.html', **context)


@whatsapp_bp.route('/whatsapp_integration/connect', methods=['POST'])
@login_required
def connect_whatsapp_api():
    """
    API to save WhatsApp Credentials to MongoDB.
    """
    try:
        data = request.get_json()
        company_id = session.get('user_id')

        # 1. Validate Input
        required_fields = ['phone_number', 'phone_number_id', 'waba_id', 'access_token']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'status': 'error', 'message': f'Missing field: {field}'}), 400

        # 2. Prepare Document
        config_doc = {
            "company_id": ObjectId(company_id),
            "phone_number": data['phone_number'],
            "phone_number_id": data['phone_number_id'],
            "waba_id": data['waba_id'],
            "access_token": data['access_token'],

            # Generate or keep verify token (used for Webhook handshake)
            "verify_token": data.get('verify_token', f"carely_ai_secure_token_{company_id}"),

            "status": "connected",  # Assumed connected if data is saved
            "updated_at": datetime.now(timezone.utc)
        }

        # 3. Upsert to MongoDB
        result = whatsapp_config_collection.update_one(
            {"company_id": ObjectId(company_id)},
            {
                "$set": config_doc,
                "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
            },
            upsert=True
        )

        return jsonify({'status': 'success', 'message': 'Credentials saved successfully'})

    except Exception as e:
        print(f"WhatsApp Connection Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# =========================================================================
# WEBHOOK ROUTE (EXTERNAL FACING)
# This is the URL you provide to Meta: https://your-domain.com/webhook
# =========================================================================

@whatsapp_bp.route('/webhook', methods=['GET'])
def webhook_verify():
    """
    Handles the Webhook Verification Challenge from Meta.
    """
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode and token:
        if mode == 'subscribe':
            # Check if this token matches ANY company in our DB
            # (In production, you might want stricter checks)
            exists = whatsapp_config_collection.find_one({"verify_token": token})

            if exists:
                print("WEBHOOK_VERIFIED")
                return challenge, 200
            else:
                return "Forbidden", 403

    return "Bad Request", 400


@whatsapp_bp.route('/webhook', methods=['POST'])
def webhook_handler():
    """
    Receives incoming WhatsApp messages from Meta.
    """
    try:
        body = request.get_json()
        print(f"Incoming Webhook: {body}")

        # TODO: Add logic here to:
        # 1. Parse the message (sender, text)
        # 2. Find which company owns this phone number ID
        # 3. Trigger the RAG Agent to generate a reply
        # 4. Send the reply back via WhatsApp API

        return jsonify({"status": "received"}), 200

    except Exception as e:
        print(f"Webhook Error: {e}")
        return jsonify({"status": "error"}), 500