#!/usr/bin/env python3
"""Credentialed smoke for validation web proxy routes."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_SMOKE_BOT_NAME = "validation-proxy-smoke"
DEFAULT_SMOKE_OWNER_EMAIL = "smoke.validation+proxy@lona.agency"
DEFAULT_SMOKE_PARTNER_KEY = "partner-bootstrap"


@dataclass
class HttpResult:
    status: int
    latency_ms: int | None
    json_payload: dict[str, Any] | None
    text_payload: str
    error: str | None = None


@dataclass
class RouteCheck:
    name: str
    method: str
    route: str
    status: int
    non401: bool
    expected_status: bool
    ok: bool
    request_id: str | None
    run_id: str | None
    latency_ms: int | None
    error: str | None


@dataclass
class BootstrapResult:
    attempted: bool
    ok: bool
    status: int
    request_id: str | None
    bot_id: str | None
    key_id: str | None
    route: str
    error: str | None


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_base_url(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    return trimmed[:-1] if trimmed.endswith("/") else trimmed


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def mkdir_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def write_text(path: str, content: str) -> None:
    mkdir_parent(path)
    Path(path).write_text(content, encoding="utf-8")


def write_json(path: str, payload: dict[str, Any]) -> None:
    mkdir_parent(path)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_tsv(path: str, checks: list[RouteCheck]) -> None:
    mkdir_parent(path)
    lines = [
        "name\tmethod\troute\tstatus\tnon401\texpectedStatus\tok\trunId\trequestId\tlatencyMs\terror",
    ]
    for check in checks:
        lines.append(
            "\t".join(
                [
                    check.name,
                    check.method,
                    check.route,
                    str(check.status),
                    str(check.non401).lower(),
                    str(check.expected_status).lower(),
                    str(check.ok).lower(),
                    check.run_id or "",
                    check.request_id or "",
                    "" if check.latency_ms is None else str(check.latency_ms),
                    (check.error or "").replace("\t", " "),
                ]
            )
        )
    write_text(path, "\n".join(lines) + "\n")


def http_json_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    timeout_seconds: float,
    payload: dict[str, Any] | None = None,
) -> HttpResult:
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url=url, method=method, headers=headers, data=body)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            status = int(response.status)
    except urllib.error.HTTPError as http_error:
        raw = http_error.read()
        status = int(http_error.code)
    except Exception as exc:  # noqa: BLE001
        return HttpResult(
            status=0,
            latency_ms=None,
            json_payload=None,
            text_payload="",
            error=f"{type(exc).__name__}: {exc}",
        )

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    text_payload = raw.decode("utf-8", errors="replace")
    json_payload: dict[str, Any] | None = None
    if text_payload:
        try:
            maybe_json = json.loads(text_payload)
            if isinstance(maybe_json, dict):
                json_payload = maybe_json
        except json.JSONDecodeError:
            json_payload = None

    return HttpResult(
        status=status,
        latency_ms=elapsed_ms,
        json_payload=json_payload,
        text_payload=text_payload,
        error=None,
    )


def get_request_id(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    for key in ("requestId", "request_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def get_run_id(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    direct = payload.get("runId")
    if isinstance(direct, str) and direct:
        return direct
    run = payload.get("run")
    if isinstance(run, dict):
        run_id = run.get("id")
        if isinstance(run_id, str) and run_id:
            return run_id
    artifact = payload.get("artifact")
    if isinstance(artifact, dict):
        artifact_run_id = artifact.get("runId")
        if isinstance(artifact_run_id, str) and artifact_run_id:
            return artifact_run_id
    return None


def get_error_summary(result: HttpResult) -> str | None:
    if result.error:
        return result.error
    payload = result.json_payload
    if isinstance(payload, dict):
        error_payload = payload.get("error")
        if isinstance(error_payload, dict):
            code = error_payload.get("code")
            message = error_payload.get("message")
            if isinstance(code, str) and isinstance(message, str):
                return f"{code}: {message}"
            if isinstance(message, str):
                return message
            if isinstance(code, str):
                return code
        if isinstance(error_payload, str):
            return error_payload
    if result.status >= 400 and result.text_payload:
        compact = " ".join(result.text_payload.split())
        if compact.startswith("<"):
            return f"HTTP {result.status} response body omitted (non-JSON)."
        return compact[:180]
    return None


def get_issued_runtime_bot_key(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    issued_key = payload.get("issuedKey")
    if not isinstance(issued_key, dict):
        return None
    raw_key = issued_key.get("rawKey")
    if isinstance(raw_key, str) and raw_key.startswith("tnx.bot."):
        return raw_key
    return None


def get_issued_key_id(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    issued_key = payload.get("issuedKey")
    if not isinstance(issued_key, dict):
        return None
    key = issued_key.get("key")
    if not isinstance(key, dict):
        return None
    key_id = key.get("id")
    return key_id if isinstance(key_id, str) and key_id else None


def get_bot_id(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    bot = payload.get("bot")
    if not isinstance(bot, dict):
        return None
    bot_id = bot.get("id")
    return bot_id if isinstance(bot_id, str) and bot_id else None


def build_route_check(
    *,
    name: str,
    method: str,
    route: str,
    result: HttpResult,
    expected_statuses: set[int],
    default_run_id: str | None = None,
) -> RouteCheck:
    payload = result.json_payload
    status = result.status
    non401 = status != 401 and status != 0
    expected = status in expected_statuses
    request_id = get_request_id(payload)
    run_id = get_run_id(payload) or default_run_id
    ok = non401 and expected
    return RouteCheck(
        name=name,
        method=method,
        route=route,
        status=status,
        non401=non401,
        expected_status=expected,
        ok=ok,
        request_id=request_id,
        run_id=run_id,
        latency_ms=result.latency_ms,
        error=get_error_summary(result),
    )


def require_non_empty(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} is required.")
    return normalized


def bootstrap_runtime_bot_api_key(
    *,
    base_url: str,
    timeout_seconds: float,
    smoke_shared_key: str,
    partner_key: str,
    partner_secret: str,
    owner_email: str,
    bot_name: str,
) -> tuple[str | None, BootstrapResult]:
    bootstrap_path = "/api/validation/bots/registrations/partner-bootstrap"
    debug_enabled = os.getenv("VALIDATION_PROXY_SMOKE_DEBUG") == "1"
    if debug_enabled:
        print(
            "DEBUG bootstrap "
            f"base_url={base_url} route={bootstrap_path} "
            f"smoke_shared_len={len(smoke_shared_key)} "
            f"partner_key={partner_key} "
            f"partner_secret_len={len(partner_secret)} "
            f"owner_email={owner_email} bot_name={bot_name}",
            flush=True,
        )
    headers = {
        "Accept": "application/json",
        "User-Agent": "trade-nexus-validation-proxy-smoke/1.0",
        "Content-Type": "application/json",
        "X-Validation-Smoke-Key": smoke_shared_key,
        "Idempotency-Key": f"idem-validation-proxy-smoke-bootstrap-{uuid.uuid4()}",
    }
    payload = {
        "partnerKey": partner_key,
        "partnerSecret": partner_secret,
        "ownerEmail": owner_email,
        "botName": bot_name,
    }

    result = http_json_request(
        method="POST",
        url=f"{base_url}{bootstrap_path}",
        headers=headers,
        timeout_seconds=timeout_seconds,
        payload=payload,
    )
    response_payload = result.json_payload
    runtime_bot_api_key = get_issued_runtime_bot_key(response_payload)
    bootstrap_result = BootstrapResult(
        attempted=True,
        ok=result.status in {200, 201} and runtime_bot_api_key is not None,
        status=result.status,
        request_id=get_request_id(response_payload),
        bot_id=get_bot_id(response_payload),
        key_id=get_issued_key_id(response_payload),
        route=bootstrap_path,
        error=get_error_summary(result),
    )
    if debug_enabled:
        print(
            "DEBUG bootstrap-result "
            f"status={bootstrap_result.status} ok={bootstrap_result.ok} "
            f"request_id={bootstrap_result.request_id} error={bootstrap_result.error}",
            flush=True,
        )
    return runtime_bot_api_key, bootstrap_result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("VALIDATION_PROXY_SMOKE_BASE_URL", ""),
        help="Frontend base URL (for example: https://trade-nexus.lona.agency).",
    )
    parser.add_argument(
        "--smoke-shared-key",
        default=os.getenv("VALIDATION_PROXY_SMOKE_SHARED_KEY", ""),
        help="Shared proxy smoke credential key.",
    )
    parser.add_argument(
        "--runtime-bot-api-key",
        default=os.getenv("VALIDATION_PROXY_SMOKE_API_KEY", ""),
        help="Pre-provisioned runtime bot API key forwarded to backend via the web proxy.",
    )
    parser.add_argument(
        "--partner-key",
        default=os.getenv("VALIDATION_PROXY_SMOKE_PARTNER_KEY", ""),
        help="Partner bootstrap key used to mint a runtime bot key through web proxy route.",
    )
    parser.add_argument(
        "--partner-secret",
        default=os.getenv("VALIDATION_PROXY_SMOKE_PARTNER_SECRET", ""),
        help="Partner bootstrap secret used to mint a runtime bot key through web proxy route.",
    )
    parser.add_argument(
        "--owner-email",
        default=os.getenv("VALIDATION_PROXY_SMOKE_OWNER_EMAIL", DEFAULT_SMOKE_OWNER_EMAIL),
        help="Owner email used for partner bootstrap registration.",
    )
    parser.add_argument(
        "--bot-name",
        default=os.getenv("VALIDATION_PROXY_SMOKE_BOT_NAME", DEFAULT_SMOKE_BOT_NAME),
        help="Bot name used for partner bootstrap registration.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(
            os.getenv("VALIDATION_PROXY_SMOKE_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
        ),
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--strategy-id",
        default=os.getenv("VALIDATION_PROXY_SMOKE_STRATEGY_ID", "strat-001"),
        help="Synthetic strategyId for smoke create-run payload.",
    )
    parser.add_argument(
        "--provider-ref-id",
        default=os.getenv("VALIDATION_PROXY_SMOKE_PROVIDER_REF_ID", "lona-strategy-123"),
        help="Synthetic providerRefId for smoke create-run payload.",
    )
    parser.add_argument(
        "--prompt",
        default=os.getenv(
            "VALIDATION_PROXY_SMOKE_PROMPT",
            "Validation proxy credentialed smoke run via GitHub Actions.",
        ),
        help="Prompt field for create-run payload.",
    )
    parser.add_argument(
        "--requested-indicators",
        default=os.getenv("VALIDATION_PROXY_SMOKE_REQUESTED_INDICATORS", "zigzag,ema"),
        help="Comma-separated requested indicators.",
    )
    parser.add_argument(
        "--dataset-ids",
        default=os.getenv("VALIDATION_PROXY_SMOKE_DATASET_IDS", "dataset-btc-1h-2025"),
        help="Comma-separated dataset IDs.",
    )
    parser.add_argument(
        "--backtest-report-ref",
        default=os.getenv(
            "VALIDATION_PROXY_SMOKE_BACKTEST_REPORT_REF",
            "blob://validation/smoke/proxy-backtest-report.json",
        ),
        help="Backtest report reference for create-run payload.",
    )
    parser.add_argument(
        "--output-json",
        default=os.getenv(
            "VALIDATION_PROXY_SMOKE_OUTPUT_JSON",
            ".ops/artifacts/validation-proxy-smoke.json",
        ),
        help="Output path for machine-readable JSON report.",
    )
    parser.add_argument(
        "--output-tsv",
        default=os.getenv(
            "VALIDATION_PROXY_SMOKE_OUTPUT_TSV",
            ".ops/artifacts/validation-proxy-smoke.tsv",
        ),
        help="Output path for concise TSV route summary.",
    )
    parser.add_argument(
        "--output-text",
        default=os.getenv(
            "VALIDATION_PROXY_SMOKE_OUTPUT_TEXT",
            ".ops/artifacts/validation-proxy-smoke.txt",
        ),
        help="Output path for concise text summary.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = utc_now()
    checks: list[RouteCheck] = []
    fatal_error: str | None = None
    run_id: str | None = None
    artifact_type: str | None = None
    runtime_key_source = "configured_runtime_key"
    bootstrap_result = BootstrapResult(
        attempted=False,
        ok=False,
        status=0,
        request_id=None,
        bot_id=None,
        key_id=None,
        route="/api/validation/bots/registrations/partner-bootstrap",
        error=None,
    )

    normalized_base_url = normalize_base_url(args.base_url)

    try:
        base_url = require_non_empty(normalized_base_url, "VALIDATION_PROXY_SMOKE_BASE_URL")
        smoke_shared_key = require_non_empty(
            args.smoke_shared_key, "VALIDATION_PROXY_SMOKE_SHARED_KEY"
        )

        partner_key = (args.partner_key or "").strip()
        partner_secret = (args.partner_secret or "").strip()
        if partner_secret and not partner_key:
            partner_key = DEFAULT_SMOKE_PARTNER_KEY
        using_partner_bootstrap = bool(partner_key or partner_secret)

        if using_partner_bootstrap:
            if partner_key == "" or partner_secret == "":
                raise ValueError(
                    "VALIDATION_PROXY_SMOKE_PARTNER_KEY and VALIDATION_PROXY_SMOKE_PARTNER_SECRET "
                    "must both be set when partner bootstrap is enabled."
                )
            owner_email = require_non_empty(args.owner_email, "VALIDATION_PROXY_SMOKE_OWNER_EMAIL")
            bot_name = require_non_empty(args.bot_name, "VALIDATION_PROXY_SMOKE_BOT_NAME")
            runtime_bot_api_key, bootstrap_result = bootstrap_runtime_bot_api_key(
                base_url=base_url,
                timeout_seconds=args.timeout_seconds,
                smoke_shared_key=smoke_shared_key,
                partner_key=partner_key,
                partner_secret=partner_secret,
                owner_email=owner_email,
                bot_name=bot_name,
            )
            runtime_key_source = "partner_bootstrap"
            if runtime_bot_api_key is None:
                raise ValueError(
                    "Partner bootstrap did not issue a runtime bot key "
                    f"(status={bootstrap_result.status}, requestId={bootstrap_result.request_id or 'n/a'}, "
                    f"error={bootstrap_result.error or 'none'})."
                )
        else:
            runtime_bot_api_key = require_non_empty(
                args.runtime_bot_api_key,
                "VALIDATION_PROXY_SMOKE_API_KEY or partner bootstrap credentials",
            )
            if not runtime_bot_api_key.startswith("tnx.bot."):
                raise ValueError("VALIDATION_PROXY_SMOKE_API_KEY must start with 'tnx.bot.'.")

        requested_indicators = parse_csv(args.requested_indicators)
        dataset_ids = parse_csv(args.dataset_ids)
        if not requested_indicators:
            raise ValueError("VALIDATION_PROXY_SMOKE_REQUESTED_INDICATORS must not be empty.")
        if not dataset_ids:
            raise ValueError("VALIDATION_PROXY_SMOKE_DATASET_IDS must not be empty.")

        smoke_payload = {
            "strategyId": args.strategy_id,
            "providerRefId": args.provider_ref_id,
            "prompt": args.prompt,
            "requestedIndicators": requested_indicators,
            "datasetIds": dataset_ids,
            "backtestReportRef": args.backtest_report_ref,
            "policy": {
                "profile": "STANDARD",
                "blockMergeOnFail": True,
                "blockReleaseOnFail": True,
                "blockMergeOnAgentFail": True,
                "blockReleaseOnAgentFail": False,
                "requireTraderReview": False,
                "hardFailOnMissingIndicators": True,
                "failClosedOnEvidenceUnavailable": True,
            },
        }

        base_headers = {
            "Accept": "application/json",
            "User-Agent": "trade-nexus-validation-proxy-smoke/1.0",
            "X-Validation-Smoke-Key": smoke_shared_key,
            "X-API-Key": runtime_bot_api_key,
        }

        create_path = "/api/validation/runs"
        create_headers = dict(base_headers)
        create_headers["Content-Type"] = "application/json"
        create_headers["Idempotency-Key"] = f"idem-validation-proxy-smoke-{uuid.uuid4()}"

        create_result = http_json_request(
            method="POST",
            url=f"{base_url}{create_path}",
            headers=create_headers,
            timeout_seconds=args.timeout_seconds,
            payload=smoke_payload,
        )
        create_check = build_route_check(
            name="create-run",
            method="POST",
            route=create_path,
            result=create_result,
            expected_statuses={200, 201, 202},
        )
        checks.append(create_check)
        run_id = create_check.run_id

        if run_id:
            run_path = f"/api/validation/runs/{run_id}"
            get_run_result = http_json_request(
                method="GET",
                url=f"{base_url}{run_path}",
                headers=base_headers,
                timeout_seconds=args.timeout_seconds,
            )
            checks.append(
                build_route_check(
                    name="get-run",
                    method="GET",
                    route=run_path,
                    result=get_run_result,
                    expected_statuses={200},
                    default_run_id=run_id,
                )
            )

            artifact_path = f"/api/validation/runs/{run_id}/artifact"
            get_artifact_result = http_json_request(
                method="GET",
                url=f"{base_url}{artifact_path}",
                headers=base_headers,
                timeout_seconds=args.timeout_seconds,
            )
            artifact_payload = get_artifact_result.json_payload
            if isinstance(artifact_payload, dict):
                maybe_artifact_type = artifact_payload.get("artifactType")
                if isinstance(maybe_artifact_type, str):
                    artifact_type = maybe_artifact_type
            checks.append(
                build_route_check(
                    name="get-artifact",
                    method="GET",
                    route=artifact_path,
                    result=get_artifact_result,
                    expected_statuses={200},
                    default_run_id=run_id,
                )
            )
        else:
            checks.extend(
                [
                    RouteCheck(
                        name="get-run",
                        method="GET",
                        route="/api/validation/runs/{runId}",
                        status=0,
                        non401=False,
                        expected_status=False,
                        ok=False,
                        request_id=None,
                        run_id=None,
                        latency_ms=None,
                        error="Skipped because create-run did not return runId.",
                    ),
                    RouteCheck(
                        name="get-artifact",
                        method="GET",
                        route="/api/validation/runs/{runId}/artifact",
                        status=0,
                        non401=False,
                        expected_status=False,
                        ok=False,
                        request_id=None,
                        run_id=None,
                        latency_ms=None,
                        error="Skipped because create-run did not return runId.",
                    ),
                ]
            )

    except Exception as exc:  # noqa: BLE001
        fatal_error = f"{type(exc).__name__}: {exc}"

    all_non401 = all(check.non401 for check in checks) if checks else False
    all_expected_status = all(check.expected_status for check in checks) if checks else False
    status_value = "pass" if checks and all(check.ok for check in checks) and not fatal_error else "fail"

    report = {
        "schemaVersion": "validation-proxy-smoke.v2",
        "generatedAt": utc_now(),
        "startedAt": started_at,
        "status": status_value,
        "fatalError": fatal_error,
        "target": {
            "baseUrl": normalized_base_url,
            "routes": [
                "/api/validation/runs",
                "/api/validation/runs/{runId}",
                "/api/validation/runs/{runId}/artifact",
            ],
        },
        "auth": {
            "mode": "smoke_shared_key_runtime_bot_api_key",
            "smokeSharedKeyRedacted": True,
            "runtimeBotApiKeyRedacted": True,
            "runtimeBotApiKeyConfigured": bool((args.runtime_bot_api_key or "").strip()),
            "runtimeBotApiKeySource": runtime_key_source,
            "partnerBootstrapConfigured": bool((args.partner_key or "").strip() or (args.partner_secret or "").strip()),
        },
        "bootstrap": asdict(bootstrap_result),
        "result": {
            "allNon401": all_non401,
            "allExpectedStatus": all_expected_status,
            "runId": run_id,
            "artifactType": artifact_type,
            "requestIds": {
                check.name: check.request_id for check in checks if check.request_id is not None
            },
            "github": {
                "repository": os.getenv("GITHUB_REPOSITORY"),
                "runId": os.getenv("GITHUB_RUN_ID"),
                "runAttempt": os.getenv("GITHUB_RUN_ATTEMPT"),
            },
        },
        "checks": [asdict(check) for check in checks],
    }

    write_json(args.output_json, report)
    write_tsv(args.output_tsv, checks)

    summary_lines = [
        f"VALIDATION_PROXY_SMOKE status={status_value.upper()} all_non401={str(all_non401).lower()} "
        f"all_expected_status={str(all_expected_status).lower()}",
        f"RUNTIME_BOT_KEY_SOURCE {runtime_key_source}",
        (
            "BOOTSTRAP "
            f"attempted={str(bootstrap_result.attempted).lower()} "
            f"ok={str(bootstrap_result.ok).lower()} "
            f"status={bootstrap_result.status} "
            f"request_id={bootstrap_result.request_id or 'n/a'} "
            f"bot_id={bootstrap_result.bot_id or 'n/a'} "
            f"key_id={bootstrap_result.key_id or 'n/a'}"
        ),
        f"RUN_ID {run_id or 'n/a'}",
        "ROUTE_SUMMARY",
    ]
    for check in checks:
        summary_lines.append(
            " ".join(
                [
                    f"- name={check.name}",
                    f"method={check.method}",
                    f"route={check.route}",
                    f"status={check.status}",
                    f"request_id={check.request_id or 'n/a'}",
                    f"latency_ms={check.latency_ms if check.latency_ms is not None else 'n/a'}",
                    f"ok={str(check.ok).lower()}",
                ]
            )
        )
    if bootstrap_result.error:
        summary_lines.append(f"BOOTSTRAP_ERROR {bootstrap_result.error}")
    if fatal_error:
        summary_lines.append(f"FATAL_ERROR {fatal_error}")
    summary_lines.append(f"ARTIFACT_JSON {args.output_json}")
    summary_lines.append(f"ARTIFACT_TSV {args.output_tsv}")
    write_text(args.output_text, "\n".join(summary_lines) + "\n")

    print(summary_lines[0])
    print(f"Smoke report: {args.output_json}")
    print(f"Smoke summary: {args.output_text}")
    return 0 if status_value == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
