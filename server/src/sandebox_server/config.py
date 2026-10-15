from __future__ import annotations

import os

from core.config import SandboxConfig
from pydantic import BaseModel, Field


class ServerSettings(BaseModel):
    host: str = Field(
        default_factory=lambda: os.environ.get("SANDEBOX_SERVER_HOST", "0.0.0.0")
    )
    port: int = Field(
        default_factory=lambda: int(os.environ.get("SANDEBOX_SERVER_PORT", "8000"))
    )
    api_keys: list[str] = Field(
        default_factory=lambda: [
            k.strip()
            for k in os.environ.get("SANDEBOX_API_KEYS", "sk-sandebox-dev-key").split(
                ","
            )
            if k.strip()
        ]
    )
    admin_token: str = Field(
        default_factory=lambda: os.environ.get(
            "SANDEBOX_ADMIN_TOKEN", "admin-secret-token"
        )
    )
    sandbox_config: SandboxConfig = Field(default_factory=SandboxConfig.from_env)


_settings: ServerSettings | None = None


def get_server_settings() -> ServerSettings:
    global _settings
    if _settings is None:
        _settings = ServerSettings()
    return _settings
