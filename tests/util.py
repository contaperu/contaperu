"""Utilidades compartidas por los tests."""
from __future__ import annotations

import json
from pathlib import Path

from contaperu.modelo import Comprobante, Libro

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "golden"
XML = FIXTURES / "xml"

def cargar_golden(nombre_json: str) -> tuple[Libro, list[Comprobante]]:
    datos = json.loads((GOLDEN / nombre_json).read_text(encoding="utf-8"))
    libro = Libro(**datos["libro"])
    return libro, [Comprobante.de_dict(d) for d in datos["comprobantes"]]


def campos(linea: str, palote_final: bool) -> list[str]:
    """Separa una línea en campos. Con palote final (PLE), el último '|' cierra
    la línea y no abre un campo más."""
    if palote_final:
        assert linea.endswith("|"), linea
        linea = linea[:-1]
    return linea.split("|")
