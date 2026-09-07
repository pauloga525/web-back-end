import io
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from app.core.database import get_gridfs_documentos
from app.shared.dependencies import get_current_user
from .service import store_document

router = APIRouter(prefix="/documentos", tags=["Documentos"])

# Se valida por extensión (no solo por Content-Type que manda el navegador)
# porque para .docx algunos navegadores/SO mandan 'application/octet-stream'
# en vez del MIME correcto, y eso rechazaría subidas válidas.
EXTENSIONES_PERMITIDAS = {".pdf", ".doc", ".docx"}
CONTENT_TYPES = {
    ".pdf":  "application/pdf",
    ".doc":  "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_BYTES = 25 * 1024 * 1024  # 25 MB


def _extension(filename: str) -> str:
    idx = filename.rfind(".")
    return filename[idx:].lower() if idx != -1 else ""


@router.post("")
async def upload_documento(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    ext = _extension(file.filename or "")
    if ext not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF o Word (.pdf, .doc, .docx)")

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="El archivo supera el límite de 25 MB")

    content_type = CONTENT_TYPES.get(ext) or file.content_type or "application/octet-stream"
    return await store_document(data, file.filename or f"documento{ext}", content_type)


@router.get("/gridfs/{doc_id}")
async def get_documento(doc_id: str):
    try:
        oid = ObjectId(doc_id)
    except (InvalidId, Exception):
        raise HTTPException(status_code=400, detail="ID de documento inválido")

    gridfs = get_gridfs_documentos()
    try:
        grid_out = await gridfs.open_download_stream(oid)
    except Exception:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    chunks = []
    while True:
        chunk = await grid_out.read(65536)
        if not chunk:
            break
        chunks.append(chunk)

    content = b"".join(chunks)
    metadata = grid_out.metadata or {}
    content_type = metadata.get("contentType", "application/octet-stream")
    filename = metadata.get("originalName", grid_out.filename or "documento")

    return StreamingResponse(
        io.BytesIO(content),
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Length": str(len(content)),
            # 'inline' para que un PDF se pueda previsualizar directo en el
            # navegador (requisito: "que se pueda visualizar en la página
            # pública"), en vez de forzar la descarga.
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )
