# Collection: Company_WhatsApp_Config
# Purpose: Stores credentials for connecting to the Meta/WhatsApp Cloud API

company_whatsapp_config_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "company_id",
            "phone_number",
            "phone_number_id",
            "waba_id",
            "access_token",
            "verify_token"
        ],
        "additionalProperties": False,  # Strict schema to prevent junk data
        "properties": {
            "_id": {
                "bsonType": "objectId"
            },
            "company_id": {
                "bsonType": "objectId",
                "description": "Links config to the specific company user"
            },
            # --- Fields from your HTML Form ---
            "phone_number": {
                "bsonType": "string",
                "description": "The displayed phone number (e.g., 2547...)"
            },
            "phone_number_id": {
                "bsonType": "string",
                "description": "The Meta Graph API Phone Number ID"
            },
            "waba_id": {
                "bsonType": "string",
                "description": "WhatsApp Business Account ID"
            },
            "access_token": {
                "bsonType": "string",
                "description": "Permanent System User Token (Encrypted ideally)"
            },
            "verify_token": {
                "bsonType": "string",
                "description": "The token used to verify webhooks from Meta"
            },
            # --- Status Tracking ---
            "status": {
                "enum": ["connected", "disconnected", "error"],
                "description": "Current status of the integration"
            },
            "last_error": {
                "bsonType": ["string", "null"],
                "description": "Stores the last error message from Meta if connection fails"
            },
            # --- Timestamps ---
            "created_at": {
                "bsonType": "date"
            },
            "updated_at": {
                "bsonType": "date"
            }
        }
    }
}