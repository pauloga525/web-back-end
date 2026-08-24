import socketio

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid, environ):
    print(f"WS conectado: {sid}")


@sio.event
async def disconnect(sid):
    print(f"WS desconectado: {sid}")


async def emit_event(event: str, data: dict):
    await sio.emit(event, data)


async def notify_created(entity: str, data: dict):
    await emit_event(f"{entity}:creado", data)


async def notify_updated(entity: str, data: dict):
    await emit_event(f"{entity}:actualizado", data)


async def notify_deleted(entity: str, entity_id: str):
    await emit_event(f"{entity}:eliminado", {"id": entity_id})


async def notify_config_updated(clave: str, data: dict):
    await emit_event(f"configuracion:{clave}:actualizada", data)
