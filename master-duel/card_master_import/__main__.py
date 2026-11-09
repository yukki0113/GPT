"""CLI outputs aggregate audit only; DB ZIP is written to a new private path."""
import argparse
import json
import os
from pathlib import Path
from .importer import read_inputs, dry_run, convert

def main():
    p=argparse.ArgumentParser()
    p.add_argument('md'); p.add_argument('cards')
    p.add_argument('--base-zip'); p.add_argument('--output'); p.add_argument('--acquired-at')
    args=p.parse_args()
    if any((args.base_zip,args.output,args.acquired_at)) and not all((args.base_zip,args.output,args.acquired_at)): p.error('conversion requires --base-zip, --output, and --acquired-at')
    md,cards,meta=read_inputs(args.md,args.cards)
    if len(md) != 13948 or len(cards) != 14416: raise ValueError('unexpected pinned input row counts')
    audit,rows=dry_run(md,cards,meta)
    print(json.dumps(audit,ensure_ascii=False,sort_keys=True))
    if not audit['ok']: return 1
    if args.output:
        data,_=convert(Path(args.base_zip).read_bytes(),rows,audit,acquired_at=args.acquired_at)
        fd=os.open(args.output,os.O_WRONLY | os.O_CREAT | os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f: f.write(data)
    return 0

if __name__=='__main__': raise SystemExit(main())
