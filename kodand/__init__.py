"""
kodand - Intent-driven memory plane for coding agents.

Persistent, launch-worthy memory layer beneath coding-agent context windows.
Overcomes amnesia, cold session starts, swarm collisions, storage/retrieval
failure, and bulky-repo context limits.

Version: 0.1.0
"""

__version__ = "0.1.0"

from kodand.store import get_store, Store
from kodand.recall import create_recall_engine, recall
from kodand.trust import create_trust_surface, TrustSurface
from kodand.capture import CaptureLoop, run_capture_tick, run_capture_loop
from kodand.install import install_harness, uninstall_harness, list_harnesses

__all__ = [
    "get_store",
    "Store",
    "create_recall_engine",
    "recall",
    "create_trust_surface",
    "TrustSurface",
    "CaptureLoop",
    "run_capture_tick",
    "run_capture_loop",
    "install_harness",
    "uninstall_harness",
    "list_harnesses",
]