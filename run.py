import uvicorn
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:socket_app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.is_development,
        reload_dirs=["app"] if settings.is_development else None,
    )
