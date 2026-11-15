
import json
import re

import streamlit.components.v1 as components

_LANG = {"en": "en-US", "ar": "ar-SA", "bn": "bn-BD"}


def _plain(text):
    """Remove markdown symbols so the voice doesn't read them out."""
    text = re.sub(r"[*_`#>]+", "", text or "")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def read_aloud_button(text, lang="en", label="🔊 Read aloud"):
    payload = json.dumps(_plain(text))
    code = json.dumps(_LANG.get(lang, "en-US"))
    components.html(f"""
    <button id="b" style="padding:6px 14px;border-radius:999px;border:1px solid #C5E1C5;
            background:#E8F5E9;color:#1B5E20;font-weight:600;cursor:pointer">{label}</button>
    <script>
      const btn = document.getElementById('b');
      btn.onclick = () => {{
        const s = window.speechSynthesis;
        if (s.speaking) {{ s.cancel(); return; }}
        const u = new SpeechSynthesisUtterance({payload});
        u.lang = {code};
        u.rate = 0.95;
        s.speak(u);
      }};
    </script>""", height=48)
