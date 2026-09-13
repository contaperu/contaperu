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

**Y el total, al revés** (11-sep-2026): `aplicar_total` recibe el total del papel y deja el IGV quieto. Es
la celda «Total» del portal, que el contador corrige en la misma tabla; la cuenta, que hacía el navegador,
vive aquí. Los descuentos no entran en ninguna de las dos cuentas: la base y el IGV ya son netos.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from . import catalogos as cat
from .modelo import CENTIMO, CERO, Comprobante
from .validar import TOLERANCIA



class IgvImposible(ValueError):
    """El IGV pedido no se puede aplicar a ese comprobante; el mensaje va tal cual a la persona."""


class TotalImposible(ValueError):
    """El total pedido no se puede aplicar a ese comprobante; el mensaje va tal cual a la persona."""


def tasa_calculada(igv, base_gravada) -> Decimal | None:
    """La tasa del comprobante, en %, tal como sale de sus importes. `None` si no hay de dónde leerla
    (sin IGV, o un IGV sin base). Sin redondear: quien la necesite entera —la columna AO de CONCAR— la
    redondea él."""
    igv, base = Decimal(igv or 0), Decimal(base_gravada or 0)
    if igv <= 0 or base <= 0:
        return None
    return igv / base * 100


def tasa_legal(igv, base_gravada) -> Decimal | None:
    """La tasa legal del IGV que cuadra con la base y el IGV del comprobante, en %: la general
    (`catalogos.TASA_IGV`) o una reducida (`catalogos.TASAS_IGV_REDUCIDAS`), con la misma tolerancia con la que
    `validar` las reconoce. Es la que declara un registro que pide «el porcentaje del IGV»: la plantilla de
    CONTASIS dice «Ejemplo: 18.00», y el registro que CONTASIS validó escribe 18 aunque base e IGV, redondeados ítem
    a ítem, den 17.98. `None` si no hay de dónde leerla; si ninguna tasa legal cuadra —el IGV_NO_CUADRA que ya
    bloquea la exportación—, la del cociente, a 2 decimales."""
    igv, base = Decimal(igv or 0), Decimal(base_gravada or 0)
    if igv <= 0 or base <= 0:
        return None
    for t in (cat.TASA_IGV, *cat.TASAS_IGV_REDUCIDAS):
        if abs(igv - base * Decimal(t)) <= TOLERANCIA:
            return (Decimal(t) * 100).quantize(CENTIMO)
    return (igv / base * 100).quantize(CENTIMO, rounding=ROUND_HALF_UP)


# En compras, la boleta de venta y el recibo por honorarios no dan crédito fiscal: la boleta no permite
# ejercerlo (Reglamento de Comprobantes de Pago, art. 4, num. 3) y el recibo por honorarios no lleva IGV. Si
# traen un IGV, es costo y va con la base. En ventas no aplica: la boleta emitida lleva su débito fiscal.
SIN_CREDITO_FISCAL = ("02", "03")


def igv_del_asiento(c: Comprobante, es_venta: bool) -> Decimal:
    """El IGV que va en su propia línea del asiento: el del comprobante, salvo en compras de un tipo sin
    crédito fiscal, donde es cero y ese importe se queda en la base."""
    if not es_venta and c.tipo_cp in SIN_CREDITO_FISCAL:
        return Decimal(0)
    return Decimal(c.igv or 0).quantize(CENTIMO)


def base_imputable(c: Comprobante, es_venta: bool) -> Decimal:
    """Lo que va a la cuenta de la base —el gasto en compras, el ingreso en ventas—: el total menos el IGV
    con línea propia. Es lo que divide el reparto de la imputación de un documento, y por eso lo usan igual
    el asiento (`lineas_del_comprobante`) y la comprobación del reparto (`asiento.reparto_no_cuadra`): la regla vive
    una vez."""
    return (Decimal(c.total or 0).quantize(CENTIMO) - igv_del_asiento(c, es_venta)).quantize(CENTIMO)


def por_destino(c: Comprobante) -> tuple[tuple[Decimal, Decimal], tuple[Decimal, Decimal], tuple[Decimal, Decimal]]:
    """La base y el IGV de una compra en las tres parejas del destino de la adquisición (`destino_igv`), en el
    orden de los registros de compras: gravadas destinadas a operaciones gravadas (DG), a gravadas y no gravadas
    (DGNG) y a no gravadas (DNG). La pareja entera va a su destino y las otras dos quedan en cero; un destino
    que no es DGNG ni DNG cuenta como DG.

    Fuente: el Anexo 11 del SIRE (RS 040-2022, campos 15-20). La plantilla de importación de CONTASIS lleva las
    mismas seis columnas (J-O). Vivía dentro de `formato.columnas_igv_compras`, la del SIRE; salió aquí el
    12-sep-2026 para que no viva dos veces."""
    pareja, cero = (c.base_gravada, c.igv), (CERO, CERO)
    if c.destino_igv == "DGNG":
        return cero, pareja, cero
    if c.destino_igv == "DNG":
        return cero, cero, pareja
    return pareja, cero, cero


