from app.config import Settings


def test_openai_host_without_path_defaults_to_v1_chat_completions():
    settings = Settings(api_key="key", api_url="https://example.test", model="model")
    assert settings.endpoint_url("openai") == "https://example.test/v1/chat/completions"


def test_explicit_endpoint_is_not_changed():
    settings = Settings(api_key="key", api_url="https://example.test/custom/chat/completions", model="model")
    assert settings.endpoint_url("openai") == "https://example.test/custom/chat/completions"


def test_settings_support_primary_and_backup_urls(monkeypatch):
    monkeypatch.setenv("VAPI", "key")
    monkeypatch.setenv("URL1", "https://primary.test")
    monkeypatch.setenv("URL2", "https://backup.test")
    monkeypatch.delenv("URL", raising=False)
    monkeypatch.setenv("MODEL", "model")
    settings = Settings.from_env()
    assert settings.api_urls == ("https://primary.test", "https://backup.test")
    assert settings.api_url == "https://primary.test"


def test_settings_parse_named_multiline_ecnu_keys(monkeypatch):
    monkeypatch.setenv("ECNU_API_KEYS", "main=key-one\nbackup=key-two")
    monkeypatch.setenv("ECNU_BASE_URL", "https://ecnu.test/open/api/v1")
    monkeypatch.setenv("ECNU_MODEL", "ecnu-reasoner")
    settings = Settings.from_env()
    assert settings.ecnu_api_keys == ("key-one", "key-two")
    assert settings.ecnu_base_url.endswith("/open/api/v1")


def test_ecnu_validation_does_not_require_vapi(monkeypatch):
    settings = Settings(
        api_key="",
        api_url="",
        model="",
        provider="ecnu",
        ecnu_api_keys=("key",),
        ecnu_base_url="https://ecnu.test/open/api/v1",
        ecnu_model="ecnu-reasoner",
    )
    settings.validate()
