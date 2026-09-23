import ipaddress
import socket
from urllib.parse import urlparse
from fastapi import HTTPException

ALLOWED_URL_SCHEMES = {"http", "https"}


def is_safe_host(hostname: str) -> bool:
    """Rechaza hosts que resuelvan a rangos de IP privados/loopback/link-local/reservados,
    para evitar que el servidor sea usado como proxy hacia su propia red (SSRF)."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def assert_safe_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_URL_SCHEMES or not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL inválida o esquema no permitido")
    if not is_safe_host(parsed.hostname):
        raise HTTPException(status_code=400, detail="No se permite acceder a esa dirección")
