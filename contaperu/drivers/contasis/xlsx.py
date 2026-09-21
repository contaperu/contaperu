"""El .xlsx que importa CONTASIS y el punto de entrada `desde_comprobantes` del contrato."""
from __future__ import annotations

from typing import Any

from ...modelo import Comprobante, Libro
from ..kit import Opciones, nombre_de_archivo
from ..kit import xlsx as kit_xlsx
from . import datos, proyeccion


def nombre(libro: Libro, opciones: Opciones = datos.OPCIONES) -> str:
    return nombre_de_archivo(datos.NOMBRE, libro, opciones)


def escribir_xlsx(libro: Libro, filas: list[dict[str, Any]]) -> bytes:
    """Las filas, desde la fila 1 —sin las 13 de notas y cabeceras de la plantilla— en la pestaña oficial, cada celda
    con el formato de su clase. Una celda `None` no se escribe."""
    libro_excel, hoja = kit_xlsx.libro_con_hoja(datos.HOJAS[libro.tipo])
    columnas = datos.COLUMNAS[libro.tipo]
    for letra, _, _, _ in columnas:
        hoja.column_dimensions[letra].width = datos.ANCHOS[libro.tipo][letra]
    for numero_fila, fila in enumerate(filas, start=1):
        for letra, _, clase, _ in columnas:
            valor = fila.get(letra)
            if valor is None:
                continue
            celda = hoja[f"{letra}{numero_fila}"]
            celda.value = valor
            celda.number_format = datos.FORMATO_CELDA[clase]
    return kit_xlsx.a_bytes(libro_excel)


def desde_comprobantes(libro: Libro, comprobantes: list[Comprobante], config: dict,
                       opciones: Opciones = datos.OPCIONES) -> tuple[bytes, dict]:
    """Comprobantes → el .xlsx y su resumen. Llegan ya seleccionados, con la cuenta exigida y sin nada que no quepa
    (lo hace el núcleo antes de llamar); una fila por comprobante, en el orden en que llegan."""
    filas = [proyeccion.fila(c, libro, config, opciones) for c in comprobantes]
    return escribir_xlsx(libro, filas), {"filas": len(filas)}
