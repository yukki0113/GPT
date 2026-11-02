from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

import validate_jrdb_edge_semantic_hierarchy_v0_3 as target  # noqa: E402


def test_repository_shadow_hierarchy_is_valid() -> None:
    result=target.validate(
        ROOT/"config"/"jrdb_edge_semantic_hierarchy_v0_3.json",
        ROOT/"config"/"jrdb_edge_candidate_templates_v0_2.json",
    )
    assert result["status"]=="PASS"
    assert result["mode"]=="SHADOW_ONLY"
    assert result["hierarchies"]==4
    assert result["virtual_contexts"]==1


def test_production_mode_is_rejected(tmp_path: Path) -> None:
    hierarchy=json.loads(
        (ROOT/"config"/"jrdb_edge_semantic_hierarchy_v0_3.json").read_text(encoding="utf-8")
    )
    hierarchy["mode"]="PRODUCTION"
    path=tmp_path/"hierarchy.json"
    path.write_text(json.dumps(hierarchy),encoding="utf-8")
    with pytest.raises(target.SemanticHierarchyError,match="SHADOW_ONLY"):
        target.validate(path,ROOT/"config"/"jrdb_edge_candidate_templates_v0_2.json")
