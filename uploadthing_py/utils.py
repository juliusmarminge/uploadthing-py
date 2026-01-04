import dataclasses
import json
import typing as t
import hmac
import time
import base64
import uuid
import os
from hashlib import sha256
from urllib.parse import urlencode
from sqids import Sqids
from sqids.constants import DEFAULT_ALPHABET

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
    
    Matches the TypeScript SDK's simple approach:
    1. Add expires param to URL
    2. Sign the entire URL string with HMAC-SHA256
    3. Append signature param
    """
    from urllib.parse import urlencode
    
    # Build query params
    params = {"expires": str(int((time.time() + ttl_seconds) * 1000))}
    if data:
        params.update({k: str(v) for k, v in data.items() if v is not None})
    
    # Build URL with params (before signature)
    separator = "&" if "?" in base_url else "?"
    url_to_sign = f"{base_url}{separator}{urlencode(params)}"
    
    # Sign the URL
    signature = hmac.new(api_key.encode(), url_to_sign.encode(), sha256).hexdigest()
    
    
    # Return URL with signature appended
    return f"{url_to_sign}&signature=hmac-sha256={signature}"

