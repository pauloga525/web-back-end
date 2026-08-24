from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from datetime import datetime, timezone
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


class CreateNotificacionDto(BaseModel):
    usuario: Optional[str] = ""
    titulo: str
    descripcion: Optional[str] = ""


@router.get("/unread-count")
async def unread_count(current_user: dict = Depends(get_current_user)):
    col = get_collection("notificaciones")
    user_id = current_user.get("id")
    count = await col.count_documents({"$or": [{"usuario": user_id}, {"usuario": ""}], "leido": False})
    return {"count": count}


@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("notificaciones")
    user_id = current_user.get("id")
    docs = await col.find({"$or": [{"usuario": user_id}, {"usuario": ""}]}).sort("createdAt", -1).to_list(None)
    return serialize_list(docs)


@router.post("")
async def create(dto: CreateNotificacionDto, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("notificaciones")
    data = dto.model_dump()
    data["leido"] = False
    data["createdAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


@router.patch("/{id}/leer")
async def marcar_leida(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("notificaciones")
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": {"leido": True}})
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    return serialize_doc(doc)


@router.patch("/leer-todas")
async def marcar_todas_leidas(current_user: dict = Depends(get_current_user)):
    col = get_collection("notificaciones")
    user_id = current_user.get("id")
    await col.update_many(
        {"$or": [{"usuario": user_id}, {"usuario": ""}]},
        {"$set": {"leido": True}},
    )
    return {"message": "Todas marcadas como leídas"}


@router.delete("/{id}")
async def delete(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("notificaciones")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    return {"message": "Notificación eliminada"}

