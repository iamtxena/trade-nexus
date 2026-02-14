#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LLM_DIR = ROOT / "docs" / "llm"
CHUNKS_DIR = LLM_DIR / "chunks"

OWNER_URL_PATTERN = re.compile(r"^https://github\.com/iamtxena/trade-nexus/issues/\d+$")
ALLOWED_OWNER_ISSUES = {"76", "77", "78", "79", "80", "81", "106"}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []

    map_path = LLM_DIR / "source-map.json"
    index_path = LLM_DIR / "index.json"
    trace_path = LLM_DIR / "traceability.json"
    manifest_path = LLM_DIR / "manifest.json"

    for path in [map_path, index_path, trace_path, manifest_path]:
        if not path.exists():
            errors.append(f"Missing required file: {path}")

    if errors:
        print("LLM package validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    source_map = load_json(map_path)
    entries = source_map.get("entries", [])
    index_entries = load_json(index_path)
    trace_entries = load_json(trace_path)
    manifest = load_json(manifest_path)

    index_by_id = {item["id"]: item for item in index_entries}
    trace_by_id = {item["id"]: item for item in trace_entries}

    if len(index_by_id) != len(index_entries):
        errors.append("Duplicate IDs in docs/llm/index.json")
    if len(trace_by_id) != len(trace_entries):
        errors.append("Duplicate IDs in docs/llm/traceability.json")

    for entry in entries:
        entry_id = entry["id"]
        source_rel = entry["source"]
        source_path = ROOT / source_rel

        if not source_path.exists():
            errors.append(f"Source missing for {entry_id}: {source_rel}")

        index_item = index_by_id.get(entry_id)
        if not index_item:
            errors.append(f"Missing index entry: {entry_id}")
            continue

        trace_item = trace_by_id.get(entry_id)
        if not trace_item:
            errors.append(f"Missing traceability entry: {entry_id}")
            continue

        chunk_rel = index_item.get("chunk", "")
        chunk_path = ROOT / chunk_rel
        if not chunk_path.exists():
            errors.append(f"Missing chunk file for {entry_id}: {chunk_rel}")

        if index_item.get("source") != source_rel:
            errors.append(f"Index source mismatch for {entry_id}")

        if trace_item.get("source") != source_rel:
            errors.append(f"Trace source mismatch for {entry_id}")

        owner_issue = index_item.get("owner_issue", "")
        if not OWNER_URL_PATTERN.match(owner_issue):
            errors.append(f"Invalid owner_issue link for {entry_id}: {owner_issue}")
        else:
            issue_id = owner_issue.rsplit("/", 1)[-1]
            if issue_id not in ALLOWED_OWNER_ISSUES:
                errors.append(f"Unexpected owner_issue target for {entry_id}: {owner_issue}")

        if not index_item.get("owners"):
            errors.append(f"Missing owners for {entry_id}")

    for entry_id, trace_item in trace_by_id.items():
        chunk_path = ROOT / trace_item.get("chunk", "")
        if not chunk_path.exists():
            continue
        chunk_text = chunk_path.read_text(encoding="utf-8")
        if f"Stable ID: `{entry_id}`" not in chunk_text:
            errors.append(f"Chunk stable ID marker missing for {entry_id}")

    openapi_reference_found = False
    for trace_item in trace_by_id.values():
        chunk_path = ROOT / trace_item.get("chunk", "")
        if not chunk_path.exists():
            continue
        chunk_text = chunk_path.read_text(encoding="utf-8")
        if "docs/architecture/specs/platform-api.openapi.yaml" in chunk_text:
            openapi_reference_found = True
            break
    if not openapi_reference_found:
        errors.append("LLM chunks are missing canonical OpenAPI path reference")

    if manifest.get("entry_count") != len(entries):
        errors.append("Manifest entry_count does not match source-map entries")

    if errors:
        print("LLM package validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("LLM package validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
