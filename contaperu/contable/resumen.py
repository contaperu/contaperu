"""En qué cuentas cayó un asiento: el pre-mayor, sin destino y sin configuración.

Recibe líneas de diario —dicts u objetos, la misma entrada que `partida_doble.cuadra`— y las agrupa por
cuenta. **No sabe de compras ni de ventas y no mira ni un campo de ningún comprobante**, que es lo que le
da derecho a estar en este paquete: aquí vive la contabilidad que no depende del país ni del régimen.

**Hasta la 12.11 vivía aquí también `del_libro`**, que suma un libro de compras o de ventas, y no cumplía
ese criterio: para sumarlo hay que saber que la nota de crédito resta y qué códigos de la Tabla 10 lo son,
o sea el catálogo del Perú. Se fue a `comprobantes/resumen.py`, con su `AGRUPACIONES` y su `IMPORTES`, y
este módulo las reexporta porque `AGRUPACIONES` es el `enum` de un esquema público (`api/tabla.py`) y
quien la importaba de aquí no tiene por qué enterarse de la mudanza.
"""
from __future__ import annotations

from typing import Any, Iterable

from ..comprobantes.resumen import AGRUPACIONES, IMPORTES, del_libro
from ..contable import partida_doble
from ..modelo.coerciones import texto_monto as _texto

__all__ = ["AGRUPACIONES", "IMPORTES", "del_libro", "por_cuenta"]


def por_cuenta(lineas: Iterable[Any]) -> dict:
    """El pre-mayor: cuánto cayó en cada cuenta, con su debe y su haber **por moneda**, y el cuadre.

    La misma entrada que `partida_doble.cuadra`: las líneas de diario, como dicts o como objetos. Aquí no
    se contabiliza nada —se agrupa lo ya contabilizado—, así que esta función no sabe de compras ni de
    ventas y no mira ni un campo de ningún comprobante.

    **El cuadre lo suma `partida_doble.cuadra` sobre cada montón**, no una cuenta paralela: así el
    pre-mayor y el cuadre no pueden discrepar por construcción, y no hace falta un test que lo vigile. Y
    el cuadre **por moneda** dice algo que el global no puede: dos monedas cuyos descuadres se compensan
    salen cuadradas en el total y descuadradas cada una.

    `roles` va en plural porque la misma cuenta puede hacer dos papeles en un asiento: con una detracción,
    la cuenta por pagar aparece como `tercero` y como `recorte`. `clase` es singular: se deriva
    del primer dígito de la cuenta y no puede variar entre dos líneas de la misma.
    """
    todas = list(lineas)

    def campo(linea: Any, nombre: str) -> str:
        valor = linea.get(nombre) if isinstance(linea, dict) else getattr(linea, nombre, "")
        return str(valor or "")

    cuentas: dict[str, dict] = {}
    por_moneda: dict[str, list] = {}
    for linea in todas:
        cuenta = campo(linea, "cuenta")
        moneda = (campo(linea, "moneda") or "PEN").upper()
        ficha = cuentas.setdefault(cuenta, {"cuenta": cuenta, "clase": campo(linea, "clase"),
                                            "roles": set(), "lineas": 0, "por_moneda": {}})
        if campo(linea, "rol"):
            ficha["roles"].add(campo(linea, "rol"))
        ficha["lineas"] += 1
        ficha["por_moneda"].setdefault(moneda, []).append(linea)
        por_moneda.setdefault(moneda, []).append(linea)

    def monedas_ordenadas(cubos: dict) -> list[str]:
        return sorted(cubos, key=lambda m: (m != "PEN", m))

    fichas = []
    for cuenta in sorted(cuentas):
        ficha = cuentas[cuenta]
        suyas = ficha.pop("por_moneda")
        cuadres = {m: partida_doble.cuadra(suyas[m]) for m in monedas_ordenadas(suyas)}
        # De una cuenta solo su debe y su haber: una cuenta no tiene por qué cuadrar, y poner ahí un
        # `cuadra: false` invitaría a leer como un error lo que es el saldo normal de una cuenta.
        fichas.append({**ficha, "roles": sorted(ficha["roles"]),
                       "por_moneda": {m: {"debe": _texto(c.debe), "haber": _texto(c.haber)}
                                      for m, c in cuadres.items()}})
    return {
        "cuentas": fichas,
        "por_moneda": {m: partida_doble.cuadra(por_moneda[m]).a_dict()
                       for m in monedas_ordenadas(por_moneda)},
        "cuadre": partida_doble.cuadra(todas).a_dict(),
    }
