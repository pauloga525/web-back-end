from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from bson import ObjectId
from datetime import datetime, timezone
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list, clean_update
from app.modules.websocket.manager import notify_created, notify_updated, notify_deleted

router = APIRouter(prefix="/autoridades", tags=["Autoridades"])

ID_INVALIDO = "ID inválido"
AUTORIDAD_NO_ENCONTRADA = "Autoridad no encontrada"


class UpdateAutoridadDto(BaseModel):
    model_config = ConfigDict(extra='ignore')
    name: Optional[str] = None
    title: Optional[str] = None
    categoryLabel: Optional[str] = None
    image: Optional[str] = None
    email: Optional[str] = None
    specialization: Optional[str] = None
    linkedin: Optional[str] = None
    fullBio: Optional[str] = None
    ubicacion: Optional[str] = None
    horario: Optional[str] = None
    telefono: Optional[str] = None
    orden: Optional[int] = None
    publicada: Optional[bool] = None


class CreateAutoridadDto(BaseModel):
    name: str
    title: Optional[str] = ""
    categoryLabel: Optional[str] = ""
    image: Optional[str] = ""
    email: Optional[str] = ""
    specialization: Optional[str] = ""
    linkedin: Optional[str] = ""
    fullBio: Optional[str] = ""
    ubicacion: Optional[str] = ""
    horario: Optional[str] = ""
    telefono: Optional[str] = ""
    orden: Optional[int] = 0
    publicada: Optional[bool] = True


# ─── Rutas públicas ────────────────────────────────────────────────────────────

@router.get("/publicas")
async def find_publicas():
    col = get_collection("autoridades")
    docs = await col.find({"publicada": True}).sort("orden", 1).to_list(None)
    return serialize_list(docs)


@router.get(
    "/publica/{id}",
    responses={400: {"description": ID_INVALIDO}, 404: {"description": AUTORIDAD_NO_ENCONTRADA}},
)
async def find_publica(id: str):
    col = get_collection("autoridades")
    try:
        doc = await col.find_one({"_id": ObjectId(id), "publicada": True})
    except Exception:
        raise HTTPException(status_code=400, detail=ID_INVALIDO)
    if not doc:
        raise HTTPException(status_code=404, detail=AUTORIDAD_NO_ENCONTRADA)
    return serialize_doc(doc)


# ─── Rutas protegidas ─────────────────────────────────────────────────────────

@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("autoridades")
    docs = await col.find({}).sort("orden", 1).to_list(None)
    return serialize_list(docs)


@router.get(
    "/{id}",
    responses={400: {"description": ID_INVALIDO}, 404: {"description": AUTORIDAD_NO_ENCONTRADA}},
)
async def find_one(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("autoridades")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail=ID_INVALIDO)
    if not doc:
        raise HTTPException(status_code=404, detail=AUTORIDAD_NO_ENCONTRADA)
    return serialize_doc(doc)


@router.post("")
async def create(dto: CreateAutoridadDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("autoridades")
    data = dto.model_dump()
    data["createdAt"] = datetime.now(timezone.utc)
    data["updatedAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    try:
        await notify_created("autoridad", out)
    except Exception:
        pass
    return out


@router.put(
    "/{id}",
    responses={400: {"description": ID_INVALIDO}, 404: {"description": AUTORIDAD_NO_ENCONTRADA}},
)
async def update(id: str, dto: UpdateAutoridadDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("autoridades")
    data = clean_update(dto.model_dump(exclude_none=True))
    data["updatedAt"] = datetime.now(timezone.utc)
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": data})
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail=ID_INVALIDO)
    if not doc:
        raise HTTPException(status_code=404, detail=AUTORIDAD_NO_ENCONTRADA)
    out = serialize_doc(doc)
    try:
        await notify_updated("autoridad", out)
    except Exception:
        pass
    return out


@router.delete(
    "/{id}",
    responses={400: {"description": ID_INVALIDO}, 404: {"description": AUTORIDAD_NO_ENCONTRADA}},
)
async def delete(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("autoridades")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail=ID_INVALIDO)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=AUTORIDAD_NO_ENCONTRADA)
    try:
        await notify_deleted("autoridad", id)
    except Exception:
        pass
    return {"message": "Autoridad eliminada"}

