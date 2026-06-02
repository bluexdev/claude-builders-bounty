#!/usr/bin/env python3
"""Generate a structured Markdown PR review from a GitHub pull request diff."""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PR_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)(?:[/?#].*)?$")
RISKY_PATTERNS = (
    ("SQL data destruction handling", re.compile(r"(?i)\b(drop\s+table|truncate\s+(?:table\s+)?\w+|delete\s+from)\b")),
    ("authentication or authorization changes", re.compile(r"(?i)\b(auth|session|permission|role|jwt|oauth)\b")),
    ("billing or payment changes", re.compile(r"(?i)\b(billing|stripe|invoice|payment|checkout)\b")),
    ("destructive shell or git operations", re.compile(r"(?i)\b(rm\s+[^;&|\n]*-[^\s;&|]*r[^\s;&|]*f|git\s+push\b[^\n;&|]*(?:--force|-f\b))")),
    ("secret or environment handling", re.compile(r"(?i)\b(secret|api[_-]?key|process\.env|env\.)\b|\.env\b")),
)
TEST_PATH_RE = re.compile(r"(?i)(^|/)(test_[^/]*|[^/]*(_test|\\.test|\\.spec)|__tests__|tests?)(/|\\.|$)")


@dataclass(frozen=True)
class ChangedFile:
    path: str
    added: int
    deleted: int


@dataclass(frozen=True)
class PullRequestDiff:
    owner: str
    repo: str
    number: str
    title: str
    files: tuple[ChangedFile, ...]
    added_lines: tuple[str, ...]
    raw_diff: str


def parse_pr_url(url: str) -> tuple[str, str, str]:
    match = PR_RE.match(url)
    if not match:
        raise SystemExit("Expected a GitHub PR URL like https://github.com/owner/repo/pull/123")
    return match.group(1), match.group(2), match.group(3)


def fetch_diff(owner: str, repo: str, number: str) -> str:
    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "User-Agent": "claude-review/1.0",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8", errors="replace")
            if text.lstrip().startswith("<"):
                raise SystemExit("GitHub returned HTML instead of a diff; check authentication or PR visibility.")
            return text
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"GitHub request failed with HTTP {exc.code}: {url}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"GitHub request failed: {exc.reason}") from exc


def parse_diff(owner: str, repo: str, number: str, raw_diff: str) -> PullRequestDiff:
    title = f"{owner}/{repo}#{number}"
    files: list[ChangedFile] = []
    current_path: str | None = None
    fallback_path: str | None = None
    added = 0
    deleted = 0
    in_hunk = False
    added_lines: list[str] = []

    def finish_file() -> None:
        nonlocal current_path, fallback_path, added, deleted, in_hunk
        path = current_path or fallback_path
        if path is not None:
            files.append(ChangedFile(path, added, deleted))
        current_path = None
        fallback_path = None
        added = 0
        deleted = 0
        in_hunk = False

    for line in raw_diff.splitlines():
        if line.startswith("diff --git "):
            finish_file()
            fallback_path = line.rsplit(" ", 1)[-1].removeprefix("b/")
            continue
        if line.startswith("+++ "):
            marker = line[4:]
            if marker == "/dev/null":
                current_path = fallback_path
            elif marker.startswith("b/"):
                current_path = marker[2:]
            continue
        if line.startswith("--- "):
            continue
        if line.startswith("@@ "):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("\\"):
            continue
        if line.startswith("+"):
            added += 1
            added_lines.append(line[1:])
        elif line.startswith("-"):
            deleted += 1

    finish_file()

    return PullRequestDiff(owner, repo, number, title, tuple(files), tuple(added_lines), raw_diff)


def summarize_files(files: Iterable[ChangedFile]) -> str:
    file_list = list(files)
    if not file_list:
        return "No changed files were found in the diff."
    total_added = sum(file.added for file in file_list)
    total_deleted = sum(file.deleted for file in file_list)
    top_files = sorted(file_list, key=lambda file: file.added + file.deleted, reverse=True)[:3]
    names = ", ".join(file.path for file in top_files)
    return f"The diff changes {len(file_list)} file(s), with {total_added} added and {total_deleted} deleted line(s). The largest changes are in {names}."


def detect_risks(pr: PullRequestDiff) -> list[str]:
    haystack = review_haystack(pr)
    risks: list[str] = []
    for label, pattern in RISKY_PATTERNS:
        if pattern.search(haystack):
            risks.append(f"- Review {label}; the diff contains related paths or commands.")

    if not has_test_file(pr):
        risks.append("- No test file or test command change is visible, so behavior may rely on manual verification.")

    large_files = [file for file in pr.files if file.added + file.deleted > 250]
    if large_files:
        names = ", ".join(file.path for file in large_files[:3])
        risks.append(f"- Large changes in {names} may hide multiple concerns in one review.")

    return risks or ["- No major risks found in the reviewed diff."]


def suggestions(pr: PullRequestDiff) -> list[str]:
    haystack = review_haystack(pr)
    items: list[str] = []
    if not has_test_file(pr):
        items.append("- Add a small focused test or sample output that exercises the main changed behavior.")
    if re.search(r"(?i)(cli|argparse|command)", haystack):
        items.append("- Document the exact CLI invocation and at least one expected output snippet.")
    if re.search(r"(?i)(drop\s+table|truncate|delete\s+from|sql)", haystack):
        items.append("- Add cases for quoted SQL, semicolon-separated SQL, and safe DELETE statements with WHERE clauses.")
    if re.search(r"(?i)(hook|bash|shell)", haystack):
        items.append("- Include one allowed and one denied shell example so reviewers can reproduce the boundary.")
    if not items:
        items.append("- Keep the PR scoped to the current behavior and add a regression example if a bug motivated it.")
    return items


def review_haystack(pr: PullRequestDiff) -> str:
    paths = "\n".join(file.path for file in pr.files)
    additions = "\n".join(pr.added_lines)
    return f"{paths}\n{additions}"


def has_test_file(pr: PullRequestDiff) -> bool:
    return any(TEST_PATH_RE.search(file.path) for file in pr.files)


def confidence(pr: PullRequestDiff) -> str:
    if not pr.files:
        return "Low - The diff did not expose changed files."
    total_lines = sum(file.added + file.deleted for file in pr.files)
    if total_lines > 600:
        return "Medium - The diff is reviewable, but the change size limits confidence without running project tests."
    return "High - The diff is small enough for a reliable static review, assuming the fetched PR diff is complete."


def render_review(pr: PullRequestDiff, pr_url: str) -> str:
    summary = summarize_files(pr.files)
    risks = "\n".join(detect_risks(pr))
    improvements = "\n".join(suggestions(pr))
    return (
        "## Summary\n"
        f"This review covers [{pr.title}]({pr_url}). {summary} "
        "The review is based on the public GitHub diff and focuses on implementation risk, test coverage, and maintainability.\n\n"
        "## Identified Risks\n"
        f"{risks}\n\n"
        "## Improvement Suggestions\n"
        f"{improvements}\n\n"
        "## Confidence\n"
        f"{confidence(pr)}\n"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a structured Markdown review for a GitHub PR.")
    parser.add_argument("--pr", required=True, help="GitHub pull request URL.")
    parser.add_argument("-o", "--output", help="Optional file path for the Markdown review.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    owner, repo, number = parse_pr_url(args.pr)
    raw_diff = fetch_diff(owner, repo, number)
    pr = parse_diff(owner, repo, number, raw_diff)
    review = render_review(pr, args.pr)

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(review, encoding="utf-8")
    else:
        print(review, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
