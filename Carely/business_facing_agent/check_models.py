import os
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("❌ Error: GOOGLE_API_KEY not found in environment variables.")
else:
    print("Connecting to Google AI...")
    client = genai.Client(api_key=api_key)

    print("\n🔎 Checking available models for your API key:\n")
    try:
        # The new SDK returns model objects directly.
        # We just print the display name and resource name.
        for model in client.models.list():
            print(f"✅ {model.display_name}")
            print(f"   ID: {model.name}")
            print("-" * 30)

    except Exception as e:
        print(f"❌ Error listing models: {e}")