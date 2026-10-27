"""Static safety/contract checks for shared RaceNote r6 BTDAY T1 entrypoint."""
from pathlib import Path
import re

BASE=Path(__file__).resolve().parents[3]
WORKFLOW=BASE/".github/workflows/racenote_v055_r6_btday_turn1_shared.yml"


def test_shared_trigger_covers_future_btday_and_uses_current_rrdb():
    text=WORKFLOW.read_text(encoding="utf-8")
    assert "BTDAY-*.v055r6-turn1" in text
    assert "racenote_fetch_rrdb_current.py" in text
    assert "rrdb_current_receipt.json" in text
    assert "racenote_btday0115_rrdb_current_20261020.json" not in text
    assert "BTDAY_TARGET_DATE" in text
    assert "BTDAY_ID" in text
    assert "SKIP_LEGACY_REQUEST" in text
    assert "READY_FOR_V055_AUTHORING" in text
    assert "MARKET" not in text.upper() or "market_blind" in text


def test_shared_workflow_embedded_python_syntax():
    raw=WORKFLOW.read_text(encoding="utf-8")
    scripts=re.findall(r"(?m)^          python - <<'PY'\n(.*?)^          PY$",raw,re.DOTALL|re.MULTILINE)
    assert len(scripts)>=4
    for index,script in enumerate(scripts):
        source="\n".join(line[10:] if line.startswith("          ") else line for line in script.splitlines())
        compile(source,f"inline-step-{index}","exec")


def test_historical_archive_year_and_input_contract():
    raw=WORKFLOW.read_text(encoding="utf-8")
    assert "not date.startswith('2025-')" in raw
    assert "selection['sources'][0].get('source_mode')!='historical_warehouse'" in raw
    assert "target.exists()" in raw
    assert "if len(ids)!=1" in raw
    assert "confidence" not in raw.lower().split("name: materialize verified rrdb")[0]
