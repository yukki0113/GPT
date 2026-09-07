"""Backend-neutral machine-readable result schema."""
def build_result(*, status, backend, operation, request_id, source, destination, size_bytes, sha256, provenance, **extra):
    return {"status":status,"backend":backend,"operation":operation,"request_id":request_id,"source":source,"destination":destination,"size_bytes":size_bytes,"sha256":sha256,"provenance":provenance,**extra}
