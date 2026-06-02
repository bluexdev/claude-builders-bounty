# PR Reviewer Agent

Claude Code sub-agent and CLI for bounty #4. It accepts a GitHub pull request URL, reads the public diff, and returns a structured Markdown review comment.

## Setup

From the repository root:

```bash
chmod +x claude-review
```

Optional for private repositories or higher GitHub rate limits:

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

## Usage

```bash
./claude-review --pr https://github.com/owner/repo/pull/123
./claude-review --pr https://github.com/owner/repo/pull/123 --output review.md
```

The output always includes:

- Summary of changes.
- Identified risks.
- Improvement suggestions.
- Confidence score: Low, Medium, or High.

The companion Claude Code sub-agent definition lives at `.claude/agents/pr-reviewer.md`. Use the sub-agent when you want Claude Code to reason over the same structure with repository context; use the CLI when you want a deterministic review comment from a public PR URL.

## Verification

```bash
python agents/pr-reviewer/claude_review.py --pr https://github.com/claude-builders-bounty/claude-builders-bounty/pull/2400
python agents/pr-reviewer/claude_review.py --pr https://github.com/claude-builders-bounty/claude-builders-bounty/pull/2401
python -m compileall agents/pr-reviewer
```

Sample outputs are included in `agents/pr-reviewer/examples/`.
