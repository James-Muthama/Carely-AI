customer_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "email", "phone_no", "password"],
        "properties": {
            "name": {
                "bsonType": "string",
                "description": "Enter the company name as a string"
            },
            "email": {
                "bsonType": "string",
                "pattern": r"^.+@.+\..+$",
                "description": "Enter a valid email address"
            },
            "phone_no": {
                "bsonType": "string",
                "description": "Enter a valid 10-digit phone number"
            },
            "password": {
                "bsonType": "string",
                "description": "Enter a password with at least 6 characters"
            },
            "profile_image": {
                "bsonType": "binData",
                "description": "Upload a profile image as binary data"
            }
        }
    }
}
