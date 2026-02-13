#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SPEC_PATH="${REPO_ROOT}/docs/architecture/specs/platform-api.openapi.yaml"
SDK_PACKAGE_JSON="${REPO_ROOT}/sdk/typescript/package.json"
SDK_DIR="${REPO_ROOT}/sdk/typescript"

OPENAPI_VERSION="$(awk '/^  version: / {print $2; exit}' "${SPEC_PATH}")"
SDK_VERSION="$(node -e "const fs=require('fs');const p=JSON.parse(fs.readFileSync('${SDK_PACKAGE_JSON}','utf8'));process.stdout.write(p.version);")"

if [[ "${OPENAPI_VERSION}" != "${SDK_VERSION}" ]]; then
  echo "Version mismatch: OpenAPI=${OPENAPI_VERSION}, SDK=${SDK_VERSION}" >&2
  exit 1
fi

if [[ "${GITHUB_REF_TYPE:-}" == "tag" && -n "${GITHUB_REF_NAME:-}" ]]; then
  EXPECTED_TAG="sdk-v${SDK_VERSION}"
  if [[ "${GITHUB_REF_NAME}" != "${EXPECTED_TAG}" ]]; then
    echo "Tag mismatch: expected ${EXPECTED_TAG}, got ${GITHUB_REF_NAME}" >&2
    exit 1
  fi
fi

export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-/tmp/trade-nexus-npm-cache}"
export NPM_CONFIG_UPDATE_NOTIFIER="false"

pushd "${SDK_DIR}" >/dev/null
npm install --no-package-lock
npm run build
npm pack --dry-run --ignore-scripts
popd >/dev/null

echo "SDK release preparation passed for version ${SDK_VERSION}."
