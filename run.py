import uvicorn
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings

if __name__ == "__main__":
    # host=127.0.0.1: Uvicorn solo escucha en loopback. En producción,
    # nginx corre en la misma máquina y hace de reverse proxy con TLS
    # hacia este puerto; así el puerto de la app nunca queda expuesto
    # directo a la red pública, sea lo que sea que diga el firewall.
    uvicorn.run(
        "app.main:socket_app",
        host="127.0.0.1" if not settings.is_development else "0.0.0.0",
        port=settings.PORT,
        reload=settings.is_development,
        reload_dirs=["app"] if settings.is_development else None,
    )
