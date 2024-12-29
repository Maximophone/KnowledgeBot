# Load from environment variables or .env file
import os
from dotenv import load_dotenv

load_dotenv()

ASSEMBLY_AI_KEY = os.getenv("ASSEMBLY_AI_KEY")
GDRIVE_API_KEY = os.getenv("GDRIVE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG = os.getenv("OPENAI_ORG")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
HUGGING_FACE = os.getenv("HUGGING_FACE")
CODA_API_KEY = os.getenv("CODA_API_KEY")
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
