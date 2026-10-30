"""Deterministic descriptive frequency tables for validated historical rows."""
from collections import defaultdict

AXES = {"popularity": "final_win_popularity", "frame": "frame_no", "running_style": "running_style",
        "age": "age", "sire": "sire_name", "jockey": "jockey_name",
        "previous_distance": "previous_distance", "previous_class": "previous_class"}


def aggregate(rows):
    output = {}
    for axis, field in AXES.items():
        groups = defaultdict(lambda: {"starts": 0, "finishes": [0, 0, 0, 0], "race_keys": set()})
        missing = 0
        for row in rows:
            value, finish = row.get(field), row.get("finish")
            if value in (None, "") or not isinstance(finish, int) or finish < 1:
                missing += 1
                continue
            group = groups[str(value)]
            group["starts"] += 1
            group["finishes"][finish - 1 if finish <= 3 else 3] += 1
            group["race_keys"].add(row["race_key"])
        output[axis] = {"groups": [{"group": key, "starts": value["starts"],
                                    "finishes": value["finishes"], "top3": sum(value["finishes"][:3]),
                                    "race_keys": sorted(value["race_keys"])}
                                   for key, value in sorted(groups.items())],
                        "missing_count": missing,
                        "missing_reason": "value_or_finish_missing" if missing else None}
    return output
