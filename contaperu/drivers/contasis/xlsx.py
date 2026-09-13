"""El .xlsx que importa CONTASIS y el punto de entrada `desde_comprobantes` del contrato."""
from __future__ import annotations

import io
from typing import Any

from ...formato import Opciones
from ...modelo import Comprobante, Libro
from . import datos, proyeccion


def nombre(libro: Libro, op: Opciones = datos.OPCIONES) -> str:
    return f"CONTASIS_{libro.ruc}_{libro.periodo}_{'VENTAS' if libro.es_venta else 'COMPRAS'}{op.extension}"


def build_xlsx(libro: Libro, filas: list[dict[str, Any]]) -> bytes:
    """Las filas, desde la fila 1 —sin las 13 de notas y cabeceras de la plantilla— en la pestaña oficial, cada celda
    con el formato de su clase. Una celda `None` no se escribe."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = datos.HOJAS[libro.tipo]
    columnas = datos.COLUMNAS[libro.tipo]
    for n, fila in enumerate(filas, start=1):
        for letra, _, clase, _ in columnas:
            valor = fila.get(letra)
            if valor is None:
                continue
            celda = ws[f"{letra}{n}"]
            celda.value = valor
            celda.number_format = datos.FORMATO_CELDA[clase]
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def desde_comprobantes(libro: Libro, comprobantes: list[Comprobante], contab: dict,
                       op: Opciones = datos.OPCIONES) -> tuple[bytes, dict]:
    """Comprobantes → el .xlsx y su resumen. Llegan ya seleccionados, con la cuenta exigida y sin nada que no quepa
    (lo hace el núcleo antes de llamar); una fila por comprobante, en el orden en que llegan."""
    filas = [proyeccion.fila(c, libro, contab, op) for c in comprobantes]
    return build_xlsx(libro, filas), {"filas": len(filas)}
