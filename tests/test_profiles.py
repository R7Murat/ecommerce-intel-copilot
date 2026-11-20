"""Profile selection and the fail-closed local-mode guard."""
import importlib

import pytest

import copilot.config as config
import copilot.llm as llm

ENV_KEYS = ["COPILOT_PROFILE", "PRIMARY_MODEL", "FALLBACK_MODEL", "OLLAMA_API_BASE",
            "OLLAMA_NO_CLOUD"]


@pytest.fixture
def load(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)  # isolate from local .env
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)

    def _load(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        return importlib.reload(config)

    yield _load
    monkeypatch.undo()
    importlib.reload(config)
    importlib.reload(llm)


def test_default_profile_is_cloud(load):
    c = load()
    assert c.PROFILE == "cloud"
    assert c.PRIMARY_MODEL == "groq/openai/gpt-oss-20b"
    assert c.FALLBACK_MODEL == "gemini/gemini-2.5-flash"
    assert c.API_BASE is None


def test_unknown_profile_refused(load):
    with pytest.raises(ValueError, match="COPILOT_PROFILE"):
        load(COPILOT_PROFILE="staging")


def test_local_profile_ok(load):
    c = load(COPILOT_PROFILE="local", OLLAMA_NO_CLOUD="1")
    assert c.PRIMARY_MODEL == "ollama_chat/gpt-oss:20b"
    assert c.FALLBACK_MODEL == ""
    assert c.API_BASE == "http://localhost:11434"


@pytest.mark.parametrize("env, reason", [
    ({"OLLAMA_NO_CLOUD": ""}, "OLLAMA_NO_CLOUD"),
    ({"OLLAMA_NO_CLOUD": "0"}, "OLLAMA_NO_CLOUD"),
    ({"OLLAMA_API_BASE": "https://ollama.com"}, "api_base host"),
    ({"OLLAMA_API_BASE": "http://localhost.evil.com:11434"}, "api_base host"),
    ({"PRIMARY_MODEL": "ollama_chat/gpt-oss:20b-cloud"}, "cloud-offloaded"),
    ({"PRIMARY_MODEL": "groq/openai/gpt-oss-20b"}, "Ollama model"),
    ({"FALLBACK_MODEL": "gemini/gemini-2.5-flash"}, "fallback must be empty"),
])
def test_local_profile_fails_closed(load, env, reason):
    base = {"COPILOT_PROFILE": "local", "OLLAMA_NO_CLOUD": "1"}
    with pytest.raises(RuntimeError, match=reason):
        load(**{**base, **env})


@pytest.mark.parametrize("host", ["http://127.0.0.1:11434", "http://[::1]:11434"])
def test_local_profile_accepts_loopback(load, host):
    assert load(COPILOT_PROFILE="local", OLLAMA_NO_CLOUD="1", OLLAMA_API_BASE=host).API_BASE == host


def test_local_profile_never_falls_back(load, monkeypatch):
    load(COPILOT_PROFILE="local", OLLAMA_NO_CLOUD="1")
    importlib.reload(llm)
    calls = []

    def fake_completion(model, **kw):
        calls.append((model, kw.get("api_base")))
        raise ConnectionError("ollama down")

    monkeypatch.setattr(llm, "completion", fake_completion)
    with pytest.raises(ConnectionError):
        llm.ask_llm("s", "u")
    assert calls == [("ollama_chat/gpt-oss:20b", "http://localhost:11434")]
