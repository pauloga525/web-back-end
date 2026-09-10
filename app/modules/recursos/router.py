from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from bson import ObjectId
from datetime import datetime, timezone
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list, clean_update
from app.modules.websocket.manager import notify_created, notify_updated, notify_deleted

router = APIRouter(prefix="/recursos", tags=["Recursos"])

ID_INVALIDO = "ID inválido"
RECURSO_NO_ENCONTRADO = "Recurso no encontrado"


class UpdateRecursoDto(BaseModel):
    model_config = ConfigDict(extra='ignore')
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    tipo: Optional[str] = None
    url: Optional[str] = None
    imagen: Optional[str] = None
    categoria: Optional[str] = None
    tags: Optional[List[str]] = None
    publicado: Optional[bool] = None
    orden: Optional[int] = None


class CreateRecursoDto(BaseModel):
    titulo: str
    descripcion: Optional[str] = ""
    tipo: Optional[str] = ""
    url: Optional[str] = ""
    imagen: Optional[str] = ""
    categoria: Optional[str] = ""
    tags: Optional[List[str]] = []
    publicado: Optional[bool] = False
    orden: Optional[int] = 0


@router.get("/publicos")
async def find_publicos():
    col = get_collection("recursos")
    docs = await col.find({"publicado": True}).sort("orden", 1).to_list(None)
    return serialize_list(docs)


@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("recursos")
    docs = await col.find({}).sort("orden", 1).to_list(None)
    return serialize_list(docs)


@router.get(
    "/{id}",
    responses={400: {"description": ID_INVALIDO}, 404: {"description": RECURSO_NO_ENCONTRADO}},
)
async def find_one(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("recursos")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail=ID_INVALIDO)
    if not doc:
        raise HTTPException(status_code=404, detail=RECURSO_NO_ENCONTRADO)
    return serialize_doc(doc)


@router.post("")
async def create(dto: CreateRecursoDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("recursos")
    data = dto.model_dump()
    data["createdAt"] = datetime.now(timezone.utc)
    data["updatedAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    try:
        await notify_created("recurso", out)
    except Exception:
        pass
    return out


@router.put(
    "/{id}",
    responses={400: {"description": ID_INVALIDO}, 404: {"description": RECURSO_NO_ENCONTRADO}},
)
async def update(id: str, dto: UpdateRecursoDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("recursos")
    data = clean_update(dto.model_dump(exclude_none=True))
    data["updatedAt"] = datetime.now(timezone.utc)
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": data})
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail=ID_INVALIDO)
    if not doc:
        raise HTTPException(status_code=404, detail=RECURSO_NO_ENCONTRADO)
    out = serialize_doc(doc)
    try:
        await notify_updated("recurso", out)
    except Exception:
        pass
    return out


@router.delete(
    "/{id}",
    responses={400: {"description": ID_INVALIDO}, 404: {"description": RECURSO_NO_ENCONTRADO}},
)
async def delete(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("recursos")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail=ID_INVALIDO)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=RECURSO_NO_ENCONTRADO)
    try:
        await notify_deleted("recurso", id)
    except Exception:
        pass
    return {"message": "Recurso eliminado"}

