from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Any
from bson import ObjectId
from datetime import datetime, timezone
import re
import unicodedata
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list, clean_update
from app.modules.websocket.manager import notify_created, notify_updated, notify_deleted


def _make_slug(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "especialidad"


async def _unique_slug(col, base: str, exclude_id=None) -> str:
    slug = base
    suffix = 1
    while True:
        query = {"slug": slug}
        if exclude_id:
            query["_id"] = {"$ne": exclude_id}
        if not await col.find_one(query):
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1

router = APIRouter(prefix="/especialidades", tags=["Especialidades"])

ID_INVALIDO = "ID inválido"
ESPECIALIDAD_NO_ENCONTRADA = "Especialidad no encontrada"


class PublicacionInfo(BaseModel):
    publicada: Optional[bool] = False
    fechaPublicacion: Optional[str] = None


class CreateEspecialidadDto(BaseModel):
    icono: Optional[str] = ""
    color: Optional[str] = ""
    codigo: Optional[str] = ""
    titulo: str
    subtitulo: Optional[str] = ""
    descripcion: Optional[str] = ""
    tituloAObtener: Optional[str] = ""
    duracion: Optional[str] = ""
    nivel: Optional[str] = ""
    imagenHero: Optional[str] = ""
    imagenSecundaria: Optional[str] = ""
    videoUrl: Optional[str] = ""
    malla: Optional[Any] = None
    coordinador: Optional[str] = ""
    perfilCoordinador: Optional[Any] = None
    perfilEstudiante: Optional[Any] = None
    salidasProfesionales: Optional[List[Any]] = []
    instalaciones: Optional[Any] = None
    admisiones: Optional[Any] = None
    testimonios: Optional[List[Any]] = []
    publicacion: Optional[Any] = None
    orden: Optional[int] = 0


# ─── Rutas públicas ────────────────────────────────────────────────────────────

@router.get("/publicas")
async def find_publicas():
    col = get_collection("especialidades")
    docs = await col.find({"publicacion.publicado": True}).sort("orden", 1).to_list(None)
    return serialize_list(docs)


@router.get(
    "/publicas/{id}",
    responses={400: {"description": ID_INVALIDO}, 404: {"description": ESPECIALIDAD_NO_ENCONTRADA}},
)
async def find_publica(id: str):
    col = get_collection("especialidades")
    try:
        doc = await col.find_one({"_id": ObjectId(id), "publicacion.publicado": True})
    except Exception:
        raise HTTPException(status_code=400, detail=ID_INVALIDO)
    if not doc:
        raise HTTPException(status_code=404, detail=ESPECIALIDAD_NO_ENCONTRADA)
    return serialize_doc(doc)


# ─── Rutas protegidas ─────────────────────────────────────────────────────────

@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("especialidades")
    docs = await col.find({}).sort("orden", 1).to_list(None)
    return serialize_list(docs)


@router.get(
    "/{id}",
    responses={400: {"description": ID_INVALIDO}, 404: {"description": ESPECIALIDAD_NO_ENCONTRADA}},
)
async def find_one(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("especialidades")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail=ID_INVALIDO)
    if not doc:
        raise HTTPException(status_code=404, detail=ESPECIALIDAD_NO_ENCONTRADA)
    return serialize_doc(doc)


@router.post("")
async def create(dto: CreateEspecialidadDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("especialidades")
    data = dto.model_dump()
    base = _make_slug(data.get("titulo") or "")
    data["slug"] = await _unique_slug(col, base)
    data["createdAt"] = datetime.now(timezone.utc)
    data["updatedAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    try:
        await notify_created("especialidad", out)
    except Exception:
        pass
    return out


@router.put(
    "/{id}",
    responses={400: {"description": ID_INVALIDO}, 404: {"description": ESPECIALIDAD_NO_ENCONTRADA}},
)
async def update(id: str, request: Request, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("especialidades")
    dto = clean_update(await request.json())
    # Si el título cambió y no se envía slug explícito, regenerar
    if "titulo" in dto and not dto.get("slug"):
        try:
            base = _make_slug(dto["titulo"])
            dto["slug"] = await _unique_slug(col, base, exclude_id=ObjectId(id))
        except Exception:
            pass
    dto["updatedAt"] = datetime.now(timezone.utc)
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": dto})
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail=ID_INVALIDO)
    if not doc:
        raise HTTPException(status_code=404, detail=ESPECIALIDAD_NO_ENCONTRADA)
    out = serialize_doc(doc)
    try:
        await notify_updated("especialidad", out)
    except Exception:
        pass
    return out


@router.delete(
    "/{id}",
    responses={400: {"description": ID_INVALIDO}, 404: {"description": ESPECIALIDAD_NO_ENCONTRADA}},
)
async def delete(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("especialidades")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail=ID_INVALIDO)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=ESPECIALIDAD_NO_ENCONTRADA)
    try:
        await notify_deleted("especialidad", id)
    except Exception:
        pass
    return {"message": "Especialidad eliminada"}

