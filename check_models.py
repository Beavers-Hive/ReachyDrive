import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})

print("Listing models that support BIDI_GENERATE_CONTENT...")
for model in client.models.list():
    # Check supported generation methods
    print(f"Model Name: {model.name}")
    try:
        # Try to access supported_generation_methods if available, or just print everything
        print(f"  Supported Generation Methods: {getattr(model, 'supported_generation_methods', 'N/A')}")
    except:
        pass