def _cargos(c: Comprobante) -> Decimal:
    """Lo que forma el total y no es base gravada, IGV ni importe sin IGV: ISC, IVAP, ICBPER y otros
    cargos. Los descuentos no: la base y el IGV ya son netos. Es la fórmula del total de `validar.py` sin
    sus sumandos de IGV."""
    return c.isc + c.base_ivap + c.ivap + c.icbper + c.otros


def _entera(c: Comprobante) -> bool:
    """La nota va entera como descuento en el SIRE (la NC de descuento global)."""
    return c.dscto_base > 0 and c.dscto_base == c.base_gravada and c.dscto_igv == c.igv


def _seguir_descuento(c: Comprobante, fila: dict, error: type[ValueError]) -> None:
    """Los descuentos acompañan a la base y al IGV nuevos: si la nota iba entera como descuento, sigue
    entera; si iba en parte, esa parte tiene que seguir cabiendo."""
    if _entera(c):
        fila.update(dscto_base=fila["base_gravada"], dscto_igv=fila["igv"])
    elif fila["dscto_base"] > fila["base_gravada"] or fila["dscto_igv"] > fila["igv"]:
        raise error("La parte que va como descuento ya no cabe en la base o el IGV nuevos: corrígela primero")


def aplicar_igv(c: Comprobante, igv) -> dict[str, Decimal]:
    """Los importes del comprobante con el IGV que dice el papel, sin tocar el total.

    Devuelve los que pueden moverse —base, IGV, exonerado, inafecto, exportación y los dos descuentos—; el
    resto del comprobante no se toca. Lanza `IgvImposible` si el IGV no es un número, es negativo o no cabe.
    """
    try:
        nuevo = Decimal(str(igv).replace(",", ".").strip() or "0").quantize(CENTIMO, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise IgvImposible("El IGV debe ser un número") from None
    if nuevo < 0:
        raise IgvImposible("El IGV no puede ser negativo")
    fila = {"base_gravada": c.base_gravada, "igv": c.igv, "exonerado": c.exonerado,
            "inafecto": c.inafecto, "exportacion": c.exportacion,
            "dscto_base": c.dscto_base, "dscto_igv": c.dscto_igv}
    if nuevo == 0:
        # Sin IGV cae en inafecto: la base y el IGV que tuviera pasan ahí, y el total queda igual. Sin base
        # no hay nada que informar como descuento.
        fila.update(inafecto=c.inafecto + c.base_gravada + c.igv, base_gravada=CERO, igv=CERO,
                    dscto_base=CERO, dscto_igv=CERO)
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
    if nuevo != 0:
        _seguir_descuento(c, fila, IgvImposible)
    return {k: Decimal(v).quantize(CENTIMO, rounding=ROUND_HALF_UP) for k, v in fila.items()}


PRINCIPALES = ("base_gravada", "inafecto", "exonerado", "exportacion")


def aplicar_total(c: Comprobante, total) -> dict[str, Decimal]:
    """Los importes del comprobante con el total que dice el papel, sin tocar el IGV.

    Es la celda «Total» del portal: el contador corrige el total en la misma tabla (John, 11-sep-2026). La
    regla es la que la celda aplicaba desde el 23-ago-2026, ahora en el motor: el total lo absorbe el
    importe PRINCIPAL —la base si la hay; si no, inafecto, exonerado o exportación, en ese orden— y el IGV
    se queda como está, porque se escribe del papel en su propia celda (`aplicar_igv`). El principal se
    recalcula para que todo cuadre con el total nuevo, no sumándole la diferencia: si la IA había leído mal
    el total, sumar la diferencia arrastraba el error. Si base e IGV dejan de ser una tasa legal, lo dice
    `validar`. Devuelve el total, el principal y los descuentos; lanza `TotalImposible` si no cabe.
    """
    try:
        nuevo = Decimal(str(total).replace(",", ".").strip() or "0").quantize(CENTIMO, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise TotalImposible("El total debe ser un número") from None
    if nuevo < 0:
        raise TotalImposible("El total no puede ser negativo")
    principal = next((k for k in PRINCIPALES if getattr(c, k) > 0), "base_gravada")
    resto = (c.base_gravada + c.igv + c.inafecto + c.exonerado + c.exportacion + _cargos(c)
             - getattr(c, principal))
    valor = nuevo - resto
    if valor < 0:
        raise TotalImposible("Ese total es menor que el IGV más los otros importes del comprobante")
    fila = {"total": nuevo, principal: valor, "dscto_base": c.dscto_base, "dscto_igv": c.dscto_igv}
    if principal == "base_gravada":
        fila["igv"] = c.igv
        _seguir_descuento(c, fila, TotalImposible)
        del fila["igv"]
    return {k: Decimal(v).quantize(CENTIMO, rounding=ROUND_HALF_UP) for k, v in fila.items()}
