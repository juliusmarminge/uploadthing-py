import dataclasses
import json
import typing as t
import hmac
import time
import base64
import uuid
from hashlib import sha256
from urllib.parse import urlencode


def json_stringify(o):
    class EnhancedJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if dataclasses.is_dataclass(o):
                return dataclasses.asdict(o)
            return super().default(o)

    return json.dumps(o, cls=EnhancedJSONEncoder, separators=(",", ":"))


def del_none(d: t.Any):
    """
    Delete keys with the value ``None`` in a dictionary, recursively, in-place.
    Useful to avoid inconsistencies with null, undefined, or missing values when JSON encoding.
    """
    for key, value in list(d.items()):
        if value is None:
            del d[key]
        elif isinstance(value, dict):
            del_none(value)
    return d  # For convenience


signature_prefix = "hmac-sha256="


def sign_payload(payload: str, secret: str) -> str:
    signature = hmac.new(secret.encode(), payload.encode(), sha256).hexdigest()
    return f"{signature_prefix}{signature}"


def verify_signature(payload: str, signature: str, secret: str) -> bool:
    if not signature or not signature.startswith(signature_prefix):
        return False

    sig = signature[len(signature_prefix) :]
    if not sig:
        return False

    hmac_obj = hmac.new(secret.encode(), payload.encode(), sha256).hexdigest()
    return hmac.compare_digest(hmac_obj, sig)


def djb2(s: str) -> int:
    """
    DJB2 hash function matching Effect's Hash.string algorithm.
    
    This is the exact implementation from UploadThing docs.
    """
    h = 5381
    for char in reversed(s):
        h = (h * 33) ^ ord(char)
        # 32-bit integer overflow
        h &= 0xFFFFFFFF
    h = (h & 0xBFFFFFFF) | ((h >> 1) & 0x40000000)
    # Convert to signed 32-bit integer
    if h >= 0x80000000:
        h -= 0x100000000
    return h


def _shuffle_alphabet(string: str, seed: str) -> str:
    """Shuffle alphabet based on seed string (matching TypeScript SDK's shuffle function)."""
    import math
    chars = list(string)
    seed_num = djb2(seed)
    for i in range(len(chars)):
        j = int(math.fmod(math.fmod(seed_num, i + 1) + i, len(chars)))
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def generate_key(file_name: str, file_size: int, file_type: str, app_id: str, last_modified: int | None = None) -> str:
    """
    Generate a unique file key for uploads matching TypeScript SDK's algorithm.

    Uses SQIDs with shuffled alphabet to encode the app ID, then
    appends a unique base64 file seed.

    Args:
        file_name: The original filename
        file_size: The file size in bytes
        file_type: The MIME type of the file
        app_id: The UploadThing app ID
        last_modified: Optional last modified timestamp

    Returns:
        A unique file key that the UploadThing server will accept
    """
    from sqids import Sqids
    from sqids.constants import DEFAULT_ALPHABET
    import base64
    import time
    import os
    
    # Shuffle alphabet based on app_id (matching UploadThing docs reference)
    alphabet = _shuffle_alphabet(DEFAULT_ALPHABET, app_id)
    
    # Encode the app ID hash using SQIDs
    encoded_app_id = Sqids(alphabet, min_length=12).encode([abs(djb2(app_id))])
    
    # Generate a unique file seed (base64 encoded for URL safety)
    # Include file properties and randomness for uniqueness
    seed_data = f"{file_name}:{file_size}:{file_type}:{last_modified}:{time.time_ns()}:{os.urandom(8).hex()}"
    file_seed = base64.urlsafe_b64encode(seed_data.encode()).decode().rstrip("=")
    
    # Key is: encoded_app_id + file_seed
    return encoded_app_id + file_seed


def generate_signed_url(
    base_url: str,
    api_key: str,
    data: dict[str, t.Any] | None = None,
    ttl_seconds: int = 300,
) -> str:
    """
    Generate a presigned URL with HMAC-SHA256 signature.

    This matches the TypeScript SDK's signing approach:
    1. Append expires timestamp as query param
    2. Append all data fields as individual query params
    3. Sign the entire URL with HMAC-SHA256
    4. Append signature as final query param

    Args:
        base_url: The base URL to sign (e.g., ingest URL or file URL)
        api_key: The UploadThing API key for signing
        data: Optional additional data to include as query params
        ttl_seconds: Time-to-live in seconds (default: 5 minutes)

    Returns:
        The full signed URL with query parameters
    """
    from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode as url_encode
    
    # Parse the base URL
    parsed = urlparse(base_url)
    
    # Start with existing query params (if any)
    params = parse_qsl(parsed.query)
    
    # Add expires timestamp (in milliseconds, matching TS SDK)
    expires_ms = int((time.time() + ttl_seconds) * 1000)
    params.append(("expires", str(expires_ms)))
    
    # Add all data fields as individual query params
    if data:
        for key, value in data.items():
            if value is not None:
                # URL encode the value
                params.append((key, str(value)))
    
    # Build the URL without signature for signing
    url_without_sig = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        url_encode(params),
        parsed.fragment,
    ))
    
    # Sign the entire URL with HMAC-SHA256
    signature = hmac.new(
        api_key.encode(),
        url_without_sig.encode(),
        sha256,
    ).hexdigest()
    
    # Add signature as final query param (with prefix matching TS SDK)
    params.append(("signature", f"hmac-sha256={signature}"))
    
    # Build the final URL
    final_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        url_encode(params),
        parsed.fragment,
    ))
    
    return final_url

