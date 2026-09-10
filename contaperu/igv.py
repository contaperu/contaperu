"""El IGV de un comprobante se LEE de sus importes; nunca se supone.

Regla de John (10-sep-2026): la tasa del IGV no es un dato que se configure ni que se elija. Es la
de cada comprobante —18, 10.5 o 0— y se deduce de su base imponible y su IGV. Por eso en este
módulo no hay ninguna tasa escrita. Lo que sí hay es cómo se mueven los importes cuando alguien
escribe el IGV que trae el papel:

- **Con IGV, el comprobante es afecto.** La base se deduce para que el total no cambie. Si hasta
  entonces no tenía IGV —estaba entero en inafecto, exonerado o exportación—, ese importe pasa a la
  base: escribir un IGV es decir «esto es afecto».
- **Sin IGV, cae en inafecto** (por defecto): la base y el IGV que hubiera pasan ahí. Exonerado y
  exportación, si los había, se quedan donde estaban: son otras columnas del SIRE.

**El total nunca cambia.** Si el IGV no cabe en él, no se reparte nada: se dice. Quien consume esto
es el portal (`POST /api/procesos/{id}/facturas/{fid}/igv`), que hasta ese día hacía la cuenta en el
navegador dividiendo entre 1.18.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .modelo import Comprobante

CERO = Decimal("0")
D2 = Decimal("0.01")


class IgvImposible(ValueError):
    """El IGV pedido no se puede aplicar a ese comprobante; el mensaje va tal cual a la persona."""


def tasa(igv, base_gravada) -> Decimal | None:
    """La tasa del comprobante, en %, tal como sale de sus importes. `None` si no hay de dónde leerla
    (sin IGV, o un IGV sin base). Sin redondear: quien la necesite entera —la columna AO de CONCAR— la
    redondea él."""
    igv, base = Decimal(igv or 0), Decimal(base_gravada or 0)
    if igv <= 0 or base <= 0:
        return None
    return igv / base * 100


def _cargos(c: Comprobante) -> Decimal:
    """Lo que forma el total y no es base gravada, IGV ni importe sin IGV: ISC, IVAP, ICBPER, otros
    cargos y los descuentos. Es la fórmula del total de `validar.py` sin sus sumandos de IGV."""
    return c.isc + c.base_ivap + c.ivap + c.icbper + c.otros - c.dscto_base - c.dscto_igv


def aplicar_igv(c: Comprobante, igv) -> dict[str, Decimal]:
    """Los importes del comprobante con el IGV que dice el papel, sin tocar el total.

    Devuelve los cinco que pueden moverse —base, IGV, exonerado, inafecto, exportación—; el resto del
    comprobante no se toca. Lanza `IgvImposible` si el IGV no es un número, es negativo o no cabe.
    """
    try:
        nuevo = Decimal(str(igv).replace(",", ".").strip() or "0").quantize(D2, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise IgvImposible("El IGV debe ser un número") from None
    if nuevo < 0:
        raise IgvImposible("El IGV no puede ser negativo")
    fila = {"base_gravada": c.base_gravada, "igv": c.igv, "exonerado": c.exonerado,
            "inafecto": c.inafecto, "exportacion": c.exportacion}
    if nuevo == 0:
        # Sin IGV cae en inafecto: la base y el IGV que tuviera pasan ahí, y el total queda igual.
        fila.update(inafecto=c.inafecto + c.base_gravada + c.igv, base_gravada=CERO, igv=CERO)
    elif c.igv <= 0:
        # No tenía IGV: todo el importe sin IGV pasa a la base. Poner un IGV es decir «esto es afecto».
        fila.update(igv=nuevo, exonerado=CERO, inafecto=CERO, exportacion=CERO,
                    base_gravada=c.total - nuevo - _cargos(c))
    else:
        # Ya era afecto (o mixto): la base absorbe el cambio; lo que no lleva IGV se queda donde está.
        fila.update(igv=nuevo,
                    base_gravada=c.total - nuevo - c.exonerado - c.inafecto - c.exportacion - _cargos(c))
    if fila["base_gravada"] < 0:
        raise IgvImposible("Ese IGV supera el total del comprobante")
    return {k: Decimal(v).quantize(D2, rounding=ROUND_HALF_UP) for k, v in fila.items()}
