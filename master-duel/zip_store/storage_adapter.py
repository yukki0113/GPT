"""Adapter contract: immutable object creation, independent reads, head observation.

No method overwrites, deletes, promotes or changes sharing. Head coordination is
external; adapters must raise on missing/indeterminate reads and duplicate IDs.
"""
from typing import Protocol

class SnapshotAdapter(Protocol):
    def read_head(self) -> str: ...
    def read(self, object_id: str) -> bytes: ...
    def create(self, object_id: str, data: bytes) -> None: ...

class MemoryAdapter:
    """Test double. Head changes are controlled explicitly by the test/operator."""
    def __init__(self, head, objects):
        self.head = head
        self.objects = dict(objects)
    def read_head(self):
        if not self.head: raise ValueError('head unavailable')
        return self.head
    def read(self, object_id):
        return bytes(self.objects[object_id])
    def create(self, object_id, data):
        if object_id in self.objects: raise ValueError('object already exists')
        self.objects[object_id] = bytes(data)
