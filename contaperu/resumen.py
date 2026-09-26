"""Cuánto es un libro, y en qué cuentas cayó: la aritmética de un mes, sin destino y sin configuración.

El motor sabía armar el asiento de un mes y decir qué le faltaba, y **no sabía decir cuánto era**. Lo
único que sumaba dinero era el `resumen` de una exportación, así que para saber cuánto compró un RUC en
agosto había que generarle un archivo. Quien integraba el motor lo escribía por su cuenta, y ahí es donde
se ve por qué no era suyo: la primera aplicación que lo hizo se quedó con el `07` donde el motor dice
`("07", "87")`, así que una nota de crédito de no domiciliado **le sumaba en vez de restarle**.

Lo que aquí se decide es lo que decide cualquiera que sume un libro peruano, y son tres cosas:

- **La nota de crédito resta** (`Comprobante.es_nota_credito`, o sea `modelo.NOTAS_CREDITO`).
- **Cada moneda va por su lado.** No hay ninguna clave que sume soles con dólares, y no la habrá:
  convertir dentro de un resumen sería una cifra nueva sin caso (`INTEROPERABILIDAD.md` §7).
- **Lo excluido no es del mes y lo duplicado no va a ningún archivo**, así que ninguno suma — pero los
  dos se cuentan, porque son dos cosas distintas y quien mira necesita saber cuál le pasó.

Y lo que NO se decide aquí, con su motivo:

- **Ningún destino.** No recibe `driver` ni configuración, y por eso está en el núcleo y no en `pipeline`:
  esta capa **no puede** importar un driver (`tests/test_capas.py`), así que la garantía de que un resumen
  no mire el destino es la capa y no una promesa. Un resumen del libro y el `resumen_por_contraparte` de
  `diagnosticar` son dos cifras distintas a propósito: aquel es lo que iría a ESE archivo —filtra lo que
  el destino no lleva— y este es el libro.
- **No valida.** Quien marca una fila como duplicada es `validar.revisar`, que necesita las claves de los
  otros periodos. Si esto la llamara, el mismo documento daría cifras distintas según lo hubieran revisado
  antes o no. Quien quiera que las duplicadas del lote se marquen solas, llama a `revisar` primero.

Recibe `Comprobante` y no diccionarios, al contrario que `partida_doble.cuadra`. La diferencia tiene
motivo: una línea de diario no tiene clase en el estándar —es un dict en todas partes— y un comprobante
sí, y tipar la entrada es lo que obliga a preguntar `c.es_nota_credito` en vez de comparar un `tipo_cp` a
mano. O sea: es lo que impide que el fallo del `87` vuelva a nacer aquí dentro.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from . import partida_doble
from .modelo import CENTIMO, CERO, Comprobante

# Cómo se puede cortar el resumen. `contraparte` tiene su caso en producción —«¿a quién le compré más
# este mes?»—; un corte por tipo de comprobante no lo tiene todavía, y la regla de la casa es que un hito
# entra con su caso real. Añadir un valor a esta tupla es aditivo y cabe en una versión menor.
AGRUPACIONES: tuple[str, ...] = ("", "contraparte")

# Las tres cifras de dinero de un libro, con el nombre que el campo ya tiene en el modelo y en el
# estándar. `base_gravada` y no «base»: un resumen no le pone nombre nuevo a un dato que ya se llama algo.
IMPORTES: tuple[str, ...] = ("base_gravada", "igv", "total")


def _texto(valor: Decimal) -> str:
    """Los importes salen como TEXTO de dos decimales, como en el resto de la api: es dinero y se cita."""
    return str(valor.quantize(CENTIMO))


def _cubos(comprobantes: Iterable[Comprobante]) -> tuple[dict, dict]:
    """Por moneda, los importes y cuántos comprobantes; y el recuento de lo que no suma."""
    monedas: dict[str, dict[str, Decimal]] = {}
    cuantos: dict[str, int] = {}
    recuento = dict.fromkeys(("recibidos", "excluidos", "duplicados", "sumados"), 0)
    for c in comprobantes:
        recuento["recibidos"] += 1
        if c.excluida:
            recuento["excluidos"] += 1
            continue
        if c.estado == "duplicada":
            recuento["duplicados"] += 1
            continue
        recuento["sumados"] += 1
        signo = Decimal(-1) if c.es_nota_credito else Decimal(1)
        moneda = (c.moneda or "PEN").upper()
        acumulado = monedas.setdefault(moneda, dict.fromkeys(IMPORTES, CERO))
        cuantos[moneda] = cuantos.get(moneda, 0) + 1
        for campo in IMPORTES:
            acumulado[campo] += signo * getattr(c, campo)
    # Soles primero, que es como se lee un total peruano; el resto, alfabético.
    totales = {moneda: {**{k: _texto(v) for k, v in monedas[moneda].items()}, "sumados": cuantos[moneda]}
               for moneda in sorted(monedas, key=lambda m: (m != "PEN", m))}
    return recuento, totales


def _cuanto(totales: dict) -> tuple:
    """Para ordenar grupos: por los soles y, sin soles, por la mayor de las otras monedas.

    Se ordena por un importe porque la pregunta es «a quién le compré más», y **no se suma ninguna
    moneda** para conseguirlo: los soles primero y las demás aparte.
    """
    def total(moneda: str) -> Decimal:
        return Decimal((totales.get(moneda) or {}).get("total") or "0.00")

    otras = [total(m) for m in totales if m != "PEN"]
    return (-total("PEN"), -max(otras) if otras else CERO)


def del_libro(comprobantes: Iterable[Comprobante], *, agrupar_por: str = "") -> dict:
    """Base gravada, IGV y total de un libro, **cada moneda por su lado**, y qué cuenta y qué suma.

    `recuento` tiene cuatro números que **no se solapan y suman `recibidos`**, y eso no es cosmética: en el
    resumen de una exportación «comprobantes» significa «los que salieron» y en la pantalla de un SaaS
    significa «los que no están excluidos» — la misma palabra para dos cifras. Aquí cada número dice una
    sola cosa y nadie tiene que restar dos claves para obtener la tercera.

    Con `agrupar_por="contraparte"`, los mismos totales por proveedor o cliente, de más a menos, agrupados
    por su **documento** y no por su nombre: el mismo RUC llega escrito de tres maneras según quién lo
    leyera, y por el nombre saldría partido en tres.
    """
    agrupar_por = (agrupar_por or "").strip().lower()
    if agrupar_por not in AGRUPACIONES:
        posibles = ", ".join(repr(a) for a in AGRUPACIONES)
        raise ValueError(f"No sé agrupar por {agrupar_por!r}. Puedo: {posibles}")

    todos = list(comprobantes)
    recuento, totales = _cubos(todos)
    salida = {"recuento": recuento, "totales": totales, "agrupado_por": agrupar_por, "grupos": []}
    if not agrupar_por:
        return salida

    grupos: dict[str, list[Comprobante]] = {}
    for c in todos:
        grupos.setdefault(c.contraparte_doc or "", []).append(c)
    fichas = []
    for clave, suyos in grupos.items():
        suyo_recuento, suyos_totales = _cubos(suyos)
        if not suyos_totales:
            continue          # todo excluido o duplicado: no es una contraparte del mes
        # La etiqueta es el último nombre no vacío del grupo: el más reciente que alguien vio.
        etiqueta = next((c.contraparte_nombre for c in reversed(suyos) if c.contraparte_nombre), "")
        fichas.append({"clave": clave, "etiqueta": etiqueta,
                       "recuento": suyo_recuento, "totales": suyos_totales})
    salida["grupos"] = sorted(fichas, key=lambda g: (*_cuanto(g["totales"]), g["etiqueta"], g["clave"]))
    return salida


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
    la cuenta por pagar aparece como `tercero` y como `detraccion_tercero`. `clase` es singular: se deriva
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
