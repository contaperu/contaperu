"""Seleccionar: qué comprobantes salen hacia un destino, cuáles quedan fuera y cuáles bloquean.

- Respeta el orden de entrada: el que ordena es quien llama (la lectura por fecha y serie-número; los golden, tal cual
  vienen).
- Deja fuera lo que el usuario excluyó y los duplicados, y lo que ese destino no lleva (`EXCLUYE_TIPOS`).
"""
from __future__ import annotations

from ..comprobantes.nombre import nombre_del_comprobante
from ..modelo import Comprobante


def etiqueta(c: Comprobante) -> str:
    """El nombre con que una respuesta cita un comprobante: «01 F001-123». Desde la 15.16 es el nombre público
    (`api.nombre_del_comprobante`, que vive en `comprobantes.nombre`) y no una copia: el formato ya salía en
    `errores_de` y quien lo necesitaba fuera lo copiaba byte a byte."""
    return nombre_del_comprobante(c)


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
