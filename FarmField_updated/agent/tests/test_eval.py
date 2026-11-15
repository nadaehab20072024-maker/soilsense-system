"""The 30 evaluation questions must all pass in Mock mode (real tools, no LLM)."""
import json
from pathlib import Path

from ..tests import run_eval

from .conftest import needs_team


def test_eval_file_has_30_questions_in_three_languages():
    items = json.loads((Path(__file__).with_name("eval_questions.json")).read_text(encoding="utf-8"))
    assert len(items) == 30 and {i["lang"] for i in items} == {"ar", "en", "bn"}
    assert {"off_topic", "chemical", "tricky", "unsupported"} <= {i["category"] for i in items}


@needs_team
def test_eval_all_pass_in_mock_mode(capsys):
    assert run_eval.main([]) == 0
    assert "30/30 passed" in capsys.readouterr().out
