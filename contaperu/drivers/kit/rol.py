"""Qué papel hace una línea del asiento, **derivado de los datos que trae** y no leído de una etiqueta.

Esto vive en el kit de los drivers y no en el núcleo, y es la decisión que lo explica todo: **el `rol` existe para
los destinos.** Un sistema legacy necesita saber cuál de las cinco líneas de una compra con detracción lleva el IGV
en su columna, y no puede averiguarlo por la cuenta —la elige cada empresa—. El núcleo, en cambio, no decide nada
por él: su huella lo excluye («es una etiqueta sobre el asiento, no el asiento»), el resumen solo lo recolecta para
informarlo y la api avisa de uno desconocido diciendo «se lee igual… No rompe». Así que el cálculo pertenece a esta
capa, que es la que lo usa (John, 10-oct-2026).

**Es la lógica de SAF-T.** El estándar de auditoría de la OCDE no tiene campo de rol: distingue una línea por los
datos que trae —`CustomerID`/`SupplierID` para el tercero, `TaxInformation` para el tributo—. XBRL GL tampoco lo
tiene (`account` + `documentType` + `debitCreditCode`), ni Beancount ni hledger, que llevan cuenta e importe con
signo. El único precedente de un papel de línea es Odoo, y **usa dos vocabularios distintos**: `product`/`tax`/
`payment_term` en una factura y `liquidity`/`counterpart`/`writeoff` en un pago.

La regla, en el orden en que se pregunta, con lo que separa cada tramo:

1. **Los tres que su propio bloque identifica.** `impuesto`, `retencion` y `detraccion` son los únicos roles que
   llevan un bloque tipado, y ninguno más lo lleva. Es exactamente el `TaxInformation` de SAF-T. Van primero porque
   dos de ellos —la retención y la detracción— caen en el lado de la contraparte y el tramo 2 los confundiría.
2. **El lado dice si es la contraparte.** El `tercero` es la línea que va al lado al que este libro manda su
   contraparte: el Haber en una compra, el Debe en una venta.
3. **En el lado del hecho, la contraparte separa el hecho de un recorte.** Lo que queda son `principal` —el gasto
   de una compra, el ingreso de una venta, que es de la empresa y no de nadie más— y `recorte`, que mueve el saldo
   de un tercero en dirección contraria a como nació (el traslado de la detracción). Por eso el `recorte` lleva
   `contraparte_doc` y el `principal` no: recortar es recortarle a alguien.

Y el término que no se puede olvidar: **en una nota de crédito los dos lados se cambian** (`TIPOS_INVIERTEN`), así
que el lado del tercero se invierte con ellos. Sin ese término, el `tercero` de una nota de crédito de compra —que
va al Debe, medido— se derivaría como `recorte`.

**El orden de los tramos 2 y 3 se midió, no se supuso.** La primera versión preguntaba por `contraparte_doc` antes
que por el lado, y falló en una línea de las 324 de la batería: **el cliente de una boleta**, que no lleva RUC
porque es un consumidor final, y salía `principal` en vez de `tercero`. El sentido no tiene ese agujero: el
`tercero` está en su lado con documento de identidad o sin él.
"""
from __future__ import annotations

from typing import Any

from ...catalogos import TIPOS_INVIERTEN
from ...modelo.libro import ORIGEN_YA_ARMADO, RASGOS, Rasgos, rasgos_de

# El elemento del PCGE en el que vive el efectivo: «10 · EFECTIVO Y EQUIVALENTES AL EFECTIVO» (p. 17).
# Es la fuente con la que se distingue la línea del dinero de la de un gasto en un libro de tesorería.
GRUPO_EFECTIVO = "10"

# Los tres roles que su propio bloque tipado identifica, en el orden en que se preguntan. El orden importa en uno:
# la línea de la detracción **también** lleva `contraparte_doc`, así que si se preguntara antes por la contraparte
# saldría clasificada como tercero.
POR_SU_BLOQUE: tuple[tuple[str, str], ...] = (("impuesto", "impuesto"), ("retencion", "retencion"),
                                              ("detraccion", "detraccion"))


# Los papeles que esta regla puede devolver, enumerados al lado de la función que los devuelve. **`tesoreria` dejó
# de estar reservado en la 12.8**, cuando el motor empezó a emitir la línea del efectivo: lo que lo desbloqueó no
# fue una decisión sino una fuente, el elemento **10 del PCGE** —«Efectivo y equivalentes al efectivo», p. 17—, que
# es palabra por palabra lo que el catálogo del estándar define como ese rol («el dinero moviéndose: caja, banco o
# equivalente»). El que sigue RESERVADO es `contrapartida`, para el diario que produce un ERP (B13), y un pago a un
# proveedor NO lo usa: su 42 lleva `contraparte_doc`, así que es `tercero`. Que «reservado» signifique algo lo
# comprueba `tests/test_vocabulario.py`, comparando esta tupla con lo que los libros declaran.
ROLES_QUE_DERIVA: frozenset[str] = frozenset({rol for _, rol in POR_SU_BLOQUE}
                                             | {"tercero", "recorte", "principal", "tesoreria"})


