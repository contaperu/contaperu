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

from .. import catalogos as cat
from ..catalogos import TOLERANCIA_IGV as TOLERANCIA
from ..errores import ErrorContaperu
from ..modelo import CENTIMO, CERO, Comprobante



class IgvImposible(ErrorContaperu, ValueError):
    """El IGV pedido no se puede aplicar a ese comprobante; el mensaje va tal cual a la persona."""


class TotalImposible(ErrorContaperu, ValueError):
    """El total pedido no se puede aplicar a ese comprobante; el mensaje va tal cual a la persona."""


def tasa_calculada(igv, base_gravada) -> Decimal | None:
    """La tasa del comprobante, en %, tal como sale de sus importes. `None` si no hay de dónde leerla
    (sin IGV, o un IGV sin base). Sin redondear: quien la necesite entera —la columna AO de CONCAR— la
    redondea él.

    **Esto NO se escribe en un archivo**: es el cociente crudo, así que lleva dentro el redondeo del emisor y
    dice `18.02` donde la tasa es 18 (una base de 25.42 con un IGV de 4.58, cuyo exacto es 4.5756). Sirve para
    DECIDIR —si cuadra, y el entero que CONCAR admite—; lo que va a un archivo o a la línea del asiento es
    `tasa_legal`, que contesta «cuál de las tasas legales explica estos importes». Lo aprendió STARSOFT el
    08-oct-2026, en una importación real."""
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
    return c.isc + c.base_ivap + c.ivap + c.icbper + c.otros_neto


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

    Devuelve los que pueden moverse —base, IGV, exonerado, inafecto, exportación y los dos descuentos, y en un
    comprobante que lo declare también `valor_no_gravado`—; el resto del comprobante no se toca. Lanza
    `IgvImposible` si el IGV no es un número, es negativo o no cabe.
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
    # Un comprobante de COMPRA traído del RCE informa lo no gravado en `valor_no_gravado` (su campo 21) y
    # **no** en `exonerado`/`inafecto`, que en ese archivo no existen. Mover importes sin mirarlo dejaba dos
    # verdades —el campo declarado por un lado y el desglose por otro— y el total volvía a no cuadrar, ahora
    # de verdad. `declarado` es el interruptor: cuando lo está, lo no gravado se sigue llevando en ESE campo;
    # cuando no, todo sigue exactamente como antes de la 3.5.1.
    declarado = c.valor_no_gravado is not None
    if nuevo == 0:
        # Sin IGV, la base y el IGV que tuviera pasan a lo no gravado, y el total queda igual. Sin base no
        # hay nada que informar como descuento. En una compra del RCE ese destino es el campo declarado, no
        # `inafecto`: si se llevara ahí, la propiedad seguiría devolviendo el valor viejo y el comprobante
        # pasaría a descuadrar por un importe que nadie perdió.
        fila.update(base_gravada=CERO, igv=CERO, dscto_base=CERO, dscto_igv=CERO)
        if declarado:
            fila["valor_no_gravado"] = c.valor_no_gravado + c.base_gravada + c.igv
        else:
            fila["inafecto"] = c.inafecto + c.base_gravada + c.igv
    elif c.igv <= 0:
        # No tenía IGV: todo el importe sin IGV pasa a la base. Poner un IGV es decir «esto es afecto», así
        # que se suelta también el campo declarado (None, no cero: cero sería declarar que no hay nada no
        # gravado, y eso ganaría sobre el desglose que alguien escriba después).
        fila.update(igv=nuevo, exonerado=CERO, inafecto=CERO, exportacion=CERO,
                    base_gravada=c.total - nuevo - _cargos(c))
        if declarado:
            fila["valor_no_gravado"] = None
    else:
        # Ya era afecto (o mixto): la base absorbe el cambio; lo que no lleva IGV se queda donde está —y
        # `adquisiciones_no_gravadas` dice dónde está, que es el campo declarado o la suma de los otros dos.
        fila.update(igv=nuevo,
                    base_gravada=c.total - nuevo - c.adquisiciones_no_gravadas - c.exportacion - _cargos(c))
    if fila["base_gravada"] < 0:
        raise IgvImposible("Ese IGV supera el total del comprobante")
    if nuevo != 0:
        _seguir_descuento(c, fila, IgvImposible)
    # `valor_no_gravado` admite None —significa «no lo declaro, mira el desglose»— y por eso se queda fuera
    # del redondeo: `Decimal(None)` reventaría.
    return {k: v if v is None else Decimal(v).quantize(CENTIMO, rounding=ROUND_HALF_UP)
            for k, v in fila.items()}


