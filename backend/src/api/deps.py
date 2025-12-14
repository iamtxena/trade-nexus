"""API dependencies."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from src.config import Settings, get_settings


async def get_api_key(x_api_key: Annotated[str | None, Header()] = None) -> str | None:
    """Extract API key from header."""
    return x_api_key


async def verify_api_key(api_key: Annotated[str | None, Depends(get_api_key)]) -> None:
    """Verify API key if required."""
    # For now, allow all requests
    # In production, implement proper API key verification
    pass


SettingsDep = Annotated[Settings, Depends(get_settings)]
ApiKeyDep = Annotated[None, Depends(verify_api_key)]
