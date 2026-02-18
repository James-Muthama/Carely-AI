import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(project_root)

from Carely.mongodb_database.connection import client
from customer_live_conversations_validator import customer_live_conversations_validator

db = client.Carely

# Print available collections for debugging
print("Available collections:", db.list_collection_names())

# The correct collection name should match what's used in your RAG system code
collection_name = "Customer_Live_Conversations"  # This matches the code: self.conversations_collection = self.db.CompanyConversations

try:
    # Check if collection exists
    if collection_name in db.list_collection_names():
        print(f"Collection '{collection_name}' exists, applying validator...")
        # Collection exists, modify it
        result = db.command("collMod", collection_name, validator=customer_live_conversations_validator)
        print(f"Validator applied to existing collection! Result: {result}")
    else:
        print(f"Collection '{collection_name}' doesn't exist, creating it with validator...")
        # Collection doesn't exist, create it with validator
        db.create_collection(collection_name, validator=customer_live_conversations_validator)
        print("Collection created with validator!")

        # Create recommended indexes
        conversations_collection = db[collection_name]

        # Create indexes for better performance
        conversations_collection.create_index([("company_id", 1)], unique=True)
        conversations_collection.create_index([("updated_at", 1)])

        print("Indexes created successfully!")

except Exception as e:
    print(f"Error: {e}")
    print(f"Error type: {type(e)}")

# Verify the collection was created/modified
print("\nFinal collections list:", db.list_collection_names())
