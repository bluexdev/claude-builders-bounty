#!/usr/bin/env python3
"""Install the destructive Bash guard into ~/.claude/hooks."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any


HOOK_NAME = "block_destructive_bash.py"


def hook_command(destination: Path) -> str:
    return f'python3 "{destination}"'


def load_settings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object at the top level.")
    return data


def merge_hook(settings: dict[str, Any], command: str) -> dict[str, Any]:
    hooks = settings.setdefault("hooks", {})
    pre_tool_use = hooks.setdefault("PreToolUse", [])
    hook_entry = {"type": "command", "command": command}

    for existing in pre_tool_use:
        if not isinstance(existing, dict) or existing.get("matcher") != "Bash":
            continue
        existing_hooks = existing.setdefault("hooks", [])
        if any(hook == hook_entry for hook in existing_hooks):
            return settings
        existing_hooks.append(hook_entry)
        return settings

    pre_tool_use.append({"matcher": "Bash", "hooks": [hook_entry]})
    return settings


def main() -> int:
    source = Path(__file__).with_name(HOOK_NAME)
    claude_dir = Path.home() / ".claude"
    hook_dir = claude_dir / "hooks"
    hook_dir.mkdir(parents=True, exist_ok=True)

    destination = hook_dir / HOOK_NAME
    shutil.copy2(source, destination)
    if os.name != "nt":
        destination.chmod(0o755)

    settings_path = claude_dir / "settings.json"
    settings = merge_hook(load_settings(settings_path), hook_command(destination))
    with settings_path.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)
        handle.write("\n")

    print(f"Installed {destination}")
    print(f"Updated {settings_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
