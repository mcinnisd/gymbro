import pytest
import os
from urllib.parse import urlparse
from app import create_app

class FlaskTestClientWrapper:
    def __init__(self, flask_client):
        self.client = flask_client

    def _convert_headers(self, headers):
        if not headers:
            return {}
        h = {}
        for k, v in headers.items():
            h[k] = v
        return h

    def get(self, url, headers=None, params=None, **kwargs):
        parsed = urlparse(url)
        path = parsed.path
        if parsed.query:
            path = f"{path}?{parsed.query}"
        if params:
            from urllib.parse import urlencode
            sep = "&" if "?" in path else "?"
            path = f"{path}{sep}{urlencode(params)}"
        resp = self.client.get(path, headers=self._convert_headers(headers), follow_redirects=True)
        return ResponseWrapper(resp)

    def post(self, url, json=None, data=None, headers=None, **kwargs):
        path = urlparse(url).path
        resp = self.client.post(path, json=json, data=data, headers=self._convert_headers(headers), follow_redirects=True)
        return ResponseWrapper(resp)

    def put(self, url, json=None, data=None, headers=None, **kwargs):
        path = urlparse(url).path
        resp = self.client.put(path, json=json, data=data, headers=self._convert_headers(headers), follow_redirects=True)
        return ResponseWrapper(resp)

    def delete(self, url, headers=None, **kwargs):
        path = urlparse(url).path
        resp = self.client.delete(path, headers=self._convert_headers(headers), follow_redirects=True)
        return ResponseWrapper(resp)

class ResponseWrapper:
    def __init__(self, flask_response):
        self._resp = flask_response
        self.status_code = flask_response.status_code
        self.text = flask_response.get_data(as_text=True)

    def json(self):
        return self._resp.get_json()

    def iter_lines(self):
        for chunk in self._resp.response:
            if isinstance(chunk, bytes):
                chunk = chunk.decode('utf-8')
            for subline in chunk.splitlines():
                yield subline.encode('utf-8')

@pytest.fixture(scope="session", autouse=True)
def intercept_requests_for_testing(monkeypatch_session):
    """
    If no live server is listening, monkeypatch requests.get/post/put/delete
    to route requests directly through Flask's test_client in-process.
    """
    import socket

    def is_server_running(host="127.0.0.1", port=5001):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0

    if not is_server_running():
        app = create_app()
        app.config['TESTING'] = True
        flask_client = app.test_client()
        wrapper = FlaskTestClientWrapper(flask_client)

        import requests
        monkeypatch_session.setattr(requests, "get", wrapper.get)
        monkeypatch_session.setattr(requests, "post", wrapper.post)
        monkeypatch_session.setattr(requests, "put", wrapper.put)
        monkeypatch_session.setattr(requests, "delete", wrapper.delete)

@pytest.fixture(scope="session")
def monkeypatch_session():
    from _pytest.monkeypatch import MonkeyPatch
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_headers(app):
    from flask_jwt_extended import create_access_token
    with app.app_context():
        token = create_access_token(identity="1")
        return {"Authorization": f"Bearer {token}"}

