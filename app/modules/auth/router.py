from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.core.database import get_collection
from app.core.security import verify_password, create_access_token, decode_token, hash_password
from app.core.config import settings
from app.shared.dependencies import get_current_user
from app.shared.responses import serialize_doc

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginDto(BaseModel):
    username: str
    password: str


@router.post(
    "/login",
    responses={
        401: {"description": "Credenciales inválidas"},
        403: {"description": "Usuario inactivo"},
    },
)
async def login(dto: LoginDto):
    col = get_collection("users")
    user = await col.find_one({
        "$or": [
            {"username": dto.username},
            {"email": dto.username},
        ]
    })

    if not user or not verify_password(dto.password, user.get("password", "")):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if user.get("status") == "inactive":
        raise HTTPException(status_code=403, detail="Usuario inactivo")

    token = create_access_token({
        "userId": str(user["_id"]),
        "username": user["username"],
        "rol": user["rol"],
        "email": user.get("email", ""),
    })

    doc = serialize_doc(user)
    doc.pop("password", None)

    return {"access_token": token, "user": doc}


@router.get("/me")
async def me(current_user: Annotated[dict, Depends(get_current_user)]):
    doc = serialize_doc(current_user)
    doc.pop("password", None)
    return doc


if settings.is_development:
    @router.get("/debug-token")
    async def debug_token(current_user: Annotated[dict, Depends(get_current_user)]):
        return {
            "userId": current_user.get("id"),
            "username": current_user.get("username"),
            "rol": current_user.get("rol"),
            "email": current_user.get("email"),
        }

    @router.get("/compare-secrets")
    async def compare_secrets():
        return {"env": settings.NODE_ENV, "secret_length": len(settings.JWT_SECRET)}
