from dotenv import load_dotenv, find_dotenv
import os
from pymongo import MongoClient
from urllib.parse import quote_plus

# Load environment variables from .env file
load_dotenv(find_dotenv())

# Retrieve password from environment variables
password = os.environ.get("MONGO_PWD")

if not password:
    raise ValueError("MONGO_PWD environment variable is not set")

# URL encode the password
encoded_password = quote_plus(password)

# Form the connection string - VERIFY THIS MATCHES YOUR ATLAS CLUSTER
connection_string = f"mongodb+srv://jamesmuthaiks:{encoded_password}@carely.dzgoojj.mongodb.net/?retryWrites=true&w=majority&appName=Carely"

# Create a MongoClient with timeout settings
try:
    client = MongoClient(
        connection_string,
        serverSelectionTimeoutMS=5000,  # 5 second timeout
        connectTimeoutMS=5000
    )

    # Test the connection
    client.admin.command('ping')
    print("✓ Successfully connected to MongoDB!")

except Exception as e:
    print(f"✗ Failed to connect to MongoDB: {e}")
    raise
