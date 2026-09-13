import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from forward_trial_analysis_import import ForwardTrialValidationError
from run_forward_trial_chat_import import resolve_source_files


class RunForwardTrialChatImportTest(unittest.TestCase):
    def _files(self):
        return [
            {"id": "prediction-file-id", "name": "20260912_事前予想_ForwardTrial_Ver0.1.csv"},
            {"id": "sales-file-id", "name": "20260912_2連単1点販売選別_ForwardTrial_Ver0.1.csv"},
            {"id": "result-file-id", "name": "20260912_結果.csv"},
            {"id": "racecard-file-id", "name": "20260912_公式出走表.csv"},
            {"id": "rationale-file-id", "name": "20260912_予想根拠.csv"},
        ]

    def test_discovers_one_source_per_kind(self):
        resolved = resolve_source_files(self._files(), "20260912")
        self.assertEqual(set(resolved), {"prediction", "sales", "result", "racecard"})
        self.assertEqual(resolved["prediction"]["id"], "prediction-file-id")

    def test_ambiguous_source_fails_closed(self):
        files = self._files() + [{"id": "result-file-id-2", "name": "20260912_結果_copy.csv"}]
        with self.assertRaises(ForwardTrialValidationError):
            resolve_source_files(files, "20260912")

    def test_explicit_ids_must_be_in_folder(self):
        explicit = {"prediction": "missing", "sales": "sales-file-id",
                    "result": "result-file-id", "racecard": "racecard-file-id"}
        with self.assertRaises(ForwardTrialValidationError):
            resolve_source_files(self._files(), "20260912", explicit)


if __name__ == "__main__":
    unittest.main()
