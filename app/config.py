# app/config.py

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # General settings
    SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")
    DEBUG = False

    # Supabase configuration
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
    # JWT configuration
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your_jwt_secret_key")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    TOKEN_EXPIRATION_MINUTES = int(os.getenv("TOKEN_EXPIRATION_MINUTES", 60))
    
    # OAuth (Strava) configuration
    STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
    STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
    REDIRECT_URI = os.getenv("REDIRECT_URI", "http://127.0.0.1:5001/exchange_token")
    
    # Other keys
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # CORS: Use a default for local development; override in production
    CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost:3001")

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False