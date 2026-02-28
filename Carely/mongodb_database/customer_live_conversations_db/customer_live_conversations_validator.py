# COLLECTION: Customer_Live_Conversations
# PURPOSE: Stores real WhatsApp customer interactions with Analytics tags

customer_live_conversations_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["company_id", "customer_phone", "messages"],
        "additionalProperties": False,
        "properties": {
            "_id": {
                "bsonType": "objectId"
            },
            "company_id": {
                "bsonType": "objectId",
                "description": "Unique company identifier"
            },
            "customer_phone": {
                "bsonType": "string",
                "description": "WhatsApp Phone Number (Unique Key)"
            },
            "customer_name": {
                "bsonType": ["string", "null"],
                "description": "WhatsApp Profile Name"
            },
            "messages": {
                "bsonType": "array",
                "description": "Chronological list of all messages in this chat",
                "items": {
                    "bsonType": "object",
                    "required": ["role", "content", "timestamp"],
                    "additionalProperties": False,
                    "properties": {
                        "role": {
                            "enum": ["user", "assistant", "system"],
                            "description": "user = customer, assistant = your AI"
                        },
                        "content": {
                            "bsonType": "string",
                            "description": "The message text"
                        },
                        "timestamp": {
                            "bsonType": "date",
                            "description": "Exact time (Critical for Analytics)"
                        },
                        "status": {
                            "enum": ["sent", "delivered", "read", "failed", "received"],
                            "description": "WhatsApp delivery status"
                        },
                        "category": {
                            "bsonType": ["string", "null"],
                            "description": "E.g., 'Pricing', 'Complaint' (Classified by Business Agent)"
                        },
                        "sentiment_score": {
                            "bsonType": ["double", "null"],
                            "description": "-1.0 to 1.0 score"
                        }
                    }
                }
            },
            # --- SESSION METADATA ---
            "last_interaction_at": {
                "bsonType": "date",
                "description": "Helps quickly sort 'Recent Chats' in your dashboard"
            },
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"}
        }
    }
}