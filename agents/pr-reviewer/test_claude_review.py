#!/usr/bin/env python3
"""Smoke tests for the PR reviewer parser and heuristics."""

from __future__ import annotations

import claude_review as review


SAMPLE_DIFF = """diff --git a/src/old name.py b/src/new name.py
similarity index 87%
rename from src/old name.py
rename to src/new name.py
index 1111111..2222222 100644
--- a/src/old name.py
+++ b/src/new name.py
@@ -1,3 +1,4 @@
 context
-old line
+new line
+print("contest should not count as tests")
\\ No newline at end of file
diff --git a/tests/test_new_name.py b/tests/test_new_name.py
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/tests/test_new_name.py
@@ -0,0 +1,2 @@
+def test_new_name():
+    assert True
diff --git a/src/delete_me.py b/src/delete_me.py
deleted file mode 100644
index 4444444..0000000
--- a/src/delete_me.py
+++ /dev/null
@@ -1,2 +0,0 @@
-removed
-content
"""


def test_parse_paths_and_counts() -> None:
    parsed = review.parse_diff("owner", "repo", "1", SAMPLE_DIFF)
    assert [file.path for file in parsed.files] == [
        "src/new name.py",
        "tests/test_new_name.py",
        "src/delete_me.py",
    ]
    assert [(file.added, file.deleted) for file in parsed.files] == [(2, 1), (2, 0), (0, 2)]
    assert "\\ No newline at end of file" not in parsed.added_lines


def test_test_detection_uses_paths_only() -> None:
    parsed = review.parse_diff("owner", "repo", "1", SAMPLE_DIFF)
    assert review.has_test_file(parsed)

    no_test = review.PullRequestDiff(
        owner="owner",
        repo="repo",
        number="2",
        title="owner/repo#2",
        files=(review.ChangedFile("src/latest.py", 1, 0),),
        added_lines=("contest attestation",),
        raw_diff="",
    )
    assert not review.has_test_file(no_test)
    assert review.has_test_file(
        review.PullRequestDiff(
            owner="owner",
            repo="repo",
            number="4",
            title="owner/repo#4",
            files=(review.ChangedFile("hooks/destructive-bash-guard/test_block_destructive_bash.py", 1, 0),),
            added_lines=(),
            raw_diff="",
        )
    )


def test_risks_use_added_lines_not_removed_lines() -> None:
    raw = """diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
-os.system("rm -rf build")
+print("safe replacement")
"""
    parsed = review.parse_diff("owner", "repo", "3", raw)
    assert not any("destructive shell" in risk for risk in review.detect_risks(parsed))


def main() -> int:
    test_parse_paths_and_counts()
    test_test_detection_uses_paths_only()
    test_risks_use_added_lines_not_removed_lines()
    print("All PR reviewer checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
