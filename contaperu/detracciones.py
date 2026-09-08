"""La detracción del comprobante, contrastada con la tabla del contribuyente.

Existe por un error concreto y caro: las IAs que leen facturas confunden la **retención del
IGV** —el 3 % que retiene un agente de retención cuando la factura pasa de S/ 700, y que no
toca el registro de compras ni el asiento— con una **detracción**, y devuelven un código
inventado, casi siempre «000». Ese código llegaba al asiento como si fuera real.

La regla, de un contador: **si el código no está en la tabla de detracciones del contribuyente,
la detracción queda en blanco**. Nada se adivina; si toca, la elige una persona.

La tabla efectiva sale de la configuración (`detraccion_codigos`), que es la misma que usa el
asiento — así no hay dos verdades sobre qué códigos existen.
"""
from __future__ import annotations

from typing import Iterable

from .modelo import Comprobante


def codigos_de(contab: dict) -> set[str]:
    """Los códigos de detracción que el contribuyente reconoce."""
    return {str(k) for k in (contab.get("detraccion_codigos") or {})}


def normalizar_una(det, codigos: set[str]) -> dict | None:
    """El bloque de detracción con el código a 3 dígitos si está en la tabla; si no, `None`."""
    if not isinstance(det, dict):
        return None
    cod = str(det.get("codigo") or "").strip()
    if cod.isdigit():
        cod = cod.zfill(3)
    if not cod or cod not in codigos:
        return None
    return dict(det, codigo=cod)


def normalizar(comprobantes: Iterable[Comprobante], contab: dict) -> list[Comprobante]:
    """Deja en blanco la detracción cuyo código no reconoce el contribuyente.

    Devuelve **solo los comprobantes que cambió**, para que quien llame sepa qué guardar.
    """
    con = [c for c in comprobantes if c.detraccion]
    if not con:
        return []
    codigos = codigos_de(contab)
    cambiados = []
    for c in con:
        nuevo = normalizar_una(c.detraccion, codigos)
        if nuevo != c.detraccion:
            c.detraccion = nuevo
            cambiados.append(c)
    return cambiados


# Conciliar las constancias del Banco de la Nación —el segundo tiempo, que pasa la detracción
# de PROVISIONADO a PAGADO— todavía no está implementado: hace falta un archivo de constancias
# real para saber su formato exacto, y en este proyecto ninguna regla se escribe de memoria.
# El estándar ya tiene el hueco (`detraccion.estado`, `nro_constancia`, `fecha_constancia`).
