from bson import ObjectId
from datetime import datetime
from typing import Any, Optional

_PROTECTED = {"_id", "createdAt"}


def _serialize_value(v: Any) -> Any:
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, list):
        return [_serialize_value(i) for i in v]
    if isinstance(v, dict):
        return serialize_doc(v)
    return v


def serialize_doc(doc: Optional[dict]) -> Optional[dict]:
    if doc is None:
        return None
    result = {}
    for k, v in doc.items():
        result[k] = str(v) if k == "_id" else _serialize_value(v)
    return result


def serialize_list(docs: list) -> list:
    return [serialize_doc(d) for d in docs]


def clean_update(data: dict) -> dict:
    """Elimina campos inmutables antes de un $set en MongoDB."""
    return {k: v for k, v in data.items() if k not in _PROTECTED}
