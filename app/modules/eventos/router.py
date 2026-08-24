from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from bson import ObjectId
from datetime import datetime, timezone
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list, clean_update
from app.modules.websocket.manager import notify_created, notify_updated, notify_deleted

router = APIRouter(prefix="/eventos", tags=["Eventos"])


class UpdateEventoDto(BaseModel):
    model_config = ConfigDict(extra='ignore')
    slug: Optional[str] = None
    titulo: Optional[str] = None
    descripcionCorta: Optional[str] = None
    descripcionCompleta: Optional[str] = None
    categoria: Optional[str] = None
    categoriaColor: Optional[str] = None
    fecha: Optional[str] = None
    horaInicio: Optional[str] = None
    horaFin: Optional[str] = None
    ubicacion: Optional[str] = None
    direccion: Optional[str] = None
    imagenPrincipal: Optional[str] = None
    galeria: Optional[List[str]] = None
    agenda: Optional[List[Any]] = None
    registro: Optional[Any] = None
    publicado: Optional[bool] = None
    destacado: Optional[bool] = None


class AgendaItem(BaseModel):
    id: Optional[int] = None
    hora: str
    titulo: str
    descripcion: Optional[str] = ""


class RegistroAsistencia(BaseModel):
    habilitado: Optional[bool] = False
    labelBoton: Optional[str] = "Registrarse"
    url: Optional[str] = ""


class CreateEventoDto(BaseModel):
    slug: str
    titulo: str
    descripcionCorta: str
    descripcionCompleta: Optional[str] = ""
    categoria: str
    categoriaColor: Optional[str] = "blue"
    fecha: str
    horaInicio: Optional[str] = "08:00"
    horaFin: Optional[str] = "17:00"
    ubicacion: Optional[str] = ""
    direccion: Optional[str] = ""
    imagenPrincipal: Optional[str] = ""
    galeria: Optional[List[str]] = []
    agenda: Optional[List[Any]] = []
    registro: Optional[Any] = None
    publicado: Optional[bool] = False
    destacado: Optional[bool] = False


# ─── Rutas públicas (sin auth) ────────────────────────────────────────────────

@router.get("/publicos")
async def find_publicos(
    q: Optional[str] = Query(None),
    categoria: Optional[str] = Query(None),
    mes: Optional[int] = Query(None),
    anio: Optional[int] = Query(None),
    pagina: int = Query(1),
    porPagina: int = Query(10),
):
    col = get_collection("eventos")
    query: dict = {"publicado": True}

    if q:
        query["$or"] = [
            {"titulo": {"$regex": q, "$options": "i"}},
            {"descripcionCorta": {"$regex": q, "$options": "i"}},
        ]
    if categoria:
        query["categoria"] = categoria
    if mes:
        query["$expr"] = {"$eq": [{"$month": {"$dateFromString": {"dateString": "$fecha"}}}, mes]}
    if anio:
        prefix = str(anio)
        query["fecha"] = {"$regex": f"^{prefix}"}

    total = await col.count_documents(query)
    skip = (pagina - 1) * porPagina
    docs = await col.find(query).sort("fecha", -1).skip(skip).limit(porPagina).to_list(None)

    return {
        "items": serialize_list(docs),
        "total": total,
        "pagina": pagina,
        "porPagina": porPagina,
        "totalPaginas": (total + porPagina - 1) // porPagina,
    }


@router.get("/destacado")
async def find_destacado():
    col = get_collection("eventos")
    doc = await col.find_one({"destacado": True, "publicado": True}, sort=[("fecha", -1)])
    if not doc:
        doc = await col.find_one({"publicado": True}, sort=[("fecha", -1)])
    if not doc:
        raise HTTPException(status_code=404, detail="No hay evento destacado")
    return serialize_doc(doc)


@router.get("/slug/{slug}")
async def find_by_slug(slug: str):
    col = get_collection("eventos")
    doc = await col.find_one({"slug": slug})
    if not doc:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return serialize_doc(doc)


# ─── Rutas protegidas (admin) ─────────────────────────────────────────────────

@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("eventos")
    docs = await col.find({}).sort("fecha", -1).to_list(None)
    return serialize_list(docs)


@router.get("/{id}")
async def find_one(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("eventos")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return serialize_doc(doc)


@router.post("")
async def create(dto: CreateEventoDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("eventos")
    data = dto.model_dump()
    data["slug"] = data["slug"].lower().strip()
    data["createdAt"] = datetime.now(timezone.utc)
    data["updatedAt"] = datetime.now(timezone.utc)

    existing = await col.find_one({"slug": data["slug"]})
    if existing:
        raise HTTPException(status_code=409, detail="El slug ya existe")

    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    try:
        await notify_created("evento", out)
    except Exception:
        pass
    return out


@router.put("/{id}")
async def update(id: str, dto: UpdateEventoDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("eventos")
    data = clean_update(dto.model_dump(exclude_none=True))
    data["updatedAt"] = datetime.now(timezone.utc)
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": data})
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    out = serialize_doc(doc)
    try:
        await notify_updated("evento", out)
    except Exception:
        pass
    return out


@router.delete("/{id}")
async def delete(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("eventos")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    try:
        await notify_deleted("evento", id)
    except Exception:
        pass
    return {"message": "Evento eliminado"}


@router.patch("/{id}/destacado")
async def set_destacado(id: str, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("eventos")
    await col.update_many({}, {"$set": {"destacado": False}})
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": {"destacado": True, "updatedAt": datetime.now(timezone.utc)}})
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    out = serialize_doc(doc)
    try:
        await notify_updated("evento", out)
    except Exception:
        pass
    return out


@router.patch("/{id}/toggle-publicado")
async def toggle_publicado(id: str, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("eventos")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    nuevo_estado = not doc.get("publicado", False)
    await col.update_one({"_id": ObjectId(id)}, {"$set": {"publicado": nuevo_estado, "updatedAt": datetime.now(timezone.utc)}})
    doc = await col.find_one({"_id": ObjectId(id)})
    out = serialize_doc(doc)
    try:
        await notify_updated("evento", out)
    except Exception:
        pass
    return out
