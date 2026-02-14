#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MARKDOWN_PATHS = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
]
MARKDOWN_PATHS.extend(sorted((ROOT / "docs" / "portal").rglob("*.md")))

LINK_PATTERN = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")
CHECK_EXTERNAL = os.getenv("CHECK_EXTERNAL_LINKS", "0") == "1"


def should_skip_local(link: str) -> bool:
    return link.startswith(("http://", "https://", "mailto:", "#", "/", "pathname://"))


def link_target(path: Path, link: str) -> Path | None:
    base = link.split("#", 1)[0]
    if not base:
        return None
    return (path.parent / base).resolve()


def main() -> int:
    errors: list[str] = []
    external_links: set[str] = set()

    for path in MARKDOWN_PATHS:
        if not path.exists():
            continue

        text = path.read_text(encoding="utf-8")
        for link in LINK_PATTERN.findall(text):
            if CHECK_EXTERNAL and link.startswith(("http://", "https://")) and "github.com/iamtxena/" in link:
                external_links.add(link)
            if should_skip_local(link):
                continue
            target = link_target(path, link)
            if target is None:
                continue
            if not target.exists():
                errors.append(f"{path}: missing link target '{link}'")

    if CHECK_EXTERNAL:
        for link in sorted(external_links):
            head_req = urllib.request.Request(link, method="HEAD", headers={"User-Agent": "trade-nexus-docs-check"})
            try:
                with urllib.request.urlopen(head_req, timeout=20):
                    pass
            except urllib.error.HTTPError as err:
                if err.code in {403, 405}:
                    get_req = urllib.request.Request(
                        link,
                        method="GET",
                        headers={"User-Agent": "trade-nexus-docs-check"},
                    )
                    try:
                        with urllib.request.urlopen(get_req, timeout=20):
                            pass
                    except Exception as get_err:  # noqa: BLE001
                        errors.append(f"external link check failed for '{link}': {get_err}")
                else:
                    errors.append(f"external link check failed for '{link}': HTTP {err.code}")
            except Exception as err:  # noqa: BLE001
                errors.append(f"external link check failed for '{link}': {err}")

    if errors:
        print("Link validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Markdown link validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
