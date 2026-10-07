import csv
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

MODULE_PATH = Path(__file__).parents[1] / "src" / "aggregate_jrdb_edge_v05_first_history.py"
SPEC = importlib.util.spec_from_file_location("first_history", MODULE_PATH)
first_history = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(first_history)


class FirstHistoryAggregationTests(unittest.TestCase):
    def test_warehouse_verification_requires_exact_partition_matrix_and_hashes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            assets = []
            for family in ("KYI", "SED"):
                for year in range(2010, 2026):
                    relative = f"objects/{family.lower()}/year={year}/asset.parquet"
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(f"{family}-{year}".encode())
                    assets.append({"family": family, "year": year, "relative_path": relative,
                                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                   "size_bytes": path.stat().st_size})
            manifest = {"status": "PASS", "generation_id": first_history.WAREHOUSE_GENERATION,
                        "families": ["KYI", "SED"], "years": list(range(2010, 2026)),
                        "asset_count": 32, "assets": assets}
            (root / "research_materialization_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = first_history.verify_warehouse(root)
            self.assertEqual(result["partition_count"], 32)
            self.assertEqual(result["family_partition_counts"], {"KYI": 16, "SED": 16})
            (root / assets[0]["relative_path"]).write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                first_history.verify_warehouse(root)

    def test_exact_history_flags_duplicate_reconciliation_and_unknowns(self):
        duckdb = __import__("duckdb")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            empty_sed = pa.table({"blood_registration_no": pa.array([], pa.string()),
                                  "race_key_raw": pa.array([], pa.string()), "horse_no": pa.array([], pa.string()),
                                  "race_date": pa.array([], pa.string()), "surface_code": pa.array([], pa.string())})
            empty_kyi = pa.table({"blood_registration_no": pa.array([], pa.string()), "race_key_raw": pa.array([], pa.string()),
                                  "horse_no": pa.array([], pa.string()), "blinker_code": pa.array([], pa.string())})
            assets = []
            for family in ("KYI", "SED"):
                for year in range(2010, 2026):
                    rel = f"objects/{family.lower()}/year={year}/asset.parquet"
                    path = root / rel; path.parent.mkdir(parents=True, exist_ok=True)
                    table = empty_kyi if family == "KYI" else empty_sed
                    pq.write_table(table, path)
                    assets.append({"family": family, "year": year, "relative_path": rel,
                                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size_bytes": path.stat().st_size})
            def sed(hid, key, day, surface, no="01"):
                return {"blood_registration_no": hid, "race_key_raw": key, "horse_no": no,
                        "race_date": day, "surface_code": surface}
            sed_rows = [sed("00000001", "r20", "2020-01-01", "1"), sed("00000001", "r21", "2021-01-01", "1"),
                        sed("00000001", "r22", "2022-01-01", "2"), sed("00000001", "r22", "2022-01-01", "2"),
                        sed("00000002", "r10", "2010-01-01", "1"), sed("00000002", "r23", "2023-01-01", "2")]
            # Replace the SED 2020, 2021, 2022 and 2023 annual partitions.
            for year in range(2010, 2026):
                rel = f"objects/sed/year={year}/asset.parquet"
                rows = [r for r in sed_rows if int(r["race_date"][:4]) == year]
                pq.write_table(pa.Table.from_pylist(rows, schema=empty_sed.schema) if not rows else pa.Table.from_pylist(rows), root / rel)
            kyi_rows = [
                {"blood_registration_no": "00000001", "race_key_raw": "r20", "horse_no": "01", "blinker_code": "0"},
                {"blood_registration_no": "00000001", "race_key_raw": "r21", "horse_no": "01", "blinker_code": "1"},
                {"blood_registration_no": "00000001", "race_key_raw": "r22", "horse_no": "01", "blinker_code": "3"},
                {"blood_registration_no": "00000002", "race_key_raw": "r10", "horse_no": "01", "blinker_code": "0"},
                {"blood_registration_no": "00000002", "race_key_raw": "r23", "horse_no": "01", "blinker_code": "1"},
            ]
            pq.write_table(pa.Table.from_pylist(kyi_rows[:1]), root / "objects/kyi/year=2020/asset.parquet")
            pq.write_table(pa.Table.from_pylist(kyi_rows[1:2]), root / "objects/kyi/year=2021/asset.parquet")
            pq.write_table(pa.Table.from_pylist(pa.Table.from_pylist(kyi_rows[2:3]).to_pylist()), root / "objects/kyi/year=2022/asset.parquet")
            pq.write_table(pa.Table.from_pylist(kyi_rows[3:4]), root / "objects/kyi/year=2010/asset.parquet")
            pq.write_table(pa.Table.from_pylist(kyi_rows[4:]), root / "objects/kyi/year=2023/asset.parquet")
            # Refresh manifest SHA/size after annual fixture partitions were replaced.
            for asset in assets:
                path = root / asset["relative_path"]
                asset["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest(); asset["size_bytes"] = path.stat().st_size
            manifest = {"status": "PASS", "generation_id": first_history.WAREHOUSE_GENERATION,
                        "families": ["KYI", "SED"], "years": list(range(2010, 2026)), "asset_count": 32, "assets": assets}
            (root / "research_materialization_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            feature_rows = [
                {"race_date": "2022-01-01", "race_key": "r22", "horse_no": "01", "horse_id": "00000001", "surface_code": "2", "sire_name": "Sire A", "is_pre_race_eligible": 1},
                {"race_date": "2023-01-01", "race_key": "r23", "horse_no": "01", "horse_id": "00000002", "surface_code": "2", "sire_name": "Sire B", "is_pre_race_eligible": 1},
            ]
            feature = root / "feature.parquet"; pq.write_table(pa.Table.from_pylist(feature_rows), feature)
            out = root / "enriched.parquet"
            con = duckdb.connect()
            try:
                audit = first_history.build_history_features(con, root, feature, out)
                cur = con.execute("SELECT * FROM read_parquet(?)", [str(out)])
                names = [d[0] for d in cur.description]
                rows = {r["horse_id"]: r for r in (dict(zip(names, row)) for row in cur.fetchall())}
            finally:
                con.close()
            self.assertFalse(rows["00000001"]["first_dirt"] is None)
            self.assertTrue(rows["00000001"]["first_dirt"])
            self.assertIsNone(rows["00000002"]["first_dirt"])  # 2010 left censor
            self.assertIsNone(rows["00000002"]["first_turf"])  # left censor also applies to the other surface
            self.assertFalse(rows["00000001"]["first_blinkers"])  # prior code 1; target code 3 is not first
            self.assertEqual(audit["sed_duplicate_groups_collapsed"], 1)
            self.assertGreaterEqual(audit["blinker_code_parity_mismatch_count"], 0)

    def test_frozen_value_gate_and_deterministic_history_ids(self):
        base = first_history.base
        base.SPECS.update(first_history.FIRST_SPECS)
        self.assertTrue(base.positive_value_eligible(5, 100))
        self.assertFalse(base.positive_value_eligible(4, 500))
        self.assertEqual(base.support_class(5), "MICRO")
        row = {"sire_name": "Sire A", "first_dirt": "true"}
        self.assertEqual(base.candidate_id("T4_SIRE_FIRST_DIRT", row), base.candidate_id("T4_SIRE_FIRST_DIRT", dict(reversed(list(row.items())))))


if __name__ == "__main__":
    unittest.main()
