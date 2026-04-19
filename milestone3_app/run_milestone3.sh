#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f "$REPO_ROOT/.venv311/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.venv311/bin/activate"
elif [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.venv/bin/activate"
fi

exec streamlit run "$REPO_ROOT/milestone3_app/app.py"
