#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PYTHON_CMD=()
for candidate in python3 python "py -3"; do
  if $candidate --version >/dev/null 2>&1; then
    read -r -a PYTHON_CMD <<< "$candidate"
    break
  fi
done

if [[ ${#PYTHON_CMD[@]} -eq 0 ]]; then
  echo "Python 3 is required to generate the changelog." >&2
  exit 1
fi

exec "${PYTHON_CMD[@]}" "$SCRIPT_DIR/scripts/generate_changelog.py" "$@"
