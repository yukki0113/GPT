"""Materialize audited exact P8B source files to a new directory. No data retrieval or execution."""
from pathlib import Path
import json,hashlib,sys
root=Path(__file__).parent
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
for p in sorted(root.glob('executed_sources_*.json')):
    b=json.loads(p.read_text())
    assert b['format']=='utf8-source-bundle-v1'
    for name,x in b['files'].items():
        rel=Path(name);assert not rel.is_absolute() and '..' not in rel.parts
        dst=out/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        data=x['text'].encode('utf-8');assert hashlib.sha256(data).hexdigest()==x['sha256']
        if dst.exists():assert dst.read_bytes()==data
        else:dst.write_bytes(data)
print('Exact source materialized. See evidence report and input/Freeze manifests before execution.')
