"""El formato de un registro de texto: saneado, fechas, importes y números como van al archivo."""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal

from ...modelo import Comprobante
from .opciones import Opciones

_CONTROLES = re.compile(r"[\x00-\x1f\x7f]")


def sanear(texto: str, opciones: Opciones) -> str:
    """Texto apto para un campo del TXT: nunca lleva '|' (es el separador) ni
    saltos de línea. Con `opciones.sanear`, además se convierte a ASCII (tildes fuera,
    Ñ → N) y '/' y '\\' → '-' (la Tabla 12 los prohíbe). El '&' se conserva: las
    razones sociales lo llevan."""
    s = _CONTROLES.sub(" ", str(texto or "")).replace("|", " ")
    if opciones.sanear:
        s = unicodedata.normalize("NFKD", s)
        s = s.encode("ascii", "ignore").decode("ascii")
        s = s.replace("/", "-").replace("\\", "-")
    return " ".join(s.split())


def formatear_fecha(d: date | None, opciones: Opciones) -> str:
    if d is None:
        return ""
    if opciones.fecha == "AAAAMMDD":
        return d.strftime("%Y%m%d")
    if opciones.fecha == "DD/MM/AAAA":
        return d.strftime("%d/%m/%Y")
    if opciones.fecha == "AAAA-MM-DD":
        return d.isoformat()
    raise ValueError(f"Formato de fecha desconocido: {opciones.fecha!r}")


def formatear_monto(d: Decimal, opciones: Opciones, negativo: bool = False) -> str:
    """`d` viene siempre positivo del modelo; el signo se decide aquí."""
    if d == 0:
        return opciones.cero
    s = f"{d:.2f}"
    return f"-{s}" if negativo else s


def formatear_cambio(c: Comprobante, opciones: Opciones) -> str:
    if c.moneda == "PEN":
        return opciones.tc_pen
    return f"{c.tipo_cambio:.3f}" if c.tipo_cambio else ""


def formatear_numero(numero: str, opciones) -> str:
    """Número del comprobante tal como va al archivo. Por defecto SIN ceros a la izquierda
    (`00028806` → `28806`): SUNAT identifica el comprobante por su número y los ceros son cosmética del emisor. Vale
    con cualquier opciones que digan `sin_ceros`."""
    n = (numero or "").strip()
    if getattr(opciones, "sin_ceros", True) and n.isdigit():
        return n.lstrip("0") or "0"
    return n


def negativo(c: Comprobante, opciones) -> bool:
    return getattr(opciones, "signo_nc", True) and c.es_nota_credito


def armar_linea(campos: list[str], opciones: Opciones) -> str:
    linea = "|".join(campos)
    return linea + "|" if opciones.palote_final else linea
