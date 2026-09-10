import io
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Body
from fastapi.responses import StreamingResponse
from app.core.database import get_gridfs, get_collection
from app.shared.dependencies import get_current_user
from app.core.config import settings
from .service import process_and_store_image, fetch_and_store_image

router = APIRouter(prefix="/imagenes", tags=["Imagenes"])

CONTENT_TYPE_WEBP = "image/webp"


@router.get("/health")
async def health():
    return {"status": "ok", "service": "imagenes"}


@router.post(
    "",
    responses={400: {"description": "Tipo de archivo no permitido o supera el límite de 15 MB"}},
)
async def upload_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    allowed = {"image/jpeg", "image/jpg", "image/png", CONTENT_TYPE_WEBP, "image/avif", "image/svg+xml"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido")

    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El archivo supera el límite de 15 MB")

    result = await process_and_store_image(data, file.filename or "imagen", file.content_type)
    return result


@router.post(
    "/from-url",
    responses={400: {"description": "sourceUrl es requerido"}},
)
async def upload_from_url(
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    source_url = body.get("sourceUrl") or body.get("source_url")
    if not source_url:
        raise HTTPException(status_code=400, detail="sourceUrl es requerido")

    result = await fetch_and_store_image(source_url)
    return result


@router.get(
    "/gridfs/{image_id}",
    responses={400: {"description": "ID de imagen inválido"}, 404: {"description": "Imagen no encontrada"}},
)
async def get_image(image_id: str):
    try:
        oid = ObjectId(image_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="ID de imagen inválido")

    gridfs = get_gridfs()
    try:
        grid_out = await gridfs.open_download_stream(oid)
    except Exception:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    chunks = []
    while True:
        chunk = await grid_out.read(65536)
        if not chunk:
            break
        chunks.append(chunk)

    content = b"".join(chunks)
    content_type = grid_out.metadata.get("contentType", CONTENT_TYPE_WEBP) if grid_out.metadata else CONTENT_TYPE_WEBP

    return StreamingResponse(
        io.BytesIO(content),
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Length": str(len(content)),
        },
    )
