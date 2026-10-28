#!/usr/bin/env python3
"""Publish one validated LLM prediction checkpoint to GitHub, then verify it.

Requires an authenticated gh CLI; never commits to main or generates predictions.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from racenote_v055_r6_publish_handoff import make
from racenote_v055_r6_race_checkpoint_store import canon
from racenote_v055_turn2_two_phase import resolve_root

def gh(method: str, endpoint: str, body=None):
    command=["gh","api","--method",method,endpoint,"-H","Accept: application/vnd.github+json"]
    if body is not None:
        # --input - keeps JSON data out of arguments and uses GitHub contents REST API.
        command+=["--input","-"]
    result=subprocess.run(command,input=json.dumps(body,ensure_ascii=False) if body is not None else None,
                          text=True,capture_output=True,check=False)
    if result.returncode:
        raise RuntimeError("GitHub operation failed: "+result.stderr[:500])
    return json.loads(result.stdout)

def publish(root: Path,store: Path,draft: Path):
    plan=make(root,store,"checkpoint",draft)
    repo=plan["repo"]
    path=plan["path"]
    branch=plan["branch"]
    endpoint=f"repos/{repo}/contents/{path}"
    expected=canon(json.loads(draft.read_text(encoding='utf-8')))
    if hashlib.sha256(expected).hexdigest()!=plan['sha256']:
        raise ValueError('checkpoint canonical SHA mismatch')
    # The remote file must be absent or exactly identical; never overwrite a revision.
    def remote():
        try:
            return gh("GET",endpoint+f"?ref={branch}")
        except RuntimeError as exc:
            if "404" in str(exc):return None
            raise
    existing=remote()
    if existing:
        found=base64.b64decode(existing["content"].replace("\n",""))
        if hashlib.sha256(found).hexdigest()!=plan["sha256"]:
            raise ValueError("immutable remote checkpoint conflict")
        result="ALREADY_PUBLISHED"
    else:
        response=gh("PUT",endpoint,{"message":"RaceNote r6 LLM checkpoint: "+path.rsplit("/",1)[-1],
            "branch":branch,"content":base64.b64encode(expected).decode("ascii")})
        if not response.get("commit",{}).get("sha"):
            raise ValueError("GitHub commit SHA missing")
        result="PUBLISHED"
    verified=remote()
    if not verified:
        raise ValueError("GitHub read-after-write verification failed")
    actual=base64.b64decode(verified["content"].replace("\n",""))
    if hashlib.sha256(actual).hexdigest()!=plan["sha256"]:
        raise ValueError("GitHub persisted SHA mismatch")
    return {"status":result,"path":path,"branch":branch,"sha256":plan["sha256"],
            "completed":plan["completed"],"remaining":plan["remaining"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--store",required=True,type=Path)
    p.add_argument("--draft",required=True,type=Path)
    args=p.parse_args()
    print(json.dumps(publish(resolve_root(args.root),args.store,args.draft),ensure_ascii=False))
if __name__=="__main__":
    try:main()
    except (ValueError,RuntimeError,FileNotFoundError) as exc:
        print(json.dumps({"status":"BLOCKED","error":str(exc)},ensure_ascii=False),file=sys.stderr)
        sys.exit(1)
