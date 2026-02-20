#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require_contains(path: Path, needle: str, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"Missing required file: {path}")
        return
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        errors.append(f"{path}: missing required reference '{needle}'")


def require_pull_request_without_paths(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"Missing required workflow: {path}")
        return

    text = path.read_text(encoding="utf-8")
    if "pull_request:" not in text:
        errors.append(f"{path}: missing pull_request trigger")

    pr_block = re.search(r"(?m)^  pull_request:\n((?: {4}.*\n)*)", text)
    if pr_block and "paths:" in pr_block.group(1):
        errors.append(f"{path}: pull_request trigger must not be path-filtered")

    if "push:" not in text or "branches:" not in text or "- main" not in text:
        errors.append(f"{path}: expected push trigger for main branch")


def main() -> int:
    errors: list[str] = []

    api_doc = ROOT / "docs" / "portal" / "api" / "platform-api.md"
    require_contains(api_doc, "docs/architecture/specs/platform-api.openapi.yaml", errors)

    gate_doc = ROOT / "docs" / "portal" / "operations" / "gate-workflow.md"
    for token in ["STARTED", "IN_REVIEW", "MERGED", "BLOCKED"]:
        require_contains(gate_doc, token, errors)

    adr_doc = ROOT / "docs" / "architecture" / "decisions" / "ADR-0003-docs-portal-framework.md"
    require_contains(adr_doc, "Docusaurus", errors)
    require_contains(adr_doc, "Redocly", errors)

    gate5_release_doc = ROOT / "docs" / "portal" / "operations" / "gate5-release-runbooks-and-client-validation.md"
    require_contains(gate5_release_doc, "Scenario D: Replay Gate Blocked", errors)
    require_contains(gate5_release_doc, "python -m src.platform_api.validation.release_gate_check", errors)
    require_contains(gate5_release_doc, "mergeGateStatus", errors)
    require_contains(gate5_release_doc, "releaseGateStatus", errors)
    require_contains(gate5_release_doc, "remediation PR URL", errors)

    gate5_profile_doc = ROOT / "docs" / "portal" / "operations" / "gate5-deployment-profile.md"
    require_contains(gate5_profile_doc, "test_sdk_validation_contract_shape.py", errors)
    require_contains(gate5_profile_doc, "release_gate_check", errors)

    require_contains(
        gate_doc,
        "run on every `pull_request` event",
        errors,
    )
    require_contains(gate_doc, "check_stale_references.py", errors)

    contracts_workflow = ROOT / ".github" / "workflows" / "contracts-governance.yml"
    docs_workflow = ROOT / ".github" / "workflows" / "docs-governance.yml"
    llm_workflow = ROOT / ".github" / "workflows" / "llm-package-governance.yml"
    backend_deploy_workflow = ROOT / ".github" / "workflows" / "backend-deploy.yml"

    for workflow in (contracts_workflow, docs_workflow, llm_workflow):
        require_pull_request_without_paths(workflow, errors)

    require_contains(
        contracts_workflow,
        "pytest backend/tests/contracts/test_sdk_validation_contract_shape.py",
        errors,
    )
    require_contains(
        contracts_workflow,
        "python -m src.platform_api.validation.release_gate_check",
        errors,
    )
    require_contains(
        backend_deploy_workflow,
        "python -m src.platform_api.validation.release_gate_check",
        errors,
    )

    governance_doc = ROOT / "docs" / "architecture" / "API_CONTRACT_GOVERNANCE.md"
    require_contains(governance_doc, "test_sdk_validation_contract_shape.py", errors)
    require_contains(governance_doc, "python -m src.platform_api.validation.release_gate_check", errors)

    resource_map_doc = ROOT / "docs" / "ops" / "RESOURCE_MAP.md"
    require_contains(resource_map_doc, "All `pull_request` events", errors)

    llm_readme = ROOT / "docs" / "llm" / "README.md"
    require_contains(llm_readme, "`llm-package-governance` workflow", errors)

    portal_package = ROOT / "docs" / "portal-site" / "package.json"
    require_contains(portal_package, "\"check:stale\"", errors)
    require_contains(portal_package, "npm run check:stale", errors)

    generated_ref = ROOT / "docs" / "portal-site" / "static" / "api" / "platform-api.html"
    if not generated_ref.exists():
        errors.append(f"Missing generated API reference: {generated_ref}")

    if errors:
        print("Stale-reference validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Stale-reference validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
