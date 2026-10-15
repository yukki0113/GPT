"""Public evidence schema and consumer semantics."""
import copy
import json
from pathlib import Path
from unittest.mock import patch

import jsonschema
import pytest

from test_jrdb_race_lap_dataset import archive, build_dataset, PARTIAL
from jrdb_race_lap_reader import RaceLapReader

SCHEMA=json.loads((Path(__file__).resolve().parents[1]/"schema/race_lap_evidence_schema.json").read_text())
VALIDATOR=jsonschema.Draft202012Validator(SCHEMA,format_checker=jsonschema.FormatChecker())


@pytest.mark.parametrize("options", [{},{"distance":1700,"laps":PARTIAL},{"laps":[]},
                                     {"laps":[],"pace":"3","comment":"注意"}])
def test_public_contract(tmp_path,options):
    p=tmp_path/"race_lap.parquet"
    build_dataset([archive(tmp_path,**options)],p,tmp_path/"audit.json")
    reader=RaceLapReader.from_parquet(p)
    context=reader.get_race_context("05264501")
    json.dumps(context,ensure_ascii=False,allow_nan=False)
    VALIDATOR.validate(context)
    assert context["policy"]["leader_based"] is True
    assert context["policy"]["individual_sectionals"] is False
    assert context["policy"]["score_status"] == "NO_ADDITIVE_SCORE"
    assert context["policy"]["target_race_usage"] == "HISTORICAL_ONLY_AS_OF_EXCLUSIVE"
    assert context["laps"]["individual_horse_sectionals"] is False
    assert context["provenance"]["archive"] == "SED261012.zip"
    segments=context["laps"]["segments"]
    if options.get("laps") == []:
        assert context["coverage"]["status"] == "NO_LAPS"
        assert segments == []
        assert all(x is None for x in context["shape"].values())
    else:
        assert segments[0]["start_m"] == 0
        assert segments[-1]["end_m"] == context["race"]["distance_m"]
        assert all(a["end_m"] == b["start_m"] for a,b in zip(segments,segments[1:]))
        if options.get("distance") == 1700:
            assert segments[0]["segment_distance_m"] == 100
            assert segments[0]["lap_sec"] == 7.0
            assert context["shape"]["early3f_sec"] is None
    assert reader.get_race_context("00000000") is None
    with patch.object(reader.store,"get_many",wraps=reader.store.get_many) as batch:
        result=reader.get_race_contexts(["05264501","00000000"])
        assert result == {"05264501":context,"00000000":None}
        assert batch.call_count == 1
    assert reader.get_race_contexts([]) == {}
    bad=copy.deepcopy(context); bad["policy"]["score_status"]="SCORE"
    assert list(VALIDATOR.iter_errors(bad))
    bad=copy.deepcopy(context); bad["shape"]["categorical_label"]="FAST"
    assert list(VALIDATOR.iter_errors(bad))


def test_schema_is_valid():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
