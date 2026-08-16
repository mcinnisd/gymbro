import pytest
from app.biomarkers.pdf_service import (
    parse_reference_range,
    normalize_analyte_name,
    infer_dynamic_category,
    detect_mime_type,
    evaluate_biomarker_status,
    adjudicate_biomarker_record,
    generate_sports_science_insight,
    extract_lab_report_from_pdf,
    extract_lab_report_from_files,
    parse_lab_pdf_with_gemini
)

def test_parse_reference_range_standard_interval():
    assert parse_reference_range("30 - 400") == (30.0, 400.0)
    assert parse_reference_range("30.0-400.0 ng/mL") == (30.0, 400.0)
    assert parse_reference_range("3.5 to 5.0") == (3.5, 5.0)
    assert parse_reference_range("13.5 - 17.5 g/dL") == (13.5, 17.5)

def test_parse_reference_range_upper_bound_only():
    assert parse_reference_range("< 1.0") == (None, 1.0)
    assert parse_reference_range("<= 1.0 mg/L") == (None, 1.0)
    assert parse_reference_range("<100") == (None, 100.0)

def test_parse_reference_range_lower_bound_only():
    assert parse_reference_range("> 50") == (50.0, None)
    assert parse_reference_range(">= 50.0 ng/mL") == (50.0, None)
    assert parse_reference_range("> 40") == (40.0, None)

def test_parse_reference_range_invalid_or_text():
    assert parse_reference_range("Negative") == (None, None)
    assert parse_reference_range("") == (None, None)
    assert parse_reference_range(None) == (None, None)

def test_detect_mime_type_pdf_and_screenshots():
    # PDF
    assert detect_mime_type(b"%PDF-1.4 header", "results.pdf") == "application/pdf"
    # PNG screenshot
    assert detect_mime_type(b"\x89PNG\r\n\x1a\n\x00\x00", "screenshot.png") == "image/png"
    # JPEG screenshot
    assert detect_mime_type(b"\xff\xd8\xff\xe0\x00", "lab_photo.jpg") == "image/jpeg"
    # WEBP screenshot
    assert detect_mime_type(b"RIFF\x00\x00\x00\x00WEBPVP8", "portal.webp") == "image/webp"

def test_normalize_analyte_name_and_category():
    # Iron & Oxygen
    name, cat = normalize_analyte_name("Serum Ferritin")
    assert name == "Ferritin"
    assert cat == "Iron & Oxygen"

    # Inflammation
    name, cat = normalize_analyte_name("High Sensitivity C-Reactive Protein")
    assert name == "hs-CRP"
    assert cat == "Inflammation & Recovery"

    # Hormones
    name, cat = normalize_analyte_name("Total Testosterone")
    assert name == "Testosterone, Total"
    assert cat == "Hormones & Endocrine"

    # Lipids
    name, cat = normalize_analyte_name("Apolipoprotein B")
    assert name == "ApoB"
    assert cat == "Cardiometabolic & Lipids"

    # Vitamins
    name, cat = normalize_analyte_name("25-Hydroxyvitamin D")
    assert name == "Vitamin D 25-OH"
    assert cat == "Vitamins & Minerals"

def test_open_vocabulary_dynamic_category_inference():
    # Novel / niche markers not in static dictionary
    assert infer_dynamic_category("EPA + DHA Omega-3 Index") == "Cardiometabolic & Lipids"
    assert infer_dynamic_category("Blood Lead Level") == "Toxicology & Heavy Metals"
    assert infer_dynamic_category("Thyroglobulin Antibodies") == "Thyroid Axis"
    assert infer_dynamic_category("IGF-Binding Protein 3") == "Peptides & Growth Factors"

    # With LLM suggested category preserved
    name, cat = normalize_analyte_name("Novel Longevity Peptide X", suggested_category="Cellular Bioenergetics")
    assert name == "Novel Longevity Peptide X"
    assert cat == "Cellular Bioenergetics"

