# app/__init__.py

import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request  # Imported 'request' here
from .config import DevelopmentConfig, ProductionConfig
from .extensions import mongo, cors, jwt, limiter
import os

# from flask_apscheduler import APScheduler
# from apscheduler.jobstores.mongodb import MongoDBJobStore
# from app.scheduler_jobs import scheduled_garmin_sync

def create_app():
    app = Flask(__name__)

    # Load configuration
    env = os.getenv('FLASK_ENV', 'development')
    if env == 'production':
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    # Initialize extensions
    mongo.init_app(app)
    
    # Adjust CORS based on environment
    if env == 'production':
        cors_origins = os.getenv("CORS_ORIGINS", "https://your-production-domain.com")
        cors.init_app(app, resources={r"/*": {"origins": cors_origins}})
    else:
        cors.init_app(app, resources={r"/*": {"origins": "*"}})  # Allow all origins in development

    jwt.init_app(app)
    limiter.init_app(app)

    app.mongo = mongo

    # Import and register blueprints
    from app.auth.routes import auth_bp
    from app.strava.routes import strava_bp
    from app.activities.routes import activities_bp
    from app.garmin.routes import garmin_bp
    # from app.food_logging.routes import food_logging_bp
    # from app.goals.routes import goals_bp
    # from app.summaries.routes import summaries_bp
    # Register additional blueprints similarly

    app.register_blueprint(auth_bp)
    app.register_blueprint(strava_bp, url_prefix="/strava")
    app.register_blueprint(garmin_bp, url_prefix="/garmin")
    app.register_blueprint(activities_bp)
    # app.register_blueprint(food_logging_bp)
    # app.register_blueprint(goals_bp)
    # app.register_blueprint(summaries_bp)

    # Set up logging
    if not app.debug:
        handler = RotatingFileHandler('error.log', maxBytes=100000, backupCount=3)
        handler.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)

    # scheduler = APScheduler()
    # scheduler.init_app(app)
    # scheduler.start()

    # # Register scheduled jobs
    # scheduler.add_job(
    #     id='Daily Garmin Sync',
    #     func=scheduled_garmin_sync,
    #     trigger='cron',
    #     hour=0,
    #     minute=0
    # )

    # Handle 404 Errors
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not Found"}), 404

    # Handle 500 Errors
    @app.errorhandler(500)
    def internal_error(error):
        # Log the error details
        app.logger.error(f"Server Error: {error}, Path: {request.path}")
        return jsonify({"error": "Internal Server Error"}), 500

    return app