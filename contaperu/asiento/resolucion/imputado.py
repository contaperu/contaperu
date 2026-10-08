"""Lo que dice la imputación de cada documento, que llega aparte y se enlaza por `id_externo` (12-sep-2026).

A qué cuentas va la base (`partes_de`) y cuál es la del tercero (`cuenta_tercero`): una sola resolución para el
asiento, los drivers de registro y las faltas, para que no acaben diciendo cosas distintas.
"""
from __future__ import annotations

from decimal import Decimal

from ...catalogos import TIPO_HONORARIOS
from ...configuracion import CONFIG_POR_DEFECTO
from ...modelo import Comprobante
from ..imputacion import Imputacion
from .configurado import _cuenta_por_moneda, cuenta_honorarios, cuenta_por_pagar


def imputacion_de(c: Comprobante, config: dict) -> Imputacion | None:
    """La imputación de ESTE documento, si la configuración trae una con su `id_externo`; si no, None."""
    id_externo = (c.id_externo or "").strip()
    valor = (config.get("imputaciones") or {}).get(id_externo) if id_externo else None
    return Imputacion.de(valor) if valor is not None else None


def partes_de(c: Comprobante, config: dict, es_venta: bool = False) -> list[tuple[str, str, Decimal | None]]:
    """A qué cuentas va la base del documento: `[(cuenta, centro, importe)]`, con importe None = la base entera.

    Con reparto en su imputación, una parte por cada una. Si no, una sola: la cuenta y el centro que traiga su
    imputación. Es la única resolución: el asiento, los drivers de registro y las faltas de cuenta y de centro leen
    esto.

    **Sin imputación no hay cuenta** (3.0): la configuración de la empresa ya no suple la del comprobante, así que
    `comprobantes_sin_cuenta` lo cuenta y `exigir_requisitos` detiene la exportación. Es a propósito — una compra
    imputada a un comodín que nadie eligió es un asiento mal hecho que nadie mira—."""
    imputacion = imputacion_de(c, config)
    if imputacion is not None and imputacion.reparto:
        return [(p.cuenta_contable, p.centro_costo, p.importe) for p in imputacion.reparto]
    cuenta = imputacion.cuenta_contable if imputacion is not None else ""
    centro = imputacion.centro_costo if imputacion is not None else ""
    return [(cuenta, centro, None)]


def cuenta_tercero(c: Comprobante, config: dict, es_venta: bool = False) -> str:
    """La cuenta del total: el cliente en ventas, el proveedor en compras (el recibo por honorarios, la suya).

    Manda la de la imputación del documento cuando el contador la decidió —un gasto de representación a la
    4699—; si no, la de la configuración por moneda. Vivía dentro de `lineas_del_comprobante`; salió aquí el
    12-sep-2026 para que la resuelva UNA función para todos los drivers —el asiento de CONCAR y el registro de
    CONTASIS—, como `partes_de` resuelve la de la base."""
    imputacion = imputacion_de(c, config)
    if imputacion is not None and imputacion.cuenta_tercero:
        return imputacion.cuenta_tercero
    moneda = (c.moneda or "PEN").upper()
    cuentas = config.get("cuentas") or {}
    if es_venta:
        return _cuenta_por_moneda(cuentas.get("clientes"), moneda, CONFIG_POR_DEFECTO["cuentas"]["clientes"]["PEN"])
    if c.tipo_cp == TIPO_HONORARIOS:
        return cuenta_honorarios(cuentas, moneda)
    return cuenta_por_pagar(cuentas, moneda)

# `_cuenta_de_respaldo` murió en la 3.0 (John, 23-sep-2026): daba la cuenta de la configuración cuando la imputación
# no traía ninguna —la de ingreso tenía hasta un valor de fábrica, `701101`— y con eso una venta sin cuenta salía
# imputada sola y el mes se daba por listo. **La cuenta del comprobante es de su imputación o no hay**, que es lo que
# el estándar dice desde que la imputación viaja aparte. Si reaparece en un grep, es código revivido.
