#!/usr/bin/env python3
"""Research-only ④ detailed sidecar and non-predictive preview from fixed M7 output.

No production BRDB CURRENT/RaceNote/PWA writes. Outputs must be outside repo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import jsonschema

from brdb_m7_relatives_detail_candidate import build as detail_build
from brdb_m7_research_consumer_preview import build_preview

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / 'horse-racing/brdb/schema'


def raw(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate(name, payload):
    schema = json.loads((SCHEMAS/name).read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(payload)


def run(v03_path, relatives_path, output_dir):
    v03_path, relatives_path = Path(v03_path).resolve(strict=True), Path(relatives_path).resolve(strict=True)
    output_dir = Path(output_dir).resolve()
    if output_dir.is_relative_to(ROOT):
        raise ValueError('horse-level research output must not be in repository')
    v03 = json.loads(v03_path.read_text(encoding='utf-8'))
    relatives = json.loads(relatives_path.read_text(encoding='utf-8'))
    validate('brdb_integrated_review_v0_3_candidate.schema.json', v03)

    def create():
        detail = detail_build(v03, relatives)
        validate('brdb_m7_relatives_detail_v0_1_candidate.schema.json', detail)
        preview = build_preview(v03, detail)
        validate('brdb_m7_research_consumer_preview_v0_1.schema.json', preview)
        return raw(detail), raw(preview)

    a, b = create(), create()
    if a != b:
        raise ValueError('non-deterministic detailed/preview replay')
    receipt = {
        'status': 'RESEARCH_ONLY_PASS', 'publication_authorized': False,
        'prediction_safe': False, 'historical_asof_status': 'AS_OF_UNVERIFIED',
        'race_key': v03['race']['race_key'], 'field_size': len(v03['horses']),
        'input_sha256': {'integrated_v03_bytes': sha(v03_path.read_bytes()),
                         'relatives_bytes': sha(relatives_path.read_bytes())},
        'output_sha256': {'relatives_detail':sha(a[0]), 'research_preview':sha(a[1])},
        'coverage': detail_build(v03, relatives)['aggregate_coverage'],
        'schemas_validated': ['v0.3', '④-detail-v0.1', 'research-preview-v0.1'],
        'two_runs_byte_identical': True,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (('m7_relatives_detail_candidate.json', a[0]),
                       ('m7_research_consumer_preview.json', a[1]),
                       ('m7_relatives_detail_receipt.json', raw(receipt))):
        (output_dir/name).write_bytes(data)
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--integrated-v03', required=True, type=Path)
    p.add_argument('--relatives', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    a=p.parse_args()
    print(json.dumps(run(a.integrated_v03, a.relatives, a.output_dir),
                     ensure_ascii=False, sort_keys=True))

if __name__ == '__main__':
    main()