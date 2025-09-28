import os
import dotenv

# Load environment variables from .env file
dotenv.load_dotenv(dotenv_path="./secrets/.env", override=True)



class ApiConfig:
    NAME = os.getenv("API_NAME") or "My Application"
    DESCRIPTION = os.getenv("API_DESCRIPTION") or "My Application Description"

    HOST = os.getenv("API_HOST") or "0.0.0.0"
    PORT = int(os.getenv("API_PORT") or 8000)

    VERSION = os.getenv("API_VERSION") or "1.0.0"
    DEBUG = os.getenv("API_DEBUG") or False

    MASTER_KEY = os.getenv("API_MASTER_KEY") or "master_key"

    BASE_URL = os.getenv("API_BASE_URL") or "http://localhost:8000"