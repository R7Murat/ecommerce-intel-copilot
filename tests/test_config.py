"""Model IDs come from config with env override; default primary is gpt-oss-20b."""
import importlib

import pytest

import copilot.config as config


@pytest.fixture
def reload_config(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)  # isolate from local .env
    yield lambda: importlib.reload(config)
    monkeypatch.undo()
    importlib.reload(config)  # restore module state for other tests


def test_primary_model_default_is_gpt_oss(monkeypatch, reload_config):
    monkeypatch.delenv("PRIMARY_MODEL", raising=False)
    assert reload_config().PRIMARY_MODEL == "groq/openai/gpt-oss-20b"


def test_primary_model_env_override(monkeypatch, reload_config):
    monkeypatch.setenv("PRIMARY_MODEL", "ollama_chat/gpt-oss:20b")
    assert reload_config().PRIMARY_MODEL == "ollama_chat/gpt-oss:20b"
