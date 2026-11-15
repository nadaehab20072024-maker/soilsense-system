"""Plant photo analysis with a free vision model (Gemini -> Groq Llama 4 Scout -> optional OpenRouter).

The result is an EARLY HINT, never a diagnosis: no pesticide or chemical doses (checked in code),
confidence is never "high", and the farmer is told when to call an extension officer."""
from __future__ import annotations

import base64
import io
import json
import re

from . import config as C
from . import guards
from .llm import AllProvidersFailed, chat

LANG_NAME = {"ar": "Arabic", "en": "English", "bn": "Bengali", "ur": "Urdu", "hi": "Hindi"}

PROMPT = """You look at ONE photo sent by a farmer in Oman. Reply in {lang} with ONE JSON object only:
{{"is_plant": true/false,
 "plant_guess": "what plant this looks like (or 'unknown')",
 "observations": ["what you can actually see, short"],
 "possible_problems": [{{"name": "...", "likelihood": "low|medium|high", "signs": "which visible signs point to it"}}],
 "checks": ["simple things the farmer can check in the field to confirm"],
 "safe_actions": ["safe first steps without chemicals: e.g. remove badly affected leaves, adjust watering, improve airflow"],
 "see_expert_if": ["when to call the agricultural extension office"],
 "image_quality": "good|fair|poor", "confidence": "low|medium"}}
Rules: this is an early hint, not a diagnosis. NEVER give pesticide, fungicide or fertiliser names with doses,
mixing rates or spray schedules. If the photo is not a plant, set is_plant=false and leave the lists empty.
If the photo is blurry or dark, say so in image_quality and keep confidence low. Short, plain words.
Farmer's crop (may be empty): {crop}. Farmer's note (may be empty): {note}"""


def prepare_image(data: bytes, max_px: int | None = None) -> tuple[str, dict]:
    """-> (data URL for the API, info). Shrinks to max_px and re-encodes as JPEG (strips EXIF/GPS too)."""
    max_px = max_px or C.IMAGE_MAX_PX
    info = dict(original_bytes=len(data))
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        data = buf.getvalue()
        info.update(width=img.width, height=img.height, sent_bytes=len(data), resized=True)
    except Exception as e:          # Pillow missing or odd format: send as is
        info.update(resized=False, sent_bytes=len(data), note=f"{type(e).__name__}")
    return "data:image/jpeg;base64," + base64.b64encode(data).decode(), info


def _parse(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    m = re.search(r"\{.*\}", text, re.S)
    try:
        d = json.loads(m.group(0) if m else text)
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, AttributeError):
        return {"observations": [text[:400]]} if text else {}


def _clean(rep: dict) -> dict:
    """Enforce the hard rules on whatever the model returned."""
    lists = ("observations", "checks", "safe_actions", "see_expert_if")
    out = {k: [str(x) for x in (rep.get(k) or []) if str(x).strip()][:5] for k in lists}
    probs = []
    for p in (rep.get("possible_problems") or [])[:4]:
        if isinstance(p, dict) and p.get("name"):
            lk = p.get("likelihood") if p.get("likelihood") in ("low", "medium", "high") else "low"
            probs.append(dict(name=str(p["name"]), likelihood=lk, signs=str(p.get("signs", ""))))
    out["possible_problems"] = probs
    removed = False
    for k in lists:
        keep = [x for x in out[k] if not guards.answer_has_dose(x)]
        removed |= len(keep) != len(out[k])
        out[k] = keep
    out["possible_problems"] = [p for p in probs if not guards.answer_has_dose(p["name"] + " " + p["signs"])]
    out["removed_dose_text"] = removed
    out["is_plant"] = bool(rep.get("is_plant", True))
    out["plant_guess"] = str(rep.get("plant_guess") or "unknown")
    out["image_quality"] = rep.get("image_quality") if rep.get("image_quality") in ("good", "fair", "poor") else "fair"
    conf = "medium" if rep.get("confidence") in ("medium", "high") else "low"         # capped at medium
    out["confidence"] = "low" if out["image_quality"] == "poor" or not out["is_plant"] else conf   # never "high"
    return out


def analyze_plant_photo(image: bytes, lang: str = "en", crop: str | None = None, note: str | None = None) -> dict:
    """-> report dict, or {"error": "no_vision" | "too_big" | "failed", ...}. Never raises."""
    if not image:
        return dict(error="empty")
    if len(image) > C.PHOTO_MAX_MB * 1024 * 1024:
        return dict(error="too_big", max_mb=C.PHOTO_MAX_MB)
    if C.USE_MOCK or not any(C.get_secret(p["key_env"]) and p.get("model") for p in C.VISION_PROVIDERS):
        return dict(error="no_vision")
    url, info = prepare_image(image)
    messages = [{"role": "user", "content": [
        {"type": "text", "text": PROMPT.format(lang=LANG_NAME.get(lang, "English"), crop=crop or "", note=note or "")},
        {"type": "image_url", "image_url": {"url": url}}]}]
    try:
        msg, provider = chat(messages, providers=C.VISION_PROVIDERS, max_tokens=700)
    except AllProvidersFailed as e:
        return dict(error="failed", detail=str(e)[:300])
    rep = _clean(_parse(msg.get("content")))
    rep.update(provider=provider, image=info, lang=lang, kind="early_hint_not_diagnosis")
    return rep


def short_summary(rep: dict) -> str:
    """One line kept in the farm profile for the farm report."""
    if rep.get("error"):
        return ""
    probs = ", ".join(f"{p['name']} ({p['likelihood']})" for p in rep.get("possible_problems", []))
    return f"{rep.get('plant_guess', 'plant')}: {probs or 'no clear problem seen'}"
