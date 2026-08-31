from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Request
from typing import Any
from datetime import datetime, timezone
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, clean_update
from app.modules.websocket.manager import notify_config_updated
from app.modules.imagenes.service import process_and_store_image

router = APIRouter(prefix="/configuracion", tags=["Configuracion"])

# Cada 'clave' tiene su propia forma de JSON (home, nosotros, admisiones, ...),
# por lo que no se modela con un DTO fijo por campo. Aun así se valida que sea
# un objeto JSON (no un array/string/null suelto) y se limita su tamaño para
# evitar payloads abusivos.
MAX_CONFIG_BYTES = 2 * 1024 * 1024  # 2 MB


@router.get("")
async def list_claves(current_user: dict = Depends(get_current_user)):
    col = get_collection("configuraciones")
    docs = await col.find({}, {"clave": 1, "updatedAt": 1}).sort("clave", 1).to_list(None)
    return [{"_id": str(d["_id"]), "clave": d["clave"], "updatedAt": d.get("updatedAt")} for d in docs]


@router.get("/publica/{clave}")
async def get_publica(clave: str):
    col = get_collection("configuraciones")
    doc = await col.find_one({"clave": clave})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Configuración '{clave}' no encontrada")
    return serialize_doc(doc)


@router.get("/{clave}")
async def get_config(clave: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("configuraciones")
    doc = await col.find_one({"clave": clave})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Configuración '{clave}' no encontrada")
    return serialize_doc(doc)


@router.put("/{clave}")
async def upsert_config(clave: str, request: Request, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("configuraciones")
    now = datetime.now(timezone.utc)

    body = await request.body()
    if len(body) > MAX_CONFIG_BYTES:
        raise HTTPException(status_code=413, detail="La configuración supera el límite de tamaño permitido")

    datos = await request.json()
    if not isinstance(datos, dict):
        raise HTTPException(status_code=422, detail="El cuerpo debe ser un objeto JSON")

    await col.update_one(
        {"clave": clave},
        {"$set": {"datos": datos, "updatedAt": now}, "$setOnInsert": {"clave": clave, "createdAt": now}},
        upsert=True,
    )
    doc = await col.find_one({"clave": clave})
    out = serialize_doc(doc)
    try:
        await notify_config_updated(clave, {"clave": clave, "updatedAt": out.get("updatedAt")})
    except Exception:
        pass
    return out


@router.delete("/{clave}")
async def delete_config(clave: str, current_user: dict = Depends(require_roles("super_admin"))):
    col = get_collection("configuraciones")
    result = await col.delete_one({"clave": clave})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Configuración '{clave}' no encontrada")
    return {"message": f"Configuración '{clave}' eliminada"}


@router.post("/imagenes")
async def upload_imagen_config(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor")),
):
    allowed = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/avif", "image/svg+xml"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido")

    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo supera el límite de 15 MB")

    return await process_and_store_image(data, file.filename or "config-imagen", file.content_type)
