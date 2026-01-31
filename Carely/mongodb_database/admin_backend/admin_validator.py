admin_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["customer_id", "login_date", "logout_date"],
        "properties": {
            "customer_id": {
                "bsonType": "objectId",  # Assuming you store customer_id as a string
                "description": "Enter the customer's ID as a string"
            },
            "login_date": {
                "bsonType": "date",
                "description": "Enter the login date as a Date object"
            },
            "logout_date": {
                "bsonType": ["date", "null"],  # Allow null as well as date
                "description": "Enter the logout date as a Date object or null"
            }
        }
    }
}
