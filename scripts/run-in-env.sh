#!/usr/bin/env bash
# Used by the local pre-commit hooks (mypy, pylint) to run inside whatever
# virtualenv the repo was set up with, instead of the interpreter pre-commit
# itself uses. Mirrors the same script from other Home Assistant custom
# component templates (e.g. ludeeus/integration_blueprint).
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

exec "$@"
