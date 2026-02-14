#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORTAL_DIR="$ROOT_DIR/docs/portal-site"

if [[ ! -d "$PORTAL_DIR" ]]; then
  echo "Docs portal directory not found: $PORTAL_DIR" >&2
  exit 1
fi

npm --prefix "$PORTAL_DIR" run api:build
