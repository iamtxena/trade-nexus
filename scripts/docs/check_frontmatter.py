#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORTAL_DIR = ROOT / "docs" / "portal"
REQUIRED_KEYS = {"title", "summary", "owners", "updated"}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_frontmatter(text: str, path: Path) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing opening frontmatter delimiter")

    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError(f"{path}: missing closing frontmatter delimiter")

    block = text[4:end]
    data: dict[str, str] = {}
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    if not PORTAL_DIR.exists():
        print(f"Missing docs portal directory: {PORTAL_DIR}")
        return 1

    errors: list[str] = []
    for path in sorted(PORTAL_DIR.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        try:
            frontmatter = parse_frontmatter(text, path)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        missing = REQUIRED_KEYS - set(frontmatter)
        if missing:
            errors.append(f"{path}: missing frontmatter keys: {', '.join(sorted(missing))}")

        updated = frontmatter.get("updated", "")
        if updated and not DATE_PATTERN.match(updated):
            errors.append(f"{path}: updated must be YYYY-MM-DD")

    if errors:
        print("Frontmatter validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Frontmatter validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
