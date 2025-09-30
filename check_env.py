import os
from dotenv import load_dotenv

load_dotenv()

print("🔍 CHECKING ENVIRONMENT VARIABLES:")
print(f"SUPABASE_URL: {os.getenv('SUPABASE_URL')}")
print(f"SUPABASE_KEY: {os.getenv('SUPABASE_KEY')}")
print(f"GROQ_API_KEY_1: {os.getenv('GROQ_API_KEY_1')}")
print(f"REDIS_URL: {os.getenv('REDIS_URL')}")
