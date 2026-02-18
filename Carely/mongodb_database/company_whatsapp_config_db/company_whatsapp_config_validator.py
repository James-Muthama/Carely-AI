# Company_WhatsApp_Config Collection Validator
# Stores encrypted credentials for WhatsApp Business API integration

company_whatsapp_config_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "company_id",
            "phone_number",
            "phone_number_id",
            "waba_id",
            "access_token",
            "verify_token",
            "status",
            "updated_at"
        ],
        "additionalProperties": False,
        "properties": {
            "_id": {
                "bsonType": "objectId"
            },
            "company_id": {
                "bsonType": "objectId",
                "description": "Unique identifier linking this config to a specific company user"
            },
            "phone_number": {
                "bsonType": "string",
                "description": "The display phone number (e.g., 254712345678) used for UI reference"
            },
            "phone_number_id": {
                "bsonType": "string",
                "description": "The Meta Graph API Phone Number ID required for sending messages"
            },
            "waba_id": {
                "bsonType": "string",
                "description": "The WhatsApp Business Account ID for billing and management"
            },
            "access_token": {
                "bsonType": "string",
                "description": "ENCRYPTED Permanent System User Token. Must be decrypted via security.py before use."
            },
            "verify_token": {
                "bsonType": "string",
                "description": "The custom token used to verify Webhook handshakes from Meta"
            },
            "status": {
                "bsonType": "string",
                "enum": ["connected", "disconnected", "error"],
                "description": "Current status of the integration connection"
            },
            "last_error": {
                "bsonType": ["string", "null"],
                "description": "Stores the last error message from Meta if connection fails"
            },
            "created_at": {
                "bsonType": "date",
                "description": "Timestamp when the integration was first set up"
            },
            "updated_at": {
                "bsonType": "date",
                "description": "Timestamp when the credentials or status were last updated"
            }
        }
    }
}