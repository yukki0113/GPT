#!/usr/bin/env python3
"""Deterministic research-only D4 sidecar from pinned canonical D3 inputs.

The requested race field is explicitly user-supplied for research; no PACI
implicit fetching, no prediction, no modifying live/frozen review contracts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from brdb_d4_supplemental_adapter import build, D4ContractError

PINS = {
    'full': '705a85d4c43b369b14cbba9177f5af13ed3111f1a5031a97ee76acf51064e764',
    'temporal': '27abb3aafabd8b5350009cf8623d43246bda70365427cc772d07e3aba4d8c8bf',
    'receipt': '4a128dc02baf4a6ee82a1b560fa1cafb62f540cba8bed38511a97af43c3abd2e',
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(full_path:Path,temporal_path:Path,receipt_path:Path,
        context_path:Path,output_path:Path)->dict:
    for label,path in (('full',full_path),('temporal',temporal_path),('receipt',receipt_path)):
        if sha256(path) != PINS[label]:
            raise D4ContractError('frozen D3 source SHA mismatch: '+label)
    full=json.loads(full_path.read_text(encoding='utf-8'))
    temporal=json.loads(temporal_path.read_text(encoding='utf-8'))
    receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    context=json.loads(context_path.read_text(encoding='utf-8'))
    if set(context) != {'race','entrants'}:
        raise D4ContractError('research context must contain race and entrants only')
    sidecar=build(full,temporal,receipt,context['race'],context['entrants'])
    sidecar['provenance']={
        'd3_full_sha256':PINS['full'],
        'd3_temporal_sha256':PINS['temporal'],
        'd3_receipt_sha256':PINS['receipt'],
        'research_field_sha256':sha256(context_path),
    }
    output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text(json.dumps(sidecar,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return {'status':'PASS','research_only':True,
            'horse_count':len(sidecar['horses']),
            'research_evidence_items':sidecar['aggregate_coverage']['research_evidence_items'],
            'output_sha256':sha256(output_path)}


def main():
    parser=argparse.ArgumentParser()
    for arg in ('full','temporal','receipt','context','output'):
        parser.add_argument('--'+arg,required=True,type=Path)
    a=parser.parse_args()
    print(json.dumps(run(a.full,a.temporal,a.receipt,a.context,a.output),sort_keys=True))


if __name__ == '__main__':
    main()