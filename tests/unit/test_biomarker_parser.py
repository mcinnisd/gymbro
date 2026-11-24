import pytest
from app.biomarkers.pdf_service import (
    adjudicate_biomarker_record, detect_mime_type, evaluate_biomarker_status,
    extract_lab_report_from_files, extract_lab_report_from_pdf, generate_sports_science_insight,
    infer_dynamic_category, normalize_analyte_name, parse_lab_pdf_with_gemini, parse_reference_range,
)


@pytest.mark.parametrize("raw,expected", [
    ("30 - 400", (30.0, 400.0)),
    ("30.0-400.0 ng/mL", (30.0, 400.0)),
    ("3.5 to 5.0", (3.5, 5.0)),
    ("13.5 - 17.5 g/dL", (13.5, 17.5)),
    ("< 1.0", (None, 1.0)),
    ("<= 1.0 mg/L", (None, 1.0)),
    ("<100", (None, 100.0)),
    ("> 50", (50.0, None)),
    (">= 50.0 ng/mL", (50.0, None)),
    ("> 40", (40.0, None)),
    ("Negative", (None, None)),
    ("", (None, None)),
    (None, (None, None)),
])
def test_parse_reference_range(raw, expected):
    assert parse_reference_range(raw) == expected


@pytest.mark.parametrize("blob,name,mime", [
    (b"%PDF-1.4 header", "results.pdf", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n\x00\x00", "screenshot.png", "image/png"),
    (b"\xff\xd8\xff\xe0\x00", "lab_photo.jpg", "image/jpeg"),
    (b"RIFF\x00\x00\x00\x00WEBPVP8", "portal.webp", "image/webp"),
])
def test_detect_mime_type(blob, name, mime):
    assert detect_mime_type(blob, name) == mime


@pytest.mark.parametrize("raw,name,cat", [
    ("Serum Ferritin", "Ferritin", "Iron & Oxygen"),
    ("High Sensitivity C-Reactive Protein", "hs-CRP", "Inflammation & Recovery"),
    ("Total Testosterone", "Testosterone, Total", "Hormones & Endocrine"),
    ("Apolipoprotein B", "ApoB", "Cardiometabolic & Lipids"),
    ("25-Hydroxyvitamin D", "Vitamin D 25-OH", "Vitamins & Minerals"),
])
def test_normalize_known_analytes(raw, name, cat):
    assert normalize_analyte_name(raw) == (name, cat)


@pytest.mark.parametrize("raw,cat", [
    ("EPA + DHA Omega-3 Index", "Cardiometabolic & Lipids"),
    ("Blood Lead Level", "Toxicology & Heavy Metals"),
    ("Thyroglobulin Antibodies", "Thyroid Axis"),
    ("IGF-Binding Protein 3", "Peptides & Growth Factors"),
])
def test_infer_dynamic_category(raw, cat):
    assert infer_dynamic_category(raw) == cat


def test_suggested_category_is_kept_for_unknown_markers():
    assert normalize_analyte_name("Novel Longevity Peptide X", suggested_category="Cellular Bioenergetics") == (
        "Novel Longevity Peptide X", "Cellular Bioenergetics",
    )


@pytest.mark.parametrize("value,lo,hi,status", [
    (45.0, 30.0, 100.0, "optimal"),
    (20.0, 30.0, 100.0, "flagged_low"),
    (150.0, 30.0, 100.0, "flagged_high"),
    (0.5, None, 1.0, "optimal"),
    (2.5, None, 1.0, "flagged_high"),
    (60.0, 50.0, None, "optimal"),
    (35.0, 50.0, None, "flagged_low"),
])
def test_evaluate_biomarker_status(value, lo, hi, status):
    assert evaluate_biomarker_status(value, lo, hi) == status


def test_adjudication_flags_boundary_collision_and_implausible_values():
    clean = adjudicate_biomarker_record({
        "marker_name": "Ferritin", "value": 45.0, "unit": "ng/mL",
        "raw_reference_range": "30 - 400 ng/mL", "ref_range_min": 30.0, "ref_range_max": 400.0, "status": "optimal",
    })
    assert clean["requires_review"] is False and clean["extraction_confidence"] >= 0.90
    collision = adjudicate_biomarker_record({**clean, "value": 400.0})
    assert collision["requires_review"] is True
    assert any("collision" in flag.lower() for flag in collision["adjudication_flags"])
    extreme = adjudicate_biomarker_record({
        "marker_name": "HbA1c", "value": 45.0, "unit": "%", "ref_range_min": 4.0, "ref_range_max": 5.6,
    })
    assert extreme["requires_review"] is True and extreme["extraction_confidence"] < 0.85


def test_insights_and_offline_extraction_return_structured_markers():
    assert any(word in generate_sports_science_insight("Ferritin", 22.0, "ng/mL", "flagged_low").lower() for word in ("iron", "endurance", "oxygen"))
    assert any(word in generate_sports_science_insight("hs-CRP", 3.2, "mg/L", "flagged_high").lower() for word in ("inflammation", "recovery"))
    report = extract_lab_report_from_pdf(b"%PDF-1.4 dummy report")
    assert {"provider_name", "test_date", "biomarkers"} <= report.keys() and len(report["biomarkers"]) >= 3
    shots = extract_lab_report_from_files([
        (b"\x89PNG\r\n\x1a\n\x00\x00 page1", "screenshot1.png"),
        (b"\x89PNG\r\n\x1a\n\x00\x00 page2", "screenshot2.png"),
    ])
    assert len(shots["biomarkers"]) >= 3
    parsed = parse_lab_pdf_with_gemini(b"%PDF-1.4 dummy report")
    assert parsed and "marker_name" in parsed[0]
