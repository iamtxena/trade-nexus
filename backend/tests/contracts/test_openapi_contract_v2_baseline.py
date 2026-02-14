"""Baseline checks for additive /v2 KB/Data contract surface."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_SPEC = REPO_ROOT / "docs/architecture/specs/platform-api.openapi.yaml"


def _spec_text() -> str:
    return OPENAPI_SPEC.read_text(encoding="utf-8")


def test_v2_paths_are_declared() -> None:
    spec = _spec_text()
    for path in (
        "/v2/knowledge/search:",
        "/v2/knowledge/patterns:",
        "/v2/knowledge/regimes/{asset}:",
        "/v2/data/exports/backtest:",
        "/v2/data/exports/{exportId}:",
        "/v2/research/market-scan:",
    ):
        assert path in spec, f"Missing required v2 path: {path}"


def test_v2_operation_ids_are_declared() -> None:
    spec = _spec_text()
    for operation_id in (
        "searchKnowledgeV2",
        "listKnowledgePatternsV2",
        "getKnowledgeRegimeV2",
        "createBacktestDataExportV2",
        "getBacktestDataExportV2",
        "postMarketScanV2",
    ):
        assert f"operationId: {operation_id}" in spec


def test_v2_schema_components_are_present() -> None:
    spec = _spec_text()
    for component in (
        "KnowledgeSearchRequest:",
        "KnowledgeSearchResponse:",
        "KnowledgePattern:",
        "KnowledgeRegimeResponse:",
        "BacktestDataExportRequest:",
        "BacktestDataExportResponse:",
        "MarketScanV2Response:",
    ):
        assert component in spec
