import base64
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "gpt_git_binary_tool.py"
SPEC = importlib.util.spec_from_file_location("gpt_git_binary_tool", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load module: {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GitBinaryToolTests(unittest.TestCase):
    """Unit tests for protocol parsing and local binary transformation helpers."""

    def test_normalize_repository_path_rejects_parent(self) -> None:
        """Parent traversal must be rejected before any GitHub request is sent."""
        with self.assertRaises(MODULE.GitBinaryToolError):
            MODULE.normalize_repository_path("../secret.xlsx")

    def test_parse_read_result(self) -> None:
        """Structured binary-read result JSON must be parsed from the final comment."""
        body = (
            "@yukki0113\n\n"
            "✅ ready\n\n"
            "GIT_BINARY_READ_RESULT\n"
            "```json\n"
            '{"status":"success","run_id":123,"artifact_name":"abc",'
            '"size_bytes":5,"sha256":"00"}\n'
            "```\n"
        )
        result = MODULE.parse_read_result(body)
        self.assertIsNotNone(result)
        self.assertEqual(123, result["run_id"])

    def test_extract_update_success(self) -> None:
        """Final binary-update commit metadata must be extracted exactly."""
        body = (
            "✅ Binary Git update reconstructed, verified, and pushed to `main`.\n\n"
            "Path: `a/b.xlsx`\n"
            "Size: `123 bytes`\n"
            "SHA-256: `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`\n"
            "Commit: `bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb`\n"
        )
        result = MODULE.extract_update_success(body)
        self.assertIsNotNone(result)
        self.assertEqual("a/b.xlsx", result["target_path"])
        self.assertEqual(
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            result["commit_sha"],
        )

    def test_split_base64_payload_round_trip(self) -> None:
        """Chunking must preserve the exact original bytes after recombination."""
        with tempfile.TemporaryDirectory() as temporary_text:
            path = Path(temporary_text) / "sample.bin"
            original = bytes(range(256)) * 100
            path.write_bytes(original)

            encoded, chunks = MODULE.split_base64_payload(path, 1000)

            self.assertEqual(encoded, "".join(chunks))
            self.assertEqual(original, base64.b64decode("".join(chunks)))


if __name__ == "__main__":
    unittest.main()
