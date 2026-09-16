# test_gemini_key.py — run this standalone, not through main.py
import os
from dotenv import load_dotenv

load_dotenv()  # loads your .env file

key_name = "GOOGLE_API_KEY"  # change to whatever your report_writer.py actually reads
api_key =AQ.Ab8RN6L-PYxnXw8JIIEXssAs8G7a5z6QVULcv_YOAuRKHPvnUQ
print(f"Key loaded from env: {'YES' if api_key else 'NO'}")
print(f"Key preview: {api_key[:8]}..." if api_key else "No key found!")

from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key)
response = llm.invoke("Say hello in one sentence.")
print("SUCCESS:", response.content)