"""Convertir lo que llega en lo que el motor usa: un importe en `Decimal`, una fecha en `date`, una serie y
un número en la cadena con que se citan.

No son modelo: son las utilidades de tipo de las que el modelo depende, y estaban en el mismo fichero. Aquí
viven las dos constantes que mandan en todo el dinero —`CERO` y `CENTIMO`, el cuántum de un importe— porque
quien convierte es quien tiene que saber a qué redondear.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

CERO = Decimal("0.00")
CENTIMO = Decimal("0.01")     # el cuántum de todo importe: una sola fuente para el motor
_TRES = Decimal("0.001")

# Del catálogo del estándar (`vocabulario.TIPOS_LIBRO`), que es la única fuente desde la 1.0: estaba aquí y otra

def a_decimal(v: Any) -> Decimal:
    """Un número cualquiera (una tasa, un porcentaje) a `Decimal`, sin redondear y sin quitarle el signo; vacío o
    ilegible, 0. Para importes está `monto`, que además los deja en 2 decimales y en positivo."""
    try:
        return Decimal(str(v if v not in (None, "") else 0))
    except Exception:
        return Decimal(0)


def texto_tasa(tasa: Decimal) -> str:
    """Una tasa como se escribe: a 2 decimales y sin ceros de más (18 → «18», 10.5 → «10.5», 4.50 → «4.5»)."""
    return format(tasa.quantize(CENTIMO, rounding=ROUND_HALF_UP).normalize(), "f")


def serie_y_numero(serie: str, numero: str) -> str:
    """«F001-123», o solo la parte que haya: un documento sin serie (un DUA, un recibo de servicios) se nombra por su
    número, y sin número por su serie."""
    return f"{serie}-{numero}" if serie and numero else (serie or numero)


def monto(v: Any) -> Decimal:
    """Normaliza a Decimal de 2 decimales. Acepta str ('1,234.50'), int, float,
    Decimal o vacío/None (→ 0.00). Devuelve el valor absoluto: el signo no es
    parte del dato (ver docstring del módulo)."""
    if v is None or v == "":
        return CERO
    if isinstance(v, Decimal):
        d = v
    else:
        s = str(v).strip().replace(",", "")
        if s == "":
            return CERO
        try:
            d = Decimal(s)
        except InvalidOperation as e:
            raise ValueError(f"Importe inválido: {v!r}") from e
    return abs(d).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def tipo_cambio(v: Any) -> Decimal | None:
    """Tipo de cambio con 3 decimales (formato `#.###` de SUNAT); vacío → None."""
    if v is None or v == "":
        return None
    try:
        d = Decimal(str(v).strip().replace(",", ""))
    except InvalidOperation as e:
        raise ValueError(f"Tipo de cambio inválido: {v!r}") from e
    if d <= 0:
        return None
    return d.quantize(_TRES, rounding=ROUND_HALF_UP)


_FORMATOS_FECHA = ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y", "%d-%m-%Y")


def fecha(v: Any) -> date | None:
    """Acepta date/datetime, 'AAAA-MM-DD', 'AAAAMMDD', 'DD/MM/AAAA', 'DD-MM-AAAA';
    vacío → None. Cualquier otra cosa es un error (mejor fallar que inventar)."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()[:10]
    for f in _FORMATOS_FECHA:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha inválida: {v!r}")


def solo_digitos(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))


def numero_sin_ceros(numero: str) -> str:
    """El número de un comprobante sin ceros a la izquierda (`00028806` → `28806`, `0000` → `0`): SUNAT identifica el
    comprobante por su número y los ceros son cosmética del emisor. Un número con letras queda tal cual."""
    n = (numero or "").strip()
    return (n.lstrip("0") or "0") if n.isdigit() else n