def clase_de_igv(c: Comprobante, es_venta: bool) -> str:
    """Qué le cobraron de IGV a este comprobante, deducido de sus importes.

    **No se elige: sale de los importes** (John, 10-sep-2026), y por eso vive aquí y no en una columna: quien quiera
    cambiarla escribe el IGV o el importe no gravado que trae el papel y el motor recoloca el resto.

    **No es `destino_igv`**, y la confusión cuesta cara. Aquella dice PARA QUÉ se usa una compra —`DG`, `DGNG`,
    `DNG`— y solo tiene sentido si te cobraron IGV; ésta dice SI te lo cobraron. El modelo pone `DG` por defecto a
    todo comprobante, también a una compra que no tiene IGV que destinar, así que leer el destino para responder a
    esta pregunta contesta «gravada» a media contabilidad. El mismo aviso está escrito desde la 2.x en
    `drivers/starsoft/proyeccion.destino_de`, que tuvo que resolverlo por su cuenta dentro de un driver; esto lo sube
    al núcleo, que es donde podía mirarlo también la pantalla.

    **Los dos libros no dan las mismas clases, porque no informan lo mismo.** El RVIE separa lo exonerado (campo 19)
    de lo inafecto (campo 20); el RCE tiene una sola columna de adquisiciones no gravadas (campo 21) que no dice cuál
    de los dos es, así que en compras se dice «no gravada» y no se inventa el desglose. Y la importación solo existe
    en compras, donde se reconoce por la DUA y no por un importe.

    Devuelve **cadena vacía cuando no hay ningún importe**: un comprobante que SUNAT declara en cero porque se dio de
    baja no es gravado ni no gravado, y decir cualquiera de las dos cosas sería inventar. Antes de la 3.7 la pantalla
    caía en «inafecto» por descarte y lo enseñaba con un importe de `0.00` al lado, que es exactamente la confusión
    que esto viene a quitar.
    """
    if not es_venta and (c.anio_dua or c.cod_dep_aduanera):
        return "importacion"
    no_gravado = c.adquisiciones_no_gravadas
    gravada = c.igv > 0 or c.base_gravada > 0
    if es_venta:
        partes = [gravada, c.exonerado > 0, c.inafecto > 0, c.exportacion > 0]
        if sum(partes) > 1:
            return "mixto"
        if gravada:
            return "afecto"
        if c.exonerado > 0:
            return "exonerado"
        if c.exportacion > 0:
            return "exportacion"
        return "inafecto" if c.inafecto > 0 else ""
    # Compras. `exportacion` no se mira: el RCE no tiene esa columna.
    if gravada and no_gravado > 0:
        return "mixto"
    if gravada:
        return "gravada"
    return "no_gravada" if no_gravado > 0 else ""


class NoGravadoImposible(ErrorContaperu, ValueError):
    """El importe no gravado que se quiere poner no cabe en el comprobante."""

    clave = "no_gravado_imposible"


#: Dónde puede vivir lo no gravado, y no es lo mismo en los dos libros: el RVIE separa exonerado (campo 19) de
#: inafecto (campo 20) y el RCE tiene UNA sola columna, «Valor de las adquisiciones no gravadas» (campo 21), que no
#: dice cuál de los dos es. Quien llama elige el campo con el libro delante; el motor no lo adivina.
CAMPOS_NO_GRAVADO = ("valor_no_gravado", "exonerado", "inafecto")


