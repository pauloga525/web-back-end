from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from .config import settings

_client: AsyncIOMotorClient = None
_db = None
_gridfs: AsyncIOMotorGridFSBucket = None


def connect_db():
    global _client, _db, _gridfs
    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    _db = _client.get_default_database()
    _gridfs = AsyncIOMotorGridFSBucket(_db, bucket_name="images")
    print(f"MongoDB conectado: {settings.MONGODB_URI}")


def close_db():
    global _client
    if _client:
        _client.close()


def get_db():
    return _db


def get_gridfs() -> AsyncIOMotorGridFSBucket:
    return _gridfs


def get_collection(name: str):
    return _db[name]
