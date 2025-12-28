# app/__init__.py

import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request
from .config import DevelopmentConfig, ProductionConfig
from .extensions import cors, jwt, limiter  # Removed 'mongo'
import os

def create_app():
    app = Flask(__name__)

    # Load configuration based on FLASK_ENV
    env = os.getenv('FLASK_ENV', 'development')
    if env == 'production':
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    # Remove Mongo initialization since we now use Supabase.
    # mongo.init_app(app)
    # app.mongo = mongo  # No longer needed.

    # Initialize CORS
    # Allow localhost:3000 specifically to support credentials
    cors.init_app(app, resources={r"/*": {"origins": ["http://localhost:3000"]}}, supports_credentials=True)

    # Initialize JWT and rate limiter
    jwt.init_app(app)
    limiter.init_app(app)

    # Register blueprints (ensure your routes now use Supabase instead of Mongo)
    from app.auth.routes import auth_bp
    from app.strava.routes import strava_bp
    from app.activities.routes import activities_bp
    from app.garmin.routes import garmin_bp
    from app.chats.routes import chats_bp
    from app.analytics.routes import analytics_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(activities_bp, url_prefix="/activities")
    app.register_blueprint(strava_bp, url_prefix="/strava")
    app.register_blueprint(garmin_bp, url_prefix="/garmin")
    app.register_blueprint(chats_bp, url_prefix="/chats")
    app.register_blueprint(analytics_bp, url_prefix="/analytics")
    
    from app.coach.routes import coach_bp
    app.register_blueprint(coach_bp, url_prefix="/coach")
    
    from app.calendar.routes import calendar_bp
    app.register_blueprint(calendar_bp, url_prefix="/calendar")

    # Set up logging if not in debug mode
    if not app.debug:
        handler = RotatingFileHandler('error.log', maxBytes=100000, backupCount=3)
        handler.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)

    # Simple route to list endpoints (for debugging)
    @app.route("/routes")
    def list_routes():
        import urllib
        output = []
        for rule in app.url_map.iter_rules():
            methods = ','.join(rule.methods)
            line = urllib.parse.unquote(f"{rule.endpoint} {methods} {rule.rule}")
            output.append(line)
        return "<br>".join(output)

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not Found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Server Error: {error}, Path: {request.path}")
        return jsonify({"error": "Internal Server Error"}), 500

    return app