#!/usr/bin/env bash
set -euo pipefail

root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

if [[ -n "${CLAUDE_SEO_PYTHON:-}" ]]; then
    py="${CLAUDE_SEO_PYTHON}"
elif command -v python3 >/dev/null 2>&1; then
    py="python3"
else
    echo "python3 is required (3.10+)." >&2
    exit 1
fi

exec "${py}" "${root}/scripts/install_hermes.py" --uninstall "$@"
