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
