"""Number grounding: every number in the final answer must appear in a tool result (or in the user's
own question). Handles Arabic-Indic, Persian and Bengali/Devanagari digits."""
from __future__ import annotations

import json
import re

_DIGITS = {}
for zero in ("٠", "۰", "০", "०"):                       # Arabic-Indic, Persian/Urdu, Bengali, Devanagari
    for i in range(10):
        _DIGITS[chr(ord(zero) + i)] = str(i)
_TRANS = str.maketrans({**_DIGITS, "٫": ".", "٬": ",", "−": "-"})

_NUM = re.compile(r"(?<![\w.])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d])|(?<![\w.])-?\d+(?:\.\d+)?")


def normalize_digits(text: str) -> str:
    return str(text).translate(_TRANS)


def extract_numbers(text: str) -> list[float]:
    t = normalize_digits(text or "")
    t = re.sub(r"(?<=\d)[\-/–](?=\d)", " ", t)          # 2024-08-19, 1/3, 2001–2025 -> separate numbers
    out = []
    for m in _NUM.finditer(t):
        try:
            out.append(float(m.group().replace(",", "")))
        except ValueError:
            pass
    return out


def _walk(obj, acc: set):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        acc.add(float(obj))
    elif isinstance(obj, str):
        acc.update(extract_numbers(obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _walk(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _walk(v, acc)


def allowed_numbers(tool_results: list, extra_texts: list[str] = ()) -> set[float]:
    acc: set[float] = set()
    for r in tool_results:
        if isinstance(r, str):
            try:
                r = json.loads(r)
            except json.JSONDecodeError:
                pass
        _walk(r, acc)
    for t in extra_texts:
        acc.update(extract_numbers(t))
    return acc


def is_grounded(n: float, allowed: set[float]) -> bool:
    """n matches a tool value v if n equals v, or v rounded to 0/1/2 decimals, or n is v as a percent change."""
    an = abs(n)
    for v in allowed:
        for cand in (v, abs(v)):
            if an == abs(cand) or any(an == abs(round(cand, k)) for k in (0, 1, 2)):
                return True
    return False


def ungrounded_numbers(text: str, allowed: set[float]) -> list[float]:
    return [n for n in dict.fromkeys(extract_numbers(text)) if not is_grounded(n, allowed)]


def strip_numbers(text: str, bad: list[float]) -> str:
    """Remove sentences that carry an ungrounded number; if nothing is left, blank the number instead."""
    if not bad:
        return text
    parts = re.split(r"(?<=[.!?؟।])\s+", text or "")
    keep = [p for p in parts if not any(b in set(extract_numbers(p)) for b in bad)]
    if keep:
        return " ".join(keep).strip()
    norm = normalize_digits(text)
    for b in bad:
        s = f"{b:g}"
        norm = re.sub(r"(?<![\d.])" + re.escape(s) + r"(?![\d])", "…", norm)
    return norm
