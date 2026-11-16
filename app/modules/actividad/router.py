from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from app.core.database import get_collection
from app.shared.dependencies import get_current_user, require_roles
from app.shared.responses import serialize_doc, serialize_list

router = APIRouter(prefix="/actividad", tags=["Actividad"])


class CreateActividadDto(BaseModel):
    tipo: str
    descripcion: str
    usuario: Optional[str] = ""
    entidad: Optional[str] = ""
    entidadId: Optional[str] = ""
    metadata: Optional[dict] = None


@router.get("/recientes")
async def find_recientes(current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("actividad")
    docs = await col.find({}).sort("createdAt", -1).limit(20).to_list(None)
    return serialize_list(docs)


@router.get("")
async def find_all(current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("actividad")
    # Purga automática: el historial conserva 1 año (lo usan los informes por fecha)
    await col.delete_many({"createdAt": {"$lt": datetime.now(timezone.utc) - timedelta(days=365)}})
    docs = await col.find({}).sort("createdAt", -1).limit(500).to_list(None)
    return serialize_list(docs)


# ─── Informe de actividad (solo administradores) ──────────────────────────────

ROLES_INFORME = ("super_admin", "admin")

NOMBRES_MODULO = {
    "eventos": "Eventos", "noticias": "Noticias", "especialidades": "Especialidades",
    "autoridades": "Autoridades", "estudiantes": "Estudiantes", "logros": "Logros",
    "users": "Usuarios", "recursos": "Recursos", "uniformes": "Uniformes",
    "consejo": "Consejo estudiantil", "configuracion": "Configuración",
}


def _parse_fecha(valor: str, campo: str) -> datetime:
    try:
        fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Fecha '{campo}' inválida")
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc)


async def _consultar_informe(desde: str, hasta: str, usuario_id: Optional[str]) -> list:
    inicio = _parse_fecha(desde, "desde")
    fin = _parse_fecha(hasta, "hasta")
    if fin < inicio:
        raise HTTPException(status_code=400, detail="La fecha 'hasta' debe ser posterior a 'desde'")
    filtro: dict = {"createdAt": {"$gte": inicio, "$lte": fin}}
    if usuario_id:
        filtro["usuarioId"] = usuario_id
    col = get_collection("actividad")
    return await col.find(filtro).sort("createdAt", 1).to_list(None)


@router.get("/informe")
async def informe(
    desde: str,
    hasta: str,
    usuarioId: Optional[str] = None,
    current_user: dict = Depends(require_roles(*ROLES_INFORME)),
):
    docs = await _consultar_informe(desde, hasta, usuarioId)
    return serialize_list(docs)


@router.get("/informe/excel")
async def informe_excel(
    desde: str,
    hasta: str,
    usuarioId: Optional[str] = None,
    tz: int = 0,
    current_user: dict = Depends(require_roles(*ROLES_INFORME)),
):
    """`tz` = minutos de desfase del navegador (Date.getTimezoneOffset), para mostrar hora local."""
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    docs = await _consultar_informe(desde, hasta, usuarioId)
    zona = timezone(timedelta(minutes=-tz))

    def local(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(zona).replace(tzinfo=None)

    inicio, fin = local(_parse_fecha(desde, "desde")), local(_parse_fecha(hasta, "hasta"))
    generado_por = f"{current_user.get('nombre', '')} {current_user.get('apellido', '')}".strip() or current_user.get("username", "")

    wb = Workbook()
    ws = wb.active
    ws.title = "Informe"
    ws.append(["Informe de actividad del panel administrativo"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([f"Periodo: {inicio:%d/%m/%Y} al {fin:%d/%m/%Y}"])
    ws.append([f"Generado por: {generado_por} el {local(datetime.now(timezone.utc)):%d/%m/%Y %H:%M}"])
    ws.append([f"Total de registros: {len(docs)}"])
    ws.append([])

    encabezado = ["Fecha", "Hora", "Usuario", "Módulo", "Acción", "Detalle"]
    ws.append(encabezado)
    fila_enc = ws.max_row
    for celda in ws[fila_enc]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="1E3A8A")
        celda.alignment = Alignment(horizontal="center")

    for d in docs:
        f = local(d["createdAt"])
        ws.append([
            f.strftime("%d/%m/%Y"),
            f.strftime("%H:%M"),
            d.get("usuario") or "—",
            NOMBRES_MODULO.get(d.get("entidad", ""), d.get("entidad") or "—"),
            d.get("titulo") or "",
            d.get("descripcion") or "",
        ])

    for col, ancho in zip("ABCDEF", (12, 8, 28, 20, 26, 60)):
        ws.column_dimensions[col].width = ancho
    ws.freeze_panes = ws.cell(row=fila_enc + 1, column=1)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    nombre = f"informe-actividad_{inicio:%Y-%m-%d}_{fin:%Y-%m-%d}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.post("")
async def create(dto: CreateActividadDto, current_user: dict = Depends(get_current_user)):
    col = get_collection("actividad")
    data = dto.model_dump()
    data["createdAt"] = datetime.now(timezone.utc)
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    return serialize_doc(doc)


@router.delete("/limpiar")
async def limpiar(current_user: dict = Depends(require_roles("super_admin"))):
    col = get_collection("actividad")
    result = await col.delete_many({})
    return {"deleted": result.deleted_count}


@router.delete("/{id}")
async def delete(id: str, current_user: dict = Depends(require_roles("super_admin", "admin"))):
    col = get_collection("actividad")
    try:
        result = await col.delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return {"message": "Actividad eliminada"}

