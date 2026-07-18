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
