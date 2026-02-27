import os
import requests
from datetime import datetime, timezone
from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify, session, current_app, redirect, url_for
from cryptography.fernet import Fernet
from Carely.app.utils import login_required
from Carely.mongodb_database.connection import client

whatsapp_bp = Blueprint('whatsapp_integration', __name__)

whatsapp_config_collection = client.Carely.Company_WhatsApp_Config


def get_cipher_suite():
    key = current_app.config.get('ENCRYPTION_KEY')
    if not key:
        return Fernet(Fernet.generate_key())
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_data(data: str) -> str:
    if not data:
        return None
    try:
        cipher_suite = get_cipher_suite()
        encrypted_bytes = cipher_suite.encrypt(data.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        print(f"Encryption Error: {e}")
        return None


def decrypt_data(token: str) -> str:
    if not token:
        return None
    try:
        cipher_suite = get_cipher_suite()
        decrypted_bytes = cipher_suite.decrypt(token.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        print(f"Decryption Error: {e}")
        return None


@whatsapp_bp.route('/whatsapp_integration', methods=['GET'])
@login_required
def whatsapp_integration_page():
    company_id = session.get('user_id')
    config = whatsapp_config_collection.find_one({"company_id": ObjectId(company_id)})

    # If already connected, optionally redirect them straight to the success/dashboard page
    if config and config.get('status') == 'connected':
        return redirect(url_for('whatsapp_integration.whatsapp_success_page'))

    has_token = False
    if config and config.get("access_token"):
        has_token = True

    context = {
        "status": config.get("status", "disconnected") if config else "disconnected",
        "phone_number": config.get("phone_number", "") if config else "",
        "phone_number_id": config.get("phone_number_id", "") if config else "",
        "waba_id": config.get("waba_id", "") if config else "",
        "has_token": has_token
    }

    return render_template('whatsapp_integration.html', **context)


@whatsapp_bp.route('/whatsapp_integration/success', methods=['GET'])
@login_required
def whatsapp_success_page():
    """Renders the success/dashboard page for a connected WhatsApp integration."""
    company_id = session.get('user_id')
    config = whatsapp_config_collection.find_one({"company_id": ObjectId(company_id)})

    if not config or config.get('status') != 'connected':
        return redirect(url_for('whatsapp_integration.whatsapp_integration_page'))

    # Build the full webhook URL for the UI
    host_url = request.host_url.rstrip('/')
    webhook_url = f"{host_url}/webhook"

    return render_template('whatsapp_success.html', config=config, webhook_url=webhook_url)


@whatsapp_bp.route('/whatsapp_integration/connect', methods=['POST'])
@login_required
def connect_whatsapp_api():
    try:
        data = request.get_json()
        company_id = session.get('user_id')

        required_fields = ['phone_number', 'phone_number_id', 'waba_id']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'status': 'error', 'message': f'Missing field: {field}'}), 400

        access_token_plain = data.get('access_token')

        # Determine the token to use for testing (either newly provided or existing decrypted)
        token_to_test = access_token_plain
        if not token_to_test:
            existing_config = whatsapp_config_collection.find_one({"company_id": ObjectId(company_id)})
            if existing_config and existing_config.get("access_token"):
                token_to_test = decrypt_data(existing_config["access_token"])

        if not token_to_test:
            return jsonify({'status': 'error', 'message': 'Access token is required.'}), 400

        test_url = f"https://graph.facebook.com/v18.0/{data['phone_number_id']}"
        headers = {"Authorization": f"Bearer {token_to_test}"}

        api_response = requests.get(test_url, headers=headers)
        if api_response.status_code != 200:
            error_data = api_response.json()
            error_msg = error_data.get('error', {}).get('message', 'Invalid credentials.')
            return jsonify({'status': 'error', 'message': f'Meta API Rejected Credentials: {error_msg}'}), 401

        encrypted_token = None
        if access_token_plain:
            encrypted_token = encrypt_data(access_token_plain)
            if not encrypted_token:
                return jsonify({'status': 'error', 'message': 'Encryption failed. Check server logs.'}), 500

        update_fields = {
            "phone_number": data['phone_number'],
            "phone_number_id": data['phone_number_id'],
            "waba_id": data['waba_id'],
            "status": "connected",
            "updated_at": datetime.now(timezone.utc)
        }

        if encrypted_token:
            update_fields["access_token"] = encrypted_token

        verify_token = data.get('verify_token', f"carely_ai_secure_token_{company_id}")

        whatsapp_config_collection.update_one(
            {"company_id": ObjectId(company_id)},
            {
                "$set": update_fields,
                "$setOnInsert": {
                    "created_at": datetime.now(timezone.utc),
                    "verify_token": verify_token
                }
            },
            upsert=True
        )

        return jsonify({'status': 'success', 'message': 'Credentials verified and saved successfully'})

    except requests.exceptions.RequestException as e:
        return jsonify({'status': 'error', 'message': f'Failed to contact Meta servers: {str(e)}'}), 502
    except Exception as e:
        print(f"WhatsApp Connection Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@whatsapp_bp.route('/webhook', methods=['GET'])
def webhook_verify():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode and token:
        if mode == 'subscribe':
            exists = whatsapp_config_collection.find_one({"verify_token": token})

            if exists:
                return challenge, 200
            else:
                return "Forbidden", 403

    return "Bad Request", 400


@whatsapp_bp.route('/webhook', methods=['POST'])
def webhook_handler():
    try:
        body = request.get_json()

        if body.get("object") == "whatsapp_business_account":
            return jsonify({"status": "received"}), 200
        else:
            return jsonify({"status": "ignored", "message": "Not a WhatsApp event"}), 404

    except Exception as e:
        print(f"Webhook Error: {e}")
        return jsonify({"status": "error"}), 500