from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.supabase_client import supabase
import logging

analytics_bp = Blueprint('analytics', __name__)
logger = logging.getLogger(__name__)

@analytics_bp.route("/baselines", methods=["GET"])
@jwt_required()
def get_user_baselines():
    """
    Fetch calculated fitness baselines for the user.
    """
    user_id = get_jwt_identity()
    try:
        res = supabase.table("user_baselines").select("baselines").eq("user_id", user_id).eq("metric_category", "running").execute()
        if res.data:
            return jsonify(res.data[0]["baselines"]), 200
        else:
            return jsonify({}), 200 # Return empty object if no baselines yet
    except Exception as e:
        logger.error(f"Error fetching baselines for user {user_id}: {e}")
        return jsonify({"error": str(e)}), 500
@analytics_bp.route("/summary", methods=["GET"])
@jwt_required()
def get_analytics_summary():
    user_id = get_jwt_identity()
    try:
        from app.analytics.analytics_service import AnalyticsService
        
        # New Unifed Dynamic Response
        response_data = AnalyticsService.get_aggregated_metrics(user_id=user_id, days=90)
        
        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Error fetching analytics summary for user {user_id}: {e}")
        return jsonify({"error": str(e)}), 500
