from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from typing import Optional
from bson import ObjectId
from datetime import datetime, timezone
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list, clean_update
from app.modules.websocket.manager import notify_created, notify_updated, notify_deleted

router = APIRouter(prefix="/consejo", tags=["Consejo Estudiantil"])


class CreateMiembroConsejoDto(BaseModel):
    titulo: Optional[str] = ""       # cargo, ej. "Presidente"
    nombre: str
    descripcion: Optional[str] = ""
    imagen: Optional[str] = ""
    publicado: Optional[bool] = True
    orden: Optional[int] = 0


class UpdateMiembroConsejoDto(BaseModel):
    model_config = ConfigDict(extra='ignore')
    titulo: Optional[str] = None
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    imagen: Optional[str] = None
    publicado: Optional[bool] = None
    orden: Optional[int] = None


# ─── Rutas públicas ────────────────────────────────────────────────────────────

@router.get("/publicos")
async def find_publicos():
    col = get_collection("consejo")
    docs = await col.find({"publicado": True}).sort("orden", 1).to_list(None)
    return serialize_list(docs)


# ─── Rutas protegidas ─────────────────────────────────────────────────────────

@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("consejo")
    docs = await col.find({}).sort("orden", 1).to_list(None)
    return serialize_list(docs)


@router.get("/{id}")
async def find_one(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("consejo")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    return serialize_doc(doc)


@router.post("")
async def create(dto: CreateMiembroConsejoDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("consejo")
    data = dto.model_dump()
    data["createdAt"] = datetime.now(timezone.utc)
    data["updatedAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    if out.get("publicado"):
        try:
            await notify_created("consejo", out)
        except Exception:
            pass
    return out


@router.put("/{id}")
async def update(id: str, dto: UpdateMiembroConsejoDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("consejo")
    data = clean_update(dto.model_dump(exclude_none=True))
    data["updatedAt"] = datetime.now(timezone.utc)
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": data})
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    out = serialize_doc(doc)
    if out.get("publicado"):
        try:
            await notify_updated("consejo", out)
        except Exception:
            pass
    return out


@router.delete("/{id}")
async def delete(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("consejo")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Miembro no encontrado")
    try:
        await notify_deleted("consejo", id)
    except Exception:
        pass
    return {"message": "Miembro eliminado"}
