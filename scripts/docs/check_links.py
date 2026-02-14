#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MARKDOWN_PATHS = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
]
MARKDOWN_PATHS.extend(sorted((ROOT / "docs" / "portal").rglob("*.md")))

LINK_PATTERN = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")


def should_skip(link: str) -> bool:
    return link.startswith(("http://", "https://", "mailto:", "#", "/"))


def link_target(path: Path, link: str) -> Path | None:
    base = link.split("#", 1)[0]
    if not base:
        return None
    return (path.parent / base).resolve()


def main() -> int:
    errors: list[str] = []

    for path in MARKDOWN_PATHS:
        if not path.exists():
            continue

        text = path.read_text(encoding="utf-8")
        for link in LINK_PATTERN.findall(text):
            if should_skip(link):
                continue
            target = link_target(path, link)
            if target is None:
                continue
            if not target.exists():
                errors.append(f"{path}: missing link target '{link}'")

    if errors:
        print("Link validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Markdown link validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
