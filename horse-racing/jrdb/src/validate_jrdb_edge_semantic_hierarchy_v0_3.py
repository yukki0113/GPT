#!/usr/bin/env python3
"""Validate the Edge v0.3 shadow semantic hierarchy contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class SemanticHierarchyError(RuntimeError):
    pass


def _load(path: str | Path) -> dict[str, Any]:
    value=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value,dict):
        raise SemanticHierarchyError(f"JSON object required: {path}")
    return value


def validate(
    hierarchy_path: str | Path,
    templates_path: str | Path,
) -> dict[str, Any]:
    hierarchy=_load(hierarchy_path)
    templates=_load(templates_path)

    if hierarchy.get("mode")!="SHADOW_ONLY":
        raise SemanticHierarchyError("v0.3 semantic hierarchy must remain SHADOW_ONLY")

    template_rows=templates.get("templates")
    if not isinstance(template_rows,list):
        raise SemanticHierarchyError("template config has no templates list")
    known={
        str(row.get("template_id"))
        for row in template_rows
        if isinstance(row,dict) and row.get("enabled") is True
    }

    contexts=hierarchy.get("virtual_contexts")
    if not isinstance(contexts,list):
        raise SemanticHierarchyError("virtual_contexts must be a list")
    context_ids=[str(row.get("context_id") or "") for row in contexts if isinstance(row,dict)]
    if any(not value for value in context_ids) or len(context_ids)!=len(set(context_ids)):
        raise SemanticHierarchyError("virtual context ids must be non-empty and unique")
    context_set=set(context_ids)

    refs:set[str]=set()
    for item in hierarchy.get("hierarchies") or []:
        if not isinstance(item,dict):
            raise SemanticHierarchyError("hierarchy row must be an object")
        child=str(item.get("child_template") or "")
        if child not in known:
            raise SemanticHierarchyError(f"unknown child_template: {child}")
        refs.add(child)
        parent_template=item.get("parent_template")
        parent_context=item.get("parent_context")
        if bool(parent_template)==bool(parent_context):
            raise SemanticHierarchyError(
                f"{item.get('hierarchy_id')}: specify exactly one parent_template or parent_context"
            )
        if parent_template:
            parent=str(parent_template)
            if parent not in known:
                raise SemanticHierarchyError(f"unknown parent_template: {parent}")
            refs.add(parent)
        else:
            parent=str(parent_context)
            if parent not in context_set:
                raise SemanticHierarchyError(f"unknown parent_context: {parent}")

    for group in hierarchy.get("orthogonal_groups") or []:
        if not isinstance(group,dict):
            raise SemanticHierarchyError("orthogonal group must be an object")
        for template in group.get("templates") or []:
            if str(template) not in known:
                raise SemanticHierarchyError(f"unknown orthogonal template: {template}")
            refs.add(str(template))

    for template in hierarchy.get("unresolved_templates") or []:
        if str(template) not in known:
            raise SemanticHierarchyError(f"unknown unresolved template: {template}")
        refs.add(str(template))

    derivations=hierarchy.get("deterministic_derivations") or {}
    frame=(derivations.get("frame_zone_from_frame_no") or {})
    expected={str(value) for value in range(1,9)}
    if set(frame)!=expected:
        raise SemanticHierarchyError("frame_zone_from_frame_no must define frames 1..8 exactly")
    if set(frame.values())-{"INNER","MIDDLE","OUTER"}:
        raise SemanticHierarchyError("invalid frame-zone value")

    return {
        "status":"PASS",
        "design_version":hierarchy.get("design_version"),
        "mode":hierarchy.get("mode"),
        "enabled_v02_templates":len(known),
        "referenced_v02_templates":len(refs),
        "virtual_contexts":len(context_set),
        "hierarchies":len(hierarchy.get("hierarchies") or []),
        "orthogonal_groups":len(hierarchy.get("orthogonal_groups") or []),
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--hierarchy",required=True)
    parser.add_argument("--templates",required=True)
    args=parser.parse_args()
    result=validate(args.hierarchy,args.templates)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
