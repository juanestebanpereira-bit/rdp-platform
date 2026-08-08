#!/usr/bin/env bash
# Bootstrap rdp-platform's local dev environment on a new machine.
# Safe to re-run: every step checks current state before acting.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_ROOT/dbt-env"
REQUIREMENTS="$REPO_ROOT/requirements.txt"
PYTHON_BIN="python3.12"

info() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
fail() { printf '\033[1;31mERROR:\033[0m %s\n' "$1" >&2; exit 1; }

# --- Prerequisites ----------------------------------------------------------

info "Checking prerequisites..."

command -v brew >/dev/null 2>&1 \
  || fail "Homebrew not found. Install it from https://brew.sh and re-run this script."

command -v "$PYTHON_BIN" >/dev/null 2>&1 \
  || fail "$PYTHON_BIN not found. Install it with: brew install python@3.12"

info "Prerequisites OK (brew, $PYTHON_BIN)."

# --- dbt-env venv ------------------------------------------------------

if [ -d "$VENV_DIR" ]; then
  info "dbt-env already exists at $VENV_DIR, skipping creation."
else
  info "Creating dbt-env venv..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

info "Installing requirements.txt into dbt-env..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$REQUIREMENTS"

# --- Done ----------------------------------------------------------------

cat <<EOF

Setup complete.

Next steps:
  1. Activate the venv:   source dbt-env/bin/activate
  2. Check dbt:           dbt --version
  3. See README.md for merge_manifests.py / dbterd / colibri usage.
EOF
