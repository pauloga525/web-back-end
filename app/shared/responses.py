from bson import ObjectId
from datetime import datetime
from typing import Any

_PROTECTED = {"_id", "createdAt"}


def serialize_doc(doc: dict) -> dict:
    if doc is None:
        return None
    result = {}
    for k, v in doc.items():
        if k == "_id":
            result["_id"] = str(v)
        elif isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, list):
            result[k] = [serialize_doc(i) if isinstance(i, dict) else (str(i) if isinstance(i, ObjectId) else i) for i in v]
        elif isinstance(v, dict):
            result[k] = serialize_doc(v)
        else:
            result[k] = v
    return result


def serialize_list(docs: list) -> list:
    return [serialize_doc(d) for d in docs]


def clean_update(data: dict) -> dict:
    """Elimina campos inmutables antes de un $set en MongoDB."""
    return {k: v for k, v in data.items() if k not in _PROTECTED}
