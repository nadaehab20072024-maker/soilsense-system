"""Run the 30 evaluation questions.

    python -m soilsense_agent.tests.run_eval            # Mock mode: no LLM, real tools (default)
    python -m soilsense_agent.tests.run_eval --live     # real free LLM (needs GEMINI/GROQ/OPENROUTER key)

Writes eval_report.json next to this file and prints one line per question.
Checks: expected tools, refusals, words that must / must not appear, confidence, and number grounding."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from soilsense_agent import config as C            # noqa: E402
from soilsense_agent.agent import ask_agent         # noqa: E402
from soilsense_agent.i18n import S                  # noqa: E402

REFUSAL = {"chemical": S["refuse_chemical"], "offtopic": S["refuse_offtopic"]}


def check(item: dict, r: dict, live: bool) -> list[str]:
    e, probs = item["expect"], []
    tools = r["meta"].get("tools_used", [])
    ans = (r["answer"] or "").lower()
    if e.get("refuse"):
        if not live and r["answer"] != REFUSAL[e["refuse"]].get(item["lang"], REFUSAL[e["refuse"]]["en"]):
            probs.append(f"expected {e['refuse']} refusal")
        if live and tools and e["refuse"] == "offtopic":
            probs.append("called tools for an off-topic question")
        return probs
    if e.get("tools_any") and not set(e["tools_any"]) & set(tools):
        probs.append(f"expected one of {e['tools_any']}, got {tools}")
    if "recommend" in e.get("tools_none", []) and r.get("compare"):   # may be called, must not succeed
        probs.append("recommend should not succeed for unsupported crops")
    if not (e.get("mock_skip_content") and not live):
        if e.get("contains_any") and not any(w.lower() in ans for w in e["contains_any"]):
            probs.append(f"answer lacks any of {e['contains_any']}")
        for w in e.get("not_contains", []):
            if w.lower() in ans:
                probs.append(f"answer contains forbidden '{w}'")
    if e.get("confidence") and r["confidence"] != e["confidence"]:
        probs.append(f"confidence {r['confidence']} != {e['confidence']}")
    g = r["meta"].get("grounding") or {}
    if g.get("ungrounded_after_retry") or (not live and g.get("ungrounded")):
        probs.append(f"ungrounded numbers {g.get('ungrounded_after_retry') or g.get('ungrounded')}")
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="use a real LLM key instead of Mock mode")
    ap.add_argument("--only", help="comma-separated ids, e.g. q01,q11")
    args = ap.parse_args(argv)
    C.USE_MOCK = not args.live
    items = json.loads((HERE / "eval_questions.json").read_text(encoding="utf-8"))
    if args.only:
        keep = set(args.only.split(","))
        items = [i for i in items if i["id"] in keep]
    report, ok = [], 0
    for it in items:
        t0 = time.time()
        r = ask_agent(it["question"], {"lang": it["lang"], **it.get("context", {})}, use_cache=False)
        probs = check(it, r, args.live)
        ok += not probs
        report.append(dict(id=it["id"], lang=it["lang"], category=it["category"], question=it["question"],
                           answer=r["answer"], tools=r["meta"].get("tools_used"), confidence=r["confidence"],
                           provider=r["meta"].get("provider"), problems=probs, seconds=round(time.time() - t0, 2)))
        print(f"{'PASS' if not probs else 'FAIL'} {it['id']} [{it['lang']}/{it['category']}] {r['meta'].get('tools_used')}"
              + (f"  -> {probs}" if probs else ""))
        if args.live:
            time.sleep(1.0)            # be gentle with free-tier rate limits
    (HERE / "eval_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{ok}/{len(items)} passed ({'live LLM' if args.live else 'Mock mode'}). Report: {HERE / 'eval_report.json'}")
    return 0 if ok == len(items) else 1


if __name__ == "__main__":
    sys.exit(main())
