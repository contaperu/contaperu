"""El .xlsx de CONCAR (cabecera y formatos de celda de la plantilla oficial) y el
punto de entrada `construir` que exige el contrato de `generar.py`.
"""
from __future__ import annotations

import calendar
import io
from datetime import date
from decimal import Decimal
from typing import Any

from ...modelo import Comprobante, Libro
from ... import partida_doble
from ...asiento.lineas import a_lineas
from ...formato import Opciones
from ...asiento.construir import (MonedaSinCodigo, SinCuenta, TipoSinMapa, asiento, mes_del_libro,
                      etiquetas_sub_diario, filas_sin_cuenta, monedas_sin_codigo, numerar, tipos_sin_mapa)
from ...asiento.datos import (ANCHOS, COLUMNAS_FECHA, COLUMNAS_IMPORTE, COLUMNAS_TEXTO, D2,
                    EXCEL_HEADERS, FORMATOS, OPCIONES)


def build_xlsx(filas: list[dict[str, Any]]) -> bytes:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "CONCAR"
    # Formato de la plantilla oficial de CONCAR: titulos
    # en azul marino con letra blanca, notas sin relleno con la fila alta, panel
    # congelado en A4 y autofiltro sobre la fila de formatos.
    fill_titulo = PatternFill(start_color="191970", end_color="191970", fill_type="solid")
    font_titulo = Font(name="Aptos Narrow", size=11, bold=True, color="FFFFFF")
    font_nota = Font(name="Aptos Narrow", size=11)
    font_datos = Font(name="Aptos Narrow", size=11)
    align_titulo = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_nota = Alignment(vertical="top", wrap_text=True)
    align_formato = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for col, header in EXCEL_HEADERS["row1"].items():
        cell = ws[f"{col}1"]
        cell.value, cell.fill, cell.font, cell.alignment = header, fill_titulo, font_titulo, align_titulo
    for col, desc in EXCEL_HEADERS["row2"].items():
        cell = ws[f"{col}2"]
        cell.value, cell.font, cell.alignment = desc, font_nota, align_nota
    for col, fmt in EXCEL_HEADERS["row3"].items():
        cell = ws[f"{col}3"]
        cell.value, cell.font, cell.alignment = fmt, font_nota, align_formato
    ws["A3"].font = Font(name="Aptos Narrow", size=11, bold=True)
    ws.row_dimensions[1].height = 45
    ws.row_dimensions[2].height = 120
    ws.row_dimensions[3].height = 30
    for idx, fila in enumerate(filas, start=4):
        ws.row_dimensions[idx].height = 15.8
        for col, valor in fila.items():
            if valor == "" or valor is None:
                continue
            cell = ws[f"{col}{idx}"]
            cell.value = valor
            cell.font = font_datos
            if col in COLUMNAS_FECHA:
                cell.number_format = "dd/mm/yyyy"
            elif col in COLUMNAS_IMPORTE and isinstance(valor, (int, float)):
                cell.number_format = "#,##0.00"
            elif col in COLUMNAS_TEXTO:
                cell.number_format = "@"
    for col, ancho in ANCHOS.items():
        ws.column_dimensions[col].width = ancho
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = "A3:AO3"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def construir(libro: Libro, comprobantes: list[Comprobante], contab: dict, correlativos: dict[str, int],
              op: Opciones = OPCIONES) -> tuple[bytes, dict]:
    """Comprobantes (ya seleccionados y en orden) → bytes del .xlsx + resumen para `contab_exportaciones`."""
    if FORMATOS.get(libro.tipo) is None:
        raise ValueError("Tipo de libro no soportado")
    venta = libro.es_venta
    sin_mapa = tipos_sin_mapa(comprobantes, contab)
    if sin_mapa:
        raise TipoSinMapa(sin_mapa)
    sin_moneda = monedas_sin_codigo(comprobantes, contab)
    if sin_moneda:
        raise MonedaSinCodigo(sin_moneda)
    sin = filas_sin_cuenta(comprobantes, contab, venta)
    if sin:
        raise SinCuenta(sin)
    # Los limites del mes del proceso: cada asiento se fecha por comprobante
    # dentro de ellos (regla del 30-ago-2026; el detalle vive en asiento()).
    mes = mes_del_libro(libro)
    numeros, rangos = numerar(comprobantes, contab, libro.periodo, correlativos, venta)
    filas: list[dict[str, Any]] = []
    for c in comprobantes:
        filas.extend(asiento(c, contab, mes, numeros[id(c)], op, venta))
    # El asiento tiene que cuadrar ANTES de escribir un solo byte. Por construccion siempre
    # cuadra, asi que esto es una red de seguridad: si salta, hay un error de verdad.
    cuadre = partida_doble.exigir(a_lineas(filas, contab))
    resumen = {
        "filas_excel": len(filas), "fechas": "por comprobante (extemporáneos al " + mes[0].strftime("%d/%m/%Y") + ")",
        "sub_diarios": {s: {"etiqueta": etiquetas_sub_diario(contab).get(s, s), **r} for s, r in rangos.items()},
        "debe": str(cuadre.debe), "haber": str(cuadre.haber),
    }
    return build_xlsx(filas), resumen
