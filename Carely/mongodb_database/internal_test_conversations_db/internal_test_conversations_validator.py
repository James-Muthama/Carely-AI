# COLLECTION: Internal_Test_Conversations
# PURPOSE: Stores internal RAG playground sessions (Question-Answer Pairs)

internal_test_conversations_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["company_id"],
        "properties": {
            "company_id": {
                "bsonType": "objectId",
                "description": "The company identifying the test session"
            },
            "history": {
                "bsonType": ["array", "null"],
                "description": "Simple list of [Question, Answer] pairs",
                "items": {
                    "bsonType": "array",
                    "description": "A single exchange",
                    "items": {
                        "bsonType": "string"
                    },
                    "minItems": 2,
                    "maxItems": 2
                }
            },
            "session_info": {
                "bsonType": ["object", "null"],
                "properties": {
                    "session_id": {"bsonType": ["string", "null"]},
                    "tester_email": {
                        "bsonType": ["string", "null"],
                        "description": "Optional: Track WHICH employee ran this test"
                    }
                }
            },
            "created_at": {"bsonType": ["date", "null"]},
            "updated_at": {"bsonType": ["date", "null"]}
        }
    }
}