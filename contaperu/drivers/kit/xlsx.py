"""Un libro de Excel con su hoja, y sus bytes. openpyxl se importa al usarlo: quien no escribe Excel no lo necesita."""
from __future__ import annotations

import io
from typing import Any


def libro_con_hoja(titulo: str) -> tuple[Any, Any]:
    """Un libro nuevo y su única hoja, con `titulo`."""
    import openpyxl

    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = titulo
    return libro, hoja


def a_bytes(libro: Any) -> bytes:
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
