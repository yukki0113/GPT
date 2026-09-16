class StorageError(RuntimeError):
    """Base error with a stable machine-readable status."""

    status = "STORAGE_ERROR"


class DependencyMissingError(StorageError):
    status = "DEPENDENCY_MISSING"


class ConfigError(StorageError):
    status = "INVALID_CONFIG"


class ValidationError(StorageError):
    status = "VALIDATION_FAILED"

