# list_models.py
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("📋 Available models for your API key:")
for m in genai.list_models():
    print("-", m.name)
