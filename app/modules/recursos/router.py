from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Body
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from bson import ObjectId
from datetime import datetime, timezone
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list, clean_update
from app.modules.websocket.manager import notify_created, notify_updated, notify_deleted
from .excel_parser import parsear_tabla_excel, parsear_grafico_excel
from .google_drive import descargar_excel_desde_google

router = APIRouter(prefix="/recursos", tags=["Recursos"])

# ── Boscómetro: tablas y gráficos importados desde Excel ─────────────────
# Se guardan como recursos más (tipo='boscometro_tabla'/'boscometro_grafico')
# para reusar el mismo almacenamiento/listado que biblioteca/instructivos,
# en vez de crear una colección aparte.
EXCEL_EXTENSIONES = {".xlsx", ".xls"}
EXCEL_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


def _extension(filename: str) -> str:
    idx = filename.rfind(".")
    return filename[idx:].lower() if idx != -1 else ""


async def _leer_excel(file: UploadFile) -> bytes:
    ext = _extension(file.filename or "")
    if ext not in EXCEL_EXTENSIONES:
        raise HTTPException(status_code=400, detail="Solo se permiten archivos Excel (.xlsx, .xls)")
    data = await file.read()
    if len(data) > EXCEL_MAX_BYTES:
        raise HTTPException(status_code=400, detail="El archivo supera el límite de 10 MB")
    return data


async def _siguiente_orden(col, tipo: str) -> int:
    ultimo = await col.find({"tipo": tipo}).sort("orden", -1).limit(1).to_list(1)
    return (ultimo[0]["orden"] + 1) if ultimo else 0


async def _siguiente_orden_seccion(col) -> int:
    """Orden compartido por la tabla y el gráfico de una misma sección, para
    poder ordenar secciones completas en el listado combinado del frontend."""
    ultimo = await col.find({"tipo": {"$in": ["boscometro_tabla", "boscometro_grafico"]}}) \
        .sort("orden", -1).limit(1).to_list(1)
    return (ultimo[0]["orden"] + 1) if ultimo else 0


class EnlaceRecursoDto(BaseModel):
    """Un enlace adicional dentro de un recurso (ej: varios videos en un mismo instructivo)."""
    url: str
    descripcion: Optional[str] = ""


class UpdateRecursoDto(BaseModel):
    model_config = ConfigDict(extra='ignore')
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    tipo: Optional[str] = None
    url: Optional[str] = None
    imagen: Optional[str] = None
    categoria: Optional[str] = None
    tags: Optional[List[str]] = None
    enlaces: Optional[List[EnlaceRecursoDto]] = None
    publicado: Optional[bool] = None
    orden: Optional[int] = None


class CreateRecursoDto(BaseModel):
    titulo: str
    descripcion: Optional[str] = ""
    tipo: Optional[str] = ""
    url: Optional[str] = ""
    imagen: Optional[str] = ""
    categoria: Optional[str] = ""
    tags: Optional[List[str]] = []
    enlaces: Optional[List[EnlaceRecursoDto]] = []
    publicado: Optional[bool] = False
    orden: Optional[int] = 0


@router.get("/publicos")
async def find_publicos():
    col = get_collection("recursos")
    docs = await col.find({"publicado": True}).sort("orden", 1).to_list(None)
    return serialize_list(docs)


@router.get("")
async def find_all(current_user: dict = Depends(get_current_user)):
    col = get_collection("recursos")
    docs = await col.find({}).sort("orden", 1).to_list(None)
    return serialize_list(docs)


