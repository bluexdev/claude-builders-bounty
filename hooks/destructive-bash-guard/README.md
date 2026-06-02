# Destructive Bash Guard

Claude Code `PreToolUse` hook for bounty #3. It intercepts Bash tool calls and denies destructive shell or SQL commands before they execute.

## Install

Run this from the repository root:

```bash
python3 hooks/destructive-bash-guard/install.py
```

The installer copies `block-destructive-bash.py` into `~/.claude/hooks/` and adds the `PreToolUse` Bash matcher shown in `settings.example.json` to `~/.claude/settings.json`.

## What It Blocks

- `rm -rf`, including combined flag variants like `rm -fr`.
- `DROP TABLE`.
- `TRUNCATE`.
- `git push --force`, `git push -f`, and `git push --force-with-lease`.
- `DELETE FROM ...` statements that do not include a `WHERE` clause before the statement terminator.

Normal Bash commands exit silently with status `0` and no hook output.

## Blocked Attempt Log

Every blocked command is appended to:

```text
~/.claude/hooks/blocked.log
```

Each JSONL entry includes `timestamp`, `attempted_command`, `project_path`, and `reason`.

## Manual Checks

```bash
printf '{"tool_input":{"command":"rm -rf build"},"cwd":"/tmp/demo"}' | python3 hooks/destructive-bash-guard/block-destructive-bash.py
printf '{"tool_input":{"command":"git status"},"cwd":"/tmp/demo"}' | python3 hooks/destructive-bash-guard/block-destructive-bash.py
```

The first command prints a `permissionDecision: deny` response. The second command prints nothing and allows execution.
