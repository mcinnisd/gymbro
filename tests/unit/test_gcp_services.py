import pytest
from unittest.mock import patch, MagicMock
from app.gcp.storage_service import upload_file_to_gcs
from app.biomarkers.pdf_service import parse_lab_pdf_with_gemini

def test_upload_file_to_gcs_fallback():
    # Test uploading file when GCS bucket is not configured
    with patch('app.config.Config.GCS_BUCKET_NAME', ''):
        url = upload_file_to_gcs(b"dummy image bytes", "test_photo.jpg", "image/jpeg")
        assert url is not None
        assert "local" in url or "storage" in url or url.startswith("/")

def test_parse_lab_pdf_with_gemini_fallback():
    # Test PDF lab parsing using Gemini multimodal document parser
    dummy_pdf_bytes = b"%PDF-1.4 dummy pdf content"
    result = parse_lab_pdf_with_gemini(dummy_pdf_bytes)
    assert isinstance(result, list)
    assert len(result) > 0
    first = result[0]
    assert "marker_name" in first
    assert "value" in first
    assert "status" in first
