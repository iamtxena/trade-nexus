#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SPEC_PATH="${REPO_ROOT}/docs/architecture/specs/platform-api.openapi.yaml"
CONFIG_PATH="${REPO_ROOT}/contracts/config/openapi-generator-sdk.yaml"
SDK_OUT_DIR="${REPO_ROOT}/sdk/typescript"
GENERATOR_VERSION="2.21.5"
OPENJDK_HOME="/opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home"

if [[ ! -f "${SPEC_PATH}" ]]; then
  echo "OpenAPI spec not found at ${SPEC_PATH}" >&2
  exit 1
fi

SDK_VERSION="$(awk '/^  version: / {print $2; exit}' "${SPEC_PATH}")"
if [[ -z "${SDK_VERSION}" ]]; then
  echo "Unable to read info.version from ${SPEC_PATH}" >&2
  exit 1
fi

rm -rf "${SDK_OUT_DIR}"
mkdir -p "${SDK_OUT_DIR}"

# Prefer Homebrew OpenJDK when macOS system java is a non-functional stub.
if ! java -version >/dev/null 2>&1 && [[ -x "${OPENJDK_HOME}/bin/java" ]]; then
  export JAVA_HOME="${OPENJDK_HOME}"
  export PATH="${JAVA_HOME}/bin:${PATH}"
fi

# Keep npm cache writable under sandboxed environments.
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-/tmp/trade-nexus-npm-cache}"
export NPM_CONFIG_UPDATE_NOTIFIER="false"

npx --yes "@openapitools/openapi-generator-cli@${GENERATOR_VERSION}" generate \
  -i "${SPEC_PATH}" \
  -o "${SDK_OUT_DIR}" \
  -c "${CONFIG_PATH}" \
  --additional-properties "npmName=@trade-nexus/sdk,npmVersion=${SDK_VERSION}"

# Normalize generated package metadata for publish workflow and consumers.
node - "${REPO_ROOT}" <<'NODE'
const fs = require('fs');
const path = require('path');

const repoRoot = process.argv[2];
const packageJsonPath = path.join(repoRoot, 'sdk/typescript/package.json');
const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
const backtestsApiPath = path.join(repoRoot, 'sdk/typescript/src/apis/BacktestsApi.ts');

packageJson.description = 'Generated TypeScript SDK for the Trade Nexus Platform API';
packageJson.license = 'MIT';
packageJson.repository = {
  type: 'git',
  url: 'git+https://github.com/iamtxena/trade-nexus.git',
};
packageJson.homepage = 'https://github.com/iamtxena/trade-nexus#readme';
packageJson.bugs = { url: 'https://github.com/iamtxena/trade-nexus/issues' };
packageJson.publishConfig = { access: 'public' };

fs.writeFileSync(packageJsonPath, `${JSON.stringify(packageJson, null, 2)}\n`, 'utf8');

if (fs.existsSync(backtestsApiPath)) {
  const backtestsApi = fs.readFileSync(backtestsApiPath, 'utf8');
  const nullableSignature = 'createBacktestRequest: CreateBacktestRequest | null;';
  const requiredSignature = 'createBacktestRequest: CreateBacktestRequest;';
  let normalizedBacktestsApi = backtestsApi;

  if (normalizedBacktestsApi.includes(nullableSignature)) {
    normalizedBacktestsApi = normalizedBacktestsApi.replace(nullableSignature, requiredSignature);
  }

  if (!normalizedBacktestsApi.includes(requiredSignature)) {
    throw new Error('Failed to normalize BacktestsApi request signature.');
  }

  if (normalizedBacktestsApi !== backtestsApi) {
    fs.writeFileSync(backtestsApiPath, normalizedBacktestsApi, 'utf8');
  }
}
NODE

# Remove generator metadata to keep drift checks stable across environments.
rm -rf "${SDK_OUT_DIR}/.openapi-generator"

echo "Generated SDK at ${SDK_OUT_DIR} (version ${SDK_VERSION})"
