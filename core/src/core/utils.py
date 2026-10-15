import re

from .contract import SessionIdentity


def _sanitize_name(raw: str, prefix: str) -> str:
    # Lowercase and replace non-alphanumeric with -
    name = re.sub(r"[^a-z0-9-]", "-", raw.lower())
    # Collapse consecutive dashes
    name = re.sub(r"-+", "-", name).strip("-")
    # Truncate to 63 chars (DNS-1123 max length)
    full_name = f"{prefix}-{name}"
    if len(full_name) > 63:
        # Keep the prefix and truncate the name
        max_name_len = 63 - len(prefix) - 1
        full_name = f"{prefix}-{name[:max_name_len].strip('-')}"
    return full_name


def get_pod_name(identity: SessionIdentity, prefix: str = "rb-sbx") -> str:
    return _sanitize_name(identity.stable_key, prefix)


def get_service_name(
    identity: SessionIdentity, port: int, prefix: str = "rb-srv"
) -> str:
    return _sanitize_name(f"{identity.stable_key}-{port}", prefix)
