import dataclasses
import json
import typing as t
import hmac
from hashlib import sha256


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
