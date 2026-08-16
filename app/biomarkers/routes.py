import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.gcp.storage_service import upload_file_to_gcs
from app.biomarkers.pdf_service import (
    extract_lab_report_from_files,
    extract_lab_report_from_pdf,
    detect_mime_type
)
from app.biomarkers.service import (
    save_lab_panel,
    get_user_panels,
    get_panel_details,
    get_flagged_biomarkers,
    get_biomarker_trends,
    get_biomarker_summary,
    delete_lab_panel,
    update_biomarker_record
)

biomarkers_bp = Blueprint('biomarkers', __name__, url_prefix='/biomarkers')
logger = logging.getLogger(__name__)


def _extract_user_id():
    user_identity = get_jwt_identity()
    return user_identity.get('id') if isinstance(user_identity, dict) else user_identity


@biomarkers_bp.route('/upload-pdf', methods=['POST'])
@jwt_required()
def upload_lab_pdf():
    """
    Accepts single or multiple lab documents/screenshots (PDFs, PNG, JPEG, WEBP, HEIC),
    extracts structured analytes via Gemini 2.5 multimodal vision, runs verification
    adjudication, and persists the panel.
    """
    user_id = _extract_user_id()
    
    # Gather uploaded files (supports 'file' or 'files')
    uploaded_files = []
    if 'files' in request.files:
        uploaded_files = request.files.getlist('files')
    elif 'file' in request.files:
        uploaded_files = [request.files['file']]

    if not uploaded_files or not uploaded_files[0] or uploaded_files[0].filename == '':
        return jsonify({"error": "No file uploaded"}), 400

    try:
        files_data = []
        primary_gcs_url = None
        for f in uploaded_files:
            file_bytes = f.read()
            filename = f"user_{user_id or 'guest'}_{f.filename}"
            mime = detect_mime_type(file_bytes, f.filename)
            gcs_url = upload_file_to_gcs(file_bytes, filename, content_type=mime)
            if not primary_gcs_url:
                primary_gcs_url = gcs_url
            files_data.append((file_bytes, f.filename))

        # 2. Extract structured report using Gemini 2.5 Multimodal Document Parser
        report = extract_lab_report_from_files(files_data)
        
        # 3. Apply optional form overrides
        provider_name = request.form.get('provider_name') or report.get('provider_name') or f"Lab Report ({uploaded_files[0].filename})"
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
            pdf_storage_path=primary_gcs_url
        )
        
        saved_markers = panel_result.get('biomarkers', [])
        flagged_count = len([b for b in saved_markers if b.get('status') in ['flagged_low', 'flagged_high']])
        review_count = len([b for b in saved_markers if b.get('requires_review', False)])

        return jsonify({
            "message": "Lab blood test document successfully uploaded, parsed by Gemini 2.5, and adjudicated!",
            "file_url": primary_gcs_url,
            "panel_id": panel_result.get('panel_id'),
            "provider_name": provider_name,
            "test_date": test_date,
            "extracted_biomarkers": saved_markers,
            "flagged_count": flagged_count,
            "requires_review_count": review_count
        }), 200
        
    except Exception as e:
        logger.error(f"Error uploading lab document: {e}")
        return jsonify({"error": str(e)}), 500


@biomarkers_bp.route('/preview', methods=['POST'])
@jwt_required()
def preview_lab_extraction():
    """
    Staged extraction preview: runs Gemini multimodal parser and adjudication
    returning candidate analyte records with confidence scores without saving immediately.
    """
    uploaded_files = []
    if 'files' in request.files:
        uploaded_files = request.files.getlist('files')
    elif 'file' in request.files:
        uploaded_files = [request.files['file']]

    if not uploaded_files or not uploaded_files[0] or uploaded_files[0].filename == '':
        return jsonify({"error": "No file uploaded"}), 400

    try:
        files_data = [(f.read(), f.filename) for f in uploaded_files]
        report = extract_lab_report_from_files(files_data)
        return jsonify({"preview": report}), 200
    except Exception as e:
        logger.error(f"Error previewing lab extraction: {e}")
        return jsonify({"error": str(e)}), 500


@biomarkers_bp.route('/records/<biomarker_id>', methods=['PUT'])
@jwt_required()
def update_record(biomarker_id):
    """
    Review / correction seam: edit an extracted analyte's value, bounds, or units.
    """
    user_id = _extract_user_id()
    updates = request.get_json() or {}
    updated = update_biomarker_record(user_id, biomarker_id, updates)
    if not updated:
        return jsonify({"error": "Biomarker record not found or update failed."}), 404
    return jsonify({"message": "Biomarker successfully updated and verified.", "biomarker": updated}), 200


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
