from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from datetime import datetime, timezone
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list

router = APIRouter(prefix="/actividad", tags=["Actividad"])


class CreateActividadDto(BaseModel):
    tipo: str
    descripcion: str
    usuario: Optional[str] = ""
    entidad: Optional[str] = ""
    entidadId: Optional[str] = ""
    metadata: Optional[dict] = None


@router.get("/recientes")
async def find_recientes(current_user: dict = Depends(get_current_user)):
    col = get_collection("actividad")
    docs = await col.find({}).sort("createdAt", -1).limit(20).to_list(None)
    return serialize_list(docs)


@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("actividad")
    docs = await col.find({}).sort("createdAt", -1).to_list(None)
    return serialize_list(docs)


@router.post("")
async def create(dto: CreateActividadDto, current_user: dict = Depends(get_current_user)):
    col = get_collection("actividad")
    data = dto.model_dump()
    data["createdAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


@router.delete("/limpiar")
async def limpiar(current_user: dict = Depends(require_roles("super_admin"))):
    col = get_collection("actividad")
    result = await col.delete_many({})
    return {"deleted": result.deleted_count}


@router.delete(
    "/{id}",
    responses={400: {"description": "ID inválido"}, 404: {"description": "Actividad no encontrada"}},
)
async def delete(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("actividad")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return {"message": "Actividad eliminada"}

