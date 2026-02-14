# LLM Documentation Package

This folder contains generated machine-readable docs artifacts for agent consumption.

## Files

- `source-map.json`: source-of-truth chunk map with stable IDs and ownership metadata.
- `index.json`: machine-readable index of concepts, endpoints, workflows, and ownership.
- `traceability.json`: mapping from chunk IDs to source docs and hashes.
- `manifest.json`: package metadata and source-map hash.
- `chunks/*.md`: normalized topic chunks generated from source docs.

## Regeneration

```bash
python3 scripts/docs/generate_llm_package.py
```

## Validation

```bash
python3 scripts/docs/check_llm_package.py
```

## CI Enforcement

`docs-governance` workflow regenerates this package and fails on drift or invalid ownership/reference links.
