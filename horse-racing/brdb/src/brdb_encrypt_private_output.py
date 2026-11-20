#!/usr/bin/env python3
"""Encrypt a transient horse-level BRDB output using the existing Data Storage bridge crypto."""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BRIDGE=ROOT/'tools'/'data-storage'/'scripts'/'drive_gpt_actions_bridge.py'

def load_bridge():
    spec=importlib.util.spec_from_file_location('drive_gpt_actions_bridge',BRIDGE)
    if spec is None or spec.loader is None:raise RuntimeError('bridge module unavailable')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--public-key',required=True)
    ap.add_argument('--ciphertext',required=True);ap.add_argument('--metadata',required=True);a=ap.parse_args()
    src=Path(a.input);require=src.is_file()
    if not require:raise ValueError('input missing')
    bridge=load_bridge();key=bridge.load_public_key(Path(a.public_key));data=src.read_bytes();cipher,meta=bridge.encrypt_file(data,key)
    out=Path(a.ciphertext);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(cipher)
    m={'contract_version':'brdb-encrypted-horse-level-output-v0.1','cipher':'AES-256-GCM','key_wrap':'RSA-OAEP-SHA256',**meta}
    Path(a.metadata).write_text(json.dumps(m,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':'ENCRYPTED','size_bytes':meta['size_bytes'],'ciphertext_sha256':meta['ciphertext_sha256']}))
if __name__=='__main__':main()
