"""El libro: la cabecera de lo que se registra —un RUC, un mes, ventas o compras—.

Es lo primero que se valida de un documento y lo que decide todo lo demás: de `Libro.es_venta` cuelga qué
cuentas se usan, qué sub-diario toca y qué columnas escribe cada driver.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, fields

from .. import vocabulario
from .coerciones import solo_digitos

# Del catálogo del estándar (`vocabulario.TIPOS_LIBRO`), que es la única fuente desde la 1.0.
TIPOS_LIBRO = vocabulario.TIPOS_LIBRO

@dataclass
class Libro:
    """El registro que se genera: un RUC, un mes, ventas o compras."""

    ruc: str
    razon_social: str
    periodo: str  # 'AAAAMM'
    tipo: str     # 'venta' | 'compra'

    def __post_init__(self) -> None:
        self.ruc = solo_digitos(self.ruc)
        self.periodo = solo_digitos(self.periodo)[:6]
        self.razon_social = " ".join(str(self.razon_social or "").split())
        self.tipo = str(self.tipo or "").strip().lower()
        if len(self.ruc) != 11:
            raise ValueError(f"RUC inválido: {self.ruc!r} (11 dígitos)")
        if not re.fullmatch(r"20[0-9]{2}(0[1-9]|1[0-2])", self.periodo):
            raise ValueError(f"Periodo inválido: {self.periodo!r} (AAAAMM)")
        if self.tipo not in TIPOS_LIBRO:
            raise ValueError(f"Tipo de libro inválido: {self.tipo!r} (venta|compra)")

    @property
    def anio(self) -> int:
        return int(self.periodo[:4])

    @property
    def mes(self) -> int:
        return int(self.periodo[4:6])

    @property
    def es_venta(self) -> bool:
        return self.tipo == "venta"

    def a_dict(self) -> dict[str, str]:
        return {"ruc": self.ruc, "razon_social": self.razon_social, "periodo": self.periodo, "tipo": self.tipo}

    @classmethod
    def de_dict(cls, d: dict) -> "Libro":
        """Lo desconocido se ignora; lo que falta llega vacío y lo rechaza la validación del libro (`ValueError`)."""
        if not isinstance(d, dict):
            raise ValueError("El libro tiene que ser un objeto con ruc, razon_social, periodo y tipo")
        return cls(**{f.name: d.get(f.name, "") for f in fields(cls)})

