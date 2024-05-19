import dataclasses, json, typing as t


def json_stringify(o):
    class EnhancedJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if dataclasses.is_dataclass(o):
                return dataclasses.asdict(o)
            return super().default(o)

    return EnhancedJSONEncoder().encode(o)


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
