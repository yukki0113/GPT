import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1] / "src"))

from racenote_analysis_backend import DuckDBParquetAnalysisBackend
import racenote_history_engine as engine


class RaceNoteParquetBackendTest(unittest.TestCase):
    def test_as_of_query_excludes_target_and_future_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            generation = root / "generations" / "g-test"
            fact = generation / "fact_entry_result_lite" / "year=2025.parquet"
            fact.parent.mkdir(parents=True)
            rows = [
                {"race_date": "2024-05-01", "year": 2024, "venue_code": "06", "race_no": 1, "track_type": "1", "distance": 1600, "race_key": "r2024", "horse_no": 1, "horse_id": "h", "frame_no": 1, "sire_name": "Sire-A", "jockey_name": "J", "finish": 1, "final_win_odds": 2.0, "final_win_popularity": 1},
                {"race_date": "2025-05-01", "year": 2025, "venue_code": "06", "race_no": 1, "track_type": "1", "distance": 1600, "race_key": "r2025a", "horse_no": 1, "horse_id": "h", "frame_no": 1, "sire_name": "Sire-A", "jockey_name": "J", "finish": 1, "final_win_odds": 2.0, "final_win_popularity": 1},
                {"race_date": "2025-06-01", "year": 2025, "venue_code": "06", "race_no": 1, "track_type": "1", "distance": 1600, "race_key": "target", "horse_no": 1, "horse_id": "h", "frame_no": 1, "sire_name": "Sire-A", "jockey_name": "J", "finish": 1, "final_win_odds": 2.0, "final_win_popularity": 1},
                {"race_date": "2025-07-01", "year": 2025, "venue_code": "06", "race_no": 1, "track_type": "1", "distance": 1600, "race_key": "future", "horse_no": 1, "horse_id": "h", "frame_no": 1, "sire_name": "Sire-A", "jockey_name": "J", "finish": 1, "final_win_odds": 2.0, "final_win_popularity": 1},
            ]
            table = pa.Table.from_pylist(rows)
            pq.write_table(table, fact)
            meta = {}
            for name in ("meta_analysis_build", "meta_analysis_ingest_batch"):
                path = generation / f"{name}.parquet"
                path.write_bytes(b"metadata")
                meta[name] = {"relative_path": str(path.relative_to(root)), "rows": 0, "sha256": hashlib.sha256(b"metadata").hexdigest(), "size_bytes": 8}
            manifest = {
                "artifact_type": "jrdb_analysis",
                "schema_version": "v1.3",
                "storage_format": "parquet",
                "validation_status": "PASS",
                "generation_id": "g-test",
                "total_rows": len(rows),
                "fact_table": {"name": "fact_entry_result_lite", "canonical_key": ["race_key", "horse_no"], "partitions": [{"year": 2025, "relative_path": str(fact.relative_to(root)), "rows": len(rows), "sha256": hashlib.sha256(fact.read_bytes()).hexdigest(), "size_bytes": fact.stat().st_size}]},
                "metadata_tables": meta,
            }
            (generation / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "current.json").write_text(json.dumps({"status": "CURRENT", "generation_id": "g-test", "manifest": "generations/g-test/manifest.json"}), encoding="utf-8")

            backend = DuckDBParquetAnalysisBackend(root)
            try:
                result = engine.as_of_summary(backend, "sire_name", "Sire-A", "2025-06-01", "06", "1", "distance=?", [1600], 5)
                self.assertEqual(result["starts"], 2)
                self.assertEqual(result["wins"], 2)
                target = backend.execute("SELECT finish FROM analysis_fact WHERE race_key=?", ["target"]).fetchone()
                self.assertEqual(target["finish"], 1)
            finally:
                backend.close()


if __name__ == "__main__":
    unittest.main()
