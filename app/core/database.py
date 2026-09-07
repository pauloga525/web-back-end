from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from .config import settings

_client: AsyncIOMotorClient = None
_db = None
_gridfs: AsyncIOMotorGridFSBucket = None
_gridfs_documentos: AsyncIOMotorGridFSBucket = None


async def connect_db():
    global _client, _db, _gridfs, _gridfs_documentos
    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    _db = _client.get_default_database()
    _gridfs = AsyncIOMotorGridFSBucket(_db, bucket_name="images")
    # Bucket separado (colecciones documentos.files/documentos.chunks) para
    # PDFs/Word — mismo mecanismo que las imágenes (chunkeado, no infla un
    # documento de Mongo como haría un Base64 embebido), pero aparte para no
    # mezclar archivos binarios de distinto tipo en la misma colección.
    _gridfs_documentos = AsyncIOMotorGridFSBucket(_db, bucket_name="documentos")
    print(f"MongoDB conectado: {settings.MONGODB_URI}")


async def close_db():
    global _client
    if _client:
        _client.close()


def get_db():
    return _db


def get_gridfs() -> AsyncIOMotorGridFSBucket:
    return _gridfs


def get_gridfs_documentos() -> AsyncIOMotorGridFSBucket:
    return _gridfs_documentos


def get_collection(name: str):
    return _db[name]
