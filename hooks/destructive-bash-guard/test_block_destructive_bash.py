#!/usr/bin/env python3
"""Smoke tests for the destructive Bash guard."""

from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("block-destructive-bash.py")
SPEC = importlib.util.spec_from_file_location("block_destructive_bash", MODULE_PATH)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


BLOCKED = [
    "rm -rf build",
    "rm -fr build",
    "psql -c 'DROP TABLE users'",
    "sqlite3 app.db 'TRUNCATE audit_log'",
    "git push --force origin main",
    "git push -f origin main",
    "git push --force-with-lease origin main",
    "sqlite3 app.db 'DELETE FROM users'",
]

ALLOWED = [
    "git status",
    "rm -r build",
    "python manage.py migrate",
    "sqlite3 app.db 'DELETE FROM users WHERE id = 1'",
    "git push origin main",
]


def main() -> int:
    for command in BLOCKED:
        assert guard.block_reason(command), f"expected blocked: {command}"
    for command in ALLOWED:
        assert guard.block_reason(command) is None, f"expected allowed: {command}"
    print("All destructive Bash guard checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
