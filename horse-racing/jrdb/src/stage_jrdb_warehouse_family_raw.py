#!/usr/bin/env python3
"""Stage one frozen JRDB family on an ephemeral Actions runner."""
from __future__ import annotations
import argparse, hashlib, json, time, zipfile
from pathlib import Path
import requests

def stage(inventory_path: Path, family: str, output_root: Path) -> dict:
    inventory=json.loads(inventory_path.read_text(encoding="utf-8"))
    family=family.upper()
    source=next((x for x in inventory["families"] if x["family"]==family and x.get("status")=="TARGET"),None)
    if source is None: raise ValueError(f"unavailable target family: {family}")
    archives=sorted((x for x in source["archives"] if x.get("archive_class")=="annual"),key=lambda x:x["year"])
    if [x["year"] for x in archives] != list(range(2010,2026)): raise ValueError(f"incomplete annual coverage: {family}")
    session=requests.Session(); receipt=[]
    for item in archives:
        target=output_root/str(item["year"])/f"{family}.zip"; target.parent.mkdir(parents=True,exist_ok=True)
        for attempt in range(1,5):
            part=target.with_suffix(".zip.part")
            try:
                response=session.get("https://drive.usercontent.google.com/download",params={"id":item["drive_id"],"export":"download","confirm":"t"},stream=True,timeout=(20,180))
                response.raise_for_status()
                with part.open("wb") as handle:
                    for block in response.iter_content(1024*1024):
                        if block: handle.write(block)
                if part.stat().st_size != int(item["size_bytes"]): raise ValueError("size mismatch")
                with zipfile.ZipFile(part) as archive:
                    if archive.testzip(): raise ValueError("corrupt ZIP")
                digest=hashlib.sha256(part.read_bytes()).hexdigest(); part.replace(target)
                receipt.append({"year":item["year"],"drive_id":item["drive_id"],"size_bytes":item["size_bytes"],"sha256":digest,"attempt":attempt}); break
            except Exception:
                part.unlink(missing_ok=True)
                if attempt==4: raise
                time.sleep(attempt)
    return {"status":"PASS","family":family,"archives":receipt}

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--inventory",type=Path,required=True); p.add_argument("--family",required=True); p.add_argument("--output-root",type=Path,required=True); p.add_argument("--receipt",type=Path,required=True); a=p.parse_args()
    result=stage(a.inventory,a.family,a.output_root); a.receipt.parent.mkdir(parents=True,exist_ok=True); a.receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
