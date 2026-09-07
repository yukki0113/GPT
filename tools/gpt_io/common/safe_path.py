"""Conservative shared repository path checks; backends may add restrictions."""
from pathlib import PurePosixPath
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
def validate_repository_path(value: str) -> str:
    path = PurePosixPath(value); lower = value.lower()
    if path.is_absolute() or not path.parts or ".." in path.parts: raise ValueError(f"Unsafe repository path: {value}")
    if any(p.lower()==".git" or p.lower()==".env" or p.lower().startswith(".env.") for p in path.parts) or lower.endswith(SENSITIVE_SUFFIXES) or any(x in lower for x in ("secret", "credential", "password")): raise ValueError(f"Sensitive repository path: {value}")
    return path.as_posix()
