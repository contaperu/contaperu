"""Armar un documento `open-accounting` desde el modelo."""
from __future__ import annotations

from ..modelo import Comprobante, Libro
from ..pipeline import preparacion


def documento_de(libro: Libro | dict, comprobantes: list[Comprobante | dict] | None = None, *,
                 lineas: list[dict] | None = None, **extra) -> dict:
    """Un documento `open-accounting` con el libro, los comprobantes y las líneas del asiento que se le den.

    `libro` es un `Libro` o su diccionario; cada comprobante, un `Comprobante` o el suyo. Lo que va en `extra` se añade
    tal cual: son las anotaciones `_*` que el estándar deja pasar."""
    if isinstance(libro, dict):
        libro = preparacion.libro_de({"libro": libro})
    if comprobantes is not None:
        comprobantes = [c if isinstance(c, Comprobante) else Comprobante.de_dict(c) for c in comprobantes]
    return preparacion.documento(libro, comprobantes, lineas, **extra)
