import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(project_root)


from admin_validator import admin_validator
from mongodb_database.connection import client

db = client.Carely

# Check if collection exists
if "Admin" in db.list_collection_names():
    # Collection exists, modify it
    db.command("collMod", "Admin", validator=admin_validator)
    print("Validator applied to existing collection!")
else:
    # Collection doesn't exist, create it with validator
    db.create_collection("Admin", validator=admin_validator)
    print("Collection created with validator!")
