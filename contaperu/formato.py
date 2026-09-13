"""Piezas comunes de los drivers: opciones, formateadores y saneado de texto.

Las "microdecisiones" (formato de fecha, qué va en el tipo de cambio cuando la
moneda es soles, si un cero se escribe `0.00` o vacío, el signo de las notas de
crédito…) son OPCIONES, no código: así se itera con el reporte de SUNAT en la
mano sin tocar los drivers.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from .igv import por_destino
from .modelo import Comprobante


@dataclass(frozen=True)
class Opciones:
    fecha: str = "AAAAMMDD"       # 'AAAAMMDD' | 'DD/MM/AAAA'
    nueva_linea: str = "\n"       # LF (archivos de referencia) | CRLF
    palote_final: bool = True     # cada línea termina en '|' (el SIRE: ver `drivers/sire/txt.py`)
    tc_pen: str = "1.000"         # tipo de cambio cuando la moneda es PEN ('' = vacío)
    cero: str = "0.00"            # cómo se escribe un importe a cero ('' = vacío)
    signo_nc: bool = True         # notas de crédito con importes en negativo
    sin_ceros: bool = True        # quitar los ceros a la izquierda del número (regla de contabilidad: SIRE y CONCAR)
    sanear: bool = True           # quitar tildes/Ñ/controles → ASCII puro
    extension: str = ".txt"
    # SIRE Anexo 3: los campos 34-40 los "completa la Administración" y el archivo REAL que
    # SUNAT aceptó (un RVIE real de 2026, 25-ago-2026) no los manda: 33 campos y palote.
    # Mandarlos vacíos era lo que hacía el generador antes y da 40 campos por fila.
    rvie_vacios: int = 0
    # SIRE Anexo 11 (compras): aquí la nota de SUNAT dice lo CONTRARIO que en ventas —
    # "los campos 38 al 41 deberán mostrarse vacíos"—, así que van (37 + 4). No está
    # comprobado contra un RCE aceptado: si SUNAT devuelve el 453 en compras, la
    # respuesta es `rce_vacios=0`, sin tocar código. Que en ventas la nota fuera
    # "los completa la Administración" y aun así hubiera que quitarlos es el motivo
    # de que esto sea una opción y no un número escrito en el driver.
    rce_vacios: int = 4
    codificacion: str = "ascii"

    def con(self, **cambios) -> "Opciones":
        return replace(self, **cambios)


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


def formatear_numero(numero: str, opciones: Opciones) -> str:
    """Número del comprobante tal como va al archivo. Por defecto SIN ceros a la izquierda
    (`00028806` → `28806`): decisión de formato para el SIRE y, más adelante, para CONCAR —
    SUNAT identifica el comprobante por su número y los ceros son cosmética del emisor."""
    n = (numero or "").strip()
    if opciones.sin_ceros and n.isdigit():
        return n.lstrip("0") or "0"
    return n


def negativo(c: Comprobante, opciones: Opciones) -> bool:
    return opciones.signo_nc and c.es_nota_credito


def armar_linea(campos: list[str], opciones: Opciones) -> str:
    linea = "|".join(campos)
    return linea + "|" if opciones.palote_final else linea


def columnas_igv_compras(c: Comprobante, opciones: Opciones) -> list[str]:
    """Las 6 columnas de base/IGV de compras según el destino de la adquisición:
    DG (gravadas), DGNG (gravadas y no gravadas), DNG (no gravadas). La división es de `igv.por_destino`;
    aquí solo se escribe, con el signo de la nota de crédito."""
    neg = negativo(c, opciones)
    return [formatear_monto(v, opciones, neg) for pareja in por_destino(c) for v in pareja]
