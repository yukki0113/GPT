#!/usr/bin/env python3
"""Unified external I/O entry point."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.gpt_io.git.git_binary_tool import main as git_main
def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {"git", "gdrive"}: print("usage: gpt_io.py {git|gdrive} ...", file=sys.stderr); return 2
    backend=sys.argv.pop(1)
    if backend=="git": return git_main()
    from tools.gpt_io.gdrive.gdrive_tool import main as gdrive_main
    return gdrive_main()
if __name__ == "__main__": raise SystemExit(main())