class RolNoDerivable(ValueError):
    """Se pidió el rol de una línea de un libro cuyo asiento el motor no origina.

    No es un fallo de la regla: es que no hay nada que derivar. Un libro de tesorería no declara roles
    (`modelo.RASGOS`) justamente porque el motor no emite ni una línea suya, así que nadie sabe todavía qué papeles
    tendrá su asiento — lo dirá el archivo del destino que lo acepte."""


def _campo(linea: Any, nombre: str) -> Any:
    """El campo de una línea, venga como `LineaDiario` o como el diccionario que produce `a_dict()`.

    Las dos formas circulan: un driver recibe objetos y un test o un ERP de fuera, diccionarios. Es el mismo trato
    que da `tesoreria.cuadra`."""
    if isinstance(linea, dict):
        return linea.get(nombre)
    return getattr(linea, nombre, None)


def rol_de(linea: Any, libro: Any) -> str:
    """El papel de esta línea, derivado. Acepta la línea como objeto o como diccionario, y el libro, sus rasgos o
    el tipo por su nombre.

    Devuelve siempre uno de los roles que el motor emite (`asiento.ROLES_DEL_MOTOR`). No devuelve `contrapartida`
    ni `tesoreria`: son vocabulario para quien produce un asiento que el motor no origina, y por eso están en el
    catálogo y fuera de esa tupla."""
    rasgos = rasgos_de(libro)
    # **Un libro que llega ya armado no tiene rol que derivar, y eso es un dato y no un fallo** (B13): la columna
    # existe en el CSV y en el pre-mayor, y lo que corresponde escribir ahí es nada. Lanzar sería tratar «aquí
    # eso no se puede saber» como «te equivocaste», y dejaría a un destino neutral sin poder escribir un diario
    # que por lo demás está completo. Quien produjo esas líneas sabe qué papel cumple cada una; este motor no.
    if rasgos.origen == ORIGEN_YA_ARMADO:
        return ""
    if not rasgos.roles:
        con_roles = sorted(t for t, r in RASGOS.items() if r.roles)
        raise RolNoDerivable(
            f"El motor no origina el asiento de un libro {rasgos.tipo!r}, así que no declara qué roles caben en él "
            f"y no hay nada que derivar. Los libros que sí: {', '.join(con_roles)}.")

    for bloque, rol in POR_SU_BLOQUE:
        if _campo(linea, bloque):
            return rol

    # Lo que queda depende de POR DÓNDE entró el libro, y lo elige la tabla del final (13.1).
    return DERIVACION_DEL_ROL[rasgos.origen](linea, rasgos)


def _rol_del_dinero(linea: Any, rasgos: Rasgos) -> str:
    """El rol de una línea de tesorería: lo distingue QUÉ cuenta es, no a qué lado cae.

    **Se deriva aparte del comprobante, y no es una variante suya**, por dos razones. Una es que el camino del
    comprobante lee `rasgos.sentido_contraparte`, que en un libro cuyo lado lo dice cada operación **levanta** en
    vez de contestar. La otra es que aquí no hay un lado «de la contraparte» que preguntar: lo que distingue una
    línea de otra es qué cuenta es, y para eso hay fuente publicada —el elemento 10 del PCGE—.
    """
    if str(_campo(linea, "contraparte_doc") or "").strip():
        return "tercero"            # el 42 de un pago o el 12 de un cobro: se le debe a alguien
    cuenta = str(_campo(linea, "cuenta") or "").strip()
    return "tesoreria" if cuenta.startswith(GRUPO_EFECTIVO) else "principal"


def _rol_del_comprobante(linea: Any, rasgos: Rasgos) -> str:
    """El rol de una línea de una compra o una venta: lo dice el lado al que cae, contra el del libro."""
    # El lado al que va la contraparte en este libro, cambiado si el comprobante invierte los sentidos.
    tipo_cp = str((_campo(linea, "documento") or {}).get("tipo_cp") or "").strip()
    lado_del_tercero = rasgos.sentido_principal if tipo_cp in TIPOS_INVIERTEN else rasgos.sentido_contraparte
    if str(_campo(linea, "debe_haber") or "") == lado_del_tercero:
        return "tercero"
    return "recorte" if str(_campo(linea, "contraparte_doc") or "").strip() else "principal"


# **Cómo se deriva el rol, dicho por el origen del libro y no por su nombre** (13.1). Los tramos de antes de la
# tabla —el guardián de los `roles` vacíos y `POR_SU_BLOQUE`— son comunes a los dos y se quedan arriba: lo que
# cambia es solo el final, que en un comprobante mira el lado y en el dinero mira la cuenta.
def _rol_de_lo_ya_armado(linea: Any, rasgos: Rasgos) -> str:
    """Un libro que llega armado **no tiene rol que derivar**: la columna sale vacía.

    La regla lee el lado contra el del libro, o la cuenta contra el elemento 10 del PCGE. Un Libro Diario no fija
    lado —cada asiento el suyo— y sus líneas pueden ser cualquier cosa: una planilla, una depreciación, un
    ajuste. Derivar aquí sería adivinar. En la práctica no se alcanza, porque `rol_de` corta antes por el mismo
    motivo; está escrita para que la tabla esté completa y el día que alguien cambie aquel atajo esto siga
    diciendo lo mismo.
    """
    return ""


DERIVACION_DEL_ROL = {"comprobantes": _rol_del_comprobante, "movimientos": _rol_del_dinero,
                      "asiento": _rol_de_lo_ya_armado}
