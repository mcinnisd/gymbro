import io
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_analyze_photo_endpoint(client):
    data = {
        'image': (io.BytesIO(b"fake_image_bytes"), 'test_meal.jpg')
    }
    response = client.post('/nutrition/analyze-photo', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'estimated_calories' in json_data
    assert 'meal_name' in json_data

def test_update_food_log_item_recalculates_macros(client):
    res = client.put('/nutrition/logs/log_123', json={
        'item_name': '200g Grilled Chicken Breast',
    })
    assert res.status_code == 200
    assert res.json['calories'] > 0

