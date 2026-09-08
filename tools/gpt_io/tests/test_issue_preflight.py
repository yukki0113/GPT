import tempfile
from pathlib import Path
import subprocess
import unittest

from tools.gpt_io.git.issue_preflight import PreflightError, validate_request


class IssuePreflightTests(unittest.TestCase):
    def test_git_update_requires_commit_message(self) -> None:
        body = """```diff
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-old
+new
```
"""
        with self.assertRaisesRegex(PreflightError, "commit_message"):
            validate_request("[gpt-git-update] test", body)

    def test_git_update_rejects_protected_workflow_path(self) -> None:
        body = """commit_message: test

```diff
--- a/.github/workflows/example.yml
+++ b/.github/workflows/example.yml
@@ -1 +1 @@
-old
+new
```
"""
        with self.assertRaisesRegex(PreflightError, "protected path"):
            validate_request("[gpt-git-update] test", body)

    def test_binary_read_accepts_path_and_request_id(self) -> None:
        result = validate_request(
            "[gpt-git-binary-read] ledger",
            "path: horse-racing/example.xlsx\nrequest_id: ledger-20260908\n",
        )
        self.assertEqual("gpt-git-binary-read", result["protocol"])

    def test_binary_update_rejects_bad_sha(self) -> None:
        body = """target_path: example/file.xlsx
commit_message: update
sha256: bad
size_bytes: 123
chunks: 1
encoding: base64
"""
        with self.assertRaisesRegex(PreflightError, "sha256"):
            validate_request("[gpt-git-binary-update] update", body)

    def test_generic_required_keys(self) -> None:
        result = validate_request(
            "[PROJECT_REQUEST] test",
            "run_id: 123\nartifact_name: output\n",
            protocol="generic",
            required_keys=["run_id", "artifact_name"],
        )
        self.assertEqual("generic-key-value", result["protocol"])

    def test_git_apply_check_detects_stale_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "README.md").write_text("current\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "init"],
                check=True,
            )
            body = """commit_message: stale patch

```diff
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-old
+new
```
"""
            with self.assertRaisesRegex(PreflightError, "patch does not apply|patch failed|while searching"):
                validate_request("[gpt-git-update] stale", body, repo_root=repo)


if __name__ == "__main__":
    unittest.main()
