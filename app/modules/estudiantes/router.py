from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from typing import Optional
from bson import ObjectId
from datetime import datetime, timezone
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list, clean_update

router = APIRouter(prefix="/estudiantes", tags=["Estudiantes"])


class UpdateEstudianteDto(BaseModel):
    model_config = ConfigDict(extra='ignore')
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    cedula: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    especialidad: Optional[str] = None
    curso: Optional[str] = None
    foto: Optional[str] = None
    anioLectivo: Optional[str] = None
    estado: Optional[str] = None


class CreateEstudianteDto(BaseModel):
    nombre: str
    apellido: str
    cedula: str
    email: Optional[str] = ""
    telefono: Optional[str] = ""
    especialidad: Optional[str] = ""
    curso: Optional[str] = ""
    foto: Optional[str] = ""
    anioLectivo: Optional[str] = ""
    estado: Optional[str] = "activo"


@router.get("/stats/por-especialidad")
async def stats_por_especialidad(current_user: dict = Depends(get_current_user)):
    col = get_collection("estudiantes")
    pipeline = [
        {"$group": {"_id": "$especialidad", "total": {"$sum": 1}}},
        {"$project": {"especialidad": "$_id", "total": 1, "_id": 0}},
        {"$sort": {"total": -1}},
    ]
    result = await col.aggregate(pipeline).to_list(None)
    return result


@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("estudiantes")
    docs = await col.find({}).sort("apellido", 1).to_list(None)
    return serialize_list(docs)


@router.get("/{id}")
async def find_one(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("estudiantes")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    return serialize_doc(doc)


@router.post("")
async def create(dto: CreateEstudianteDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("estudiantes")
    existing = await col.find_one({"cedula": dto.cedula})
    if existing:
        raise HTTPException(status_code=409, detail="Cédula ya registrada")
    data = dto.model_dump()
    data["createdAt"] = datetime.now(timezone.utc)
    data["updatedAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


@router.put("/{id}")
async def update(id: str, dto: UpdateEstudianteDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("estudiantes")
    data = clean_update(dto.model_dump(exclude_none=True))
    data["updatedAt"] = datetime.now(timezone.utc)
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": data})
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    return serialize_doc(doc)


@router.delete("/{id}")
async def delete(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("estudiantes")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    return {"message": "Estudiante eliminado"}

