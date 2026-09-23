"""
Descarga de archivos públicos de Google Sheets / Google Drive para
importarlos como Boscómetro, reutilizando el mismo parser de Excel que
ya se usa para archivos subidos manualmente (excel_parser.py).

Solo soporta archivos públicos o compartidos como "Cualquiera con el
enlace" — no hay integración con la API oficial de Google ni OAuth.
"""
import re
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from app.shared.url_safety import assert_safe_url

MAX_REDIRECTS = 5
ACCESO_DENEGADO_MSG = (
    "No se puede acceder a este archivo de Google Drive. "
    "Verifica que el archivo tenga permisos de acceso adecuados "
    "(compártelo como 'Cualquiera con el enlace')."
)

_SHEETS_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")
_DRIVE_FILE_ID_RE = re.compile(r"/file/d/([a-zA-Z0-9_-]+)")
_DRIVE_ID_QUERY_RE = re.compile(r"[?&]id=([a-zA-Z0-9_-]+)")


def _resolver_url_exportacion(source_url: str) -> str:
    parsed = urlparse(source_url)
    if parsed.hostname not in {"docs.google.com", "drive.google.com"}:
        raise HTTPException(status_code=400, detail="El enlace debe ser de Google Sheets o Google Drive.")

    m = _SHEETS_ID_RE.search(source_url)
    if m:
        return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=xlsx"

    m = _DRIVE_FILE_ID_RE.search(source_url) or _DRIVE_ID_QUERY_RE.search(source_url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"

    raise HTTPException(status_code=400, detail="No se pudo identificar el archivo en el enlace proporcionado.")


async def descargar_excel_desde_google(source_url: str, max_bytes: int) -> bytes:
    export_url = _resolver_url_exportacion(source_url)
    assert_safe_url(export_url)

    url = export_url
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(MAX_REDIRECTS):
            resp = await client.get(url, follow_redirects=False)
            if resp.is_redirect:
                location = resp.headers.get("location")
                if not location:
                    raise HTTPException(status_code=400, detail="Redirección sin destino")
                url = str(httpx.URL(url).join(location))
                if urlparse(url).hostname == "accounts.google.com":
                    raise HTTPException(status_code=400, detail=ACCESO_DENEGADO_MSG)
                assert_safe_url(url)
                continue
            break
        else:
            raise HTTPException(status_code=400, detail="Demasiadas redirecciones")

    if resp.status_code == 404:
        raise HTTPException(status_code=400, detail="El archivo no existe o fue eliminado.")
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=ACCESO_DENEGADO_MSG)

    content_type = resp.headers.get("content-type", "").split(";")[0].strip()
    if content_type.startswith("text/html"):
        raise HTTPException(status_code=400, detail=ACCESO_DENEGADO_MSG)

    if not resp.content:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(resp.content) > max_bytes:
        raise HTTPException(status_code=400, detail="El archivo supera el límite de 10 MB")

    return resp.content
