#!/usr/bin/env python3
"""Smoke tests for the destructive Bash guard."""

from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load_module("block_destructive_bash", Path(__file__).with_name("block_destructive_bash.py"))
installer = load_module("install_destructive_bash_guard", Path(__file__).with_name("install.py"))


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


def test_installer_rejects_unexpected_settings_shapes() -> None:
    for invalid in (
        {"hooks": []},
        {"hooks": {"PreToolUse": {}}},
        {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": {}}]}},
    ):
        try:
            installer.merge_hook(invalid, 'python3 "/tmp/block_destructive_bash.py"')
        except SystemExit:
            pass
        else:
            raise AssertionError(f"expected invalid settings shape to fail: {invalid}")


def test_log_block_rejects_symlink() -> None:
    if os.name == "nt" or not hasattr(os, "symlink"):
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "blocked.log"
        target_path = Path(tmpdir) / "target.log"
        os.symlink(target_path, log_path)

        original_log_file_path = guard.log_file_path
        guard.log_file_path = lambda: log_path
        try:
            try:
                guard.log_block("rm -rf build", "/tmp/project", "blocked")
            except SystemExit as exc:
                assert "symlink" in str(exc).lower()
            else:
                raise AssertionError("expected symlink log path to be rejected")
        finally:
            guard.log_file_path = original_log_file_path


def main() -> int:
    test_blocked_commands()
    test_allowed_commands()
    test_redacts_secrets()
    test_installer_rejects_unexpected_settings_shapes()
    test_log_block_rejects_symlink()
    print("All destructive Bash guard checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
