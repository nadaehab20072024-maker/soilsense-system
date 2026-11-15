"""Free providers only. One client for every provider (Gemini, Groq, OpenRouter all accept the OpenAI chat format).
If a provider is rate-limited or down, the next one is tried automatically."""
import logging
import time

import requests

from . import config as C

log = logging.getLogger("soilsense.llm")
CALL_COUNT: dict[str, int] = {}        # printed by the demo so you can see where requests go
_down_until: dict[str, float] = {}


class AllProvidersFailed(Exception):
    pass


def chat(messages: list[dict], tools: list[dict] | None = None):
    """-> (assistant message dict, provider name)."""
    errors = []
    for p in C.PROVIDERS:
        key = C.get_secret(p["key_env"])      # st.secrets first, then environment
        if not key:
            continue
        if _down_until.get(p["name"], 0) > time.time():
            errors.append(f"{p['name']}: cooling down")
            continue
        payload = {"model": p["model"], "messages": messages, "temperature": 0.2, "max_tokens": C.MAX_TOKENS}
        if tools:
            payload["tools"], payload["tool_choice"] = tools, "auto"
        try:
            r = requests.post(p["base_url"].rstrip("/") + "/chat/completions", json=payload,
                              headers={"Authorization": f"Bearer {key}"}, timeout=C.LLM_TIMEOUT)
            CALL_COUNT[p["name"]] = CALL_COUNT.get(p["name"], 0) + 1
            if r.status_code == 429 or r.status_code >= 500:
                _down_until[p["name"]] = time.time() + 60
                errors.append(f"{p['name']}: HTTP {r.status_code}")
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"], p["name"]
        except Exception as e:
            _down_until[p["name"]] = time.time() + 20
            errors.append(f"{p['name']}: {e}")
            log.warning("provider %s failed: %s", p["name"], e)
    raise AllProvidersFailed("; ".join(errors) or "no API key configured")
