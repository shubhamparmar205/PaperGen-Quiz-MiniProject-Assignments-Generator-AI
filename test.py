.\venv\Scripts\activateimport google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

try:
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    response = model.generate_content("Hello Gemini! which model are you specifc your type like flash pr whic exactly are you?")
    print(response.text)
except Exception as e:
    print("Error:", e)
