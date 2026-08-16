import io
import json
import pytest
from app import create_app
from app.mock_supabase import MockSupabaseClient
import app.biomarkers.service as service

@pytest.fixture
def test_app(monkeypatch):
    mock_db = MockSupabaseClient()
    monkeypatch.setattr(service, 'supabase', mock_db)
    import app.biomarkers.routes as routes
    monkeypatch.setattr(routes, 'upload_file_to_gcs', lambda bytes_data, fname, content_type: f"https://storage.googleapis.com/mock-bucket/{fname}")

    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(test_app):
    return test_app.test_client()

@pytest.fixture
def auth_headers(test_app):
    from flask_jwt_extended import create_access_token
    with test_app.app_context():
        token = create_access_token(identity="1")
        return {'Authorization': f'Bearer {token}'}


def test_upload_lab_pdf_route(client, auth_headers):
    pdf_data = b"%PDF-1.4 Mock Lab Blood Test PDF Content"
    data = {
        'file': (io.BytesIO(pdf_data), 'blood_test_aug2026.pdf'),
        'provider_name': 'Quest Diagnostics',
        'test_date': '2026-08-08'
    }

    res = client.post('/biomarkers/upload-pdf', headers=auth_headers, data=data, content_type='multipart/form-data')
    assert res.status_code == 200
    res_data = res.get_json()
    assert 'panel_id' in res_data
    assert 'extracted_biomarkers' in res_data
    assert len(res_data['extracted_biomarkers']) > 0


def test_upload_screenshot_images_route(client, auth_headers):
    png_data = b"\x89PNG\r\n\x1a\n\x00\x00 mock png image"
    data = {
        'file': (io.BytesIO(png_data), 'quest_screenshot_1.png'),
        'provider_name': 'Quest Portal Screenshot'
    }

    res = client.post('/biomarkers/upload-pdf', headers=auth_headers, data=data, content_type='multipart/form-data')
    assert res.status_code == 200
    res_data = res.get_json()
    assert 'panel_id' in res_data
    assert len(res_data['extracted_biomarkers']) > 0


def test_preview_lab_extraction_route(client, auth_headers):
    pdf_data = b"%PDF-1.4 Mock Lab Report"
    data = {
        'file': (io.BytesIO(pdf_data), 'report.pdf')
    }

    res = client.post('/biomarkers/preview', headers=auth_headers, data=data, content_type='multipart/form-data')
    assert res.status_code == 200
    preview_data = res.get_json()
    assert 'preview' in preview_data
    assert 'biomarkers' in preview_data['preview']


def test_get_panels_and_panel_details_route(client, auth_headers):
    pdf_data = b"%PDF-1.4 Mock Lab Report"
    res = client.post('/biomarkers/upload-pdf', headers=auth_headers, data={'file': (io.BytesIO(pdf_data), 'report.pdf')}, content_type='multipart/form-data')
    panel_id = res.get_json()['panel_id']

    panels_res = client.get('/biomarkers/panels', headers=auth_headers)
    assert panels_res.status_code == 200
    panels_data = panels_res.get_json()
    assert 'panels' in panels_data
    assert len(panels_data['panels']) >= 1

    detail_res = client.get(f'/biomarkers/panels/{panel_id}', headers=auth_headers)
    assert detail_res.status_code == 200
    detail_data = detail_res.get_json()
    assert 'panel' in detail_data
    assert detail_data['panel']['id'] == panel_id
    assert len(detail_data['panel']['biomarkers']) > 0


def test_update_biomarker_record_route(client, auth_headers):
    pdf_data = b"%PDF-1.4 Mock Lab Report"
    res = client.post('/biomarkers/upload-pdf', headers=auth_headers, data={'file': (io.BytesIO(pdf_data), 'report.pdf')}, content_type='multipart/form-data')
    marker = res.get_json()['extracted_biomarkers'][0]
    marker_id = marker['id']

    # Update value from athlete review modal
    update_payload = {
        "value": 95.0,
        "unit": "ng/mL"
    }
    update_res = client.put(f'/biomarkers/records/{marker_id}', headers=auth_headers, json=update_payload)
    assert update_res.status_code == 200
    updated = update_res.get_json()['biomarker']
    assert updated['value'] == 95.0
    assert updated['verified_by_user'] is True


def test_get_flagged_biomarkers_route(client, auth_headers):
    pdf_data = b"%PDF-1.4 Mock Lab Report"
    client.post('/biomarkers/upload-pdf', headers=auth_headers, data={'file': (io.BytesIO(pdf_data), 'report.pdf')}, content_type='multipart/form-data')

    res = client.get('/biomarkers/flagged', headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert 'flagged_biomarkers' in data
    assert isinstance(data['flagged_biomarkers'], list)


def test_get_trends_route(client, auth_headers):
    pdf_data = b"%PDF-1.4 Mock Lab Report"
    client.post('/biomarkers/upload-pdf', headers=auth_headers, data={'file': (io.BytesIO(pdf_data), 'report.pdf')}, content_type='multipart/form-data')

    res = client.get('/biomarkers/trends', headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert 'trends' in data
    assert len(data['trends']) > 0

    filtered_res = client.get('/biomarkers/trends?markers=Ferritin,hs-CRP', headers=auth_headers)
    assert filtered_res.status_code == 200
    filtered_data = filtered_res.get_json()
    names = [t['marker_name'] for t in filtered_data['trends']]
    assert 'Ferritin' in names or 'hs-CRP' in names


def test_get_summary_route(client, auth_headers):
    pdf_data = b"%PDF-1.4 Mock Lab Report"
    client.post('/biomarkers/upload-pdf', headers=auth_headers, data={'file': (io.BytesIO(pdf_data), 'report.pdf')}, content_type='multipart/form-data')

    res = client.get('/biomarkers/summary', headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert 'summary' in data
    assert data['summary']['has_data'] is True
    assert 'optimal_count' in data['summary']


def test_delete_panel_route(client, auth_headers):
    pdf_data = b"%PDF-1.4 Mock Lab Report"
    res = client.post('/biomarkers/upload-pdf', headers=auth_headers, data={'file': (io.BytesIO(pdf_data), 'report.pdf')}, content_type='multipart/form-data')
    panel_id = res.get_json()['panel_id']

    del_res = client.delete(f'/biomarkers/panels/{panel_id}', headers=auth_headers)
    assert del_res.status_code == 200

    detail_res = client.get(f'/biomarkers/panels/{panel_id}', headers=auth_headers)
    assert detail_res.status_code == 404
