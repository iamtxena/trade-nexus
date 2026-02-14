#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LLM_DIR = ROOT / "docs" / "llm"
MAP_PATH = LLM_DIR / "source-map.json"
CHUNKS_DIR = LLM_DIR / "chunks"
INDEX_PATH = LLM_DIR / "index.json"
TRACE_PATH = LLM_DIR / "traceability.json"
MANIFEST_PATH = LLM_DIR / "manifest.json"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + 5 :]


def normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip() + "\n"


def extract_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def main() -> int:
    source_map = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    entries = source_map.get("entries", [])

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    for existing in CHUNKS_DIR.glob("*.md"):
        existing.unlink()

    index_entries = []
    trace_entries = []

    for entry in entries:
        source_path = ROOT / entry["source"]
        source_raw = source_path.read_text(encoding="utf-8")
        source_clean = normalize_text(strip_frontmatter(source_raw))
        title = extract_heading(source_clean, entry["title"])

        chunk_id = entry["id"]
        chunk_path = CHUNKS_DIR / f"{chunk_id}.md"
        chunk_body = (
            f"# {title}\n\n"
            f"Source: `{entry['source']}`\n"
            f"Topic: `{entry['topic']}`\n"
            f"Stable ID: `{chunk_id}`\n\n"
            f"{source_clean}"
        )
        chunk_path.write_text(chunk_body, encoding="utf-8")

        chunk_rel = chunk_path.relative_to(ROOT).as_posix()
        source_hash = sha256(source_clean)
        chunk_hash = sha256(chunk_body)

        index_entries.append(
            {
                "id": chunk_id,
                "title": entry["title"],
                "topic": entry["topic"],
                "source": entry["source"],
                "chunk": chunk_rel,
                "concepts": entry["concepts"],
                "endpoints": entry["endpoints"],
                "workflows": entry["workflows"],
                "owners": entry["owners"],
                "owner_issue": entry["owner_issue"],
                "source_hash": source_hash,
                "chunk_hash": chunk_hash,
            }
        )

        trace_entries.append(
            {
                "id": chunk_id,
                "source": entry["source"],
                "chunk": chunk_rel,
                "source_hash": source_hash,
                "chunk_hash": chunk_hash,
            }
        )

    index_entries.sort(key=lambda item: item["id"])
    trace_entries.sort(key=lambda item: item["id"])

    map_hash = sha256(json.dumps(source_map, sort_keys=True))

    manifest = {
        "schema_version": source_map.get("schema_version", "1.0"),
        "entry_count": len(index_entries),
        "source_map": "docs/llm/source-map.json",
        "source_map_hash": map_hash,
    }

    INDEX_PATH.write_text(json.dumps(index_entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    TRACE_PATH.write_text(json.dumps(trace_entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Generated LLM package with {len(index_entries)} chunks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
