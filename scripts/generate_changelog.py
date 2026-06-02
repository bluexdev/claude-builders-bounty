#!/usr/bin/env python3
"""Generate a structured CHANGELOG.md from git commits since the last tag."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


CATEGORIES = ("Added", "Fixed", "Changed", "Removed")


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str


def run_git(args: list[str], repo: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise SystemExit(f"git {' '.join(args)} failed: {message}") from exc
    return completed.stdout.strip()


def find_repo_root(start: Path) -> Path:
    root = run_git(["rev-parse", "--show-toplevel"], start)
    return Path(root)


def last_tag(repo: Path) -> str | None:
    try:
        tag = run_git(["describe", "--tags", "--abbrev=0"], repo)
    except SystemExit:
        return None
    return tag or None


def commits_since(repo: Path, tag: str | None) -> list[Commit]:
    revision = f"{tag}..HEAD" if tag else "HEAD"
    raw = run_git(["log", revision, "--pretty=format:%h%x09%s"], repo)
    commits: list[Commit] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        commits.append(Commit(sha=sha, subject=subject.strip()))
    return commits


def clean_subject(subject: str) -> str:
    subject = re.sub(r"^\w+(?:\([^)]+\))?!?:\s*", "", subject).strip()
    return subject[:1].upper() + subject[1:] if subject else subject


def categorize(subject: str) -> str:
    lowered = subject.lower()
    prefix = lowered.split(":", 1)[0]

    if prefix.startswith(("feat", "add")) or re.search(r"\b(add|adds|added|new|introduce|implement)\b", lowered):
        return "Added"
    if prefix.startswith(("fix", "bug", "hotfix")) or re.search(r"\b(fix|fixed|bug|patch|resolve|repair)\b", lowered):
        return "Fixed"
    if prefix.startswith(("remove", "delete", "drop")) or re.search(r"\b(remove|removed|delete|deleted|drop|dropped|deprecate)\b", lowered):
        return "Removed"
    return "Changed"


def render_changelog(commits: list[Commit], tag: str | None) -> str:
    today = dt.date.today().isoformat()
    compare_label = f"since {tag}" if tag else "from repository history"

    grouped: dict[str, list[Commit]] = {category: [] for category in CATEGORIES}
    for commit in commits:
        grouped[categorize(commit.subject)].append(commit)

    lines = [
        "# Changelog",
        "",
        f"## Unreleased - {today}",
        "",
        f"_Generated from commits {compare_label}._",
        "",
    ]

    if not commits:
        lines.extend(["No commits found for this range.", ""])
        return "\n".join(lines)

    for category in CATEGORIES:
        lines.append(f"### {category}")
        if grouped[category]:
            for commit in grouped[category]:
                lines.append(f"- {clean_subject(commit.subject)} ({commit.sha})")
        else:
            lines.append("- No changes.")
        lines.append("")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate CHANGELOG.md from git history.")
    parser.add_argument(
        "-o",
        "--output",
        default="CHANGELOG.md",
        help="Output file path, relative to the repo root unless absolute.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print changelog to stdout instead of writing a file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = find_repo_root(Path.cwd())
    tag = last_tag(repo)
    commits = commits_since(repo, tag)
    changelog = render_changelog(commits, tag)

    if args.print:
        print(changelog)
        return 0

    output = Path(args.output)
    if not output.is_absolute():
        output = repo / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(changelog, encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
