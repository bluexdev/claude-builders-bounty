#!/usr/bin/env python3
"""Claude Code PreToolUse hook that blocks destructive Bash commands."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


BLOCK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "rm -rf recursively deletes files and is blocked by the destructive Bash guard.",
        re.compile(
            r"(?is)(?:^|[\s;&|()])rm\s+(?:(?:-[^\s;]*r[^\s;]*f[^\s;]*)|(?:-[^\s;]*f[^\s;]*r[^\s;]*)|(?:-[^\s;]*r[^\s;]*\s+-[^\s;]*f[^\s;]*)|(?:-[^\s;]*f[^\s;]*\s+-[^\s;]*r[^\s;]*))"
        ),
    ),
    (
        "DROP TABLE is destructive SQL and is blocked by the destructive Bash guard.",
        re.compile(r"(?is)\bdrop\s+table\b"),
    ),
    (
        "TRUNCATE is destructive SQL and is blocked by the destructive Bash guard.",
        re.compile(r"(?is)\btruncate\b"),
    ),
    (
        "Force-pushing can rewrite shared history and is blocked by the destructive Bash guard.",
        re.compile(r"(?is)\bgit\s+push\b[^\n;|&]*(?:--force(?:=\S+)?\b|--force-with-lease\b|(?<!\S)-f(?!\S))"),
    ),
)


def read_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid hook JSON input: {exc}") from exc
    return payload if isinstance(payload, dict) else {}


def attempted_command(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict) and isinstance(tool_input.get("command"), str):
        return tool_input["command"]
    command = payload.get("command")
    return command if isinstance(command, str) else ""


def project_path(payload: dict[str, Any]) -> str:
    for key in ("cwd", "project_dir", "project_path"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def delete_from_without_where(command: str) -> str | None:
    lowered = command.lower()
    for match in re.finditer(r"\bdelete\s+from\b", lowered):
        statement_end = lowered.find(";", match.start())
        if statement_end == -1:
            statement_end = len(lowered)
        statement = lowered[match.start() : statement_end]
        if not re.search(r"\bwhere\b", statement):
            return "DELETE FROM without a WHERE clause is blocked by the destructive Bash guard."
    return None


def block_reason(command: str) -> str | None:
    for reason, pattern in BLOCK_PATTERNS:
        if pattern.search(command):
            return reason
    return delete_from_without_where(command)


def log_block(command: str, cwd: str, reason: str) -> None:
    log_path = Path.home() / ".claude" / "hooks" / "blocked.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "project_path": cwd,
        "reason": reason,
        "attempted_command": command,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def main() -> int:
    payload = read_payload()
    command = attempted_command(payload)
    if not command:
        return 0

    reason = block_reason(command)
    if reason is None:
        return 0

    cwd = project_path(payload)
    log_block(command, cwd, reason)
    deny(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
