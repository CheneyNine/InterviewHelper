import asyncio

from app.config import Settings
from app.model_client import ModelClientError, OpenAICompatibleClient


def test_model_client_uses_backup_after_primary_dependency_failure(monkeypatch):
    settings = Settings(
        api_key="key",
        api_url="https://primary.test",
        model="model",
        api_urls=("https://primary.test", "https://backup.test"),
        failover_delay_seconds=0,
    )
    client = OpenAICompatibleClient(settings)
    calls = []

    async def fake_request_once(messages, *, base_url, json_mode=True):
        calls.append(base_url)
        if base_url == "https://primary.test":
            raise ModelClientError("DEPENDENCY_UNAVAILABLE", "primary unavailable")
        return '{"questions": []}'

    monkeypatch.setattr(client, "_request_once", fake_request_once)
    result = asyncio.run(client._request([{"role": "user", "content": "test"}]))
    assert result == '{"questions": []}'
    assert set(calls) == {"https://primary.test", "https://backup.test"}


def test_ecnu_rotates_key_after_429(monkeypatch):
    settings = Settings(
        api_key="",
        api_url="",
        model="",
        provider="ecnu",
        ecnu_api_keys=("key-one", "key-two"),
        ecnu_base_url="https://ecnu.test/open/api/v1",
        ecnu_model="ecnu-reasoner",
    )
    client = OpenAICompatibleClient(settings)
    calls = []

    async def fake_request_once(messages, *, base_url, api_key=None, model=None, json_mode=True):
        calls.append(api_key)
        if api_key == "key-one":
            raise ModelClientError("MODEL_RATE_LIMITED", "rate limited", status_code=429)
        return "ok"

    monkeypatch.setattr(client, "_request_once", fake_request_once)
    result = asyncio.run(client._request([{"role": "user", "content": "test"}]))
    assert result == "ok"
    assert calls == ["key-one", "key-two"]
