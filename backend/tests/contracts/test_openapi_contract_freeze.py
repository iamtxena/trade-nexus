"""Gate1 freeze checks for the canonical OpenAPI contract.

These checks lock the agreed v1 contract surface so downstream teams can
implement in parallel without ambiguity.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_SPEC = REPO_ROOT / "docs/architecture/specs/platform-api.openapi.yaml"

EXPECTED_V1_PATHS = {
    "/v1/health",
    "/v1/research/market-scan",
    "/v1/strategies",
    "/v1/strategies/{strategyId}",
    "/v1/strategies/{strategyId}/backtests",
    "/v1/backtests/{backtestId}",
    "/v1/deployments",
    "/v1/deployments/{deploymentId}",
    "/v1/deployments/{deploymentId}/actions/stop",
    "/v1/portfolios",
    "/v1/portfolios/{portfolioId}",
    "/v1/orders",
    "/v1/orders/{orderId}",
    "/v1/datasets/uploads:init",
    "/v1/datasets/{datasetId}/uploads:complete",
    "/v1/datasets/{datasetId}/validate",
    "/v1/datasets/{datasetId}/transform/candles",
    "/v1/datasets/{datasetId}/publish/lona",
    "/v1/datasets",
    "/v1/datasets/{datasetId}",
    "/v1/datasets/{datasetId}/quality-report",
}

EXPECTED_OPERATION_IDS = {
    "getHealthV1",
    "postMarketScanV1",
    "listStrategiesV1",
    "createStrategyV1",
    "getStrategyV1",
    "updateStrategyV1",
    "createBacktestV1",
    "getBacktestV1",
    "listDeploymentsV1",
    "createDeploymentV1",
    "getDeploymentV1",
    "stopDeploymentV1",
    "listPortfoliosV1",
    "getPortfolioV1",
    "listOrdersV1",
    "createOrderV1",
    "getOrderV1",
    "cancelOrderV1",
    "initDatasetUploadV1",
    "completeDatasetUploadV1",
    "validateDatasetV1",
    "transformDatasetCandlesV1",
    "publishDatasetLonaV1",
    "listDatasetsV1",
    "getDatasetV1",
    "getDatasetQualityReportV1",
}


def _spec_text() -> str:
    return OPENAPI_SPEC.read_text(encoding="utf-8")


def test_v1_path_set_is_frozen() -> None:
    spec = _spec_text()
    discovered_paths = set(re.findall(r"^  (/v1/.+):$", spec, flags=re.MULTILINE))
    assert discovered_paths == EXPECTED_V1_PATHS


def test_all_operations_define_unique_operation_ids() -> None:
    spec = _spec_text()
    operation_ids = re.findall(r"^\s+operationId:\s+([A-Za-z0-9_]+)\s*$", spec, flags=re.MULTILINE)
    v1_operation_ids = {operation_id for operation_id in operation_ids if operation_id.endswith("V1")}
    assert v1_operation_ids == EXPECTED_OPERATION_IDS
    assert len(operation_ids) == len(set(operation_ids)), "operationId values must be unique."


def test_error_component_responses_reference_error_envelope() -> None:
    spec = _spec_text()
    for error_name in ("Error400", "Error401", "Error404", "Error409", "Error429"):
        pattern = rf"{error_name}:\n(?:[ \t].*\n)*?[ \t]+\$ref: '#/components/schemas/ErrorResponse'"
        assert re.search(pattern, spec), f"{error_name} must reference ErrorResponse."
