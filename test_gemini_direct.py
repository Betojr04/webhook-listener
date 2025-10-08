import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

print("🔑 Key starts with:", key[:10])
print("📦 Model:", model_name)

genai.configure(api_key=key)
model = genai.GenerativeModel(model_name=model_name)

resp = model.generate_content("Write a haiku about Phoenix")
print("✅ Reply:", resp.text)
