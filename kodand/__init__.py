"""
kodand - Memory plane for coding agents.

Persistent, launch-worthy memory layer beneath coding-agent context windows.
Overcomes amnesia, cold session starts, swarm collisions, storage/retrieval
failure, and bulky-repo context limits.

Version: 1.0.0
"""

__version__ = "1.0.0"

from kodand.store import get_store, Store
from kodand.recall import create_recall_engine, recall
from kodand.trust import create_trust_surface, TrustSurface
from kodand.capture import CaptureLoop, run_capture_tick, run_capture_loop
from kodand.install import install_harness, uninstall_harness, list_harnesses, init_repo
from kodand.outcome import create_outcome_labeler
from kodand.utility import create_utility_scorer
from kodand.warmstart import create_warm_start, get_warm_context

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
    "init_repo",
    "create_outcome_labeler",
    "create_utility_scorer",
    "create_warm_start",
    "get_warm_context",
    "__version__",
]