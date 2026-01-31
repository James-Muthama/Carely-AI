import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("app.secret_key", "dev_key")
    ALLOWED_IP = os.environ.get("allowed_ip")
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
    EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
    RECAPTCHA_SITE_KEY = os.environ.get("RECAPTCHA_SITE_KEY")
    RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY")
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB limit