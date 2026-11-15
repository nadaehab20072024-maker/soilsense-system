"""Shared fixtures. Run from the repo root:  python -m pytest agent/tests -q   (no API key, no LLM call)"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]       # repo root (folder that contains the agent package)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from .. import config as C          # noqa: E402

HAS_TEAM = (C.REPO_ROOT / "agent_tools.py").exists()
needs_team = pytest.mark.skipif(not HAS_TEAM, reason="teammates' agent_tools.py not next to the agent folder")


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(C, "USE_POWER_API", False)
    monkeypatch.setattr(C, "USE_MOCK", False)
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def fake_llm(monkeypatch):
    """Scripted LLM: replies are returned in order (last one repeats)."""
    from .. import agent as A

    def make(replies):
        calls = []

        def fake_chat(messages, tools=None):
            calls.append([dict(m) for m in messages])
            return replies[min(len(calls), len(replies)) - 1], "fake"
        monkeypatch.setattr(A, "chat", fake_chat)
        return calls
    return make
