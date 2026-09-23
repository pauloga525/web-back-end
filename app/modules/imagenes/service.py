import io
from datetime import datetime, timezone
from PIL import Image
import httpx
from fastapi import HTTPException
from app.core.database import get_gridfs
from app.core.config import settings
from app.shared.url_safety import assert_safe_url as _assert_safe_url


MAX_DIM = 1920
WEBP_QUALITY = 82

MAX_REDIRECTS = 5


async def process_and_store_image(data: bytes, filename: str, content_type: str) -> dict:
    original_bytes = len(data)

    data, content_type = _optimize(data)

    gridfs = get_gridfs()
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
    url = f"{settings.BACKEND_URL}/api/v1/imagenes/gridfs/{str_id}"

    return {
        "url": url,
        "stored": "gridfs",
        "id": str_id,
        "originalBytes": original_bytes,
        "optimizedBytes": len(data),
        "contentType": content_type,
    }


async def fetch_and_store_image(source_url: str) -> dict:
    _assert_safe_url(source_url)

    url = source_url
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(MAX_REDIRECTS):
            resp = await client.get(url, follow_redirects=False)
            if resp.is_redirect:
                location = resp.headers.get("location")
                if not location:
                    raise HTTPException(status_code=400, detail="Redirección sin destino")
                url = str(httpx.URL(url).join(location))
                _assert_safe_url(url)
                continue
            resp.raise_for_status()
            break
        else:
            raise HTTPException(status_code=400, detail="Demasiadas redirecciones")

    content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    filename = url.split("/")[-1].split("?")[0] or "imagen-remota"

    return await process_and_store_image(resp.content, filename, content_type)


def _optimize(data: bytes) -> tuple[bytes, str]:
    try:
        img = Image.open(io.BytesIO(data))

        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        w, h = img.size
        if w > MAX_DIM or h > MAX_DIM:
            img.thumbnail((MAX_DIM, MAX_DIM), Image.LANCZOS)

        out = io.BytesIO()
        img.save(out, format="WEBP", quality=WEBP_QUALITY, method=6)
        return out.getvalue(), "image/webp"
    except Exception:
        raise HTTPException(status_code=400, detail="El archivo no es una imagen válida")
