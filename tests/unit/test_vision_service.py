import pytest
from app.nutrition.vision_service import analyze_meal_image

def test_analyze_meal_image_mock_fallback():
    dummy_image_bytes = b"fake_jpeg_header_data_sample"
    result = analyze_meal_image(dummy_image_bytes)
    
    assert isinstance(result, dict)
    assert 'estimated_calories' in result
    assert 'protein_g' in result
    assert 'carbs_g' in result
    assert 'fat_g' in result
    assert 'quality_score' in result
    assert 1 <= result['quality_score'] <= 10
    assert 'meal_name' in result
