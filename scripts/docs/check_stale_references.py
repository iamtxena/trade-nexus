#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require_contains(path: Path, needle: str, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"Missing required file: {path}")
        return
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        errors.append(f"{path}: missing required reference '{needle}'")


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
