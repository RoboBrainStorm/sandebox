from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from .config import ServerSettings, get_server_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_auth = HTTPBearer(auto_error=False)

# In-memory dynamic key store extending initial config keys
_registered_keys: set[str] = set()


def get_active_keys(settings: ServerSettings) -> set[str]:
    return set(settings.api_keys).union(_registered_keys)


def issue_api_key(prefix: str = "sk-sbx") -> str:
    key = f"{prefix}-{secrets.token_urlsafe(24)}"
    _registered_keys.add(key)
    return key


async def verify_api_key(
    header_key: Annotated[str | None, Security(_api_key_header)] = None,
    bearer: Annotated[
        HTTPAuthorizationCredentials | None, Security(_bearer_auth)
    ] = None,
    settings: Annotated[ServerSettings, Depends(get_server_settings)] = None,
) -> str:
    provided_key: str | None = header_key or (bearer.credentials if bearer else None)
    if not provided_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key in 'X-API-Key' or 'Authorization: Bearer' header",
        )

    valid_keys = get_active_keys(settings)
    if provided_key not in valid_keys and provided_key != settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

    return provided_key
