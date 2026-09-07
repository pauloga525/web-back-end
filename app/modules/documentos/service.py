import io
from datetime import datetime, timezone
from app.core.database import get_gridfs_documentos
from app.core.config import settings


async def store_document(data: bytes, filename: str, content_type: str) -> dict:
    """
    Guarda un documento (PDF/Word) tal cual en GridFS, sin intentar
    procesarlo como imagen. A diferencia de un Base64 embebido en un
    documento de configuración, GridFS lo parte en chunks aparte
    (colección 'documentos.chunks'), así que no infla ni hace lento el
    documento que solo guarda la URL.
    """
    gridfs = get_gridfs_documentos()
    file_id = await gridfs.upload_from_stream(
        filename,
        io.BytesIO(data),
        metadata={
            "originalName": filename,
            "uploadedAt": datetime.now(timezone.utc).isoformat(),
            "contentType": content_type,
        },
    )

    str_id = str(file_id)
    url = f"{settings.BACKEND_URL}/api/v1/documentos/gridfs/{str_id}"

    return {
        "url": url,
        "stored": "gridfs",
        "id": str_id,
        "filename": filename,
        "sizeBytes": len(data),
        "contentType": content_type,
    }
