"""La detracción del comprobante, contrastada con la tabla del contribuyente.

Existe por un error concreto y caro: las IAs que leen facturas confunden la **retención del
IGV** —el 3 % que retiene un agente de retención cuando la factura pasa de S/ 700, y que no
toca el registro de compras ni el asiento— con una **detracción**, y devuelven un código
inventado, casi siempre «000». Ese código llegaba al asiento como si fuera real.

La regla, de un contador: **si el código no está en la tabla de detracciones del contribuyente,
la detracción queda en blanco**. Nada se adivina; si toca, la elige una persona.

La tabla efectiva sale de la configuración (`detraccion_codigos`), que es la misma que usa el
asiento — así no hay dos verdades sobre qué códigos existen.

**Y el monto lo calcula el motor, una sola vez** (10-sep-2026). Hasta ese día había dos cifras: la
del asiento (total × tasa en soles enteros) y la que enseñaba el portal —calculada en el navegador con
decimales, o la que la IA leyó del PDF—, y no siempre coincidían. Ahora `monto_detraccion()` es la única: la usan
el asiento y `normalizar()`, y lo que ve la persona es lo que va a CONCAR.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

from .modelo import CENTIMO, Comprobante, a_decimal, texto_tasa


def codigos_de(config: dict) -> set[str]:
    """Los códigos de detracción que el contribuyente reconoce."""
    return {str(k) for k in (config.get("detraccion_codigos") or {})}


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


def tasa_de_tabla(codigo: Any, config: dict) -> Decimal:
    """La tasa que el contribuyente tiene para ese código en su tabla; 0 si no la tiene."""
    return a_decimal((config.get("detraccion_tasas") or {}).get(str(codigo or "").strip()))


def tasa_detraccion(c: Comprobante, config: dict) -> Decimal:
    """La tasa con la que se calcula: la del comprobante y, si no la trae, la de la tabla."""
    d = c.detraccion if isinstance(c.detraccion, dict) else {}
    t = a_decimal(d.get("porcentaje"))
    return t if t > 0 else tasa_de_tabla(d.get("codigo"), config)


def monto_detraccion(c: Comprobante, config: dict) -> tuple[Decimal, Decimal]:
    """El monto de la detracción (Excel real validado en CONCAR, 2026): total × tasa en SOLES ENTEROS —
    la detracción se deposita en soles (4 956 × 4 % = 198.24 → 198). En dólares la base se convierte
    con el T.C. del comprobante y el monto vuelve a dólares para la línea, porque el asiento va en US.
    Devuelve (soles, en la moneda del comprobante); (0, 0) si no hay tasa o falta el T.C."""
    t = tasa_detraccion(c, config)
    es_usd = (c.moneda or "PEN").upper() == "USD"
    tc = c.tipo_cambio if es_usd and c.tipo_cambio else None
    if t <= 0 or (es_usd and not tc):
        return Decimal(0), Decimal(0)
    total = Decimal(c.total or 0).quantize(CENTIMO)
    cambio = Decimal(str(tc)) if es_usd else Decimal(1)
    base_soles = (total * cambio).quantize(CENTIMO, rounding=ROUND_HALF_UP)
    soles = (base_soles * t / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    en_moneda = (soles / cambio).quantize(CENTIMO, rounding=ROUND_HALF_UP) if es_usd else soles
    return soles, en_moneda


def normalizar(comprobantes: Iterable[Comprobante], config: dict) -> list[Comprobante]:
    """Deja en blanco la detracción cuyo código no reconoce el contribuyente, y a la que queda le
    anota lo que dice el motor: su `monto` (soles enteros, lo que va a CONCAR) y la tasa de la tabla
    para ese código (`tasa_tabla`), que `validar` compara con la del comprobante.

    **La tasa del comprobante no se toca**: es la que leyó la IA o la que eligió la persona, y la
    huella con que se sabe si un comprobante cambió después de exportarse depende de ella.

    Devuelve **solo los comprobantes que cambió**, para que quien llame sepa qué guardar. Es
    idempotente: repetirla sobre lo ya normalizado no cambia nada.
    """
    con = [c for c in comprobantes if c.detraccion]
    if not con:
        return []
    codigos = codigos_de(config)
    cambiados = []
    for c in con:
        antes = c.detraccion
        nuevo = normalizar_una(c.detraccion, codigos)
        if nuevo is not None:
            c.detraccion = nuevo
            soles, _ = monto_detraccion(c, config)
            nuevo = dict(nuevo, monto=str(soles) if soles > 0 else "")
            de_tabla = tasa_de_tabla(nuevo["codigo"], config)
            if de_tabla > 0:
                nuevo["tasa_tabla"] = texto_tasa(de_tabla)
            else:
                nuevo.pop("tasa_tabla", None)
        c.detraccion = nuevo
        if nuevo != antes:
            cambiados.append(c)
    return cambiados


# Conciliar las constancias del Banco de la Nación —el segundo tiempo, que pasa la detracción
# de PROVISIONADO a PAGADO— todavía no está implementado: hace falta un archivo de constancias
# real para saber su formato exacto, y en este proyecto ninguna regla se escribe de memoria.
# El estándar ya tiene el hueco (`detraccion.estado`, `nro_constancia`, `fecha_constancia`).
