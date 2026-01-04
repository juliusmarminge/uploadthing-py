"""
Configuration module for UploadThing SDK.

Handles token parsing and provides configuration dataclasses.
"""

import base64
import json
import os
from dataclasses import dataclass, field


class ConfigError(Exception):
    """Raised when there's an error with the SDK configuration."""

    pass


@dataclass
class UTConfig:
    """UploadThing configuration."""

    api_key: str
    app_id: str
    api_url: str = "https://api.uploadthing.com"
    ingest_url: str = "https://ingest.uploadthing.com"
    ufs_host: str = "ufs.sh"


def parse_token(token: str) -> tuple[str, str, list[str]]:
    """
    Parse the UPLOADTHING_TOKEN into (api_key, app_id, regions).

    The token is a Base64-encoded JSON object with the structure:
    {
        "apiKey": "sk_live_...",
        "appId": "your-app-uuid",
        "regions": ["sea1"]
    }

    Args:
        token: The Base64-encoded UPLOADTHING_TOKEN

    Returns:
        A tuple of (api_key, app_id, regions)

    Raises:
        ConfigError: If the token is invalid or missing required fields
    """
    try:
        decoded = base64.b64decode(token)
        data = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as e:
        raise ConfigError(f"Invalid UPLOADTHING_TOKEN format: {e}") from e

    api_key = data.get("apiKey")
    app_id = data.get("appId")
    regions = data.get("regions", [])

    if not api_key:
        raise ConfigError("UPLOADTHING_TOKEN is missing 'apiKey' field")
    if not app_id:
        raise ConfigError("UPLOADTHING_TOKEN is missing 'appId' field")

    return api_key, app_id, regions


def get_config_from_env(
    token: str | None = None,
    api_url: str | None = None,
    ingest_url: str | None = None,
    ufs_host: str | None = None,
) -> UTConfig:
    """
    Get UTConfig from environment variables or provided values.

    Args:
        token: Optional token override. If not provided, reads from UPLOADTHING_TOKEN env var.
        api_url: Optional API URL override.
        ingest_url: Optional ingest URL override.
        ufs_host: Optional UFS host override.

    Returns:
        UTConfig with parsed values

    Raises:
        ConfigError: If token is missing or invalid
    """
    token = token or os.environ.get("UPLOADTHING_TOKEN")
    if not token:
        raise ConfigError(
            "UPLOADTHING_TOKEN environment variable is not set. "
            "Please set it or pass the token directly."
        )

    api_key, app_id, regions = parse_token(token)

    # Build region-specific ingest URL if regions are provided
    default_ingest_url = "https://ingest.uploadthing.com"
    if regions and len(regions) > 0:
        # Use first region for ingest URL (e.g., sea1 -> https://sea1.ingest.uploadthing.com)
        default_ingest_url = f"https://{regions[0]}.ingest.uploadthing.com"

    return UTConfig(
        api_key=api_key,
        app_id=app_id,
        api_url=api_url or "https://api.uploadthing.com",
        ingest_url=ingest_url or default_ingest_url,
        ufs_host=ufs_host or "ufs.sh",
    )
