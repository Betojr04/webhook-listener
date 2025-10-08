import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Test different model names
test_models = [
    "gemini-pro",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "models/gemini-pro",
    "models/gemini-1.5-flash",
    "models/gemini-1.5-pro",
]

print("Testing which Gemini models work...\n")

for model_name in test_models:
    try:
        print(f"Trying: {model_name}")
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content("Say 'Hello!'")
        print(f"✅ SUCCESS with {model_name}")
        print(f"   Response: {response.text}\n")
        break  # Stop at first working model
    except Exception as e:
        print(f"❌ Failed: {e}\n")
