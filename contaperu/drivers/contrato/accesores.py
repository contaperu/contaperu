"""Leer lo que un driver declara, con su valor por defecto cuando no lo declara.

Toda pregunta sobre un driver pasa por aquí —qué forma tiene, qué canal, qué exige, qué columnas admite— y
nadie mira sus constantes directamente. Así un valor por defecto se decide una vez, y añadir algo opcional
al contrato no obliga a tocar a los diez drivers que ya existen.
"""
from __future__ import annotations

import copy
import inspect
from typing import Any

from ... import configuracion as _declaracion
from ...asiento.faltas import NoExportable
from ...asiento.motor import CENTRO_EN_ANEXO
from ...configuracion import Campo, Columna
from ...modelo import Comprobante, Libro
from .taxonomia import (EXIGE_NUCLEO_ASIENTO, EXIGE_NUCLEO_NEUTRAL, EXIGE_NUCLEO_REGISTRO, FAMILIA, FORMAS,
                        TIPO_DEL_PLAN, VOCABULARIO_POR_DEFECTO)

def forma(modulo: Any) -> str:
    """Cuál de las cuatro formas implementa el driver (la preferida si expone varias); '' si ninguna."""
    return next((f for f in FORMAS if callable(getattr(modulo, f, None))), "")


def familia(modulo: Any) -> str:
    """'registro' (una fila por comprobante: `linea`, `desde_comprobantes`) o 'asiento' (
    `desde_lineas`); '' si no implementa ninguna forma."""
    return FAMILIA.get(forma(modulo), "")


def canal(modulo: Any) -> str:
    """A quién se entrega lo que sale: el `CANAL` que declara el driver —`legacy`, `sunat` o `erp`—. Vacío si no lo
    declara, que desde la 4.0 es un incumplimiento y no un defecto: hasta la 3.10 se trataba como `legacy`.

    Desde la 8.0 esta es la única palabra del destino. Había una segunda, `grupo()`, que traducía el canal a «SIRE»,
    «Legacy» o «ERP» para quien integra; se retiró con su tabla porque eran dos vocabularios para lo mismo y el de
    fuera mentía en el PLE."""
    return str(getattr(modulo, "CANAL", None) or "")


def declara_canal(modulo: Any) -> bool:
    """Si declara su `CANAL`, que es **obligatorio** desde la 4.0 (antes se trataba como `legacy`). Lo comprueba
    `incumplimientos`, así que un driver sin canal no carga; esto queda para que quien escriba uno lo pregunte."""
    return bool(getattr(modulo, "CANAL", None))


def vocabulario(modulo: Any) -> str:
    """Con qué vocabulario recibe sus líneas: el `VOCABULARIO` que declara, o `legacy` si no lo declara."""
    return getattr(modulo, "VOCABULARIO", None) or VOCABULARIO_POR_DEFECTO


def acepta_indice(modulo: Any) -> bool:
    """¿Su `desde_lineas` recibe el índice de cada comprobante? Lo decide su firma: un parámetro `indice` o `**kwargs`.
    Así un driver de terceros escrito antes de la 1.0 sigue funcionando sin él."""
    funcion = getattr(modulo, "desde_lineas", None)
    if not callable(funcion):
        return False
    try:
        parametros = inspect.signature(funcion).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(p.name == "indice" or p.kind is p.VAR_KEYWORD for p in parametros)


def lleva_cuentas(modulo: Any) -> bool:
    """¿Necesita la configuración contable del contribuyente? Todo driver que lleva cuentas: los de asientos y el
    registro de un sistema contable (`desde_comprobantes`). El registro de SUNAT con forma `linea`, no."""
    return forma(modulo) in ("desde_lineas", "desde_comprobantes")


def arma_asientos(modulo: Any) -> bool:
    """¿Arma asientos, y necesita por eso además los correlativos? Las dos formas de la familia asiento, y desde la
    4.2 también un **registro de SUNAT que recibe las líneas** (`desde_lineas`).

    Lo pidió el Libro Diario del PLE: su campo 2 es el CUO, que se compone del sub-diario y del correlativo del
    asiento, así que sin correlativos no hay archivo. Su familia es `registro` —viene del canal, y es correcta: lo que
    produce es un registro que se presenta a SUNAT— pero numera igual que CONCAR.

    **Para los drivers de antes de la 4.2 la condición no cambia**: todos los `desde_lineas` que había eran ya de
    familia asiento, así que esto no mueve ni un correlativo de los que ya se escribían."""
    return familia(modulo) == "asiento" or forma(modulo) == "desde_lineas"


def excluye_tipos(modulo: Any) -> frozenset[str]:
    """Los tipos de comprobante que ese destino NO lleva (su `EXCLUYE_TIPOS`, opcional).

    El SIRE y CONTASIS dejan fuera el recibo por honorarios (`02`). Es un accesor y no un `getattr` suelto por la
    misma razón que `exige` y `no_caben`: quien integra el motor pregunta al contrato y no al módulo, así que el
    día que esto se declare de otra forma no hay que buscar los `getattr` repartidos por ahí fuera."""
    return frozenset(getattr(modulo, "EXCLUYE_TIPOS", None) or ())


def exige(modulo: Any) -> frozenset[str]:
    """Todo lo que ese destino exige para exportar: lo del núcleo para su forma más lo que el driver declara en
    `EXIGE`. Un registro de SUNAT con forma `linea` no exige nada de esto: no lleva cuentas."""
    declarado = frozenset(getattr(modulo, "EXIGE", None) or ())
    if arma_asientos(modulo):
        nucleo = EXIGE_NUCLEO_NEUTRAL if vocabulario(modulo) == "neutral" else EXIGE_NUCLEO_ASIENTO
        return nucleo | declarado
    if forma(modulo) == "desde_comprobantes":
        return EXIGE_NUCLEO_REGISTRO | declarado
    return frozenset()


