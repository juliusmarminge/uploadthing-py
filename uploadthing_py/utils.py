import dataclasses
import json
import math
import typing as t
import hmac
from hashlib import sha256
from sqids import Sqids, constants
import time
import urllib.parse


def json_stringify(o):
    class EnhancedJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if dataclasses.is_dataclass(o):
                return dataclasses.asdict(o)
            return super().default(o)

    return json.dumps(o, cls=EnhancedJSONEncoder, separators=(",", ":"))


def json_parse(s):
    return json.loads(s)


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


def shuffle(string, seed):
    chars = list(string)
    seed_num = hash_string(seed)

    for i in range(len(chars)):
        j = int(math.fmod(math.fmod(seed_num, i + 1) + i, len(chars)))
        chars[i], chars[j] = chars[j], chars[i]

    return "".join(chars)


def hash_string(s):
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


def generate_key(file, app_id: str) -> str:
    alphabet = shuffle(constants.DEFAULT_ALPHABET, app_id)

    file_seed = Sqids(alphabet, min_length=36).encode(
        [abs(hash_string(f"{json_stringify(file)}{time.time()}"))]
    )
    encoded_app_id = Sqids(alphabet, min_length=12).encode([abs(hash_string(app_id))])
    return encoded_app_id + file_seed


def generate_signed_url(
    url: str, key: str, expires_in: int = None, data: dict = None
) -> str:
    query_string = urllib.parse.urlencode(
        {"expires": (int(time.time()) + (expires_in or 3600)) * 1000, **data}
    )

    signed_url = f"{url}?{query_string}"
    signature = sign_payload(signed_url, key)
    return f"{signed_url}&{urllib.parse.urlencode({'signature': signature})}"
