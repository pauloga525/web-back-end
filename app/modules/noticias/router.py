from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from bson import ObjectId
from datetime import datetime, timezone
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list, clean_update
from app.modules.websocket.manager import notify_created, notify_updated, notify_deleted

router = APIRouter(prefix="/noticias", tags=["Noticias"])


class UpdateNoticiaDto(BaseModel):
    model_config = ConfigDict(extra='ignore')
    tag: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    destacada: Optional[bool] = None
    category: Optional[str] = None
    featuredImage: Optional[str] = None
    author: Optional[str] = None
    authorImage: Optional[str] = None
    date: Optional[str] = None
    readTime: Optional[str] = None
    content: Optional[str] = None
    images: Optional[List[Any]] = None
    tags: Optional[List[str]] = None
    publicada: Optional[bool] = None


class CreateNoticiaDto(BaseModel):
    tag: Optional[str] = ""
    title: str
    description: str
    image: Optional[str] = ""
    destacada: Optional[bool] = False
    category: Optional[str] = ""
    featuredImage: Optional[str] = ""
    author: Optional[str] = ""
    authorImage: Optional[str] = ""
    date: Optional[str] = ""
    readTime: Optional[str] = ""
    content: Optional[str] = ""
    images: Optional[List[str]] = []
    tags: Optional[List[str]] = []
    publicada: Optional[bool] = False


# ─── Rutas públicas ────────────────────────────────────────────────────────────

@router.get("/publicas")
async def find_publicas(
    q: Optional[str] = Query(None),
    categoria: Optional[str] = Query(None),
    pagina: int = Query(1),
    porPagina: int = Query(10),
):
    col = get_collection("noticias")
    query: dict = {"publicada": True}
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    if categoria:
        query["category"] = categoria
    total = await col.count_documents(query)
    skip = (pagina - 1) * porPagina
    docs = await col.find(query).sort("createdAt", -1).skip(skip).limit(porPagina).to_list(None)
    return {
        "items": serialize_list(docs),
        "total": total,
        "pagina": pagina,
        "porPagina": porPagina,
        "totalPaginas": (total + porPagina - 1) // porPagina,
    }


@router.get("/destacadas")
async def find_destacadas():
    col = get_collection("noticias")
    docs = await col.find({"destacada": True, "publicada": True}).sort("createdAt", -1).to_list(None)
    return serialize_list(docs)


@router.get("/publica/{id}")
async def find_publica_by_id(id: str):
    col = get_collection("noticias")
    try:
        doc = await col.find_one({"_id": ObjectId(id), "publicada": True})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Noticia no encontrada")
    return serialize_doc(doc)


# ─── Rutas protegidas ─────────────────────────────────────────────────────────

@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("noticias")
    docs = await col.find({}).sort("createdAt", -1).to_list(None)
    return serialize_list(docs)


@router.get("/{id}")
async def find_one(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("noticias")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Noticia no encontrada")
    return serialize_doc(doc)


@router.post("")
async def create(dto: CreateNoticiaDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("noticias")
    data = dto.model_dump()
    data["createdAt"] = datetime.now(timezone.utc)
    data["updatedAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    try:
        await notify_created("noticia", out)
    except Exception:
        pass
    return out


@router.put("/{id}")
async def update(id: str, dto: UpdateNoticiaDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("noticias")
    data = clean_update(dto.model_dump(exclude_none=True))
    data["updatedAt"] = datetime.now(timezone.utc)
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": data})
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Noticia no encontrada")
    out = serialize_doc(doc)
    try:
        await notify_updated("noticia", out)
    except Exception:
        pass
    return out


@router.delete("/{id}")
async def delete(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("noticias")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Noticia no encontrada")
    try:
        await notify_deleted("noticia", id)
    except Exception:
        pass
    return {"message": "Noticia eliminada"}
