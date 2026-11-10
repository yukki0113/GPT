"""M2 private inventory and safe HEAD handoff."""
from .lifecycle import (validate_head,target_from_head,preview_inventory,
                        prepare_inventory,build_verified_head,verify_activated_head)
