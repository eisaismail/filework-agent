import httpx
import pytest

from filework.agent import Provider
from filework.documents import DocumentError


def test_provider_failure_does_not_echo_key_or_body(monkeypatch):
    def fail(*args, **kwargs):
        request = httpx.Request("POST", "https://provider.invalid/chat/completions")
        response = httpx.Response(401, request=request, text="secret-key-do-not-echo")
        response.raise_for_status()
    monkeypatch.setattr(httpx, "post", fail)
    with pytest.raises(DocumentError) as exc:
        Provider("https://provider.invalid", "secret-key-do-not-echo", "test-model").complete([])
    assert "secret-key" not in str(exc.value)


def test_nonlocal_plain_http_provider_rejected():
    with pytest.raises(DocumentError, match="HTTPS"):
        Provider("http://provider.invalid", "", "test-model").complete([])
