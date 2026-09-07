"""Machine-readable Issue protocol helpers."""
import json
import re
MARKER="GDRIVE_RESULT"
TITLE_PREFIX="[gpt-gdrive-request]"
def parse_issue(title: str, body: str):
    if not title.startswith(TITLE_PREFIX): raise ValueError("invalid Drive request title")
    match=re.search(r"```json\s*(\{.*\})\s*```", body, re.S)
    return json.loads(match.group(1) if match else body)
def format_result(result): return f"{MARKER}\n```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```"
