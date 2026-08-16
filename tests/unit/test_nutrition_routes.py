import io
import json
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_analyze_photo_endpoint_multipart(client):
    data = {
        'image': (io.BytesIO(b"fake_image_bytes"), 'test_meal.jpg')
    }
    response = client.post('/nutrition/analyze-photo', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'estimated_calories' in json_data
    assert 'calories' in json_data
    assert 'protein_g' in json_data
    assert 'meal_name' in json_data
    assert 'quality_score' in json_data


def test_analyze_photo_endpoint_base64(client):
    data = {
        'image_base64': 'ZmFrZV9pbWFnZV9ieXRlcw=='
    }
    response = client.post('/nutrition/analyze-photo', json=data)
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['calories'] > 0
    assert 'identified_ingredients' in json_data


def test_reevaluate_endpoint_various_foods(client):
    # 1. Chicken breast in grams
    res1 = client.post('/nutrition/reevaluate', json={'item_name': '200g Grilled Chicken Breast'})
    assert res1.status_code == 200
    d1 = res1.get_json()
    assert round(d1['protein']) == 62 or d1['protein'] > 50
    assert d1['carbs'] == 0.0 or d1['carbs'] < 5

    # 2. Salmon in ounces
    res2 = client.post('/nutrition/reevaluate', json={'item_name': '8oz Atlantic Salmon'})
    assert res2.status_code == 200
    d2 = res2.get_json()
    assert d2['protein'] > 40
    assert d2['fat'] > 20

    # 3. Eggs in units
    res3 = client.post('/nutrition/reevaluate', json={'item_name': '3 whole scrambled eggs'})
    assert res3.status_code == 200
    d3 = res3.get_json()
    assert d3['calories'] == 210.0
    assert d3['protein'] == 18.0

    # 4. Whey protein scoops
    res4 = client.post('/nutrition/reevaluate', json={'item_name': '2 scoops whey protein isolate'})
    assert res4.status_code == 200
    d4 = res4.get_json()
    assert d4['protein'] >= 48.0
    assert d4['calories'] >= 200.0


def test_update_food_log_item_recalculates_macros(client):
    res = client.put('/nutrition/logs/log_123', json={
        'item_name': '200g Grilled Chicken Breast',
    })
    assert res.status_code == 200
    data = res.json
    assert data['calories'] > 0
    assert data['protein'] >= 50
    assert data['meal_name'] == '200g Grilled Chicken Breast'


def test_update_food_log_with_explicit_macros_preserves_overrides(client):
    res = client.put('/nutrition/logs/log_456', json={
        'item_name': 'Custom Chef Protein Bowl',
        'calories': 680,
        'protein': 55,
        'carbs': 60,
        'fat': 22
    })
    assert res.status_code == 200
    data = res.json
    assert data['calories'] == 680.0
    assert data['protein'] == 55.0
    assert data['carbs'] == 60.0
    assert data['fat'] == 22.0


def test_nutrition_history_with_adaptive_targets(client):
    # Log a meal first
    log_res = client.post('/nutrition/log', json={
        'meal_name': 'Pre-Run Oats & Banana with Protein',
        'calories': 550,
        'protein': 35,
        'carbs': 80,
        'fat': 10,
        'date': '2026-08-16'
    }, headers={'Authorization': 'Bearer fake_or_optional_token'})
    
    # Query history
    res = client.get('/nutrition/history?start_date=2026-08-16&end_date=2026-08-16')
    assert res.status_code == 200
    data = res.get_json()
    assert 'logs' in data
    assert 'daily_summaries' in data
    assert 'daily_targets' in data
    assert 'daily_adherence' in data
    assert 'period_averages' in data


def test_delete_nutrition_log(client):
    res = client.delete('/nutrition/logs/log_123')
    assert res.status_code == 200
    assert res.json['id'] == 'log_123'


def test_barcode_lookup_endpoint(client):
    # Test known sports barcode or fallback UPC lookup
    res = client.get('/nutrition/barcode/041570054771')
    assert res.status_code == 200
    data = res.get_json()
    assert 'meal_name' in data or 'product_name' in data
    assert data['calories'] > 0
    assert 'protein_g' in data or 'protein' in data

