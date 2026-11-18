"""
Dirección pública del backend para armar las URLs de imágenes y documentos subidos.

Antes se usaba siempre settings.BACKEND_URL. Si en el servidor no estaba configurado
(o seguía en el valor por defecto http://localhost:8000), los archivos subidos en
producción quedaban guardados con una URL de localhost y no abrían desde fuera.

Regla:
- Si BACKEND_URL apunta a una dirección pública, se usa tal cual.
- Si apunta a localhost/127.0.0.1 y la petición llegó por otra dirección (por ejemplo
  a través de nginx con el dominio público), se usa la dirección con la que llegó la
  petición (respetando X-Forwarded-Proto / X-Forwarded-Host del proxy).
"""
from urllib.parse import urlsplit
from fastapi import Request
from app.core.config import settings

_LOOPBACK = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _es_loopback(host: str) -> bool:
    return (host or "").split(":")[0].strip("[]").lower() in _LOOPBACK


def public_base_url(request: Request | None = None) -> str:
    configurada = (settings.BACKEND_URL or "").rstrip("/")
    if request is None or not _es_loopback(urlsplit(configurada).hostname or ""):
        return configurada

    headers = request.headers
    host = (headers.get("x-forwarded-host") or headers.get("host") or "").split(",")[0].strip()
    if not host or _es_loopback(host):
        return configurada
    proto = (headers.get("x-forwarded-proto") or request.url.scheme or "http").split(",")[0].strip()
    return f"{proto}://{host}"
