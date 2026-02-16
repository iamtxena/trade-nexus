"""Contract tests for startup-safe environment parsing in router_v1."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

_ROUTER_MODULE = "src.platform_api.router_v1"


def _reload_router_module() -> ModuleType:
    sys.modules.pop(_ROUTER_MODULE, None)
    return importlib.import_module(_ROUTER_MODULE)


def _restore_router_module(original_module: ModuleType | None) -> None:
    sys.modules.pop(_ROUTER_MODULE, None)
    if original_module is not None:
        sys.modules[_ROUTER_MODULE] = original_module


def test_router_market_context_ttl_uses_default_when_env_invalid(monkeypatch) -> None:
    original_module = sys.modules.get(_ROUTER_MODULE)
    monkeypatch.setenv("PLATFORM_MARKET_CONTEXT_CACHE_TTL_SECONDS", "abc")
    try:
        router_module = _reload_router_module()
        assert router_module._market_context_cache_ttl_seconds == 120.0
    finally:
        _restore_router_module(original_module)


def test_router_market_context_ttl_clamps_negative_values(monkeypatch) -> None:
    original_module = sys.modules.get(_ROUTER_MODULE)
    monkeypatch.setenv("PLATFORM_MARKET_CONTEXT_CACHE_TTL_SECONDS", "-5")
    try:
        router_module = _reload_router_module()
        assert router_module._market_context_cache_ttl_seconds == 0.0
    finally:
        _restore_router_module(original_module)


def test_router_uses_default_live_engine_timeout_when_env_invalid(monkeypatch) -> None:
    original_module = sys.modules.get(_ROUTER_MODULE)
    monkeypatch.setenv("PLATFORM_USE_REMOTE_EXECUTION", "true")
    monkeypatch.setenv("LIVE_ENGINE_TIMEOUT_SECONDS", "oops")
    try:
        router_module = _reload_router_module()
        assert router_module._execution_adapter._timeout_seconds == 8.0
    finally:
        _restore_router_module(original_module)


def test_router_uses_default_trader_data_timeout_when_env_invalid(monkeypatch) -> None:
    original_module = sys.modules.get(_ROUTER_MODULE)
    monkeypatch.setenv("PLATFORM_USE_TRADER_DATA_REMOTE", "true")
    monkeypatch.setenv("TRADER_DATA_TIMEOUT_SECONDS", "oops")
    try:
        router_module = _reload_router_module()
        assert router_module._base_data_knowledge_adapter._timeout_seconds == 8.0
    finally:
        _restore_router_module(original_module)
