import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Config:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    
    # Vertex AI Configurations (Uses Application Default Credentials)
    GOOGLE_CLOUD_PROJECT: str | None = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
    GOOGLE_GENAI_USE_VERTEXAI: bool = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() in ("true", "1", "yes")
    
    # Parallel Search API Key
    PARALLEL_API_KEY: str | None = os.getenv("PARALLEL_API_KEY")
    
    # Live partner mode
    LIVE_PARTNERS: bool = os.getenv("LIVE_PARTNERS", "False").lower() in ("true", "1", "yes")

    RUNTIME_REVISION: str = os.getenv("K_REVISION", "").strip()[:100] or "local"

config = Config()
