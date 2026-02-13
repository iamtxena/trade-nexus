#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SPEC_PATH="${REPO_ROOT}/docs/architecture/specs/platform-api.openapi.yaml"
BASE_SPEC_PATH="/tmp/platform-api.base.openapi.yaml"
OPENAPI_DIFF_VERSION="0.24.1"

if [[ ! -f "${SPEC_PATH}" ]]; then
  echo "OpenAPI spec not found at ${SPEC_PATH}" >&2
  exit 1
fi

if [[ "${GITHUB_EVENT_NAME:-}" != "pull_request" ]]; then
  echo "Skipping breaking-change check outside pull_request context."
  exit 0
fi

if [[ -z "${GITHUB_BASE_REF:-}" ]]; then
  echo "GITHUB_BASE_REF is required for breaking-change check." >&2
  exit 1
fi

git -C "${REPO_ROOT}" fetch origin "${GITHUB_BASE_REF}" --depth=1
git -C "${REPO_ROOT}" show "origin/${GITHUB_BASE_REF}:docs/architecture/specs/platform-api.openapi.yaml" > "${BASE_SPEC_PATH}"

export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-/tmp/trade-nexus-npm-cache}"
export NPM_CONFIG_UPDATE_NOTIFIER="false"

npx --yes "openapi-diff@${OPENAPI_DIFF_VERSION}" \
  "${BASE_SPEC_PATH}" \
  "${SPEC_PATH}" \
  --fail-on-incompatible

echo "No incompatible OpenAPI changes detected vs origin/${GITHUB_BASE_REF}."
