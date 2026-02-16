#!/usr/bin/env python3
"""Validate Gate5 SLO/alert baseline config and docs alignment."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "contracts/config/slo-alert-baseline.v1.json"
    docs_path = repo_root / "docs/portal/operations/gate5-slo-alerting-baseline.md"

    errors: list[str] = []
    _require(errors, config_path.exists(), f"Missing config file: {config_path}")
    _require(errors, docs_path.exists(), f"Missing docs file: {docs_path}")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    docs_text = docs_path.read_text(encoding="utf-8")

    required_root_keys = {"baselineVersion", "effectiveDate", "ownerTeam", "slos", "alerts"}
    missing_root_keys = sorted(required_root_keys.difference(config.keys()))
    _require(errors, not missing_root_keys, f"Missing config keys: {', '.join(missing_root_keys)}")

    slos = config.get("slos", [])
    alerts = config.get("alerts", [])
    _require(errors, isinstance(slos, list) and len(slos) > 0, "Config `slos` must be a non-empty list.")
    _require(errors, isinstance(alerts, list) and len(alerts) > 0, "Config `alerts` must be a non-empty list.")

    required_slo_keys = {"id", "service", "criticalPath", "sli", "target", "window", "ownerTeam"}
    required_alert_keys = {"id", "sloId", "condition", "severity", "ownerTeam"}
    required_critical_paths = {"execution", "risk", "research", "reconciliation", "conversation"}

    slo_ids: set[str] = set()
    covered_critical_paths: set[str] = set()
    owner_teams: set[str] = set()
    for index, slo in enumerate(slos):
        if not isinstance(slo, dict):
            errors.append(f"SLO at index {index} must be an object.")
            continue
        missing = sorted(required_slo_keys.difference(slo.keys()))
        _require(errors, not missing, f"SLO `{slo.get('id', index)}` missing keys: {', '.join(missing)}")
        slo_id = str(slo.get("id", "")).strip()
        _require(errors, bool(slo_id), f"SLO at index {index} must include non-empty `id`.")
        if slo_id:
            _require(errors, slo_id not in slo_ids, f"SLO id `{slo_id}` is duplicated.")
            slo_ids.add(slo_id)
        critical_path_raw = str(slo.get("criticalPath", "")).strip()
        _require(errors, bool(critical_path_raw), f"SLO `{slo_id or index}` must include non-empty `criticalPath`.")
        if critical_path_raw:
            critical_paths = {token.strip() for token in critical_path_raw.split(",") if token.strip()}
            _require(errors, bool(critical_paths), f"SLO `{slo_id or index}` has invalid `criticalPath` value.")
            covered_critical_paths.update(critical_paths)
        owner = str(slo.get("ownerTeam", "")).strip()
        _require(errors, bool(owner), f"SLO `{slo_id or index}` must include non-empty `ownerTeam`.")
        if owner:
            owner_teams.add(owner)

    missing_critical_paths = sorted(required_critical_paths.difference(covered_critical_paths))
    _require(
        errors,
        not missing_critical_paths,
        "Missing critical path coverage in SLO baseline: "
        + ", ".join(missing_critical_paths),
    )

    alert_ids: set[str] = set()
    for index, alert in enumerate(alerts):
        if not isinstance(alert, dict):
            errors.append(f"Alert at index {index} must be an object.")
            continue
        missing = sorted(required_alert_keys.difference(alert.keys()))
        _require(errors, not missing, f"Alert `{alert.get('id', index)}` missing keys: {', '.join(missing)}")
        alert_id = str(alert.get("id", "")).strip()
        _require(errors, bool(alert_id), f"Alert at index {index} must include non-empty `id`.")
        if alert_id:
            _require(errors, alert_id not in alert_ids, f"Alert id `{alert_id}` is duplicated.")
            alert_ids.add(alert_id)
        slo_id = str(alert.get("sloId", "")).strip()
        _require(
            errors,
            slo_id in slo_ids,
            f"Alert `{alert_id or index}` references unknown SLO id `{slo_id}`.",
        )
        owner = str(alert.get("ownerTeam", "")).strip()
        _require(errors, bool(owner), f"Alert `{alert_id or index}` must include non-empty `ownerTeam`.")
        if owner:
            owner_teams.add(owner)

    baseline_version = str(config.get("baselineVersion", "")).strip()
    _require(errors, bool(baseline_version), "Config `baselineVersion` must be non-empty.")
    if baseline_version:
        _require(
            errors,
            baseline_version in docs_text,
            f"Docs do not reference baseline version `{baseline_version}`.",
        )

    config_ref = "contracts/config/slo-alert-baseline.v1.json"
    _require(errors, config_ref in docs_text, f"Docs must reference `{config_ref}`.")

    for slo_id in sorted(slo_ids):
        _require(errors, slo_id in docs_text, f"Docs missing SLO id `{slo_id}`.")
    for alert_id in sorted(alert_ids):
        _require(errors, alert_id in docs_text, f"Docs missing alert id `{alert_id}`.")
    for team in sorted(owner_teams):
        _require(errors, team in docs_text, f"Docs missing owner team `{team}`.")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(
        "SLO/alert baseline validation passed: "
        f"{len(slo_ids)} SLOs, {len(alert_ids)} alerts, baseline {baseline_version}.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