def configuracion(modulo: Any) -> tuple[Campo, ...]:
    """Lo que se configura en la sección del driver (su `CONFIGURACION`); vacío si no declara nada."""
    return tuple(getattr(modulo, "CONFIGURACION", None) or ())


def cuentas_por_defecto(modulo: Any) -> dict:
    """Las cuentas de la CONTRAPARTIDA con las que nace una empresa que lleva este sistema: lo que declara en
    `CUENTAS_POR_DEFECTO` **sin las dos claves del plan**, que no son configuración (`plan_base`). Es lo que
    `config_aplicada` funde debajo de lo que la empresa haya guardado. Vacío si no declara ninguna.

    Devuelve una copia: el dict del driver es de fábrica y nadie de fuera lo muta."""
    declaradas = copy.deepcopy(getattr(modulo, "CUENTAS_POR_DEFECTO", None) or {})
    return {clave: valor for clave, valor in declaradas.items() if clave not in TIPO_DEL_PLAN}


def plan_base(modulo: Any) -> tuple[dict[str, str], ...]:
    """Con qué PLAN DE CUENTAS nace una empresa que lleva este sistema: `({"codigo", "tipo"}, …)`, una fila por cada
    clave del plan que el driver declare (3.0).

    Es la lista que esa empresa elige al imputar cada comprobante —una cuenta de compras y una de ventas, que es de
    donde se parte—, no un valor que se aplique solo: **la cuenta de un comprobante viene siempre en su imputación**.
    Vacío si el driver no declara ninguna, que es el caso de quien no es el sistema de nadie."""
    declaradas = getattr(modulo, "CUENTAS_POR_DEFECTO", None) or {}
    return tuple({"codigo": str(declaradas[clave]).strip(), "tipo": tipo}
                 for clave, tipo in TIPO_DEL_PLAN.items() if str(declaradas.get(clave) or "").strip())


def columnas_elegibles(modulo: Any) -> dict[str, tuple[Columna, ...]]:
    """En qué columnas de su archivo puede ir cada dato (su `COLUMNAS_ELEGIBLES`); vacío si no declara ninguna."""
    return {dato: tuple(declaradas) for dato, declaradas in (getattr(modulo, "COLUMNAS_ELEGIBLES", None) or {}).items()}


def seccion_por_defecto(modulo: Any) -> dict:
    """Los valores por defecto de la sección del driver, como se guardan, con sus `columnas` fijas y marcadas."""
    return _declaracion.por_defecto(configuracion(modulo), columnas_elegibles(modulo))


def describir(modulo: Any) -> dict:
    """La sección del driver en JSON, para pintar su pantalla: sus campos y sus columnas elegibles."""
    return {"sistema": modulo.NOMBRE, **_declaracion.describir(configuracion(modulo), columnas_elegibles(modulo))}


def columnas_elegidas(modulo: Any, config: dict, dato: str = "centro_costo") -> tuple[str, ...]:
    """En qué columnas de ESTE driver sale ese dato: las que la configuración eligió (`columnas.<dato>`) o, si no
    eligió ninguna, las que el driver trae marcadas de fábrica.

    Es una sola regla y la usan dos: el núcleo, para saber qué líneas llevan el centro en su anexo
    (`centro_en_anexo`), y el driver que escribe una segunda columna de centro. Hasta la 3.1 CONTASIS la
    reimplementaba contra su propio `por_defecto`, que es el mismo cálculo escrito dos veces."""
    declaradas = columnas_elegibles(modulo).get(dato)
    if not declaradas:
        return ()
    elegidas = ((config or {}).get("columnas") or {}).get(dato)
    if elegidas is None:
        elegidas = [c.columna for c in declaradas if c.fija or c.marcada]
    return tuple(elegidas)


def centro_en_anexo(modulo: Any, config: dict) -> frozenset[str]:
    """Qué líneas del asiento llevan el centro en su anexo auxiliar para ESTE driver: las de las columnas que la
    configuración eligió para el centro (`columnas.centro_costo`) o, si no eligió, las marcadas de fábrica. Un driver
    que no declara columnas lleva lo del estándar (`asiento.CENTRO_EN_ANEXO`)."""
    declaradas = columnas_elegibles(modulo).get("centro_costo")
    if not declaradas:
        return CENTRO_EN_ANEXO
    elegidas = columnas_elegidas(modulo, config)
    return frozenset(c.rol for c in declaradas if c.campo == "anexo_auxiliar" and c.columna in elegidas)


class NoCabe(NoExportable):
    """Comprobantes que el formato del destino no puede llevar, por motivo (lo dice el driver en `no_caben`). El
    núcleo se niega antes de escribir nada, igual que con un tipo sin sigla."""

    clave = "no_cabe"

    def __init__(self, motivos: dict[str, list[Comprobante]]):
        unicos = list({id(c): c for lista in motivos.values() for c in lista}.values())
        mensaje = f"{len(unicos)} comprobante(s) que el formato del destino no puede llevar: " + "; ".join(motivos)
        super().__init__(mensaje, unicos)
        self.motivos = motivos


def no_caben(modulo: Any, libro: Libro, comprobantes: list[Comprobante], config: dict) -> dict[str, list[Comprobante]]:
    """Lo que el driver dice que no cabe en su formato (su `no_caben`, opcional), sin los motivos vacíos."""
    declarado = getattr(modulo, "no_caben", None)
    if not callable(declarado):
        return {}
    return {motivo: list(lista) for motivo, lista in (declarado(libro, comprobantes, config) or {}).items() if lista}

