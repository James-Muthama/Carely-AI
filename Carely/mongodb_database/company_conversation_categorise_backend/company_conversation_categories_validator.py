# CompanyConversationCategories Collection Validator
# This validator defines the schema for storing the specific categories
# a business wants to track in their analytics dashboard.

company_conversation_categories_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["company_id", "categories", "created_at"],
        "properties": {
            "company_id": {
                "bsonType": "objectId",
                "description": "Enter the unique company/customer identifier as an ObjectId"
            },
            "categories": {
                "bsonType": "array",
                "description": "Enter the list of categories the business wants to track",
                "items": {
                    "bsonType": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {
                            "bsonType": "string",
                            "description": "The name of the category (e.g., 'Complaints', 'Sales Leads')"
                        },
                        "description": {
                            "bsonType": ["string", "null"],
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