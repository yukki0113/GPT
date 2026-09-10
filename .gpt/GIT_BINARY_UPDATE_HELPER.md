# Binary update preparation helper — Compatibility Fallback

この例は、direct binary updateが利用できず `.gpt/GIT_BINARY_UPDATE_ISSUE.md` の互換Issue経路を使う必要がある場合だけ使用します。

通常のUTF-8テキスト変更には使いません。GitHub正本バイナリでも、現在の環境でdirect write可能ならdirect経路を優先します。外部ストレージ正本には使用しません。

```python
from pathlib import Path
import base64
import hashlib

source = Path("/path/to/file.xlsx")
data = source.read_bytes()
encoded = base64.b64encode(data).decode("ascii")
chunk_size = 48_000
chunks = [encoded[i:i + chunk_size] for i in range(0, len(encoded), chunk_size)]

print("size_bytes:", len(data))
print("sha256:", hashlib.sha256(data).hexdigest())
print("chunks:", len(chunks))

for index, chunk in enumerate(chunks, start=1):
    print(f"[gpt-git-binary-chunk {index}/{len(chunks)}]")
    print("```text")
    print(chunk)
    print("```")
```

出力をIssue本文・chunk comment登録に使用し、全chunk登録後に `[gpt-git-binary-commit]` を投稿します。

Issue発行前には `.gpt/ISSUE_REQUEST_CONTRACTS.md` を適用してください。認証済み `gh` CLI環境でこのfallbackを使う場合は、手作業より `.gpt/tools/gpt_git_binary_tool.py update` を優先します。
