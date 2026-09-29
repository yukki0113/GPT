"""Read immutable annual ZIPs without extracting or modifying them."""

import hashlib
import json
import re
import zipfile
from pathlib import Path


class LogicalAssetRegistry:
    """Detect exact archive-member duplicates and reject conflicting copies."""

    def __init__(self):
        self.sha_by_path = {}

    def register(self, relative_path, raw_sha256):
        previous=self.sha_by_path.get(relative_path)
        if previous is None:
            self.sha_by_path[relative_path]=raw_sha256
            return True
        if previous!=raw_sha256:
            raise ValueError(f"same logical Raw asset has conflicting SHA-256: {relative_path}")
        return False


def read_archives(paths):
    for path in sorted(map(Path, paths)):
        match = re.fullmatch(r"keirin-historical-(20\d\d)(?:-\d{2}-poc-\d+)?\.zip", path.name)
        if not match:
            raise ValueError(f"unexpected archive name: {path.name}")
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f"corrupt ZIP member: {path.name}:{bad}")
            manifests = {}
            for name in archive.namelist():
                if re.fullmatch(r"audit/\d{6}_events_manifest\.json", name):
                    for record in json.loads(archive.read(name))["sources"]:
                        if record.get("status") == "success":
                            key = "raw/" + record["relative_path"]
                            if key in manifests:
                                raise ValueError(f"duplicate manifest asset: {key}")
                            manifests[key] = record
            event_paths = sorted(n for n in archive.namelist() if re.fullmatch(r"raw/\d{4}/\d{2}/events/[^/]+\.html", n))
            if set(event_paths) != set(manifests):
                raise ValueError(f"manifest/HTML mismatch: {path.name}, missing={len(set(manifests)-set(event_paths))}, extra={len(set(event_paths)-set(manifests))}")
            for name in event_paths:
                raw = archive.read(name)
                digest = hashlib.sha256(raw).hexdigest()
                if digest != manifests[name]["sha256"]:
                    raise ValueError(f"raw SHA mismatch: {path.name}:{name}")
                yield path.name, name, raw, manifests[name]