@router.get("/{id}")
async def find_one(id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("recursos")
    try:
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    return serialize_doc(doc)


@router.post("")
async def create(dto: CreateRecursoDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("recursos")
    data = dto.model_dump()
    data["createdAt"] = datetime.now(timezone.utc)
    data["updatedAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    if out.get("publicado"):
        try:
            await notify_created("recurso", out)
        except Exception:
            pass
    return out


@router.put("/{id}")
async def update(id: str, dto: UpdateRecursoDto, current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))):
    col = get_collection("recursos")
    data = clean_update(dto.model_dump(exclude_none=True))
    data["updatedAt"] = datetime.now(timezone.utc)
    try:
        await col.update_one({"_id": ObjectId(id)}, {"$set": data})
        doc = await col.find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    out = serialize_doc(doc)
    if out.get("publicado"):
        try:
            await notify_updated("recurso", out)
        except Exception:
            pass
    return out


@router.delete("/{id}")
async def delete(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("recursos")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    try:
        await notify_deleted("recurso", id)
    except Exception:
        pass
    return {"message": "Recurso eliminado"}


@router.post("/boscometro/tablas")
async def importar_tabla_boscometro(
    titulo: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor")),
):
    contenido = await _leer_excel(file)
    try:
        filas = parsear_tabla_excel(contenido)
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo Excel. Verifica que no esté dañado.")
    if not filas:
        raise HTTPException(status_code=400, detail="El archivo no tiene datos para importar.")

    col = get_collection("recursos")
    data = {
        "titulo": titulo, "tipo": "boscometro_tabla", "descripcion": "", "url": "", "imagen": "",
        "categoria": "", "tags": [], "enlaces": [], "filas": filas,
        "publicado": True, "orden": await _siguiente_orden(col, "boscometro_tabla"),
        "createdAt": datetime.now(timezone.utc), "updatedAt": datetime.now(timezone.utc),
    }
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    try:
        await notify_created("recurso", out)
    except Exception:
        pass
    return out


@router.post("/boscometro/tablas/desde-url")
async def importar_tabla_boscometro_desde_url(
    body: dict = Body(...),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor")),
):
    titulo = body.get("titulo")
    source_url = body.get("sourceUrl") or body.get("source_url")
    if not titulo:
        raise HTTPException(status_code=400, detail="titulo es requerido")
    if not source_url:
        raise HTTPException(status_code=400, detail="sourceUrl es requerido")

    contenido = await descargar_excel_desde_google(source_url, EXCEL_MAX_BYTES)
    try:
        filas = parsear_tabla_excel(contenido)
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo. Verifica que sea un Google Sheet o un Excel válido.")
    if not filas:
        raise HTTPException(status_code=400, detail="El archivo no tiene datos para importar.")

    col = get_collection("recursos")
    data = {
        "titulo": titulo, "tipo": "boscometro_tabla", "descripcion": "", "url": "", "imagen": "",
        "categoria": "", "tags": [], "enlaces": [], "filas": filas,
        "publicado": True, "orden": await _siguiente_orden(col, "boscometro_tabla"),
        "createdAt": datetime.now(timezone.utc), "updatedAt": datetime.now(timezone.utc),
    }
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    try:
        await notify_created("recurso", out)
    except Exception:
        pass
    return out


@router.post("/boscometro/graficos")
async def importar_grafico_boscometro(
    titulo: str = Form(...),
    subtitulo: str = Form(""),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor")),
):
    contenido = await _leer_excel(file)
    try:
        datos = parsear_grafico_excel(contenido)
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo Excel. Verifica que no esté dañado.")
    if not datos:
        raise HTTPException(status_code=400, detail="No se encontraron datos válidos (se esperan 2 columnas: curso y total).")

    col = get_collection("recursos")
    data = {
        "titulo": titulo, "tipo": "boscometro_grafico", "descripcion": subtitulo, "url": "", "imagen": "",
        "categoria": "", "tags": [], "enlaces": [], "datos": datos,
        "publicado": True, "orden": await _siguiente_orden(col, "boscometro_grafico"),
        "createdAt": datetime.now(timezone.utc), "updatedAt": datetime.now(timezone.utc),
    }
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    try:
        await notify_created("recurso", out)
    except Exception:
        pass
    return out


@router.post("/boscometro/graficos/desde-url")
async def importar_grafico_boscometro_desde_url(
    body: dict = Body(...),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor")),
):
    titulo = body.get("titulo")
    subtitulo = body.get("subtitulo", "")
    source_url = body.get("sourceUrl") or body.get("source_url")
    if not titulo:
        raise HTTPException(status_code=400, detail="titulo es requerido")
    if not source_url:
        raise HTTPException(status_code=400, detail="sourceUrl es requerido")

    contenido = await descargar_excel_desde_google(source_url, EXCEL_MAX_BYTES)
    try:
        datos = parsear_grafico_excel(contenido)
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo. Verifica que sea un Google Sheet o un Excel válido.")
    if not datos:
        raise HTTPException(status_code=400, detail="No se encontraron datos válidos (se esperan 2 columnas: curso y total).")

    col = get_collection("recursos")
    data = {
        "titulo": titulo, "tipo": "boscometro_grafico", "descripcion": subtitulo, "url": "", "imagen": "",
        "categoria": "", "tags": [], "enlaces": [], "datos": datos,
        "publicado": True, "orden": await _siguiente_orden(col, "boscometro_grafico"),
        "createdAt": datetime.now(timezone.utc), "updatedAt": datetime.now(timezone.utc),
    }
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    out = serialize_doc(doc)
    try:
        await notify_created("recurso", out)
    except Exception:
        pass
    return out


ERROR_HOJAS_MSG = (
    "El archivo debe tener 2 hojas: la primera con la tabla y la segunda "
    "con los datos del gráfico (curso y total)."
)


async def _crear_seccion_boscometro(col, titulo: str, subtitulo: str, contenido: bytes) -> dict:
    try:
        filas = parsear_tabla_excel(contenido, sheet_index=0)
        datos = parsear_grafico_excel(contenido, sheet_index=1)
    except IndexError:
        raise HTTPException(status_code=400, detail=ERROR_HOJAS_MSG)
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo. Verifica que no esté dañado.")
    if not filas:
        raise HTTPException(status_code=400, detail="La primera hoja no tiene datos para la tabla.")
    if not datos:
        raise HTTPException(status_code=400, detail="La segunda hoja no tiene datos válidos para el gráfico (se esperan 2 columnas: curso y total).")

    seccion_id = str(ObjectId())
    orden = await _siguiente_orden_seccion(col)
    ahora = datetime.now(timezone.utc)

    data_tabla = {
        "titulo": titulo, "tipo": "boscometro_tabla", "descripcion": "", "url": "", "imagen": "",
        "categoria": "", "tags": [], "enlaces": [], "filas": filas, "seccionId": seccion_id,
        "publicado": True, "orden": orden, "createdAt": ahora, "updatedAt": ahora,
    }
    data_grafico = {
        "titulo": titulo, "tipo": "boscometro_grafico", "descripcion": subtitulo, "url": "", "imagen": "",
        "categoria": "", "tags": [], "enlaces": [], "datos": datos, "seccionId": seccion_id,
        "publicado": True, "orden": orden, "createdAt": ahora, "updatedAt": ahora,
    }

    result_tabla = await col.insert_one(data_tabla)
    result_grafico = await col.insert_one(data_grafico)
    doc_tabla = await col.find_one({"_id": result_tabla.inserted_id})
    doc_grafico = await col.find_one({"_id": result_grafico.inserted_id})
    out_tabla = serialize_doc(doc_tabla)
    out_grafico = serialize_doc(doc_grafico)

    for out in (out_tabla, out_grafico):
        try:
            await notify_created("recurso", out)
        except Exception:
            pass

    return {"tabla": out_tabla, "grafico": out_grafico}


@router.post("/boscometro/secciones")
async def importar_seccion_boscometro(
    titulo: str = Form(...),
    subtitulo: str = Form(""),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor")),
):
    contenido = await _leer_excel(file)
    col = get_collection("recursos")
    return await _crear_seccion_boscometro(col, titulo, subtitulo, contenido)


@router.post("/boscometro/secciones/desde-url")
async def importar_seccion_boscometro_desde_url(
    body: dict = Body(...),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor")),
):
    titulo = body.get("titulo")
    subtitulo = body.get("subtitulo", "")
    source_url = body.get("sourceUrl") or body.get("source_url")
    if not titulo:
        raise HTTPException(status_code=400, detail="titulo es requerido")
    if not source_url:
        raise HTTPException(status_code=400, detail="sourceUrl es requerido")

    contenido = await descargar_excel_desde_google(source_url, EXCEL_MAX_BYTES)
    col = get_collection("recursos")
    return await _crear_seccion_boscometro(col, titulo, subtitulo, contenido)

