#!/usr/bin/env python3
"""Smoke tests for the destructive Bash guard."""

from __future__ import annotations

import block_destructive_bash as guard


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


def main() -> int:
    for command in BLOCKED:
        assert guard.block_reason(command), f"expected blocked: {command}"
    for command in ALLOWED:
        assert guard.block_reason(command) is None, f"expected allowed: {command}"
    print("All destructive Bash guard checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
