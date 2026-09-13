"""El .xlsx de CONCAR (cabecera y formatos de celda de la plantilla oficial) y el
punto de entrada `construir` que exige el contrato de `generar.py`.
"""
from __future__ import annotations

import io
from typing import Any

from ...modelo import Comprobante, Libro
from ... import partida_doble
from ...formato import Opciones
from ...asiento.resolucion import etiquetas_sub_diario, exigir_requisitos, limites_del_periodo, numerar
from ...asiento.huella import huella
from ...asiento.motor import lineas_del_comprobante
from ..contrato import EXIGE_NUCLEO_ASIENTO
from . import proyeccion
from .datos import (ANCHOS, AUTOFILTRO, CABECERAS, COLUMNAS_FECHA, COLUMNAS_IMPORTE, COLUMNAS_TEXTO, EXIGE, FORMATOS,
                    HOJA, OPCIONES, PANEL)


class CorrelativoDesborda(Exception):
    """Un sub-diario pasaría de 9999: CONCAR numera el asiento con MM + cuatro dígitos (`asiento.numerar`),
    y un quinto dígito no cabe en su importación. `sub_diarios` es {sub-diario: hasta dónde llegaría}."""

    def __init__(self, sub_diarios: dict[str, int]):
        super().__init__("; ".join(f"El sub-diario {s} llegaría a {n}: supera los 4 dígitos que admite CONCAR"
                                   for s, n in sub_diarios.items()))
        self.sub_diarios = sub_diarios


def nombre(libro: Libro, op: Opciones = OPCIONES) -> str:
    return f"CONCAR_{libro.ruc}_{libro.periodo}_{'VENTAS' if libro.es_venta else 'COMPRAS'}{op.extension}"


def escribir_xlsx(filas: list[dict[str, Any]]) -> bytes:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = HOJA
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
    for col, header in CABECERAS["titulos"].items():
        cell = ws[f"{col}1"]
        cell.value, cell.fill, cell.font, cell.alignment = header, fill_titulo, font_titulo, align_titulo
    for col, desc in CABECERAS["notas"].items():
        cell = ws[f"{col}2"]
        cell.value, cell.font, cell.alignment = desc, font_nota, align_nota
    for col, fmt in CABECERAS["formatos"].items():
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
    ws.freeze_panes = PANEL
    ws.auto_filter.ref = AUTOFILTRO
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def construir(libro: Libro, comprobantes: list[Comprobante], contab: dict, correlativos: dict[str, int],
              op: Opciones = OPCIONES) -> tuple[bytes, dict]:
    """Comprobantes (ya seleccionados y en orden) → bytes del .xlsx + resumen para `contab_exportaciones`."""
    if FORMATOS.get(libro.tipo) is None:
        raise ValueError("Tipo de libro no soportado")
    venta = libro.es_venta
    # Lo que CONCAR no puede importar sin: lo del núcleo (tipo con equivalencia, cuenta) y lo que
    # este driver declara en EXIGE (centro de costo donde la cuenta lo lleva, moneda con código).
    exigir_requisitos(comprobantes, contab, venta, EXIGE_NUCLEO_ASIENTO | EXIGE)
    # Los limites del mes del proceso: cada asiento se fecha por comprobante
    # dentro de ellos (regla del 30-ago-2026; el detalle vive en `asiento.lineas_del_comprobante`).
    limites = limites_del_periodo(libro)
    numeros, rangos = numerar(comprobantes, contab, libro.periodo, correlativos, venta)
    # CONCAR numera con MM + cuatro dígitos: un sub-diario que pase de 9999 no se importa. Hasta el
    # 11-sep-2026 lo comprobaba el portal antes de llamar aquí; la regla es de este formato.
    desbordan = {s: r["hasta"] for s, r in rangos.items() if r.get("desborda")}
    if desbordan:
        raise CorrelativoDesborda(desbordan)
    # La contabilidad sale en lineas neutrales; aqui solo se proyectan a las columnas de CONCAR.
    lineas, filas = [], []
    for c in comprobantes:
        propias = lineas_del_comprobante(c, contab, limites, numeros[id(c)], op, venta)
        lineas.extend(propias)
        filas.extend(proyeccion.filas(c, propias, contab))
    # El asiento tiene que cuadrar ANTES de escribir un solo byte. Por construccion siempre
    # cuadra, asi que esto es una red de seguridad: si salta, hay un error de verdad.
    cuadre = partida_doble.exigir(lineas)
    resumen = {
        "filas_excel": len(filas),
        "fechas": "por comprobante (extemporáneos al " + limites[0].strftime("%d/%m/%Y") + ")",
        "sub_diarios": {s: {"etiqueta": etiquetas_sub_diario(contab).get(s, s), **r} for s, r in rangos.items()},
        "debe": str(cuadre.debe), "haber": str(cuadre.haber),
        # La huella del contenido (asiento/huella.py): con ella quien guarde este resumen reconoce la
        # tanda si vuelve a salir. Va aquí porque este resumen es lo que el portal persiste.
        "huella": huella(lineas),
    }
    return escribir_xlsx(filas), resumen
