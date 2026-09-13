"""La regla más vieja de la contabilidad: la suma del Debe es igual a la suma del Haber.

Parece obvia y por eso casi nadie la comprueba. Antes de que esto fuera una función, el motor
sumaba el debe y el haber, los guardaba en el resumen de la exportación **y exportaba igual**
aunque no cuadraran: un asiento descuadrado salía en silencio hacia el sistema contable, donde
lo descubre el contador semanas después o nadie.

Ahora cuadrar es un requisito para escribir bytes. Por construcción el asiento siempre cuadra
—la línea de gasto vale total menos IGV, así que las dos mitades se cierran solas—, de modo que
esto es una red de seguridad: si salta, hay un error de verdad.

**Sin tolerancia.** Un céntimo de diferencia es un asiento mal armado, no un redondeo
aceptable: los importes son `Decimal` de 2 decimales de punta a punta.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from .modelo import CENTIMO, CERO



class Descuadre(Exception):
    """El asiento no cuadra. Lleva el resultado para poder decir por cuánto."""

    def __init__(self, resultado: "Cuadre") -> None:
        self.resultado = resultado
        super().__init__(
            f"El asiento no cuadra: debe {resultado.debe} != haber {resultado.haber} "
            f"(diferencia {resultado.diferencia})"
        )


@dataclass(frozen=True)
class Cuadre:
    cuadra: bool
    debe: Decimal
    haber: Decimal
    diferencia: Decimal        # debe - haber; positiva sobra en el Debe
    lineas: int
    sin_sentido: int           # líneas sin 'D' ni 'H': tampoco deberían existir

    def a_dict(self) -> dict:
        return {
            "cuadra": self.cuadra,
            "debe": str(self.debe),
            "haber": str(self.haber),
            "diferencia": str(self.diferencia),
            "lineas": self.lineas,
            "sin_sentido": self.sin_sentido,
        }


def _monto(v: Any) -> Decimal:
    if v is None or v == "":
        return CERO
    try:
        return Decimal(str(v)).quantize(CENTIMO)
    except InvalidOperation as e:
        raise ValueError(f"Importe inválido en una línea del asiento: {v!r}") from e


def _campos(linea: Any) -> tuple[str, Any]:
    """Acepta una LineaDiario, su dict, o cualquier objeto con `debe_haber` e `importe`."""
    if isinstance(linea, dict):
        return str(linea.get("debe_haber") or "").strip().upper(), linea.get("importe")
    return str(getattr(linea, "debe_haber", "") or "").strip().upper(), getattr(linea, "importe", None)


def cuadra(lineas: Iterable[Any]) -> Cuadre:
    """Suma el Debe y el Haber de las líneas de diario y dice si cierran."""
    debe = haber = CERO
    total = sin_sentido = 0
    for linea in lineas:
        total += 1
        sentido, importe = _campos(linea)
        if sentido == "D":
            debe += _monto(importe)
        elif sentido == "H":
            haber += _monto(importe)
        else:
            sin_sentido += 1
    diferencia = (debe - haber).quantize(CENTIMO)
    return Cuadre(
        cuadra=(diferencia == CERO and sin_sentido == 0),
        debe=debe.quantize(CENTIMO), haber=haber.quantize(CENTIMO), diferencia=diferencia,
        lineas=total, sin_sentido=sin_sentido,
    )


def exigir(lineas: Iterable[Any]) -> Cuadre:
    """Como `cuadra`, pero levanta `Descuadre` si no cierra. Es lo que llama un driver
    antes de escribir un archivo."""
    r = cuadra(lineas)
    if not r.cuadra:
        raise Descuadre(r)
    return r
