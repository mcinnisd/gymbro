import pytest
from app.biomarkers.pdf_service import (
    parse_reference_range,
    normalize_analyte_name,
    evaluate_biomarker_status,
    generate_sports_science_insight,
    extract_lab_report_from_pdf,
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

    # Check that individual biomarkers have structured fields
    first = report["biomarkers"][0]
    assert "marker_name" in first
    assert "value" in first
    assert "unit" in first
    assert "status" in first
    assert "category" in first
    assert "coach_insight" in first

def test_parse_lab_pdf_with_gemini_returns_biomarkers_list():
    dummy_pdf = b"%PDF-1.4 dummy report"
    biomarkers = parse_lab_pdf_with_gemini(dummy_pdf)
    assert isinstance(biomarkers, list)
    assert len(biomarkers) > 0
    assert "marker_name" in biomarkers[0]
