# Binary update preparation helper

ChatGPT / Work のローカル作業領域にあるファイルを `[gpt-git-binary-update]` Issueへ送る際の準備例です。

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

この出力をIssue本文・コメント登録に使用し、全チャンク登録後に `[gpt-git-binary-commit]` コメントを投稿します。
