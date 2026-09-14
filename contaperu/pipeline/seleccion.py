"""Seleccionar: qué comprobantes salen hacia un destino, cuáles quedan fuera y cuáles bloquean.

- Respeta el orden de entrada: el que ordena es quien llama (la lectura por fecha y serie-número; los golden, tal cual
  vienen).
- Deja fuera lo que el usuario excluyó y los duplicados, y lo que ese destino no lleva (`EXCLUYE_TIPOS`).
"""
from __future__ import annotations

from ..modelo import Comprobante, serie_y_numero


def etiqueta(c: Comprobante) -> str:
    return f"{c.tipo_cp} {serie_y_numero(c.serie, c.numero)}".strip()


def errores_de(comprobantes: list[Comprobante]) -> list[dict]:
    return [
        {
            "indice": i,
            "comprobante": etiqueta(c),
            "observaciones": [o.a_dict() for o in c.observaciones if o.nivel == "error"],
        }
        for i, c in enumerate(comprobantes)
        if c.tiene_errores
    ]


def seleccionar(comprobantes: list[Comprobante]) -> list[Comprobante]:
    return [c for c in comprobantes if not c.excluida and c.estado != "duplicada"]


def fuera_de(comprobantes: list[Comprobante], tipos) -> list[Comprobante]:
    """Los que este driver no puede llevar (hoy: el recibo por honorarios no se
    anota en el registro que se declara a SUNAT, pero sí en el asiento contable)."""
    return [c for c in comprobantes if c.tipo_cp in (tipos or frozenset())]
