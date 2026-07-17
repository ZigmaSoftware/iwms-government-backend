#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

mkdir -p "$CACHE_DIR"

export UV_CACHE_DIR="$CACHE_DIR"
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"

cd "$PROJECT_DIR"

echo "Using UV cache: $UV_CACHE_DIR"
echo "Using UV link mode: $UV_LINK_MODE"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed. Install it first:" >&2
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

if ! uv sync --locked "$@"; then
    echo "" >&2
    echo "uv sync failed." >&2
    echo "Common fixes:" >&2
    echo "1. Make sure the cache directory is writable: $UV_CACHE_DIR" >&2
    echo "2. Verify DNS/network access:" >&2
    echo "   getent hosts files.pythonhosted.org pypi.org" >&2
    echo "3. If the server is offline, reuse the existing venv at:" >&2
    echo "   /home/admin/localserver/iwms-backend/venv" >&2
    exit 1
fi
