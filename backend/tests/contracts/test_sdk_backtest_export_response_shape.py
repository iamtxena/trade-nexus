"""Contract checks for generated SDK response shapes."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SDK_MODEL = REPO_ROOT / "sdk/typescript/src/models/BacktestDataExportResponse.ts"


def _model_text() -> str:
    return SDK_MODEL.read_text(encoding="utf-8")


def test_backtest_export_response_model_exposes_export_field() -> None:
    model = _model_text()
    assert "export: BacktestDataExport;" in model
    assert "_export: BacktestDataExport;" not in model
    assert "if (!('export' in value) || value['export'] === undefined) return false;" in model


def test_backtest_export_response_model_serialization_uses_export_field() -> None:
    model = _model_text()
    assert "'export': BacktestDataExportFromJSON(json['export'])" in model
    assert "'export': BacktestDataExportToJSON(value['export'])" in model
    assert "value['_export']" not in model
