import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(project_root)

from mongodb_database.connection import client
from company_validator import customer_validator

db = client.Carely

# Check if collection exists
if "Customer" in db.list_collection_names():
    # Collection exists, modify it
    db.command("collMod", "Customer", validator=customer_validator)
    print("Validator applied to existing collection!")
else:
    # Collection doesn't exist, create it with validator
    db.create_collection("Customer", validator=customer_validator)
    print("Collection created with validator!")