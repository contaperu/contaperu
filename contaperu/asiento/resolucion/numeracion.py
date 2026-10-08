"""La numeración del asiento —`MM` más un correlativo de cuatro dígitos por sub-diario— y los límites del
periodo del libro, que es el marco dentro del que cae la fecha de cada asiento.

Un comprobante que no mueve dinero no gasta número: el porqué, en `numerar_en_orden`.
"""
from __future__ import annotations

import calendar
from datetime import date

from ...modelo import Comprobante, Libro
from ..faltas import SinCorrelativo, SinSigla
from .clasificacion import con_efecto_contable, sub_diario, sub_diarios_presentes
from .requisitos import tipos_sin_sigla


def numerar(comprobantes: list[Comprobante], config: dict, periodo: str,
            correlativos: dict[str, int], es_venta: bool = False) -> tuple[dict[int, str], dict[str, dict]]:
    """Asigna a cada comprobante (por `id()` del objeto) su número `MMNNNN`, en el orden
    recibido (el natural del registro). Devuelve también el rango usado por sub-diario,
    que es lo que se recuerda para proponer el siguiente.

    Es la forma de la 0.x, que ata el resultado a la identidad de cada objeto; la del motor es `numerar_en_orden`."""
    numeros, rangos = numerar_en_orden(comprobantes, config, periodo, correlativos, es_venta)
    return {id(c): numero for c, numero in zip(comprobantes, numeros)}, rangos


def numerar_en_orden(comprobantes: list[Comprobante], config: dict, periodo: str,
                     correlativos: dict[str, int], es_venta: bool = False) -> tuple[list[str], dict[str, dict]]:
    """El número `MMNNNN` de cada comprobante, en el orden recibido y en la misma posición, y el rango usado por
    sub-diario. No depende de la identidad de los objetos: dos llamadas con los mismos datos dan lo mismo.

    **Un comprobante que no mueve dinero no gasta número** (`sin_efecto_contable`): sale con el suyo en blanco y el
    siguiente se lleva el que le tocaba. Si consumiera uno, el asiento tendría un vóucher sin líneas y el rango que se
    recuerda para el mes siguiente contaría comprobantes que nunca se escribieron."""
    mes_mm = str(periodo)[4:6]
    sin_equivalencia = tipos_sin_sigla(comprobantes, config)
    if sin_equivalencia:
        raise SinSigla(sin_equivalencia)
    con_asiento = con_efecto_contable(comprobantes, config)
    presentes = sub_diarios_presentes(con_asiento, config, es_venta)
    faltan = [s for s in presentes if s not in correlativos]
    if faltan:
        raise SinCorrelativo(faltan)
    contadores = {s: int(correlativos[s]) for s in presentes}
    if any(n < 1 for n in contadores.values()):
        raise ValueError("Los correlativos empiezan en 1")
    sin_numero = {id(c) for c in comprobantes} - {id(c) for c in con_asiento}
    numeros: list[str] = []
    rangos: dict[str, dict] = {s: {"desde": n, "hasta": n - 1, "comprobantes": 0} for s, n in contadores.items()}
    for c in comprobantes:
        if id(c) in sin_numero:
            numeros.append("")
            continue
        s = sub_diario(c, config, es_venta)
        n = contadores[s]
        numeros.append(f"{mes_mm}{n:04d}")
        rangos[s]["hasta"] = n
        rangos[s]["comprobantes"] += 1
        contadores[s] = n + 1
    for s, r in rangos.items():
        r["desde_codigo"], r["hasta_codigo"] = f"{mes_mm}{r['desde']:04d}", f"{mes_mm}{r['hasta']:04d}"
        r["desborda"] = r["hasta"] > 9999
    return numeros, rangos


def limites_del_periodo(libro: Libro) -> tuple[date, date]:
    """El primer y el ultimo dia del periodo del libro.

    Es el marco dentro del que cae la fecha de cada asiento: un comprobante extemporaneo
    (emitido en un mes anterior) se asienta el dia 1, y uno posterior, el ultimo dia. La
    fecha del documento se conserva aparte, siempre."""
    return (date(libro.anio, libro.mes, 1),
            date(libro.anio, libro.mes, calendar.monthrange(libro.anio, libro.mes)[1]))
