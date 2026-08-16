import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.gcp.storage_service import upload_file_to_gcs
from app.biomarkers.pdf_service import extract_lab_report_from_pdf
from app.biomarkers.service import (
    save_lab_panel,
    get_user_panels,
    get_panel_details,
    get_flagged_biomarkers,
    get_biomarker_trends,
    get_biomarker_summary,
    delete_lab_panel
)

biomarkers_bp = Blueprint('biomarkers', __name__, url_prefix='/biomarkers')
logger = logging.getLogger(__name__)


def _extract_user_id():
    user_identity = get_jwt_identity()
    return user_identity.get('id') if isinstance(user_identity, dict) else user_identity


@biomarkers_bp.route('/upload-pdf', methods=['POST'])
@jwt_required()
def upload_lab_pdf():
    user_id = _extract_user_id()
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        file_bytes = file.read()
        filename = f"user_{user_id or 'guest'}_{file.filename}"
        
        # 1. Upload file to GCS or fallback storage
        gcs_url = upload_file_to_gcs(file_bytes, filename, content_type='application/pdf')
        
        # 2. Extract structured report using Gemini 2.5 Multimodal PDF Parser
        report = extract_lab_report_from_pdf(file_bytes)
        
        # 3. Apply optional form overrides
        provider_name = request.form.get('provider_name') or report.get('provider_name') or f"Lab Report ({file.filename})"
        test_date = request.form.get('test_date') or report.get('test_date')
        notes = request.form.get('notes') or report.get('notes')
        biomarkers = report.get('biomarkers', [])

        # 4. Save to database
        panel_result = save_lab_panel(
            user_id=user_id,
            provider_name=provider_name,
            test_date=test_date,
            biomarkers=biomarkers,
            notes=notes,
            pdf_storage_path=gcs_url
        )
        
        flagged_count = len([b for b in panel_result.get('biomarkers', []) if b.get('status') in ['flagged_low', 'flagged_high']])

        return jsonify({
            "message": "Lab blood test PDF successfully uploaded and analyzed by Gemini 2.5!",
            "file_url": gcs_url,
            "panel_id": panel_result.get('panel_id'),
            "provider_name": provider_name,
            "test_date": test_date,
            "extracted_biomarkers": panel_result.get('biomarkers', []),
            "flagged_count": flagged_count
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading lab PDF: {e}")
        return jsonify({"error": str(e)}), 500


@biomarkers_bp.route('/panels', methods=['GET'])
@jwt_required()
def list_user_panels():
    user_id = _extract_user_id()
    panels = get_user_panels(user_id)
    return jsonify({"panels": panels}), 200


@biomarkers_bp.route('/panels/<panel_id>', methods=['GET'])
@jwt_required()
def get_single_panel(panel_id):
    user_id = _extract_user_id()
    panel = get_panel_details(user_id, panel_id)
    if not panel:
        return jsonify({"error": "Lab panel not found"}), 404
    return jsonify({"panel": panel}), 200


@biomarkers_bp.route('/panels/<panel_id>', methods=['DELETE'])
@jwt_required()
def remove_panel(panel_id):
    user_id = _extract_user_id()
    success = delete_lab_panel(user_id, panel_id)
    if not success:
        return jsonify({"error": "Failed to delete lab panel"}), 500
    return jsonify({"message": "Lab panel successfully deleted", "panel_id": panel_id}), 200


@biomarkers_bp.route('/flagged', methods=['GET'])
@jwt_required()
def get_user_flagged_biomarkers():
    user_id = _extract_user_id()
    panel_id = request.args.get('panel_id')
    all_time_param = request.args.get('all_time', 'false').lower() in ['true', '1', 'yes']

    flagged = get_flagged_biomarkers(user_id, panel_id=panel_id, all_time=all_time_param)
    return jsonify({"flagged_biomarkers": flagged}), 200


@biomarkers_bp.route('/trends', methods=['GET'])
@jwt_required()
def get_trends():
    user_id = _extract_user_id()
    markers_param = request.args.get('markers') or request.args.get('marker')
    marker_names = [m.strip() for m in markers_param.split(',')] if markers_param else None

    category = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    trends = get_biomarker_trends(
        user_id=user_id,
        marker_names=marker_names,
        category=category,
        start_date=start_date,
        end_date=end_date
    )
    return jsonify({"trends": trends}), 200


@biomarkers_bp.route('/summary', methods=['GET'])
@jwt_required()
def get_summary():
    user_id = _extract_user_id()
    summary = get_biomarker_summary(user_id)
    return jsonify({"summary": summary}), 200
