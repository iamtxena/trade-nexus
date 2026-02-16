"""Contract tests for startup-safe environment parsing in router_v1."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from src.platform_api import router_v1


def test_float_env_uses_default_when_market_context_ttl_invalid(monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_MARKET_CONTEXT_CACHE_TTL_SECONDS", "abc")
    parsed = router_v1._float_env("PLATFORM_MARKET_CONTEXT_CACHE_TTL_SECONDS", 120.0, minimum=0.0)
    assert parsed == 120.0


def test_float_env_clamps_negative_market_context_ttl(monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_MARKET_CONTEXT_CACHE_TTL_SECONDS", "-5")
    parsed = router_v1._float_env("PLATFORM_MARKET_CONTEXT_CACHE_TTL_SECONDS", 120.0, minimum=0.0)
    assert parsed == 0.0


def test_float_env_uses_default_live_engine_timeout_when_invalid(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_ENGINE_TIMEOUT_SECONDS", "oops")
    parsed = router_v1._float_env("LIVE_ENGINE_TIMEOUT_SECONDS", 8.0, minimum=0.0)
    assert parsed == 8.0


def test_float_env_uses_default_trader_data_timeout_when_invalid(monkeypatch) -> None:
    monkeypatch.setenv("TRADER_DATA_TIMEOUT_SECONDS", "oops")
    parsed = router_v1._float_env("TRADER_DATA_TIMEOUT_SECONDS", 8.0, minimum=0.0)
    assert parsed == 8.0


def test_router_import_survives_invalid_market_context_ttl() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    backend_path = str(repo_root / "backend")
    env["PYTHONPATH"] = f"{backend_path}:{existing_pythonpath}" if existing_pythonpath else backend_path
    env["PLATFORM_MARKET_CONTEXT_CACHE_TTL_SECONDS"] = "abc"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from src.platform_api import router_v1; print(router_v1._market_context_cache_ttl_seconds)",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "120.0"
