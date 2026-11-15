
import os

import requests
import streamlit as st

from . import config as C

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")   
_LANG = {"en": "en", "ar": "ar", "bn": "bn"}

_MSG = {
    "en": dict(label="🎤 Ask with your voice", no_key="Voice input needs a GROQ_API_KEY.",
               fail="Sorry, I could not understand the recording. Please try again.",
               heard="I heard:", old="Voice input needs a newer Streamlit (pip install -U streamlit)."),
    "ar": dict(label="🎤 اسأل بصوتك", no_key="الإدخال الصوتي يحتاج مفتاح GROQ_API_KEY.",
               fail="عذراً، لم أفهم التسجيل. حاول مرة أخرى.",
               heard="سمعتُ:", old="الإدخال الصوتي يحتاج نسخة أحدث من Streamlit."),
    "bn": dict(label="🎤 কণ্ঠে প্রশ্ন করুন", no_key="ভয়েস ইনপুটের জন্য GROQ_API_KEY দরকার।",
               fail="দুঃখিত, রেকর্ডিং বুঝতে পারিনি। আবার চেষ্টা করুন।",
               heard="আমি শুনেছি:", old="ভয়েস ইনপুটের জন্য নতুন Streamlit দরকার।"),
}


def transcribe(audio_bytes, lang="en", api_key=None, timeout=30):
    """Return (text, error). Exactly one of them is None."""
    api_key = api_key or C.get_secret("GROQ_API_KEY")
    if not api_key:
        return None, "no_key"
    try:
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("speech.wav", audio_bytes, "audio/wav")},
            data={"model": STT_MODEL, "language": _LANG.get(lang, "en"), "response_format": "json"},
            timeout=timeout,
        )
        r.raise_for_status()
        text = (r.json().get("text") or "").strip()
        return (text, None) if text else (None, "fail")
    except Exception:
        return None, "fail"


def voice_question(lang, key_prefix):

    m = _MSG.get(lang, _MSG["en"])
    if not hasattr(st, "audio_input"):
        st.caption(m["old"])
        return None
    n = st.session_state.setdefault(key_prefix + "mic_n", 0)
    audio = st.audio_input(m["label"], key=f"{key_prefix}mic_{n}")
    if audio is None:
        return None
    text, err = transcribe(audio.getvalue(), lang)
    st.session_state[key_prefix + "mic_n"] = n + 1          
    if err:
        st.warning(m[err])
        return None
    st.caption(f"{m['heard']} {text}")
    return text
