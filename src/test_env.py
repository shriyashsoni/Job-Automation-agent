import os
from dotenv import load_dotenv
print("Loading .env...")
load_dotenv()
print("AI_PROVIDER:", os.getenv("AI_PROVIDER"))
print("AI_API_KEY:", os.getenv("AI_API_KEY")[:10] + "...")
print("RESUME_PATH:", os.getenv("RESUME_PATH"))
print("Done.")
