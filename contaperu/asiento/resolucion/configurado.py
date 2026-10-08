"""Lo que dice la configuración: fundirla con sus valores por defecto y sacar de ahí las etiquetas de los
sub-diarios y la cuenta que toca según la moneda.

Es el escalón de abajo del paquete, el único que no mira ningún comprobante: solo lee el diccionario que llegó
por parámetro. Los valores por defecto son el respaldo cuando una clave no viene, nunca un sustituto de lo que
el contador decide.
"""
from __future__ import annotations

from typing import Any

from ...catalogos import TIPO_BOLETA, TIPO_HONORARIOS
from ...configuracion import CONFIG_POR_DEFECTO, por_defecto
from ..configuracion import CONFIGURACION_DEL_ASIENTO


# Los valores por defecto de lo que lee el asiento: el respaldo cuando la configuración que llega no trae una clave.
_DEL_ASIENTO = por_defecto(CONFIGURACION_DEL_ASIENTO)


def fundir_config(defaults: dict, overrides: dict) -> dict:
    """Overrides sobre defaults, dict a dict (un sistema anterior lo hacía a 1 nivel: sobreescribir `cxp.USD`
    borraba `cxp.PEN`; aquí se funde en profundidad)."""
    out: dict = {k: (fundir_config(v, {}) if isinstance(v, dict) else v) for k, v in (defaults or {}).items()}
    if not isinstance(overrides, dict):
        return out
    for k, v in overrides.items():
        if isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k] = fundir_config(out[k], v)
        else:
            out[k] = v
    return out


def etiquetas_sub_diario(config: dict) -> dict[str, str]:
    """{numero: uso} segun la config vigente, para el modal de exportar y el resumen.
    Si el estudio renumera (honorarios → 33), el 33 sale etiquetado. Dos usos con el
    mismo numero se unen con " · " (p. ej. un CONCAR que no separa la detraccion)."""
    tipos = config.get("tipos") or {}
    usos = [
        (str(config.get("sub_diario_ventas") or "05"), "Ventas"),
        (str(config.get("sub_diario_compras") or "11"), "Compras"),
        (str(config.get("sub_diario_detraccion") or "").strip(), "Compras con detracción"),
        (str((tipos.get(TIPO_BOLETA) or {}).get("sub_diario") or "").strip(), "Boletas de venta"),
        (str((tipos.get(TIPO_HONORARIOS) or {}).get("sub_diario") or "").strip(), "Recibos por honorarios"),
    ]
    etiquetas: dict[str, str] = {}
    for numero, uso in usos:
        if not numero:
            continue
        etiquetas[numero] = (etiquetas[numero] + " · " + uso) if numero in etiquetas else uso
    return etiquetas


def _cuenta_por_moneda(valor: Any, moneda: str, fallback: str) -> str:
    if isinstance(valor, dict):
        return str(valor.get((moneda or "").upper()) or valor.get("PEN") or fallback)
    return str(valor) if valor else fallback


def cuenta_por_pagar(cuentas: dict, moneda: str) -> str:
    return _cuenta_por_moneda(cuentas.get("cxp"), moneda, CONFIG_POR_DEFECTO["cuentas"]["cxp"]["PEN"])


def cuenta_por_pagar_detraccion(cuentas: dict, moneda: str) -> str:
    """La cuenta por pagar de la factura afecta a detracción (421203 en las dos monedas por defecto)."""
    return _cuenta_por_moneda(cuentas.get("cxp_detraccion"), moneda, CONFIG_POR_DEFECTO["cuentas"]["cxp_detraccion"]["PEN"])


def cuenta_honorarios(cuentas: dict, moneda: str) -> str:
    return _cuenta_por_moneda(cuentas.get("honorarios"), moneda, CONFIG_POR_DEFECTO["cuentas"]["honorarios"]["PEN"])
