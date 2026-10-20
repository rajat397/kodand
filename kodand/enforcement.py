"""
kodand.enforcement - Enforcement ladder (C7.4)
Promote high-utility memories from context text → hooks → repo lint/test/CI
checks that travel with git.
"""

import os
import json
import hashlib
import subprocess
from typing import Dict, Any, List, Optional
from kodand.store import get_store


class EnforcementLadder:
    """Enforcement ladder: promote memories from context → hooks → repo checks.
    
    Ladder levels:
    1. CONTEXT - Memory in context window only
    2. HOOK - Enforced by tool hook
    3. LINT - Enforced by repo lint config
    4. TEST - Enforced by test
    5. CI - Enforced by CI check (travels with git)
    """

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
        self.store = get_store(repo_path)

    def _memory_row(self, entry_id: int):
        conn = self.store._get_conn()
        try:
            return conn.execute(
                "SELECT * FROM memories WHERE id = ?", (entry_id,)
            ).fetchone()
        finally:
            conn.close()

    @staticmethod
    def _forbidden_token(content: str, locator: str) -> str:
        """Extract a literal token identifying the forbidden mistake (v1 heuristic).

        Prefers backtick/single-quote quoted snippets, else the first
        non-trivial line of the memory content. Documented limitation:
        unquoted prose memories produce broad patterns — see iterations log.
        """
        import re
        # Prefer the FORBIDDEN side: "instead of X" beats "use Y"; "never <verb> X"
        # beats a bare first backtick (which is often the replacement).
        m = re.search(r"instead of\s+`([^`]+)`", content)
        if m:
            return m.group(1).strip()
        m = re.search(r"never\s+(?:use|leave|hardcode|do|run|commit|push)?\s*`([^`]+)`", content)
        if m:
            return m.group(1).strip()
        for pat in (r"`([^`]+)`", r"'([^']{3,})'"):
            m = re.search(pat, content)
            if m:
                return m.group(1).strip()
        for line in content.splitlines():
            line = line.strip(" -–—•#*")
            if len(line) >= 8:
                return line[:120]
        return (locator or content[:60]).strip()

    def _write_artifact(self, entry_id: int, level: str, content: str, locator: str) -> List[str]:
        """Render and write the enforcement artifact. Returns written paths."""
        repo = self.repo_path
        enforce_dir = os.path.join(repo, ".kodand", "enforce")
        os.makedirs(enforce_dir, exist_ok=True)
        token = self._forbidden_token(content, locator)
        written: List[str] = []
        header = f"# kodand:memory#{entry_id} level={level}\n# correction: {content[:200]}\n"

        if level == "hook":
            path = os.path.join(enforce_dir, f"hook-{entry_id}.sh")
            # POSIX sh single-quote escaping for the pattern.
            sh_token = token.replace("'", "'\\''")
            script = (
                "#!/bin/sh\n" + header
                + f"PATTERN='{sh_token}'\n"
                + 'if git diff --cached --name-only 2>/dev/null | grep -q .; then\n'
                + '  if git diff --cached 2>/dev/null | grep -qF "$PATTERN"; then\n'
                + f'    echo "kodand: blocked by memory#{entry_id}: {content[:120]}" >&2\n'
                + '    exit 1\n'
                + '  fi\n'
                + 'fi\n'
                + 'exit 0\n'
            )
            with open(path, "w") as f:
                f.write(script)
            os.chmod(path, 0o755)
            written.append(path)
            # Best-effort wiring into the repo pre-commit hook (local only).
            try:
                hook_path = os.path.join(repo, ".git", "hooks", "pre-commit")
                block = f'\n# kodand:memory#{entry_id}\n"{path}" || exit 1\n'
                if os.path.isdir(os.path.join(repo, ".git", "hooks")):
                    existing = ""
                    if os.path.exists(hook_path):
                        with open(hook_path) as f:
                            existing = f.read()
                    if f"kodand:memory#{entry_id}" not in existing:
                        with open(hook_path, "a") as f:
                            if not existing:
                                f.write("#!/bin/sh\n")
                            f.write(block)
                        os.chmod(hook_path, 0o755)
            except Exception:
                pass
        elif level == "lint":
            path = os.path.join(enforce_dir, f"kodand-lint-{entry_id}.py")
            with open(path, "w") as f:
                f.write(
                    header
                    + '"""kodand lint rule — fails when the forbidden pattern reappears."""\n'
                    + 'import pathlib, sys\n'
                    + f'PATTERN = {token!r}\n'
                    + f'LOCATOR = {locator!r}\n'
                    + 'hits = [str(p) for p in pathlib.Path(".").rglob("*.py")\n'
                    + '        if PATTERN in p.read_text(errors="replace")]\n'
                    + 'if hits:\n'
                    + f'    print(f"kodand-lint: memory#{entry_id} violated in: " + ", ".join(hits[:5]))\n'
                    + '    sys.exit(1)\n'
                    + 'print("kodand-lint: clean")\n'
                )
            written.append(path)
        elif level == "test":
            tests_dir = os.path.join(repo, "tests")
            os.makedirs(tests_dir, exist_ok=True)
            path = os.path.join(tests_dir, f"test_kodand_{entry_id}.py")
            with open(path, "w") as f:
                f.write(
                    '"""kodand enforcement test - generated, do not hand-edit.\n'
                    + f"memory#{entry_id} level=test\n"
                    + f"correction: {content[:200].replace(chr(10), ' ')}\n"
                    + '"""\n'
                    + f'PATTERN = {token!r}\n'
                    + 'def test_kodand_enforced_correction():\n'
                    + '    import pathlib\n'
                    + '    roots = [pathlib.Path("."), pathlib.Path("src")]\n'
                    + '    for root in roots:\n'
                    + '        if not root.exists():\n'
                    + '            continue\n'
                    + '        for p in root.rglob("*.py"):\n'
                    + '            if "test_kodand_" in str(p):\n'
                    + '                continue\n'
                    + '            assert PATTERN not in p.read_text(errors="replace"), \\\n'
                    + f'                f"kodand: memory#{entry_id} violation in {{p}}"\n'
                )
            written.append(path)
        elif level == "ci":
            wf_dir = os.path.join(repo, ".github", "workflows")
            os.makedirs(wf_dir, exist_ok=True)
            path = os.path.join(wf_dir, "kodand.yml")
            entry_block = (
                f"      # kodand:memory#{entry_id}: {content[:80]}\n"
                + "      - name: kodand guard\n"
                + "        run: |\n"
                + "          ls .kodand/enforce/hook-*.sh 2>/dev/null | while read h; do sh \"$h\"; done\n"
                + "          python3 -m pytest tests/test_kodand_*.py -q\n"
            )
            if os.path.exists(path):
                with open(path) as f:
                    existing = f.read()
                if f"kodand:memory#{entry_id}" not in existing:
                    with open(path, "a") as f:
                        f.write(entry_block)
            else:
                with open(path, "w") as f:
                    f.write(
                        "name: kodand-guards\non: [push, pull_request]\njobs:\n"
                        "  guard:\n    runs-on: ubuntu-latest\n    steps:\n"
                        "      - uses: actions/checkout@v4\n" + entry_block
                    )
            written.append(path)
        return written

    def promote(self, entry_id: int, level: str) -> bool:
        """Promote a memory entry to a higher enforcement level.

        Writes a real, git-tracked artifact (hook/lint/test/CI) that blocks
        the repeated mistake, then records the level in the DB as an index.
        """
        valid_levels = ["context", "hook", "lint", "test", "ci"]
        if level not in valid_levels:
            return False

        conn = self.store._get_conn()
        # Ensure enforcement_level column exists (migration)
        try:
            conn.execute("ALTER TABLE memories ADD COLUMN enforcement_level TEXT DEFAULT 'context'")
            conn.commit()
        except Exception:
            pass
        row = conn.execute(
            "SELECT * FROM memories WHERE id = ?", (entry_id,)
        ).fetchone()
        if not row:
            conn.close()
            return False

        # Update the memory entry with enforcement level
        conn.execute(
            "UPDATE memories SET enforcement_level = ? WHERE id = ?",
            (level, entry_id)
        )
        conn.commit()
        conn.close()

        # Write the real artifact (Fix 3) — failure to write fails the promotion.
        artifacts: List[str] = []
        if level != "context":
            try:
                artifacts = self._write_artifact(entry_id, level, row["content"], row["locator"] or "")
            except Exception as e:
                artifacts = [f"WRITE-FAILED: {e}"]
            if not artifacts or any(a.startswith("WRITE-FAILED") for a in artifacts):
                self.store.log_event(
                    kind="promotion",
                    entry_id=entry_id,
                    provenance="enforcement.cli",
                    detail=json.dumps({"entry_id": entry_id, "promoted_to": level, "error": str(artifacts)}),
                )
                return False

        # Log the promotion with artifact paths + tracked diff stat.
        try:
            diff_stat = subprocess.run(
                ["git", "diff", "--stat", "--"] + [a for a in artifacts if not a.startswith("WRITE-FAILED")],
                cwd=self.repo_path, capture_output=True, text=True, timeout=10,
            ).stdout.strip()
        except Exception:
            diff_stat = ""
        self.store.log_event(
            kind="promotion",
            entry_id=entry_id,
            provenance="enforcement.cli",
            detail=json.dumps({
                "entry_id": entry_id,
                "promoted_to": level,
                "artifacts": artifacts,
                "diff_stat": diff_stat,
            }),
        )

        return True

    def enforced_memories(self) -> List[Dict]:
        """All memories at blocking levels (hook/lint/test/ci), with tokens."""
        conn = self.store._get_conn()
        try:
            rows = conn.execute(
                "SELECT id, content, locator, enforcement_level FROM memories "
                "WHERE state = 'active' AND COALESCE(is_holdout, 0) = 0 "
                "AND enforcement_level IN ('hook', 'lint', 'test', 'ci')"
            ).fetchall()
        except Exception:
            return []
        finally:
            try:
                conn.close()
            except Exception:
                pass
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["token"] = self._forbidden_token(d.get("content", ""), d.get("locator", ""))
            except Exception:
                d["token"] = ""
            if d["token"]:
                out.append(d)
        return out

    def check_write_content(self, content: str) -> List[Dict]:
        """Forcing-function core: which enforced memories does this content violate?

        Pure read-only scan, never raises (fail-open -> []). The caller decides
        whether to block (harness hook) or warn.
        """
        try:
            hits = []
            for m in self.enforced_memories():
                if m["token"] and m["token"] in (content or ""):
                    hits.append({"id": m["id"], "level": m["enforcement_level"],
                                 "token": m["token"],
                                 "correction": m.get("content", "")[:200]})
            return hits
        except Exception:
            return []

    def demote(self, entry_id: int, level: str = None) -> bool:
        """Remove enforcement artifacts (reversible). Returns True when clean."""
        targets: List[str] = []
        levels = [level] if level else ["hook", "lint", "test", "ci"]
        for lv in levels:
            if lv == "hook":
                targets.append(os.path.join(self.repo_path, ".kodand", "enforce", f"hook-{entry_id}.sh"))
            elif lv == "lint":
                targets.append(os.path.join(self.repo_path, ".kodand", "enforce", f"kodand-lint-{entry_id}.py"))
            elif lv == "test":
                targets.append(os.path.join(self.repo_path, "tests", f"test_kodand_{entry_id}.py"))
        removed = True
        for t in targets:
            try:
                if os.path.exists(t):
                    os.remove(t)
            except Exception:
                removed = False
        # Scrub pre-commit wiring + CI block.
        try:
            hook_path = os.path.join(self.repo_path, ".git", "hooks", "pre-commit")
            if os.path.exists(hook_path):
                with open(hook_path) as f:
                    lines = f.readlines()
                kept = [l for l in lines if f"kodand:memory#{entry_id}" not in l]
                if len(kept) != len(lines):
                    with open(hook_path, "w") as f:
                        f.writelines(kept)
        except Exception:
            removed = False
        try:
            ci_path = os.path.join(self.repo_path, ".github", "workflows", "kodand.yml")
            if os.path.exists(ci_path):
                with open(ci_path) as f:
                    text = f.read()
                import re
                new_text = re.sub(rf"      # kodand:memory#{entry_id}:.*?\n(?:.*?\n)*?(?=      # kodand:memory#|\Z)", "", text)
                if new_text != text:
                    with open(ci_path, "w") as f:
                        f.write(new_text)
        except Exception:
            removed = False
        return removed

    def get_enforcement_level(self, entry_id: int) -> str:
        """Get the current enforcement level for an entry."""
        conn = self.store._get_conn()
        row = conn.execute(
            "SELECT enforcement_level FROM memories WHERE id = ?",
            (entry_id,)
        ).fetchone()
        conn.close()
        if row:
            return row["enforcement_level"] or "context"
        return "context"

    def get_entries_at_level(self, level: str) -> List[Dict]:
        """Get all entries at a given enforcement level."""
        conn = self.store._get_conn()
        rows = conn.execute(
            "SELECT * FROM memories WHERE enforcement_level = ? AND state = 'active'",
            (level,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_enforcement_summary(self) -> Dict[str, int]:
        """Get count of entries at each enforcement level."""
        levels = ["context", "hook", "lint", "test", "ci"]
        result = {}
        conn = self.store._get_conn()
        for level in levels:
            count = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE enforcement_level = ? AND state = 'active'",
                (level,)
            ).fetchone()[0]
            result[level] = count
        conn.close()
        return result


def create_enforcement_ladder(repo_path: str = None) -> EnforcementLadder:
    """Create an enforcement ladder instance."""
    return EnforcementLadder(repo_path)