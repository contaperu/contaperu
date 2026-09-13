"""La imputación de un documento: lo que un entorno decide sobre él, y que llega APARTE del documento.

Decisión de John (12-sep-2026): el documento `open-accounting` es el riel que lleva los hechos de cualquier input —el
XML, un PDF, la propuesta del SIRE, el archivo de otro sistema—, y **las cuentas viven en la aplicación**: en la
configuración de cada entorno y en lo que el contador decide en su Revisión. Por eso la cuenta, el centro de
costo, la cuenta del total y el reparto de un documento no están en el comprobante: llegan en la configuración,
bajo `imputaciones`, con el `id_externo` del comprobante como llave.

    {"imputaciones": {
       "fila-123": {"cuenta_contable": "6011020", "centro_costo": "OBRA01", "cuenta_tercero": "4699",
                    "reparto": [{"importe": "60.00", "cuenta_contable": "636301", "centro_costo": "SISTEMAS"}]}}}

**Qué trae.** La cuenta de la base, el centro, la cuenta del total y el reparto de UN documento. Lo que no
traiga sale de la configuración del entorno: desde open-accounting 0.3 el comprobante no lleva cuentas.

**El reparto** divide SOLO la base —el gasto o el ingreso—: el IGV y el total son del documento. Sus partes suman
la base del asiento (`igv.base_imputable`), y lo comprueba `construir.reparto_no_cuadra`. Un reparto con cuenta o
centro al lado es ambiguo —¿cuál manda?— y se rechaza al leerlo, en vez de elegir uno en silencio.

Aquí solo vive la forma: ninguna regla contable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..modelo import CERO, monto


def _texto(v) -> str:
    return " ".join(str(v or "").split())


@dataclass
class Parte:
    """Una parte del reparto de la base: su importe, su cuenta y, si la lleva, su centro de costo."""

    importe: Decimal = CERO
    cuenta_contable: str = ""
    centro_costo: str = ""

    def __post_init__(self) -> None:
        self.importe = monto(self.importe)
        self.cuenta_contable = _texto(self.cuenta_contable)
        self.centro_costo = _texto(self.centro_costo)

    def a_dict(self) -> dict:
        return {"importe": str(self.importe), "cuenta_contable": self.cuenta_contable,
                "centro_costo": self.centro_costo}


@dataclass
class Imputacion:
    """Lo que un entorno decide para UN documento. Todo es opcional: lo que falte sale de lo de siempre."""

    cuenta_contable: str = ""
    centro_costo: str = ""
    cuenta_tercero: str = ""
    reparto: list[Parte] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cuenta_contable = _texto(self.cuenta_contable)
        self.centro_costo = _texto(self.centro_costo)
        self.cuenta_tercero = _texto(self.cuenta_tercero)
        self.reparto = [p if isinstance(p, Parte) else Parte(**p) for p in (self.reparto or [])]
        if self.reparto and (self.cuenta_contable or self.centro_costo):
            raise ValueError("una imputación con reparto no lleva además cuenta_contable ni centro_costo "
                             "(¿cuál mandaría?): deja solo el reparto")

    @classmethod
    def de(cls, valor) -> "Imputacion":
        """La imputación ya armada, o su diccionario tal como llega por JSON."""
        if isinstance(valor, cls):
            return valor
        if not isinstance(valor, dict):
            raise ValueError("una imputación es un objeto {cuenta_contable, centro_costo, cuenta_tercero, reparto}")
        try:
            return cls(**valor)
        except TypeError as e:
            raise ValueError(f"una imputación con un campo que no existe: {e}") from None

    def a_dict(self) -> dict:
        return {"cuenta_contable": self.cuenta_contable, "centro_costo": self.centro_costo,
                "cuenta_tercero": self.cuenta_tercero, "reparto": [p.a_dict() for p in self.reparto]}
