from app.config import Settings


def test_openai_host_without_path_defaults_to_v1_chat_completions():
    settings = Settings(api_key="key", api_url="https://example.test", model="model")
    assert settings.endpoint_url("openai") == "https://example.test/v1/chat/completions"


def test_explicit_endpoint_is_not_changed():
    settings = Settings(api_key="key", api_url="https://example.test/custom/chat/completions", model="model")
    assert settings.endpoint_url("openai") == "https://example.test/custom/chat/completions"
