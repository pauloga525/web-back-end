from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from typing import Optional
from bson import ObjectId
from datetime import datetime, timezone
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list, clean_update
from app.modules.websocket.manager import notify_created, notify_updated, notify_deleted

router = APIRouter(prefix="/logros", tags=["Logros"])


class UpdateLogroDto(BaseModel):
    model_config = ConfigDict(extra='ignore')
    badge: Optional[str] = None
    badgeClass: Optional[str] = None
    date: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    featured: Optional[bool] = None
    publicado: Optional[bool] = None


class CreateLogroDto(BaseModel):
    badge: Optional[str] = ""
    badgeClass: Optional[str] = ""
    date: Optional[str] = ""
    title: str
    category: Optional[str] = ""
    description: Optional[str] = ""
    image: Optional[str] = ""
    featured: Optional[bool] = False
    publicado: Optional[bool] = False


# ─── Rutas públicas ────────────────────────────────────────────────────────────

@router.get("/publicos")
async def find_publicos():
    col = get_collection("logros")
    docs = await col.find({"publicado": True}).sort("createdAt", -1).to_list(None)
    return serialize_list(docs)


@router.get("/destacados")
async def find_destacados():
    col = get_collection("logros")
    docs = await col.find({"featured": True, "publicado": True}).sort("createdAt", -1).to_list(None)
    return serialize_list(docs)


@router.get("/categoria/{cat}")
async def find_by_categoria(cat: str):
    col = get_collection("logros")
    docs = await col.find({"category": cat, "publicado": True}).sort("createdAt", -1).to_list(None)
    return serialize_list(docs)


@router.get("/publico/{id}")
async def find_publico(id: str):
    col = get_collection("logros")
    try:
        doc = await col.find_one({"_id": ObjectId(id), "publicado": True})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Logro no encontrado")
    return serialize_doc(doc)


# ─── Rutas protegidas ─────────────────────────────────────────────────────────

@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("logros")
    docs = await col.find({}).sort("createdAt", -1).to_list(None)
    return serialize_list(docs)


@router.get("/{id}")
async def find_one(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("logros")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Logro no encontrado")
    return serialize_doc(doc)


@router.post("")
async def create(dto: CreateLogroDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("logros")
    data = dto.model_dump()
    data["createdAt"] = datetime.now(timezone.utc)
    data["updatedAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    try:
        await notify_created("logro", out)
    except Exception:
        pass
    return out


@router.put("/{id}")
async def update(id: str, dto: UpdateLogroDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("logros")
    data = clean_update(dto.model_dump(exclude_none=True))
    data["updatedAt"] = datetime.now(timezone.utc)
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": data})
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Logro no encontrado")
    out = serialize_doc(doc)
    try:
        await notify_updated("logro", out)
    except Exception:
        pass
    return out


@router.delete("/{id}")
async def delete(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("logros")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Logro no encontrado")
    try:
        await notify_deleted("logro", id)
    except Exception:
        pass
    return {"message": "Logro eliminado"}

