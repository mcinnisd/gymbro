# app/config.py

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # General Config
    SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key")
    DEBUG = False

    # MongoDB Configuration
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/gymbro_db")

    # JWT Configuration
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your_jwt_secret_key")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    TOKEN_EXPIRATION_MINUTES = int(os.getenv("TOKEN_EXPIRATION_MINUTES", 60))

    # Strava OAuth Configuration
    STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
    STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
    REDIRECT_URI = os.getenv("REDIRECT_URI", "http://127.0.0.1:5000/exchange_token")

    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # config.py (continued)

    # SCHEDULER_JOBSTORES = {
    #     'default': {
    #         'type': 'mongodb',
    #         'database': 'gymbro_db',
    #         'collection': 'apscheduler_jobs',
    #         'host': '127.0.0.1',
    #         'port': 27017,
    #     }
    # }

    # SCHEDULER_API_ENABLED = True
    # SCHEDULER_TIMEZONE = "UTC"
    # SCHEDULER_JOBSTORES = {
    #     'default': {
    #         'type': 'memory'  # Use 'mongodb' for persistent jobstore in production
    #     }
    # }
    # SCHEDULER_EXECUTORS = {
    #     'default': {
    #         'type': 'threadpool',
    #         'max_workers': 20
    #     }
    # }
    # SCHEDULER_JOB_DEFAULTS = {
    #     'coalesce': False,
    #     'max_instances': 3
    # }

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False


