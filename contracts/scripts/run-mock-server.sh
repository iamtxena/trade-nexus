#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SPEC_PATH="${REPO_ROOT}/docs/architecture/specs/platform-api.openapi.yaml"
HOST="${PRISM_HOST:-127.0.0.1}"
PORT="${PRISM_PORT:-4010}"
PRISM_VERSION="5.14.2"

if [[ ! -f "${SPEC_PATH}" ]]; then
  echo "OpenAPI spec not found at ${SPEC_PATH}" >&2
  exit 1
fi

export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-/tmp/trade-nexus-npm-cache}"
export NPM_CONFIG_UPDATE_NOTIFIER="false"

npx --yes "@stoplight/prism-cli@${PRISM_VERSION}" mock \
  --host "${HOST}" \
  --port "${PORT}" \
  "${SPEC_PATH}"
