#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SDK_DIR="${REPO_ROOT}/sdk/typescript"

if [[ ! -d "${SDK_DIR}" ]]; then
  echo "SDK directory ${SDK_DIR} does not exist. Run generate-sdk.sh first." >&2
  exit 1
fi

"${SCRIPT_DIR}/generate-sdk.sh" >/dev/null

if ! git -C "${REPO_ROOT}" diff --quiet -- "${SDK_DIR}"; then
  echo "SDK drift detected in ${SDK_DIR}. Regenerate and commit artifacts." >&2
  git -C "${REPO_ROOT}" --no-pager diff -- "${SDK_DIR}"
  exit 1
fi

echo "No SDK drift detected."
