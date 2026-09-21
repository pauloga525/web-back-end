"""
Parseo de archivos .xlsx/.xls subidos desde el panel admin para la sección
Boscómetro: convierte una hoja de Excel en datos estructurados (JSON) que
luego se guardan en Mongo, en vez de reprocesar el archivo en cada visita.

Dos formatos soportados:
- Tabla: cualquier hoja con celdas libres → cada fila se convierte en una
  lista de textos. Las filas con alguna celda con color de fondo (como la
  fila azul "EVENTOS 8VO A 10MO EGB" del Excel original) se marcan como
  encabezado para que el frontend las resalte.
- Gráfico: hoja de 2 columnas (curso, total) → lista de puntos para un
  gráfico de barras.
"""
from datetime import datetime, date
from io import BytesIO
from typing import Any

import openpyxl


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _tiene_relleno(cell) -> bool:
    """True si la celda tiene un color de fondo (no blanco/transparente)."""
    fill = getattr(cell, "fill", None)
    fg = getattr(fill, "fgColor", None) if fill else None
    rgb = getattr(fg, "rgb", None) if fg else None
    if not rgb or not isinstance(rgb, str):
        return False
    return rgb not in ("00000000", "FFFFFFFF")


def parsear_tabla_excel(contenido: bytes) -> list[dict]:
    wb = openpyxl.load_workbook(BytesIO(contenido), data_only=True)
    ws = wb.worksheets[0]

    filas_crudas: list[dict] = []
    for row in ws.iter_rows():
        valores = [_cell_text(c.value) for c in row]
        if not any(valores):
            continue  # ignora filas completamente vacías
        filas_crudas.append({
            "valores": valores,
            "esEncabezado": any(_tiene_relleno(c) for c in row),
        })

    if not filas_crudas:
        return []

    # Recorta columnas vacías sobrantes al final (el rango usado de la hoja
    # suele ser más ancho que los datos reales).
    max_col = 0
    for f in filas_crudas:
        for i in range(len(f["valores"]) - 1, -1, -1):
            if f["valores"][i]:
                max_col = max(max_col, i)
                break

    return [{"valores": f["valores"][:max_col + 1], "esEncabezado": f["esEncabezado"]} for f in filas_crudas]


def parsear_grafico_excel(contenido: bytes) -> list[dict]:
    wb = openpyxl.load_workbook(BytesIO(contenido), data_only=True)
    ws = wb.worksheets[0]

    datos: list[dict] = []
    for row in ws.iter_rows():
        if len(row) < 2:
            continue
        curso = _cell_text(row[0].value)
        total_raw = row[1].value
        if not curso or total_raw is None:
            continue
        try:
            total = float(total_raw)
        except (TypeError, ValueError):
            continue
        datos.append({"curso": curso, "total": total})

    return datos
