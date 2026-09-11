"""La línea neutral, proyectada a las 41 columnas del Excel de CONCAR.

Lo que aquí se decide es FORMATO de CONCAR, no contabilidad: el código de moneda de su T.G. 03
(MN/US), los flags de conversión, los cortes de la glosa a 40 y 30 caracteres, el importe partido en
soles o dólares, la tasa del IGV entera, el área de la detracción. La contabilidad —qué cuenta, qué
sentido, cuántas líneas— ya viene resuelta en la línea (`asiento/motor.py`).

La regla de este módulo: **el Excel no cambia ni una celda** respecto del que se validó en
producción. Lo vigila `tests/test_snapshot_concar.py`, con 42 casos congelados antes de separar la
contabilidad de su formato (11-sep-2026).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ...asiento.construir import MonedaSinCodigo, tasa_igv
from ...asiento.datos import COLUMNAS, FLAG_CONVERSION, TIPO_CONVERSION
from ...asiento.lineas import LineaDiario
from ...asiento.motor import glosa_de
from ...modelo import Comprobante


def codigo_moneda(moneda: str, contab: dict) -> str:
    """Columna E: el código de la T.G. 03. CONCAR solo admite MN y US (rechaza ME); otra moneda
    detiene la exportación en vez de inventarse un código."""
    moneda = (moneda or "PEN").upper()
    codigo = (contab.get("monedas_codigo") or {}).get(moneda)
    if not codigo:
        raise MonedaSinCodigo([moneda])
    return codigo


def _fecha(texto: str | None, vacio: Any = "") -> Any:
    return date.fromisoformat(texto) if texto else vacio


def _importe(texto: Any) -> Any:
    """Los importes viajan como texto exacto; openpyxl los quiere `float` para darles formato numérico."""
    return float(Decimal(str(texto))) if texto not in ("", None) else ""


def fila(linea: LineaDiario, c: Comprobante, contab: dict) -> dict[str, Any]:
    """Una línea neutral → una fila del Excel (claves 'A'..'AO', en el orden de la plantilla)."""
    es_usd = linea.moneda == "USD"
    importe = _importe(linea.importe)
    doc, ref, det = linea.documento or {}, linea.referencia or {}, linea.detraccion or {}
    f: dict[str, Any] = {col: "" for col in COLUMNAS}
    f.update({
        "B": linea.sub_diario, "C": linea.correlativo, "D": _fecha(linea.fecha),
        "E": codigo_moneda(linea.moneda, contab),
        # F: la glosa de la cabecera, igual en todas las filas del comprobante; W: la de la línea, con
        # su prefijo. Una sola glosa, dos largos: lo único que cambia es lo que admite CONCAR.
        "F": glosa_de(c)[:40], "W": linea.glosa[:30],
        # Con el T.C. del comprobante la conversión es especial ('C'); sin él, CONCAR lo busca en su tabla.
        "G": linea.tipo_cambio if linea.tipo_cambio else "",
        "H": "C" if linea.tipo_cambio else TIPO_CONVERSION, "I": FLAG_CONVERSION, "J": _fecha(linea.fecha),
        "K": linea.cuenta, "L": linea.contraparte_doc, "M": linea.centro_costo, "N": linea.debe_haber,
        "O": importe, "P": importe if es_usd else "", "Q": importe if not es_usd else "",
        "R": doc.get("tipo", ""), "S": doc.get("serie_numero", "")[:20],
        # Sin fecha, T y U quedan en None y no en "": así salían antes de separar el asiento de su
        # formato, y el snapshot lo fija. En el .xlsx las dos son la misma celda vacía.
        "T": _fecha(doc.get("fecha_emision"), None), "U": _fecha(doc.get("fecha_vencimiento"), None),
        "X": linea.anexo_auxiliar,
        # AO: CONCAR solo admite la tasa entera. Se redondea desde los importes del comprobante y no
        # desde la tasa de la línea, que ya va redondeada a 2 decimales: redondear dos veces puede
        # dar otro entero.
        "AO": tasa_igv(c.igv, c.base_gravada) if linea.tasa_igv not in ("", None) else "",
    })
    if linea.rol == "detraccion":
        # El área (T.G. 26) es un número propio de cada empresa y solo va en esta fila (Excel validado).
        # No se corta a los 3 caracteres de la plantilla: cortar un código lo manda a OTRA área en silencio.
        f["V"] = str(contab.get("detraccion_area") or "")
    if ref:
        f.update({"Z": ref.get("tipo", ""), "AA": ref.get("serie_numero", "")[:20],
                  "AB": _fecha(ref.get("fecha"))})
    if det:
        base = _importe(det.get("base"))
        f.update({"AI": det.get("codigo_interno", ""), "AJ": det.get("tasa", ""),
                  "AK": base if es_usd else "", "AL": base if not es_usd else ""})
    return f


def filas(c: Comprobante, lineas: list[LineaDiario], contab: dict) -> list[dict[str, Any]]:
    """Las líneas de UN comprobante → sus filas del Excel."""
    return [fila(ln, c, contab) for ln in lineas]