def aplicar_no_gravado(c: Comprobante, importe, campo: str = "valor_no_gravado") -> dict[str, Decimal | None]:
    """Los importes del comprobante con el no gravado que dice el papel, **sin tocar el total ni el IGV**.

    Es la hermana de `aplicar_igv` y `aplicar_total`, y sigue su misma regla: la persona escribe UN importe y el
    motor recalcula el resto, en vez de que la pantalla haga cuentas. Aquí el que absorbe es la base gravada, que se
    recalcula entera —no se le suma la diferencia— para que un error anterior no se arrastre.

    Existe porque hasta la 3.7 **una compra mixta no se podía corregir**: el formulario ofrecía `exonerado` e
    `inafecto`, que en el registro de compras no existen, y escondía `valor_no_gravado`, que es el único que sí. Con
    una factura de 100 + 18 de IGV y 50 sin gravar no había dónde escribir los 50.

    Poner cero en el campo declarado lo SUELTA (`None`, no cero): cero sería declarar que no hay nada no gravado, y
    eso gana sobre el desglose. Lo mismo que hace `aplicar_igv` al volver afecto un comprobante.
    """
    if campo not in CAMPOS_NO_GRAVADO:
        raise NoGravadoImposible(f"«{campo}» no es un campo de lo no gravado ({', '.join(CAMPOS_NO_GRAVADO)})")
    try:
        nuevo = Decimal(str(importe).replace(",", ".").strip() or "0").quantize(CENTIMO, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise NoGravadoImposible("El importe no gravado debe ser un número") from None
    if nuevo < 0:
        raise NoGravadoImposible("El importe no gravado no puede ser negativo")

    # Lo que NO es este campo se queda como está, y la base absorbe el resto. En compras el campo declarado manda
    # sobre el desglose, así que escribir en `valor_no_gravado` deja `exonerado` e `inafecto` donde estén: no los
    # borra, simplemente dejan de contar mientras el campo esté declarado (`adquisiciones_no_gravadas`).
    otros_no_gravados = CERO if campo == "valor_no_gravado" else sum(
        getattr(c, k) for k in ("exonerado", "inafecto") if k != campo)
    base = c.total - c.igv - nuevo - otros_no_gravados - c.exportacion - _cargos(c)
    if base < 0:
        raise NoGravadoImposible("Ese importe no gravado, con el IGV y los demás, supera el total del comprobante")

    fila: dict[str, Decimal | None] = {campo: nuevo, "base_gravada": base}
    if campo == "valor_no_gravado" and nuevo == 0:
        fila[campo] = None
    return {k: v if v is None else Decimal(v).quantize(CENTIMO, rounding=ROUND_HALF_UP) for k, v in fila.items()}


# El orden en que `aplicar_total` busca quién absorbe el total. `valor_no_gravado` va el segundo, detrás de
# la base y delante del desglose, porque es el campo con el que el RCE informa lo no gravado de una compra
# (su campo 21) y ahí no existen `exonerado` ni `inafecto`: sin él, corregir el total de una compra no
# gravada la convertía en gravada sin IGV —el importe caía en `base_gravada`— y encima dejaba el campo viejo
# sin tocar, o sea el total contado dos veces. Admite None, de ahí el `or CERO` de abajo.
PRINCIPALES = ("base_gravada", "valor_no_gravado", "inafecto", "exonerado", "exportacion")


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
    principal = next((k for k in PRINCIPALES if (getattr(c, k) or CERO) > 0), "base_gravada")
    # `adquisiciones_no_gravadas` y no `inafecto + exonerado`: dice dónde vive lo no gravado de ESTE
    # comprobante —el campo declarado en una compra del RCE, la suma de los dos en todo lo demás— y es la
    # misma propiedad con la que `validar` comprueba el total. Dos cuentas distintas para lo mismo es lo que
    # tenía a 460 compras de un enero real avisando «no cuadra».
    resto = (c.base_gravada + c.igv + c.adquisiciones_no_gravadas + c.exportacion + _cargos(c)
             - (getattr(c, principal) or CERO))
    valor = nuevo - resto
    if valor < 0:
        raise TotalImposible("Ese total es menor que el IGV más los otros importes del comprobante")
    fila = {"total": nuevo, principal: valor, "dscto_base": c.dscto_base, "dscto_igv": c.dscto_igv}
    if principal == "base_gravada":
        fila["igv"] = c.igv
        _seguir_descuento(c, fila, TotalImposible)
        del fila["igv"]
    return {k: Decimal(v).quantize(CENTIMO, rounding=ROUND_HALF_UP) for k, v in fila.items()}
