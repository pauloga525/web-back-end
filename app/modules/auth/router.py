from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from app.core.database import get_collection
from app.core.security import verify_password, create_access_token, decode_token, hash_password
from app.core.config import settings
from app.shared.dependencies import get_current_user
from app.shared.responses import serialize_doc
from app.shared.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/auth", tags=["Auth"])

_login_limiter = SlidingWindowLimiter(
    max_attempts=settings.LOGIN_MAX_ATTEMPTS,
    window_seconds=settings.LOGIN_WINDOW_SECONDS,
)


class LoginDto(BaseModel):
    username: str
    password: str


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login")
async def login(dto: LoginDto, request: Request):
    ip = _client_ip(request)
    limiter_key = f"{ip}:{dto.username.lower()}"

    blocked, retry_after = _login_limiter.is_blocked(limiter_key)
    if blocked:
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos fallidos. Intenta de nuevo más tarde.",
            headers={"Retry-After": str(retry_after)},
        )

    col = get_collection("users")
    user = await col.find_one({
        "$or": [
            {"username": dto.username},
            {"email": dto.username},
        ]
    })

    if not user or not verify_password(dto.password, user.get("password", "")):
        _login_limiter.register_attempt(limiter_key)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if user.get("status") == "inactive":
        raise HTTPException(status_code=403, detail="Usuario inactivo")

    _login_limiter.reset(limiter_key)

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
async def me(current_user: dict = Depends(get_current_user)):
    doc = serialize_doc(current_user)
    doc.pop("password", None)
    return doc


if settings.is_development:
    @router.get("/debug-token")
    async def debug_token(current_user: dict = Depends(get_current_user)):
        return {
            "userId": current_user.get("id"),
            "username": current_user.get("username"),
            "rol": current_user.get("rol"),
            "email": current_user.get("email"),
        }

    @router.get("/compare-secrets")
    async def compare_secrets():
        return {"env": settings.NODE_ENV, "secret_length": len(settings.JWT_SECRET)}
