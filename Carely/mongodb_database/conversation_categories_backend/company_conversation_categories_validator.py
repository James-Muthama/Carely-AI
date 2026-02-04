# CompanyConversationCategories Collection Validator
# This validator defines the schema for storing the specific categories
# a business wants to track in their analytics dashboard.

company_conversation_categories_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["company_id", "categories", "created_at"],
        "additionalProperties": False,  # Strict mode: rejects unknown fields
        "properties": {
            "_id": {
                "bsonType": "objectId"
            },
            "company_id": {
                "bsonType": "objectId",
                "description": "Enter the unique company/customer identifier as an ObjectId"
            },
            "categories": {
                "bsonType": "array",
                "minItems": 1,   # Constraint: Must have at least 1 category
                "maxItems": 20,  # Constraint: limit to 20 to prevent UI clutter
                "description": "Enter the list of categories the business wants to track",
                "items": {
                    "bsonType": "object",
                    "required": ["name"],
                    "additionalProperties": False, # Strict mode for items
                    "properties": {
                        "name": {
                            "bsonType": "string",
                            "minLength": 1,   # Constraint: No empty names
                            "maxLength": 50,  # Constraint: Keep names short for UI
                            "description": "The name of the category (e.g., 'Complaints')"
                        },
                        "description": {
                            "bsonType": ["string", "null"],
                            "maxLength": 300, # Constraint: Keep descriptions concise
                            "description": "A brief description helping the AI understand what belongs in this category"
                        }
                    }
                }
            },
            "created_at": {
                "bsonType": "date",
                "description": "Enter the timestamp when these categories were defined"
            },
            "updated_at": {
                "bsonType": ["date", "null"],
                "description": "Enter the timestamp when the categories were last modified"
            }
        }
    }
}