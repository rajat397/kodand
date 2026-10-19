"""
kodand.capture - Live capture loop (Tranche 1.1)
Mines environment during real sessions: user corrections, reverted commits,
failed CI runs, PR comments, broken tests.
"""

import os
import subprocess
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from kodand.store import get_store


class CaptureLoop:
    """Live capture loop that mines environment signals during sessions."""

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(repo_path)
        self.ceiling = 5  # max cards per day

    def mine_git_reverts(self) -> List[Dict]:
        """Mine git history for revert commits."""
        results = []
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "--grep=Revert", "--since=1 week ago", "-n", "20"],
                cwd=self.repo_path, capture_output=True, text=True
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split(" ", 1)
                        commit_hash = parts[0]
                        subject = parts[1] if len(parts) > 1 else ""
                        results.append({
                            "content": f"Reverted commit: {subject}",
                            "type": "correction",
                            "confidence": "high",
                            "source": "reverted_commit",
                            "evidence": f"Git commit {commit_hash}: {subject}",
                            "anchors": [{"commit_hash": commit_hash}],
                        })
        except Exception as e:
            print(f"[capture] Error mining git reverts: {e}")
        return results

    def mine_failed_tests(self) -> List[Dict]:
        """Mine for failed test runs."""
        results = []
        test_files = ["test_results.json", "pytest_results.json"]
        for tf in test_files:
            tf_path = os.path.join(self.repo_path, tf)
            if os.path.exists(tf_path):
                try:
                    with open(tf_path) as f:
                        data = json.load(f)
                    if data.get("failed", 0) > 0:
                        results.append({
                            "content": f"Test failure detected: {data.get('failed', 0)} tests failed",
                            "type": "correction",
                            "confidence": "high",
                            "source": "broken_test",
                            "evidence": f"Test results: {data.get('failed', 0)} failures",
                            "anchors": [{"file_path": tf}],
                        })
                except Exception:
                    pass
        return results

    def mine_transcript_corrections(self) -> List[Dict]:
        """Mine session transcripts for explicit user corrections (Fix 5)."""
        try:
            from kodand.capture.adapters import read_transcript_file, read_opencode_sessions
            from kodand.capture.corrections import classify_correction
        except Exception:
            return []
        turns = []
        try:
            turns.extend(read_transcript_file(self.repo_path))
        except Exception:
            pass
        try:
            turns.extend(read_opencode_sessions(self.repo_path))
        except Exception:
            pass
        results = []
        for t in turns:
            try:
                hit = classify_correction(t.get("text", ""))
            except Exception:
                hit = None
            if hit:
                results.append({
                    "content": hit["evidence"],
                    "type": "correction",
                    "confidence": "high",
                    "source": "transcript_correction",
                    "evidence": f"{t.get('source','?')} [{t.get('role','?')}]: {hit['evidence']}",
                    "anchors": [],
                })
        return results

    def mine_environment(self) -> List[Dict]:
        """Mine all environment signals for capture candidates."""
        candidates = []
        candidates.extend(self.mine_git_reverts())
        candidates.extend(self.mine_failed_tests())
        candidates.extend(self.mine_transcript_corrections())
        return candidates

    def queue_candidate(self, candidate: Dict) -> bool:
        """Queue a candidate memory for review."""
        store = self.store
        entry = store.remember(
            content=candidate["content"],
            surface="text",
            locator=candidate.get("evidence", ""),
            scope="repo",
            session_id="capture_loop",
        )
        store.log_event(
            kind="captured",
            entry_id=entry["key"],
            provenance=candidate.get("source", "capture_loop"),
            detail=json.dumps(candidate),
        )
        return True

    def run_tick(self) -> Dict[str, Any]:
        """Run one capture tick."""
        candidates = self.mine_environment()
        queued = 0
        for candidate in candidates:
            if queued >= self.ceiling:
                break
            self.queue_candidate(candidate)
            queued += 1

        return {
            "candidates": len(candidates),
            "queued": queued,
            "ceiling_hit": queued >= self.ceiling,
        }

    def run(self):
        """Run the capture loop continuously."""
        print(f"[capture] Starting live capture loop for {self.repo_path}")
        while True:
            result = self.run_tick()
            if result["queued"] > 0:
                print(f"[capture] Queued {result['queued']} cards (ceiling: {self.ceiling})")
            time.sleep(60)  # Check every minute


def run_capture_tick(repo_path: str = None) -> Dict[str, Any]:
    """Run a single capture tick."""
    loop = CaptureLoop(repo_path)
    return loop.run_tick()


def run_capture_loop(repo_path: str = None):
    """Run the continuous capture loop."""
    loop = CaptureLoop(repo_path)
    loop.run()