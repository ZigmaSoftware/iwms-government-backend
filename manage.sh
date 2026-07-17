#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

cd "$PROJECT_DIR"

if [[ -x "$VENV_PYTHON" ]]; then
    exec "$VENV_PYTHON" manage.py "$@"
fi

mkdir -p /tmp/uv-cache
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"

exec uv run python manage.py "$@"
