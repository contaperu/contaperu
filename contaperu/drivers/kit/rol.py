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
from ...modelo.libro import RASGOS, rasgos_de

# Los tres roles que su propio bloque tipado identifica, en el orden en que se preguntan. El orden importa en uno:
# la línea de la detracción **también** lleva `contraparte_doc`, así que si se preguntara antes por la contraparte
# saldría clasificada como tercero.
POR_SU_BLOQUE: tuple[tuple[str, str], ...] = (("impuesto", "impuesto"), ("retencion", "retencion"),
                                              ("detraccion", "detraccion"))


# Los papeles que esta regla puede devolver, enumerados al lado de la función que los devuelve. El catálogo del
# estándar publica dos más —`contrapartida` y `tesoreria`—, y están RESERVADOS **para dos hitos distintos**:
# `tesoreria` para el asiento de tesorería (D6) y `contrapartida` para el diario que produce un ERP (B13). Un pago a
# un proveedor NO usa `contrapartida`: su 42 lleva `contraparte_doc`, así que es `tercero` y la regla de abajo ya
# sabría derivarlo. Que «reservado» signifique algo lo comprueba
# `tests/test_vocabulario.py`, comparando esta tupla con lo que los libros declaran.
ROLES_QUE_DERIVA: frozenset[str] = frozenset({rol for _, rol in POR_SU_BLOQUE} | {"tercero", "recorte", "principal"})


class RolNoDerivable(ValueError):
    """Se pidió el rol de una línea de un libro cuyo asiento el motor no origina.

    No es un fallo de la regla: es que no hay nada que derivar. Un libro de tesorería no declara roles
    (`modelo.RASGOS`) justamente porque el motor no emite ni una línea suya, así que nadie sabe todavía qué papeles
    tendrá su asiento — lo dirá el archivo del destino que lo acepte, que es el hito D6."""


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
    if not rasgos.roles:
        con_roles = sorted(t for t, r in RASGOS.items() if r.roles)
        raise RolNoDerivable(
            f"El motor no origina el asiento de un libro {rasgos.tipo!r}, así que no declara qué roles caben en él "
            f"y no hay nada que derivar. Los libros que sí: {', '.join(con_roles)}.")

    for bloque, rol in POR_SU_BLOQUE:
        if _campo(linea, bloque):
            return rol

    # El lado al que va la contraparte en este libro, cambiado si el comprobante invierte los sentidos.
    tipo_cp = str((_campo(linea, "documento") or {}).get("tipo_cp") or "").strip()
    lado_del_tercero = rasgos.sentido_principal if tipo_cp in TIPOS_INVIERTEN else rasgos.sentido_contraparte
    if str(_campo(linea, "debe_haber") or "") == lado_del_tercero:
        return "tercero"
    return "recorte" if str(_campo(linea, "contraparte_doc") or "").strip() else "principal"
