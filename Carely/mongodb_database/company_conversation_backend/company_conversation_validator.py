# CompanyConversations Collection Validator
# This validator defines the schema for storing conversation history in the RAG system
# Each record contains the complete conversation history for a company with metadata

company_conversations_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["company_id"],
        "properties": {
            "company_id": {
                "bsonType": "objectId",
                "description": "Enter the unique company/customer identifier as a string"
            },
            "history": {
                "bsonType": ["array", "null"],
                "description": "Enter array of conversation exchanges as question-answer pairs",
                "items": {
                    "bsonType": "array",
                    "description": "Enter a conversation exchange as [question, answer] array",
                    "items": {
                        "bsonType": "string",
                        "description": "Enter question or answer text as string"
                    },
                    "minItems": 2,
                    "maxItems": 2
                }
            },
            "session_info": {
                "bsonType": ["object", "null"],
                "description": "Enter additional session information as an object",
                "properties": {
                    "session_id": {
                        "bsonType": ["string", "null"],
                        "description": "Enter the session identifier as a string"
                    },
                    "user_agent": {
                        "bsonType": ["string", "null"],
                        "description": "Enter the user agent information from browser"
                    },
                    "ip_address": {
                        "bsonType": ["string", "null"],
                        "description": "Enter the IP address of the user"
                    }
                }
            },
            "conversation_metadata": {
                "bsonType": ["object", "null"],
                "description": "Enter metadata about the conversation as an object",
                "properties": {
                    "total_questions": {
                        "bsonType": ["int", "null"],
                        "description": "Enter the total number of questions asked as integer"
                    },
                    "average_response_time": {
                        "bsonType": ["double", "null"],
                        "description": "Enter the average response time in seconds as decimal"
                    },
                    "topics_discussed": {
                        "bsonType": ["array", "null"],
                        "description": "Enter array of topics discussed in the conversation",
                        "items": {
                            "bsonType": "string",
                            "description": "Enter topic as string"
                        }
                    }
                }
            },
            "created_at": {
                "bsonType": ["date", "null"],
                "description": "Enter the timestamp when conversation was first created"
            },
            "updated_at": {
                "bsonType": ["date", "null"],
                "description": "Enter the timestamp when conversation was last updated"
            }
        }
    }
}