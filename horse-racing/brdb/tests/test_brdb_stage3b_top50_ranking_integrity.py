"""Regression checks for the pinned Stage 3-A ranking input."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import brdb_stage3b_top50_builder as builder


class RankingIntegrityTest(unittest.TestCase):
    def test_unexpected_ranking_is_rejected_before_parsing(self):
        with patch.object(builder, "sha256", side_effect=[
            builder.EXPECTED_PEDIGREE_SHA, builder.EXPECTED_RELATION_SHA, "0" * 64
        ]):
            with self.assertRaisesRegex(ValueError, "ranking SHA"):
                builder.build(Path("pedigree"), Path("relations"), Path("missing-ranking"), Path("seed"))

    def test_verified_ranking_reaches_seed_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ranking = root / "ranking.csv"
            ranking.write_text("name,birth_year,jrdb_lineage_code,sire_count,bms_count\n" +
                               "a,2000,1206,1,1\n" * 50, encoding="utf-8")
            seed = root / "seed.json"
            seed.write_text(json.dumps({"version": "wrong"}), encoding="utf-8")
            with patch.object(builder, "sha256", side_effect=[
                builder.EXPECTED_PEDIGREE_SHA, builder.EXPECTED_RELATION_SHA,
                builder.EXPECTED_RANKING_SHA
            ]):
                with self.assertRaisesRegex(ValueError, "seed version"):
                    builder.build(Path("pedigree"), Path("relations"), ranking, seed)


if __name__ == "__main__":
    unittest.main()
