"""
kodand.swarm - Team & Swarm coordination (C4)
Parallel agents coordinate like a team with live claims, deny-and-propose,
and shared writable state.
"""

import os
import time
import uuid
import json
import threading
from typing import Dict, Any, Optional, List
from kodand.store import get_store


class Claim:
    """A live claim on a resource (file, symbol, etc.) during a session."""

    def __init__(self, claim_id: str, resource: str, session_id: str,
                 claimed_at: float, ttl: int = 300):
        self.id = claim_id
        self.resource = resource
        self.session_id = session_id
        self.claimed_at = claimed_at
        self.ttl = ttl  # seconds until auto-release
        self.expires_at = claimed_at + ttl

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def refresh(self):
        self.claimed_at = time.time()
        self.expires_at = self.claimed_at + self.ttl


class SwarmCoordination:
    """Team coordination layer - live claims, deny-and-propose, shared state."""

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(repo_path)
        self._claims: Dict[str, Claim] = {}  # resource -> claim
        self._locks: Dict[str, threading.Lock] = {}  # resource -> lock
        self._lock = threading.Lock()
        self._claims_file = os.path.join(self.repo_path, ".kodand", "claims.json")
        self._load_claims()

    def _load_claims(self):
        try:
            if os.path.exists(self._claims_file):
                with open(self._claims_file) as f:
                    data = json.load(f)
                    for r, c in data.items():
                        self._claims[r] = Claim(c["id"], c["resource"], c["session_id"], c["claimed_at"], c["ttl"])
        except Exception:
            pass

    def _save_claims(self):
        try:
            os.makedirs(os.path.dirname(self._claims_file), exist_ok=True)
            data = {r: {"id": c.id, "resource": c.resource, "session_id": c.session_id, "claimed_at": c.claimed_at, "ttl": c.ttl} for r, c in self._claims.items()}
            with open(self._claims_file, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _get_lock(self, resource: str) -> threading.Lock:
        if resource not in self._locks:
            self._locks[resource] = threading.Lock()
        return self._locks[resource]

    def claim(self, resource: str, session_id: str, ttl: int = 300) -> Dict[str, Any]:
        """Claim a resource for a session. Returns claim result."""
        with self._locks.get(resource, threading.Lock()):
            existing = self._claims.get(resource)
            if existing and not existing.is_expired() and existing.session_id != session_id:
                return {
                    "allowed": False,
                    "reason": f"Already claimed by session {existing.session_id}",
                    "existing_claim": {
                        "id": existing.id,
                        "session_id": existing.session_id,
                        "claimed_at": existing.claimed_at,
                        "expires_at": existing.expires_at,
                    },
                    "action": "deny-and-propose",
                }

            # Claim it
            claim_id = str(uuid.uuid4())
            claim = Claim(claim_id, resource, session_id, time.time(), ttl)
            self._claims[resource] = claim
            self._save_claims()

            # Persist to store
            self.store.remember(
                content=f"Claim: {resource} by {session_id}",
                surface="text",
                locator=f"claim:{resource}",
                scope="repo",
                session_id=session_id,
            )

            return {
                "allowed": True,
                "claim_id": claim_id,
                "resource": resource,
                "session_id": session_id,
                "claimed_at": claim.claimed_at,
                "expires_at": claim.expires_at,
            }

    def release(self, resource: str, session_id: str) -> bool:
        """Release a claim on a resource."""
        with self._locks.get(resource, threading.Lock()):
            claim = self._claims.get(resource)
            if claim and claim.session_id == session_id:
                del self._claims[resource]
                self._save_claims()
                return True
            return False

    def check_access(self, resource: str, session_id: str) -> Dict[str, Any]:
        """Check if a session can access a resource."""
        claim = self._claims.get(resource)
        if not claim:
            return {"allowed": True, "reason": "No active claim"}
        if claim.session_id == session_id:
            return {"allowed": True, "reason": "Owned by this session"}
        if claim.is_expired():
            del self._claims[resource]
            return {"allowed": True, "reason": "Claim expired"}
        return {
            "allowed": False,
            "reason": f"Claimed by session {claim.session_id}",
            "holds": claim.session_id,
            "expires_at": claim.expires_at,
        }

    def get_active_claims(self) -> List[Dict[str, Any]]:
        """Get all active claims."""
        result = []
        now = time.time()
        for resource, claim in self._claims.items():
            if not claim.is_expired():
                result.append({
                    "rule_id": claim.id,
                    "rule_id": claim.id,
                    "resource": claim.resource,
                    "session_id": claim.session_id,
                    "claimed_at": claim.claimed_at,
                    "expires_at": claim.expires_at,
                })
        return result

    def cleanup_expired(self) -> int:
        """Remove expired claims and return count removed."""
        expired = []
        for resource, claim in list(self._claims.items()):
            if claim.is_expired():
                del self._claims[resource]
                expired.append(claim)
        return len(expired)


def create_swarm_coordination(repo_path: str = None) -> SwarmCoordination:
    """Create a swarm coordination instance."""
    return SwarmCoordination(repo_path)