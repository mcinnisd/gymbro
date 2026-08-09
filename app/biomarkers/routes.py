from flask import Blueprint, request, jsonify
import logging
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.gcp.storage_service import upload_file_to_gcs
from app.biomarkers.pdf_service import parse_lab_pdf_with_gemini
from app.biomarkers.service import save_lab_panel

biomarkers_bp = Blueprint('biomarkers', __name__, url_prefix='/biomarkers')
logger = logging.getLogger(__name__)

@biomarkers_bp.route('/upload-pdf', methods=['POST'])
@jwt_required()
def upload_lab_pdf():
    user_identity = get_jwt_identity()
    user_id = user_identity.get('id') if isinstance(user_identity, dict) else user_identity
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        file_bytes = file.read()
        filename = f"user_{user_id or 'guest'}_{file.filename}"
        
        # 1. Upload file to GCS
        gcs_url = upload_file_to_gcs(file_bytes, filename, content_type='application/pdf')
        
        # 2. Extract biomarkers using Gemini 2.5 Multimodal PDF Parser
        biomarkers = parse_lab_pdf_with_gemini(file_bytes)
        
        # 3. Save to database
        panel_result = save_lab_panel(
            user_id=user_id,
            provider_name=f"Lab Report ({file.filename})",
            test_date="2026-08-08",
            biomarkers=biomarkers
        )
        
        return jsonify({
            "message": "Lab blood test PDF successfully uploaded and analyzed by Gemini!",
            "file_url": gcs_url,
            "panel_id": panel_result.get('panel_id'),
            "extracted_biomarkers": biomarkers
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading lab PDF: {e}")
        return jsonify({"error": str(e)}), 500

@biomarkers_bp.route('/flagged', methods=['GET'])
@jwt_required()
def get_user_flagged_biomarkers():
    user_identity = get_jwt_identity()
    user_id = user_identity.get('id') if isinstance(user_identity, dict) else user_identity
    from app.biomarkers.service import get_flagged_biomarkers
    flagged = get_flagged_biomarkers(user_id)
    return jsonify({"flagged_biomarkers": flagged}), 200
