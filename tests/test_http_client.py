# tests/test_http_client.py
from unittest.mock import patch, MagicMock
from src.infrastructure.http import MsClient

class _Resp:
    def __init__(self, status=200, json=None, text="", url="http://x/y", method="GET"):
        self.status_code = status
        self._json = json
        self.text = text
        self.url = url
        self.request = MagicMock(method=method)
        self.content = b"" if json is None else b"{}"
    def json(self):
        return self._json

@patch("src.infrastructure.http.requests.get")
def test_msclient_get_ok(mock_get):
    mock_get.return_value = _Resp(status=200, json={"ok": True})
    c = MsClient("co")
    out = c.get("/v1/ping")
    assert out == {"ok": True}

@patch("src.infrastructure.http.requests.post")
def test_msclient_post_error_lanza(mock_post):
    mock_post.return_value = _Resp(status=422, json=None, text="bad", method="POST", url="http://gw/v1/x")
    c = MsClient("co")
    try:
        c.post("/v1/x", json={"a": 1})
        assert False, "Debió lanzar ValueError"
    except ValueError as e:
        assert "HTTP 422" in str(e)
        assert "/v1/x" in str(e)
