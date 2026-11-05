"""D1 catalogue governance only. No inferred lineage, joins, scores or aptitude."""
from __future__ import annotations

import json
import re
from pathlib import Path

REGIONS = frozenset({
    'JP_RACING', 'US_RACING', 'EU_RACING', 'SOUTHERN_HEMISPHERE_RACING'
})
ROLES = frozenset({
    'BMS_EXACT', 'SIRE_EXACT', 'ANY_VERIFIED_ANCESTOR',
    'REVIEWED_REGION_COMPOSITION'
})


class CatalogError(ValueError):
    pass


def load_catalog(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _required_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f'{field}: nonempty string required')


def _path_ok(path):
    return bool(re.fullmatch(r'[SD]{1,5}', path))


def validate_catalogs(regional, blood):
    """Fail closed on accidental approval or unjustified ancestry mappings."""
    if regional.get('status') != 'RESEARCH_CANDIDATES_NOT_APPROVED':
        raise CatalogError('regional catalogue cannot be approved in D1')
    if blood.get('status') != 'RESEARCH_CANDIDATES_NOT_APPROVED':
        raise CatalogError('hypothesis catalogue cannot be approved in D1')
    if regional.get('catalog_version') != 'brdb-regional-roots-candidate-v0.1':
        raise CatalogError('regional version mismatch')
    if blood.get('catalog_version') != 'brdb-embedded-blood-hypotheses-candidate-v0.1':
        raise CatalogError('blood version mismatch')
    if regional.get('mappings') != []:
        raise CatalogError('unverified official lineage mappings are forbidden in D1')
    definitions = regional.get('taxonomy_definitions')
    if not isinstance(definitions, list) or len(definitions) != 4:
        raise CatalogError('expected four candidate region definitions')
    tags = []
    for x in definitions:
        tag = x.get('region_tag')
        if tag not in REGIONS or x.get('status') != 'CANDIDATE':
            raise CatalogError('illegal region/approval status')
        _required_string(x.get('definition'), f'{tag} definition')
        if not isinstance(x.get('examples_from_gemini'), list):
            raise CatalogError('examples must remain explicitly sourced list')
        tags.append(tag)
    if len(set(tags)) != 4:
        raise CatalogError('duplicate region definition')
    entries = blood.get('hypotheses')
    if not isinstance(entries, list) or len(entries) < 4:
        raise CatalogError('missing hypothesis entries')
    ids = set()
    for item in entries:
        key = item.get('hypothesis_id')
        _required_string(key, 'hypothesis_id')
        if key in ids:
            raise CatalogError(f'duplicate hypothesis: {key}')
        ids.add(key)
        _required_string(item.get('bloodline_label'), 'bloodline_label')
        _required_string(item.get('candidate_claim'), 'candidate_claim')
        if item.get('review_status') != 'CANDIDATE':
            raise CatalogError(f'{key} not in candidate status')
        if item.get('ancestor_id') is not None:
            raise CatalogError(f'{key} resolved without audited canonical identity')
        if item.get('can_assert_aptitude') is not False:
            raise CatalogError(f'{key} makes aptitude claim')
        if item.get('validated_cohorts') != [] or item.get('effective_from') is not None:
            raise CatalogError(f'{key} unreviewed validation or effective date')
        if item.get('role_filter') not in ROLES:
            raise CatalogError(f'{key} unsupported ancestor role filter')
        paths = item.get('allowed_paths')
        if not isinstance(paths, list) or any(not isinstance(p, str) or not _path_ok(p)
                                                for p in paths):
            raise CatalogError(f'{key} illegal path')
        if item['role_filter'] == 'BMS_EXACT' and paths != ['DS']:
            raise CatalogError(f'{key} BMS path must be exactly DS')
        if item['role_filter'] == 'SIRE_EXACT' and paths != ['S']:
            raise CatalogError(f'{key} sire path must be exactly S')
        if not isinstance(item.get('source_refs'), list) or not item['source_refs']:
            raise CatalogError(f'{key} source missing')
        if not isinstance(item.get('target_condition'), dict):
            raise CatalogError(f'{key} condition predicate missing')
    policy = blood.get('release_policy', {})
    for k in ('all_candidates_unexecutable', 'require_verified_id',
              'require_condition_source', 'require_historical_asof',
              'require_oos_for_validated_trend', 'never_override_primary_review'):
        if policy.get(k) is not True:
            raise CatalogError(f'unsafe release policy {k}')
    return {
        'status': 'D1_CATALOG_VALID',
        'candidate_regions': len(definitions),
        'candidate_hypotheses': len(entries),
        'approved_mappings': 0,
        'validated_aptitudes': 0,
        'executable_hypotheses': 0,
    }


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--regions', type=Path, required=True)
    p.add_argument('--hypotheses', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(validate_catalogs(load_catalog(a.regions),
                                       load_catalog(a.hypotheses)),
                     ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
