"""
kodand.install - Harness installers
"""

import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any


HOME = os.path.expanduser("~")

HARNESS_CONFIGS = {
    "opencode": {
        "name": "OpenCode",
        "config_dir": os.path.join(HOME, ".config", "opencode", "plugins"),
        "plugin_dir": os.path.join(HOME, ".config", "opencode", "plugins"),
        "config_files": ["kodand.ts", "rules-guard.ts", "lanes-guard.ts"],
    },
    "claude-code": {
        "name": "Claude Code",
        "config_dir": os.path.join(HOME, ".claude"),
        "config_files": ["settings.json", "kodand.json"],
    },
    "cursor": {
        "name": "Cursor",
        "config_dir": os.path.join(HOME, ".cursor"),
        "config_files": ["settings.json", "kodand.json"],
    },
    "windsurf": {
        "name": "Windsurf",
        "config_dir": os.path.join(HOME, ".windsurf"),
        "config_files": ["settings.json", "kodand.json"],
    },
    "qoder": {
        "name": "Qoder",
        "config_dir": os.path.join(HOME, ".qoder"),
        "config_files": ["settings.json", "kodand.json"],
    },
    "vscode": {
        "name": "VS Code",
        "config_dir": os.path.join(HOME, ".vscode", "User"),
        "config_files": ["settings.json", "kodand.json"],
    },
}


def list_harnesses() -> List[Dict]:
    """List all harnesses and their installation status."""
    results = []
    for name, config in HARNESS_CONFIGS.items():
        if name == "all":
            continue
        installed = _check_installed(config)
        results.append({
            "name": name,
            "displayName": config["name"],
            "installed": installed,
        })
    return results


def _check_installed(config: dict) -> bool:
    """Check if kodand is installed for a harness."""
    config_dir = config["config_dir"]
    for f in config.get("config_files", []):
        if not os.path.exists(os.path.join(config_dir, f)):
            return False
    return True


def install_harness(harness: str = "all") -> List[Dict]:
    """Install kodand for a harness."""
    harnesses = ["opencode", "claude-code", "cursor", "windsurf", "qoder", "vscode"] if harness == "all" else [harness]
    results = []
    for h in harnesses:
        if h not in HARNESS_CONFIGS:
            results.append({"harness": h, "success": False, "message": f"Unknown harness: {h}", "installedFiles": [], "warnings": []})
            continue
        result = _install_single(h)
        results.append(result)
    return results


def _install_single(harness: str) -> Dict:
    config = HARNESS_CONFIGS[harness]
    config_dir = config["config_dir"]
    installed_files = []
    warnings = []

    # Check if already installed
    if _check_installed(config):
        return {"harness": harness, "success": True, "message": "Already installed", "installedFiles": [], "warnings": ["Already installed"]}

    try:
        os.makedirs(config_dir, exist_ok=True)

        if harness == "opencode":
            _install_opencode(config_dir, installed_files)
        else:
            _install_json_config(config_dir, installed_files, config["name"])

        return {"harness": harness, "success": True, "message": "Installed successfully", "installedFiles": installed_files, "warnings": warnings}
    except Exception as e:
        return {"harness": harness, "success": False, "message": str(e), "installedFiles": installed_files, "warnings": warnings}


def _install_opencode(config_dir: str, installed_files: List[str]):
    """Install kodand plugin for OpenCode."""
    plugin_dir = os.path.join(config_dir, "plugins")
    os.makedirs(plugin_dir, exist_ok=True)

    plugin_files = ["kodand.ts", "rules-guard.ts", "lanes-guard.ts"]
    plugin_dir_src = os.path.join(os.path.dirname(__file__), "..", "plugin", "opencode")
    for f in plugin_files:
        src = os.path.join(plugin_dir_src, f)
        dst = os.path.join(plugin_dir, f)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            installed_files.append(dst)

    marker_path = os.path.join(config_dir, "kodand-workspace")
    with open(marker_path, "w") as f:
        f.write(f"{os.getcwd()}\n1.0.0\n")
    installed_files.append(marker_path)


def _install_json_config(config_dir: str, installed_files: List[str], display_name: str):
    """Install kodand config for JSON-based harnesses."""
    settings_path = os.path.join(config_dir, "settings.json")
    settings = {}
    if os.path.exists(settings_path):
        with open(settings_path) as f:
            settings = json.load(f)

    settings["kodand"] = {"enabled": True, "mcpServer": "kodand", "autoStart": True}
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    installed_files.append(settings_path)

    kodand_path = os.path.join(config_dir, "kodand.json")
    with open(kodand_path, "w") as f:
        json.dump({"version": "1.0.0", "enabled": True}, f, indent=2)
    installed_files.append(kodand_path)


def uninstall_harness(harness: str = "all") -> List[Dict]:
    """Uninstall kodand from a harness."""
    harnesses = ["opencode", "claude-code", "cursor", "windsurf", "qoder", "vscode"] if harness == "all" else [harness]
    results = []
    for h in harnesses:
        if h not in HARNESS_CONFIGS:
            results.append({"harness": h, "success": False, "message": f"Unknown harness: {h}", "installedFiles": [], "warnings": []})
            continue
        config = HARNESS_CONFIGS[h]
        config_dir = config["config_dir"]
        removed_files = []
        try:
            for f in config.get("config_files", []):
                p = os.path.join(config_dir, f)
                if os.path.exists(p):
                    os.remove(p)
                    removed_files.append(p)
            if h == "opencode":
                marker_path = os.path.join(config_dir, "kodand-workspace")
                if os.path.exists(marker_path):
                    os.remove(marker_path)
                    removed_files.append(marker_path)
            results.append({"harness": h, "success": True, "message": "Uninstalled successfully", "installedFiles": removed_files, "warnings": []})
        except Exception as e:
            results.append({"harness": h, "success": False, "message": str(e), "installedFiles": removed_files, "warnings": []})
    return results


def init_repo(repo_path: str, options: dict = None) -> Dict:
    """Initialize kodand for a repository."""
    from kodand.store import Store

    repo_path = os.path.abspath(repo_path)
    options = options or {}

    # Check git repo
    if not os.path.exists(os.path.join(repo_path, ".git")):
        return {"success": False, "message": "Not a git repository. Initialize git first."}

    # Check commit count
    import subprocess
    result = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=repo_path, capture_output=True, text=True
    )
    commit_count = int(result.stdout.strip()) if result.stdout.strip() else 0
    min_commits = options.get("min_commits", 20)
    if commit_count < min_commits:
        return {
            "success": False,
            "message": f"Repository has only {commit_count} commits (minimum {min_commits}). Use --min-commits to override.",
        }

    # Create .kodand directory
    kodand_dir = os.path.join(repo_path, ".kodand")
    os.makedirs(kodand_dir, exist_ok=True)

    # Create store
    store = Store(repo_path)

    # Create repo entry
    repo_name = os.path.basename(repo_path)
    repo_entry = store.remember(
        content=f"Repository: {repo_name}",
        surface="text",
        locator="AGENTS.md",
        scope="repo",
        session_id="init",
    )

    # Write marker
    with open(os.path.join(kodand_dir, "initialized"), "w") as f:
        f.write(datetime.now().isoformat())

    return {
        "success": True,
        "message": f"Initialized kodand for {repo_name} (repository {repo_entry['key']})",
        "repoId": repo_entry["key"],
    }


# Import Store here to avoid circular import
from kodand.store import Store
from datetime import datetime