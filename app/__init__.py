# app/__init__.py

import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request
from .config import DevelopmentConfig, ProductionConfig
from .extensions import cors, jwt, limiter
import os

def create_app():
    app = Flask(__name__)

    # Load configuration based on FLASK_ENV
    env = os.getenv('FLASK_ENV', 'development')
    if env == 'production':
        app.config.from_object(ProductionConfig)
    else:
        app.config.from_object(DevelopmentConfig)

    # Initialize CORS
    if app.debug or env == 'development':
        # In development, allow requests from any origin (Expo web on port 8081/8082, Expo tunnels, localhost, LAN IPs)
        cors.init_app(app, resources={r"/*": {"origins": r"https?://.*"}}, supports_credentials=True)
    else:
        cors_origins_str = app.config.get("CORS_ORIGIN") or "http://localhost:3000,http://localhost:8081"
        cors_origins = [orig.strip() for orig in cors_origins_str.split(",") if orig.strip()]
        cors.init_app(app, resources={r"/*": {"origins": cors_origins}}, supports_credentials=True)

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
    from app.nutrition.routes import nutrition_bp
    from app.journal.routes import journal_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(activities_bp, url_prefix="/activities")
    app.register_blueprint(strava_bp, url_prefix="/strava")
    app.register_blueprint(garmin_bp, url_prefix="/garmin")
    app.register_blueprint(chats_bp, url_prefix="/chats")
    app.register_blueprint(analytics_bp, url_prefix="/analytics")
    app.register_blueprint(nutrition_bp, url_prefix="/nutrition")
    app.register_blueprint(journal_bp, url_prefix="/journal")
    
    from app.coach.routes import coach_bp
    app.register_blueprint(coach_bp, url_prefix="/coach")
    
    from app.calendar.routes import calendar_bp
    app.register_blueprint(calendar_bp, url_prefix="/calendar")

    from app.biomarkers.routes import biomarkers_bp
    app.register_blueprint(biomarkers_bp)

    from app.telemetry.routes import telemetry_bp
    app.register_blueprint(telemetry_bp, url_prefix="/telemetry")

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