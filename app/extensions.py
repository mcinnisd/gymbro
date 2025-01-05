# app/extensions.py

from flask_pymongo import PyMongo
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

# Initialize Flask extensions
mongo = PyMongo()
cors = CORS()
jwt = JWTManager()
