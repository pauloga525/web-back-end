import socketio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.database import connect_db, close_db
from app.core.security import hash_password
from app.core.database import get_collection
from app.modules.websocket.manager import sio

from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.eventos.router import router as eventos_router
from app.modules.noticias.router import router as noticias_router
from app.modules.especialidades.router import router as especialidades_router
from app.modules.autoridades.router import router as autoridades_router
from app.modules.estudiantes.router import router as estudiantes_router
from app.modules.logros.router import router as logros_router
from app.modules.actividad.router import router as actividad_router
from app.modules.notificaciones.router import router as notificaciones_router
from app.modules.configuracion.router import router as configuracion_router
from app.modules.recursos.router import router as recursos_router
from app.modules.imagenes.router import router as imagenes_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_db()
    await seed_admin()
    yield
    close_db()


async def seed_admin():
    col = get_collection("users")
    existing = await col.find_one({"username": settings.SEED_ADMIN_USERNAME})
    if not existing:
        await col.insert_one({
            "nombre": "Admin",
            "apellido": "UETS",
            "username": settings.SEED_ADMIN_USERNAME,
            "email": settings.SEED_ADMIN_EMAIL,
            "password": hash_password(settings.SEED_ADMIN_PASSWORD),
            "cargo": "Administrador",
            "rol": "super_admin",
            "status": "active",
        })
        print(f"Admin creado: {settings.SEED_ADMIN_USERNAME}")


app = FastAPI(
    title="UETS API",
    version="1.0.0",
    docs_url="/api/v1/docs" if settings.is_development else None,
    redoc_url="/api/v1/redoc" if settings.is_development else None,
    openapi_url="/api/v1/openapi.json" if settings.is_development else None,
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

origins = settings.cors_origins_list

if settings.is_development:
    # En desarrollo: acepta cualquier puerto de localhost/127.0.0.1
    cors_kwargs = {"allow_origin_regex": r"https?://(localhost|127\.0\.0\.1)(:\d+)?"}
else:
    cors_kwargs = {"allow_origins": origins}

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    **cors_kwargs,
)

# ─── Routers con prefijo /api/v1 ──────────────────────────────────────────────

PREFIX = "/api/v1"

app.include_router(auth_router, prefix=PREFIX)
app.include_router(users_router, prefix=PREFIX)
app.include_router(eventos_router, prefix=PREFIX)
app.include_router(noticias_router, prefix=PREFIX)
app.include_router(especialidades_router, prefix=PREFIX)
app.include_router(autoridades_router, prefix=PREFIX)
app.include_router(estudiantes_router, prefix=PREFIX)
app.include_router(logros_router, prefix=PREFIX)
app.include_router(actividad_router, prefix=PREFIX)
app.include_router(notificaciones_router, prefix=PREFIX)
app.include_router(configuracion_router, prefix=PREFIX)
app.include_router(recursos_router, prefix=PREFIX)
app.include_router(imagenes_router, prefix=PREFIX)

# ─── Static files ─────────────────────────────────────────────────────────────

uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "env": settings.NODE_ENV}


# ─── Socket.io ASGI mount ─────────────────────────────────────────────────────

socket_app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="/socket.io")
