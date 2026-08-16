# app/onboarding/routes.py
"""
Onboarding REST API Blueprint.

Exposes state machine endpoints, telemetry pre-population, proposal generation,
and calendar commitment for the first-time onboarding lifecycle.
"""

import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.onboarding.prepopulate_service import TelemetryPrepopulateService
from app.onboarding.service import (
    get_onboarding_state,
    save_onboarding_step,
    generate_onboarding_proposal,
    commit_onboarding
)

onboarding_bp = Blueprint("onboarding", __name__)
logger = logging.getLogger(__name__)


@onboarding_bp.route("/state", methods=["GET"])
@jwt_required()
def get_state_route():
    """
    Returns current step, Athlete Profile, pre-populated biometrics, and Goal Set draft.
    """
    try:
        user_id = get_jwt_identity()
        state = get_onboarding_state(user_id)
        return jsonify(state), 200
    except Exception as e:
        logger.error(f"Error fetching onboarding state: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route("/step", methods=["POST"])
@jwt_required()
def save_step_route():
    """
    Persists data payload for the completed step and advances interview_step.
    """
    try:
        user_id = get_jwt_identity()
        payload = request.get_json() or {}
        step = payload.get("step")
        if step is None:
            return jsonify({"error": "Step number is required."}), 400

        data = payload.get("data") or {}
        next_step = payload.get("next_step")

        result = save_onboarding_step(
            user_id=user_id,
            step=int(step),
            data=data,
            next_step=int(next_step) if next_step is not None else None
        )
        return jsonify(result), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        logger.error(f"Error saving onboarding step: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route("/prepopulate", methods=["POST"])
@jwt_required()
def prepopulate_route():
    """
    Calculates 14-day rolling telemetry biometrics from connected devices or incoming payload.
    """
    try:
        user_id = get_jwt_identity()
        raw_payload = request.get_json() or {}
        data = TelemetryPrepopulateService.get_prepopulation_data(user_id, raw_payload=raw_payload)
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Error in onboarding prepopulate: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route("/generate-proposal", methods=["POST"])
@onboarding_bp.route("/generate_proposal", methods=["POST"])
@onboarding_bp.route("/proposal", methods=["POST"])
@jwt_required()
def generate_proposal_route():
    """
    Generates a tailored multi-week training proposal with gymbro.widget/v1 calendar_proposal widget envelope.
    """
    try:
        user_id = get_jwt_identity()
        payload = request.get_json() or {}
        horizon = payload.get("horizon")
        custom_notes = payload.get("custom_notes")

        proposal_bundle = generate_onboarding_proposal(
            user_id=user_id,
            horizon=horizon,
            custom_notes=custom_notes
        )
        return jsonify(proposal_bundle), 200
    except Exception as e:
        logger.error(f"Error generating proposal: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route("/commit", methods=["POST"])
@jwt_required()
def commit_route():
    """
    Validates proposal, bulk-inserts sessions to training_events, marks athlete active,
    and produces the Day 1 Welcome Briefing.
    """
    try:
        user_id = get_jwt_identity()
        payload = request.get_json() or {}
        proposal = payload.get("proposal")

        result = commit_onboarding(user_id, proposal=proposal)
        return jsonify(result), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Error committing onboarding plan: {e}")
        return jsonify({"error": str(e)}), 500
