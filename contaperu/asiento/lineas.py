"""La línea de diario neutral: el asiento sin el vocabulario de ningún ERP.

Es el bloque `asiento` del estándar `open-accounting` y, desde la 0.7, la FUENTE del asiento: la arma
`motor.asiento_neutral()` y de ella salen todos los destinos — el Excel de CONCAR como una proyección
(`drivers/concar/proyeccion.py`), el CSV genérico, los drivers de terceros y los agentes de IA a
través del servidor MCP.

`desde_fila()` y `a_lineas()` hacen el camino inverso (de columnas de CONCAR a línea neutral) y se
conservan por compatibilidad: era como se obtenía la línea cuando el asiento nacía en columnas. No
rellenan los campos que llegaron después (`rol`, `tipo_cp`, el código SUNAT de la detracción).

La tabla de equivalencias de abajo es, de paso, la documentación de qué significa cada columna
del formato de CONCAR — que en su manual solo tiene una letra por nombre.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

D2 = Decimal("0.01")

# Columna del Excel de CONCAR -> qué es en realidad.
COLUMNA_A_CAMPO = {
    "B": "sub_diario",          "C": "correlativo",        "D": "fecha del asiento",
    "E": "moneda (código del ERP)", "F": "glosa de la cabecera", "G": "tipo de cambio",
    "H": "tipo de conversión",  "I": "flag de conversión", "J": "fecha de la operación",
    "K": "cuenta",              "L": "anexo (documento de la contraparte)",
    "M": "centro de costo",     "N": "debe o haber",       "O": "importe original",
    "P": "importe en dólares",  "Q": "importe en soles",   "R": "tipo de documento",
    "S": "serie y número",      "T": "fecha del documento", "U": "fecha de vencimiento",
    "W": "glosa del detalle",   "X": "anexo auxiliar",
    "Z": "tipo del documento de referencia", "AA": "serie y número de la referencia",
    "AB": "fecha de la referencia",
    "AI": "código interno de detracción", "AJ": "tasa de detracción",
    "AK": "base de la detracción en dólares", "AL": "base de la detracción en soles",
    "AO": "tasa del IGV",
}


def _texto(v: Any) -> str:
    if isinstance(v, date):
        return v.isoformat()
    return "" if v is None else str(v).strip()


def _importe(v: Any) -> str:
    """A texto con 2 decimales. Los importes salen del asiento como float para openpyxl;
    aquí vuelven a ser exactos, que es como viajan en el estándar."""
    if v is None or v == "":
        return ""
    return str(Decimal(str(v)).quantize(D2))


def _numero(v: Any) -> Any:
    return v if isinstance(v, (int, float)) else (v or "")


@dataclass
class LineaDiario:
    """Una línea del asiento, en el vocabulario de `open-accounting`.

    `documento` y `referencia` llevan `tipo` (la sigla del ERP, por compatibilidad) y `tipo_cp` (el
    código SUNAT de la Tabla 10, que es el que manda). `glosa` va entera: el corte es del driver.
    `tasa_igv` es la del comprobante como texto (`"18"`, `"10.5"`), sin redondear a entero.
    """

    cuenta: str
    debe_haber: str            # 'D' | 'H'
    importe: str
    rol: str = ""              # ver `motor.ROLES`: principal, igv, retencion_4ta, tercero…
    sub_diario: str = ""
    correlativo: str = ""
    fecha: str = ""
    moneda: str = ""
    tipo_cambio: Any = ""
    glosa: str = ""
    contraparte_doc: str = ""
    centro_costo: str = ""
    anexo_auxiliar: str = ""
    documento: dict = field(default_factory=dict)
    referencia: dict = field(default_factory=dict)
    detraccion: dict = field(default_factory=dict)
    tasa_igv: Any = ""

    def a_dict(self) -> dict:
        """Sin las claves vacías: un documento `open-accounting` no lleva ruido."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v not in ("", {}, None)}


def desde_fila(fila: dict, monedas: dict[str, str] | None = None) -> LineaDiario:
    """Una fila en columnas de CONCAR -> una línea de diario neutral.

    `monedas` traduce el código del ERP al ISO 4217 ('MN' -> 'PEN'); si no se pasa, el código
    se transporta tal cual.
    """
    monedas = monedas or {}
    codigo = _texto(fila.get("E"))
    documento = {
        "tipo": _texto(fila.get("R")),
        "serie_numero": _texto(fila.get("S")),
        "fecha_emision": _texto(fila.get("T")),
        "fecha_vencimiento": _texto(fila.get("U")),
    }
    referencia = {
        "tipo": _texto(fila.get("Z")),
        "serie_numero": _texto(fila.get("AA")),
        "fecha": _texto(fila.get("AB")),
    }
    detraccion = {
        "codigo_interno": _texto(fila.get("AI")),
        "tasa": _numero(fila.get("AJ")),
        "base": _importe(fila.get("AK") or fila.get("AL")),
    }
    return LineaDiario(
        cuenta=_texto(fila.get("K")),
        debe_haber=_texto(fila.get("N")),
        importe=_importe(fila.get("O")),
        sub_diario=_texto(fila.get("B")),
        correlativo=_texto(fila.get("C")),
        fecha=_texto(fila.get("D")),
        moneda=monedas.get(codigo, codigo),
        tipo_cambio=_numero(fila.get("G")),
        glosa=_texto(fila.get("W")),
        contraparte_doc=_texto(fila.get("L")),
        centro_costo=_texto(fila.get("M")),
        anexo_auxiliar=_texto(fila.get("X")),
        documento={k: v for k, v in documento.items() if v},
        referencia={k: v for k, v in referencia.items() if v},
        detraccion={k: v for k, v in detraccion.items() if v not in ("", None)},
        tasa_igv=_numero(fila.get("AO")),
    )


def a_lineas(filas: list[dict], contab: dict | None = None) -> list[LineaDiario]:
    """Todas las filas de un asiento -> líneas neutrales. `contab` solo se usa para
    devolverle a la moneda su código ISO."""
    codigos = (contab or {}).get("monedas_codigo") or {}
    monedas = {v: k for k, v in codigos.items()}
    return [desde_fila(f, monedas) for f in filas]
