from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from bson import ObjectId
from app.core.database import get_collection
from app.core.security import hash_password
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list

router = APIRouter(prefix="/users", tags=["Users"])


class CreateUserDto(BaseModel):
    nombre: str
    apellido: str
    username: str
    email: str
    password: str
    cargo: Optional[str] = ""
    rol: str = "viewer"
    status: str = "active"


class UpdateUserDto(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    cargo: Optional[str] = None
    rol: Optional[str] = None
    status: Optional[str] = None
    avatar: Optional[str] = None


@router.get("")
async def list_users(current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("users")
    docs = await col.find({}).to_list(None)
    result = serialize_list(docs)
    for u in result:
        u.pop("password", None)
    return result


@router.get("/{id}")
async def get_user(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("users")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    result = serialize_doc(doc)
    result.pop("password", None)
    return result


@router.post("")
async def create_user(dto: CreateUserDto, current_user: dict = Depends(require_roles("super_admin"))):
    col = get_collection("users")
    existing = await col.find_one({"$or": [{"username": dto.username}, {"email": dto.email}]})
    if existing:
        raise HTTPException(status_code=409, detail="Username o email ya existe")

    data = dto.model_dump()
    data["password"] = hash_password(data["password"])
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    out.pop("password", None)
    return out


@router.put("/{id}")
async def update_user(id: str, dto: UpdateUserDto, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("users")
    data = {k: v for k, v in dto.model_dump().items() if v is not None}
    if "password" in data:
        data["password"] = hash_password(data["password"])
    if not data:
        raise HTTPException(status_code=400, detail="Sin datos para actualizar")
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": data})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    doc = await col.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    out = serialize_doc(doc)
    out.pop("password", None)
    return out


@router.delete("/{id}")
async def delete_user(id: str, current_user: dict = Depends(require_roles("super_admin"))):
    col = get_collection("users")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"message": "Usuario eliminado"}

