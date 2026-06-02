#!/usr/bin/env python3
"""Smoke tests for the destructive Bash guard."""

from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("block_destructive_bash.py")
SPEC = importlib.util.spec_from_file_location("block_destructive_bash", MODULE_PATH)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


BLOCKED = [
    "rm -rf build",
    "rm -fr build",
    "rm --recursive --force build",
    "rm -r --force build",
    "rm --force -r build",
    "psql -c 'DROP TABLE users'",
    "sqlite3 app.db 'TRUNCATE audit_log'",
    "git push --force origin main",
    "git push -f origin main",
    "git push --force-with-lease origin main",
    "sqlite3 app.db 'DELETE FROM users'",
    "sqlite3 app.db 'DELETE FROM users' | grep where",
]

ALLOWED = [
    "git status",
    "rm -r build",
    "truncate -s 0 file.log",
    "python manage.py migrate",
    "sqlite3 app.db 'DELETE FROM users WHERE id = 1'",
    "git push origin main",
]


def test_blocked_commands() -> None:
    for command in BLOCKED:
        assert guard.block_reason(command), f"expected blocked: {command}"


def test_allowed_commands() -> None:
    for command in ALLOWED:
        assert guard.block_reason(command) is None, f"expected allowed: {command}"


def test_redacts_secrets() -> None:
    redacted = guard.redact_command("curl -H 'Bearer sk-test' https://user:pass@example.com API_KEY=abc123")
    assert "sk-test" not in redacted
    assert "abc123" not in redacted
    assert "user:pass" not in redacted


def main() -> int:
    test_blocked_commands()
    test_allowed_commands()
    test_redacts_secrets()
    print("All destructive Bash guard checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
