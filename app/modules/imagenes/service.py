import io
from datetime import datetime, timezone
from PIL import Image
import httpx
from app.core.database import get_gridfs
from app.core.config import settings


MAX_DIM = 1920
WEBP_QUALITY = 82


async def process_and_store_image(data: bytes, filename: str, content_type: str) -> dict:
    original_bytes = len(data)

    if content_type != "image/svg+xml":
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
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(source_url, follow_redirects=True)
        resp.raise_for_status()

    content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    filename = source_url.split("/")[-1].split("?")[0] or "imagen-remota"

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
        return data, "image/webp"
