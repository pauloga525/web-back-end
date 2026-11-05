from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


class CreateNotificacionDto(BaseModel):
    usuario: Optional[str] = ""
    titulo: str
    descripcion: Optional[str] = ""


def _visibles(user_id: str) -> dict:
    """Notificaciones dirigidas al usuario (o a todos), de otros autores y no eliminadas por él."""
    return {
        "$and": [
            {"$or": [{"usuario": user_id}, {"usuario": ""}]},
            {"autorId": {"$ne": user_id}},
            {"eliminadoPor": {"$ne": user_id}},
        ]
    }


def _para_usuario(doc: dict, user_id: str) -> dict:
    out = serialize_doc(doc)
    out["leido"] = user_id in doc.get("leidoPor", []) or bool(doc.get("leido") and doc.get("usuario") == user_id)
    out.pop("leidoPor", None)
    out.pop("eliminadoPor", None)
    return out


@router.get("/unread-count")
async def unread_count(current_user: dict = Depends(get_current_user)):
    col = get_collection("notificaciones")
    user_id = current_user.get("id")
    query = _visibles(user_id)
    query["$and"].append({"leidoPor": {"$ne": user_id}})
    query["$and"].append({"leido": {"$ne": True}})
    return {"count": await col.count_documents(query)}


@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("notificaciones")
    user_id = current_user.get("id")
    # Purga: las notificaciones con más de 60 días ya no son útiles
    await col.delete_many({"createdAt": {"$lt": datetime.now(timezone.utc) - timedelta(days=60)}})
    docs = await col.find(_visibles(user_id)).sort("createdAt", -1).limit(200).to_list(None)
    return [_para_usuario(d, user_id) for d in docs]


@router.post("")
async def create(dto: CreateNotificacionDto, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("notificaciones")
    data = dto.model_dump()
    data["leidoPor"] = []
    data["eliminadoPor"] = []
    data["autorId"] = current_user.get("id")
    data["createdAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    return _para_usuario(doc, current_user.get("id"))


def _assert_owns_notificacion(doc: dict, user_id: str) -> None:
    """Una notificación pertenece al usuario si es suya o es broadcast (usuario "")."""
    if doc.get("usuario") not in ("", user_id):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta notificación")


@router.patch("/{id}/leer")
async def marcar_leida(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("notificaciones")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    _assert_owns_notificacion(doc, current_user.get("id"))

    user_id = current_user.get("id")
    await col.update_one({"_id": ObjectId(id)}, {"$addToSet": {"leidoPor": user_id}})
    doc = await col.find_one({"_id": ObjectId(id)})
    return _para_usuario(doc, user_id)


@router.patch("/leer-todas")
async def marcar_todas_leidas(current_user: dict = Depends(get_current_user)):
    col = get_collection("notificaciones")
    user_id = current_user.get("id")
    await col.update_many(_visibles(user_id), {"$addToSet": {"leidoPor": user_id}})
    return {"message": "Todas marcadas como leídas"}


@router.delete("/{id}")
async def delete(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("notificaciones")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    _assert_owns_notificacion(doc, current_user.get("id"))

    # Es de todos: solo se oculta para quien la elimina
    await col.update_one({"_id": ObjectId(id)}, {"$addToSet": {"eliminadoPor": current_user.get("id")}})
    return {"message": "Notificación eliminada"}