def test_adjudicate_biomarker_record_clean():
    clean_marker = {
        "marker_name": "Ferritin",
        "value": 45.0,
        "unit": "ng/mL",
        "raw_reference_range": "30 - 400 ng/mL",
        "ref_range_min": 30.0,
        "ref_range_max": 400.0,
        "status": "optimal"
    }
    res = adjudicate_biomarker_record(clean_marker)
    assert res["extraction_confidence"] >= 0.90
    assert res["requires_review"] is False
    assert len(res["adjudication_flags"]) == 0

def test_adjudicate_biomarker_record_flags_collision_and_extreme_values():
    # 1. OCR collision (value = 400 which is the upper reference boundary)
    collision_marker = {
        "marker_name": "Ferritin",
        "value": 400.0,
        "unit": "ng/mL",
        "raw_reference_range": "30 - 400 ng/mL",
        "ref_range_min": 30.0,
        "ref_range_max": 400.0,
        "status": "optimal"
    }
    res_col = adjudicate_biomarker_record(collision_marker)
    assert res_col["requires_review"] is True
    assert any("collision" in f.lower() for f in res_col["adjudication_flags"])

    # 2. Implausible value (HbA1c = 45% or negative value)
    extreme_marker = {
        "marker_name": "HbA1c",
        "value": 45.0,
        "unit": "%",
        "ref_range_min": 4.0,
        "ref_range_max": 5.6
    }
    res_ext = adjudicate_biomarker_record(extreme_marker)
    assert res_ext["requires_review"] is True
    assert res_ext["extraction_confidence"] < 0.85
    assert any("plausible" in f.lower() for f in res_ext["adjudication_flags"])

def test_evaluate_biomarker_status():
    assert evaluate_biomarker_status(45.0, 30.0, 100.0) == "optimal"
    assert evaluate_biomarker_status(20.0, 30.0, 100.0) == "flagged_low"
    assert evaluate_biomarker_status(150.0, 30.0, 100.0) == "flagged_high"
    assert evaluate_biomarker_status(0.5, None, 1.0) == "optimal"
    assert evaluate_biomarker_status(2.5, None, 1.0) == "flagged_high"
    assert evaluate_biomarker_status(60.0, 50.0, None) == "optimal"
    assert evaluate_biomarker_status(35.0, 50.0, None) == "flagged_low"

def test_generate_sports_science_insight():
    insight_low = generate_sports_science_insight("Ferritin", 22.0, "ng/mL", "flagged_low")
    assert "iron" in insight_low.lower() or "endurance" in insight_low.lower() or "oxygen" in insight_low.lower()

    insight_high = generate_sports_science_insight("hs-CRP", 3.2, "mg/L", "flagged_high")
    assert "inflammation" in insight_high.lower() or "recovery" in insight_high.lower()

def test_extract_lab_report_from_pdf_fallback():
    dummy_pdf = b"%PDF-1.4 dummy report"
    report = extract_lab_report_from_pdf(dummy_pdf)
    assert isinstance(report, dict)
    assert "provider_name" in report
    assert "test_date" in report
    assert "biomarkers" in report
    assert len(report["biomarkers"]) >= 3

    # Check that individual biomarkers have structured fields and confidence
    first = report["biomarkers"][0]
    assert "marker_name" in first
    assert "value" in first
    assert "unit" in first
    assert "status" in first
    assert "category" in first
    assert "coach_insight" in first
    assert "extraction_confidence" in first

def test_extract_lab_report_from_multiple_screenshots():
    screenshot_1 = (b"\x89PNG\r\n\x1a\n\x00\x00 page1", "screenshot1.png")
    screenshot_2 = (b"\x89PNG\r\n\x1a\n\x00\x00 page2", "screenshot2.png")
    report = extract_lab_report_from_files([screenshot_1, screenshot_2])
    assert isinstance(report, dict)
    assert len(report["biomarkers"]) >= 3

def test_parse_lab_pdf_with_gemini_returns_biomarkers_list():
    dummy_pdf = b"%PDF-1.4 dummy report"
    biomarkers = parse_lab_pdf_with_gemini(dummy_pdf)
    assert isinstance(biomarkers, list)
    assert len(biomarkers) > 0
    assert "marker_name" in biomarkers[0]
