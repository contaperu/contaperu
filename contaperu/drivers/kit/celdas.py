"""Importes y fechas tal como los quiere una celda de Excel.

En todo el motor un importe es un `Decimal` o su texto exacto. La celda es el único sitio donde se vuelve `float`:
openpyxl no da formato numérico a un `Decimal`, y el valor ya viene redondeado al céntimo, así que no se pierde nada.
"""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any


def importe(texto: Any) -> Any:
    """Un importe exacto → `float` para la celda; vacío si no hay importe."""
    return float(Decimal(str(texto))) if texto not in ("", None) else ""


def fecha(texto: str | None, vacio: Any = "") -> Any:
    """Una fecha ISO (`AAAA-MM-DD`) → `date`; `vacio` si no hay fecha."""
    return date.fromisoformat(texto) if texto else vacio


def fecha_hora(d: date | None) -> datetime | None:
    """Una fecha → `datetime` a medianoche, que es como la guarda una celda de fecha; `None` si no hay."""
    return datetime.combine(d, time.min) if d else None


def numero_o_vacio(v: Any) -> Any:
    return v if isinstance(v, (int, float)) else (v or "")
