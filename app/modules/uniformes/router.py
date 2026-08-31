from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from bson import ObjectId
from datetime import datetime, timezone
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list, clean_update
from app.modules.websocket.manager import notify_created, notify_updated, notify_deleted

router = APIRouter(prefix="/uniformes", tags=["Uniformes"])


class UniformeImagenDto(BaseModel):
    url: Optional[str] = ""
    alt: Optional[str] = ""


class CreateUniformeDto(BaseModel):
    name: str
    category: Optional[str] = ""
    description: Optional[str] = ""
    price: Optional[str] = ""
    availability: Optional[str] = "En stock"
    images: Optional[List[UniformeImagenDto]] = []
    publicado: Optional[bool] = True
    orden: Optional[int] = 0


class UpdateUniformeDto(BaseModel):
    model_config = ConfigDict(extra='ignore')
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    price: Optional[str] = None
    availability: Optional[str] = None
    images: Optional[List[UniformeImagenDto]] = None
    publicado: Optional[bool] = None
    orden: Optional[int] = None


# ─── Rutas públicas ────────────────────────────────────────────────────────────

@router.get("/publicos")
async def find_publicos():
    col = get_collection("uniformes")
    docs = await col.find({"publicado": True}).sort("orden", 1).to_list(None)
    return serialize_list(docs)


# ─── Rutas protegidas ─────────────────────────────────────────────────────────

@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("uniformes")
    docs = await col.find({}).sort("orden", 1).to_list(None)
    return serialize_list(docs)


@router.get("/{id}")
async def find_one(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("uniformes")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Uniforme no encontrado")
    return serialize_doc(doc)


@router.post("")
async def create(dto: CreateUniformeDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("uniformes")
    data = dto.model_dump()
    data["createdAt"] = datetime.now(timezone.utc)
    data["updatedAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    if out.get("publicado"):
        try:
            await notify_created("uniforme", out)
        except Exception:
            pass
    return out


@router.put("/{id}")
async def update(id: str, dto: UpdateUniformeDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("uniformes")
    data = clean_update(dto.model_dump(exclude_none=True))
    data["updatedAt"] = datetime.now(timezone.utc)
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": data})
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Uniforme no encontrado")
    out = serialize_doc(doc)
    if out.get("publicado"):
        try:
            await notify_updated("uniforme", out)
        except Exception:
            pass
    return out


@router.delete("/{id}")
async def delete(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("uniformes")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Uniforme no encontrado")
    try:
        await notify_deleted("uniforme", id)
    except Exception:
        pass
    return {"message": "Uniforme eliminado"}
