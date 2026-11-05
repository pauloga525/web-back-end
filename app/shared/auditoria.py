"""
Registro automático de actividad.

Cada escritura exitosa (POST/PUT/PATCH/DELETE) hecha por un usuario autenticado
en un módulo del panel se guarda en `actividad` y genera una notificación para
los demás administradores. Así el historial y las notificaciones reflejan lo
que realmente ocurre, sin depender de que cada pantalla lo registre.
"""
import json
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import Request

from app.core.database import get_collection
from app.core.security import decode_token

PREFIX = "/api/v1/"

# módulo -> (tipo de actividad, etiqueta, femenino)
MODULOS = {
    "eventos":        ("evento", "Evento", False),
    "noticias":       ("sistema", "Noticia", True),
    "especialidades": ("especialidad", "Especialidad", True),
    "autoridades":    ("sistema", "Autoridad", True),
    "estudiantes":    ("estudiante", "Estudiante", False),
    "logros":         ("estudiante", "Logro", False),
    "users":          ("usuario", "Usuario", False),
    "recursos":       ("sistema", "Recurso", False),
    "uniformes":      ("sistema", "Uniforme", False),
    "consejo":        ("sistema", "Consejo", False),
    "configuracion":  ("sistema", "Configuración", True),
}

VERBOS = {
    "POST":   ("creado", "creó"),
    "PUT":    ("actualizado", "actualizó"),
    "PATCH":  ("actualizado", "actualizó"),
    "DELETE": ("eliminado", "eliminó"),
}

DEDUP_SEGUNDOS = 60
MAX_BODY = 200_000


def _nombre_en_body(body: bytes) -> str:
    try:
        data = json.loads(body)
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    for k in ("titulo", "title", "nombre", "name"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            extra = data.get("apellido") if k == "nombre" else None
            return f"{v.strip()} {extra}".strip() if isinstance(extra, str) else v.strip()
    return ""


async def registrar(request: Request, status_code: int, body: bytes) -> None:
    if request.method not in VERBOS or status_code >= 400:
        return
    path = request.url.path
    if not path.startswith(PREFIX):
        return
    partes = path[len(PREFIX):].strip("/").split("/")
    modulo = partes[0]
    if modulo not in MODULOS:
        return

    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return
    payload = decode_token(auth[7:])
    user_id = payload and (payload.get("userId") or payload.get("sub"))
    if not user_id:
        return
    user = await get_collection("users").find_one({"_id": ObjectId(user_id)})
    if not user:
        return

    tipo, etiqueta, fem = MODULOS[modulo]
    participio, pasado = VERBOS[request.method]
    if fem:
        participio = participio[:-1] + "a"
    nombre = _nombre_en_body(body) if request.method != "DELETE" else ""
    # /eventos/{id}/toggle-publicado y similares
    if request.method == "PATCH" and len(partes) > 2:
        participio, pasado = "modificado" if not fem else "modificada", "modificó"

    titulo = f"{etiqueta} {participio}"
    descripcion = f"Se {pasado} " + (f"\"{nombre}\"" if nombre else f"un registro de {etiqueta.lower()}") + "."
    actor = f"{user.get('nombre', '')} {user.get('apellido', '')}".strip() or user.get("username", "")

    ahora = datetime.now(timezone.utc)
    col = get_collection("actividad")
    repetida = await col.find_one({
        "usuarioId": str(user["_id"]),
        "titulo": titulo,
        "descripcion": descripcion,
        "createdAt": {"$gte": ahora - timedelta(seconds=DEDUP_SEGUNDOS)},
    })
    if repetida:
        return

    await col.insert_one({
        "tipo": tipo,
        "titulo": titulo,
        "descripcion": descripcion,
        "usuario": actor,
        "usuarioId": str(user["_id"]),
        "entidad": modulo,
        "createdAt": ahora,
    })
    await get_collection("notificaciones").insert_one({
        "titulo": titulo,
        "descripcion": f"{actor}: {descripcion[0].lower()}{descripcion[1:]}" if actor else descripcion,
        "tipo": tipo,
        "usuario": "",            # para todos los administradores
        "autorId": str(user["_id"]),
        "leidoPor": [],
        "eliminadoPor": [],
        "createdAt": ahora,
    })


async def leer_body(request: Request) -> bytes:
    if request.method not in ("POST", "PUT", "PATCH"):
        return b""
    if "application/json" not in request.headers.get("content-type", ""):
        return b""
    try:
        if int(request.headers.get("content-length", "0")) > MAX_BODY:
            return b""
    except ValueError:
        return b""
    return await request.body()
