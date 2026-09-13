"""Lo que el asiento necesita saber antes de armarse: configuración efectiva, clasificación de
cada comprobante (sigla, sub-diario, cuentas) y numeración por sub-diario. Las reglas de negocio y
su porqué, en el docstring del paquete (`__init__.py`).

Las líneas de la partida doble se arman en `motor.py`, en el vocabulario neutral de `open-accounting`;
las columnas de CONCAR, en su driver (`drivers/concar/proyeccion.py`).
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import Any

from ..catalogos import TIPO_BOLETA, TIPO_HONORARIOS
from ..igv import base_imputable
from ..modelo import Comprobante, Libro, a_decimal
from .configuracion import CONFIG_POR_DEFECTO
from .faltas import FALTAS, SubDiarioSinCorrelativo, TipoSinEquivalencia
from .imputacion import Imputacion


# ── Configuración por RUC ─────────────────────────────────────────────────────

def fundir_config(defaults: dict, overrides: dict) -> dict:
    """Overrides sobre defaults, dict a dict (un sistema anterior lo hacía a 1 nivel: sobreescribir `cxp.USD`
    borraba `cxp.PEN`; aquí se funde en profundidad)."""
    out: dict = {k: (fundir_config(v, {}) if isinstance(v, dict) else v) for k, v in (defaults or {}).items()}
    if not isinstance(overrides, dict):
        return out
    for k, v in overrides.items():
        if isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k] = fundir_config(out[k], v)
        else:
            out[k] = v
    return out


def config_aplicada(config_contable: dict | None = None) -> dict:
    """La configuración que se aplica a un entorno: `CONFIG_POR_DEFECTO` con su `config_contable` fundida encima.

    Plana, como la guarda la aplicación: la configuración es del entorno, sin capas ni clave intermedia (John,
    12-sep-2026; hasta entonces había una capa del estudio y cada capa iba bajo `contabilidad`). `fundir_config` funde
    en profundidad: el entorno puede cambiar solo `cuentas.cxp.USD` y hereda el resto."""
    return fundir_config(CONFIG_POR_DEFECTO, config_contable or {})


def etiquetas_sub_diario(config: dict) -> dict[str, str]:
    """{numero: uso} segun la config vigente, para el modal de exportar y el resumen.
    Si el estudio renumera (honorarios → 33), el 33 sale etiquetado. Dos usos con el
    mismo numero se unen con " · " (p. ej. un CONCAR que no separa la detraccion)."""
    tipos = config.get("tipos") or {}
    usos = [
        (str(config.get("sub_diario_ventas") or "05"), "Ventas"),
        (str(config.get("sub_diario_compras") or "11"), "Compras"),
        (str(config.get("sub_diario_detraccion") or "").strip(), "Compras con detracción"),
        (str((tipos.get(TIPO_BOLETA) or {}).get("sub_diario") or "").strip(), "Boletas de venta"),
        (str((tipos.get(TIPO_HONORARIOS) or {}).get("sub_diario") or "").strip(), "Recibos por honorarios"),
    ]
    etiquetas: dict[str, str] = {}
    for numero, uso in usos:
        if not numero:
            continue
        etiquetas[numero] = (etiquetas[numero] + " · " + uso) if numero in etiquetas else uso
    return etiquetas


def _cuenta_por_moneda(valor: Any, moneda: str, fallback: str) -> str:
    if isinstance(valor, dict):
        return str(valor.get((moneda or "").upper()) or valor.get("PEN") or fallback)
    return str(valor) if valor else fallback


def cuenta_por_pagar(cuentas: dict, moneda: str) -> str:
    return _cuenta_por_moneda(cuentas.get("cxp"), moneda, CONFIG_POR_DEFECTO["cuentas"]["cxp"]["PEN"])


def cuenta_por_pagar_detraccion(cuentas: dict, moneda: str) -> str:
    """La cuenta por pagar de la factura afecta a detracción (421203 en las dos monedas por defecto)."""
    return _cuenta_por_moneda(cuentas.get("cxp_detraccion"), moneda, CONFIG_POR_DEFECTO["cuentas"]["cxp_detraccion"]["PEN"])


def cuenta_honorarios(cuentas: dict, moneda: str) -> str:
    return _cuenta_por_moneda(cuentas.get("honorarios"), moneda, CONFIG_POR_DEFECTO["cuentas"]["honorarios"]["PEN"])


# ── La imputación de cada documento: llega aparte, por `id_externo` (12-sep-2026) ──

def imputacion_de(c: Comprobante, config: dict) -> Imputacion | None:
    """La imputación de ESTE documento, si la configuración trae una con su `id_externo`; si no, None."""
    id_externo = (c.id_externo or "").strip()
    valor = (config.get("imputaciones") or {}).get(id_externo) if id_externo else None
    return Imputacion.de(valor) if valor is not None else None


def partes_de(c: Comprobante, config: dict, es_venta: bool = False) -> list[tuple[str, str, Decimal | None]]:
    """A qué cuentas va la base del documento: `[(cuenta, centro, importe)]`, con importe None = la base entera.

    Con reparto en su imputación, una parte por cada una. Si no, una sola: la cuenta y el centro de la imputación, y
    la cuenta que no traiga, la de la configuración. Es la única resolución: el asiento, los drivers de registro y
    las faltas de cuenta y de centro leen esto."""
    imputacion = imputacion_de(c, config)
    if imputacion is not None and imputacion.reparto:
        return [(p.cuenta_contable, p.centro_costo, p.importe) for p in imputacion.reparto]
    cuenta = (imputacion.cuenta_contable if imputacion is not None else "") or _cuenta_de_respaldo(config, es_venta)
    centro = imputacion.centro_costo if imputacion is not None else ""
    return [(cuenta, centro, None)]


def cuenta_tercero(c: Comprobante, config: dict, es_venta: bool = False) -> str:
    """La cuenta del total: el cliente en ventas, el proveedor en compras (el recibo por honorarios, la suya).

    Manda la de la imputación del documento cuando el contador la decidió —un gasto de representación a la
    4699—; si no, la de la configuración por moneda. Vivía dentro de `lineas_del_comprobante`; salió aquí el
    12-sep-2026 para que la resuelva UNA función para todos los drivers —el asiento de CONCAR y el registro de
    CONTASIS—, como `partes_de` resuelve la de la base."""
    imputacion = imputacion_de(c, config)
    if imputacion is not None and imputacion.cuenta_tercero:
        return imputacion.cuenta_tercero
    moneda = (c.moneda or "PEN").upper()
    cuentas = config.get("cuentas") or {}
    if es_venta:
        return _cuenta_por_moneda(cuentas.get("clientes"), moneda, CONFIG_POR_DEFECTO["cuentas"]["clientes"]["PEN"])
    if c.tipo_cp == TIPO_HONORARIOS:
        return cuenta_honorarios(cuentas, moneda)
    return cuenta_por_pagar(cuentas, moneda)


# ── Clasificación de cada comprobante ────────────────────────────────────────

def equivalencia_tipo(c: Comprobante, config: dict, tipo: str | None = None) -> dict | None:
    """La equivalencia del tipo SUNAT en la configuración (`tipos.NN`) si tiene sigla; si no, None. Solo exige la
    sigla: el sub-diario tiene general (`sub_diario_compras`) desde el 29-ago-2026."""
    equivalencia = (config.get("tipos") or {}).get(tipo if tipo is not None else c.tipo_cp)
    return equivalencia if isinstance(equivalencia, dict) and equivalencia.get("sigla") else None


def sigla_documento(c: Comprobante, config: dict | None = None) -> str:
    """La sigla con la que el sistema de destino llama al tipo del comprobante (en CONCAR, su Tabla General 06)."""
    equivalencia = equivalencia_tipo(c, config or CONFIG_POR_DEFECTO)
    return str(equivalencia["sigla"]) if equivalencia else ""


def tiene_detraccion(c: Comprobante) -> bool:
    d = c.detraccion if isinstance(c.detraccion, dict) else {}
    return bool(str(d.get("codigo") or "").strip()) or a_decimal(d.get("porcentaje")) > 0


def sub_diario(c: Comprobante, config: dict, es_venta: bool = False) -> str:
    """Por USO: ventas → sub_diario_ventas; compras con detracción → sub_diario_detraccion;
    un tipo con registro propio (boletas 13, honorarios 15) → el suyo; el resto → sub_diario_compras.
    Estas cuatro fuentes son lo que una aplicación deja configurar."""
    equivalencia = equivalencia_tipo(c, config)
    if not equivalencia:
        return ""
    if es_venta:
        return str(config.get("sub_diario_ventas") or CONFIG_POR_DEFECTO["sub_diario_ventas"])
    de_detraccion = str(config.get("sub_diario_detraccion") or "").strip()
    if de_detraccion and c.tipo_cp != TIPO_HONORARIOS and tiene_detraccion(c):
        return de_detraccion
    return str(equivalencia.get("sub_diario") or config.get("sub_diario_compras")
               or CONFIG_POR_DEFECTO["sub_diario_compras"])


def tipos_sin_equivalencia(comprobantes: list[Comprobante], config: dict) -> list[str]:
    """Códigos SUNAT presentes que no tienen sigla configurada (en orden de aparición)."""
    vistos: list[str] = []
    for c in comprobantes:
        if not equivalencia_tipo(c, config) and c.tipo_cp not in vistos:
            vistos.append(c.tipo_cp)
    return vistos


def monedas_sin_codigo(comprobantes: list[Comprobante], config: dict) -> list[str]:
    codigos = config.get("monedas_codigo") or {}
    vistas: list[str] = []
    for c in comprobantes:
        moneda = (c.moneda or "PEN").upper()
        if not codigos.get(moneda) and moneda not in vistas:
            vistas.append(moneda)
    return vistas


def _cuenta_de_respaldo(config: dict, es_venta: bool = False) -> str:
    """La cuenta de la base cuando la imputación del documento no trae una: la de ingreso en ventas, que SÍ tiene un
    valor de fábrica real (el habitual), y la de gasto en compras, que va vacía a propósito (`configuracion.py`).
    Solo lee la configuración; la resolución entera, con la imputación delante, es `partes_de`."""
    cuentas = config.get("cuentas") or {}
    if es_venta:
        return str(cuentas.get("ventas") or CONFIG_POR_DEFECTO["cuentas"]["ventas"]).strip()
    return str(cuentas.get("gasto") or "").strip()


def lleva_centro(cuenta: str, config: dict) -> bool:
    """¿Esta cuenta lleva el centro de costo en la columna M?

    En CONCAR la marca «C. Costo habilitado» vive en cada cuenta del plan; aquí se declara por
    prefijo en `cuentas_con_centro`. Distinguir AUSENTE de VACÍA importa: sin la clave (un dict
    armado a mano, un consumidor viejo) valen los prefijos de fábrica; con la lista vacía, el
    estudio está diciendo que ninguna cuenta lo lleva. Un `or []` confundiría los dos casos.
    """
    if not config.get("usa_centros_costo", True):
        return False
    prefijos = config["cuentas_con_centro"] if "cuentas_con_centro" in config else CONFIG_POR_DEFECTO["cuentas_con_centro"]
    cuenta = (cuenta or "").strip()
    return bool(cuenta) and any(cuenta.startswith(p) for p in (str(x).strip() for x in (prefijos or [])) if p)


def correlativos_de_partida(comprobantes: list[Comprobante], config: dict, es_venta: bool = False,
                            dados: dict[str, int] | None = None) -> dict[str, int]:
    """Por dónde arranca cada sub-diario presente: el correlativo que se dio y, si no se dio, el 1. Es el valor de
    partida de `exportar`, `generar_asiento`, `diagnosticar` y la CLI; antes cada una lo armaba por su cuenta."""
    dados = dados or {}
    return {sub: dados.get(sub, 1) for sub in sub_diarios_presentes(comprobantes, config, es_venta)}


def sub_diarios_presentes(comprobantes: list[Comprobante], config: dict, es_venta: bool = False) -> dict[str, int]:
    """{sub_diario: cuántos comprobantes} en el orden en que aparecen."""
    presentes: dict[str, int] = {}
    for c in comprobantes:
        s = sub_diario(c, config, es_venta)
        if s:
            presentes[s] = presentes.get(s, 0) + 1
    return presentes


def comprobantes_sin_cuenta(comprobantes: list[Comprobante], config: dict, es_venta: bool = False) -> list[Comprobante]:
    """Las filas sin cuenta: basta con que a una parte de su base le falte (`partes_de`). Una parte del reparto
    no toma la cuenta por defecto: repartir entre la misma cuenta no reparte nada."""
    return [c for c in comprobantes if not all(cuenta for cuenta, _, _ in partes_de(c, config, es_venta))]


def comprobantes_sin_centro(comprobantes: list[Comprobante], config: dict, es_venta: bool = False) -> list[Comprobante]:
    """Las filas a las que les falta un centro de costo que SÍ hace falta.

    El centro es obligatorio solo donde de verdad se escribe: en la columna M de las cuentas de
    `cuentas_con_centro` (el contador, 06-sep-2026 y 09-sep-2026). Una cuenta fuera de la lista
    NO bloquea nunca, ni siquiera con `centro_como_referencia` encendido: esa X es una referencia, y
    una referencia que se puede dejar en blanco no puede impedir exportar un mes.

    `es_venta` va opcional a propósito, calcando a `comprobantes_sin_cuenta`: esto es una librería que se
    instala fuera, y un positional obligatorio sería romper su API pública por una regla interna
    de CONCAR. Ojo al llamarla: sin el flag, un libro de ventas resolvería la cuenta como gasto.
    """
    if not config.get("usa_centros_costo", True):
        return []

    def falta(c: Comprobante) -> bool:
        # Cada parte de la base con su cuenta y su centro (`partes_de`): basta con que a una le falte.
        return any(not (centro or "").strip() and lleva_centro(cuenta, config)
                   for cuenta, centro, _ in partes_de(c, config, es_venta))

    return [c for c in comprobantes if falta(c)]


def reparto_no_cuadra(c: Comprobante, config: dict, es_venta: bool = False) -> bool:
    """¿El reparto de su imputación deja de sumar la base del asiento? Sin tolerancia, como la partida doble:
    un reparto que no cuadra da un asiento que no cuadra."""
    imputacion = imputacion_de(c, config)
    if imputacion is None or not imputacion.reparto:
        return False
    return sum((p.importe for p in imputacion.reparto), Decimal("0.00")) != base_imputable(c, es_venta)


def repartos_que_no_cuadran(comprobantes: list[Comprobante], config: dict, es_venta: bool = False) -> list[Comprobante]:
    return [c for c in comprobantes if reparto_no_cuadra(c, config, es_venta)]


def con_reparto(comprobantes: list[Comprobante], config: dict) -> list[Comprobante]:
    """Los que reparten su base entre varias cuentas (`reparto` en su imputación): lo que no admite un destino que
    exige `cuenta_unica`."""
    return [c for c in comprobantes if (imputacion := imputacion_de(c, config)) is not None and imputacion.reparto]


def faltantes_para(comprobantes: list[Comprobante], config: dict, es_venta: bool = False,
                   exige: frozenset[str] | set[str] = frozenset()) -> dict[str, list]:
    """Lo que les falta a estos comprobantes para un destino que EXIGE eso — solo las claves exigidas.

    No lanza: describe. Es la misma comprobación que `exigir_requisitos` hace cumplir, y la que
    `diagnosticar` cuenta por serie-número; una sola lista de reglas para las tres.
    """
    salida: dict[str, list] = {}
    if "tipo_cp" in exige:
        salida["tipo_sin_equivalencia"] = tipos_sin_equivalencia(comprobantes, config)
    if "moneda" in exige:
        salida["moneda_sin_codigo"] = monedas_sin_codigo(comprobantes, config)
    if "cuenta_unica" in exige:
        salida["reparto_no_admitido"] = con_reparto(comprobantes, config)
    if "cuenta_contable" in exige:
        salida["sin_cuenta"] = comprobantes_sin_cuenta(comprobantes, config, es_venta)
        salida["reparto_que_no_cuadra"] = repartos_que_no_cuadran(comprobantes, config, es_venta)
    if "centro_costo" in exige:
        salida["sin_centro"] = comprobantes_sin_centro(comprobantes, config, es_venta)
    return salida


def exigir_requisitos(comprobantes: list[Comprobante], config: dict, es_venta: bool = False,
                      exige: frozenset[str] | set[str] = frozenset()) -> None:
    """Hace cumplir `faltantes_para`: la primera falta, en el orden de `FALTAS` (tipo → moneda → reparto no admitido →
    cuenta → reparto que no cuadra → centro), detiene la exportación con su excepción. Un tipo sin equivalencia no se
    inventa."""
    falta = faltantes_para(comprobantes, config, es_venta, exige)
    for regla in FALTAS:
        if regla.excepcion is not None and falta.get(regla.clave):
            raise regla.excepcion(falta[regla.clave])


# ── Numeración: MM + correlativo de 4 dígitos por sub-diario ──────────────────

def numerar(comprobantes: list[Comprobante], config: dict, periodo: str,
            correlativos: dict[str, int], es_venta: bool = False) -> tuple[dict[int, str], dict[str, dict]]:
    """Asigna a cada comprobante (por `id()` del objeto) su número `MMNNNN`, en el orden
    recibido (el natural del registro). Devuelve también el rango usado por sub-diario,
    que es lo que se recuerda para proponer el siguiente."""
    mes_mm = str(periodo)[4:6]
    sin_equivalencia = tipos_sin_equivalencia(comprobantes, config)
    if sin_equivalencia:
        raise TipoSinEquivalencia(sin_equivalencia)
    presentes = sub_diarios_presentes(comprobantes, config, es_venta)
    faltan = [s for s in presentes if s not in correlativos]
    if faltan:
        raise SubDiarioSinCorrelativo(faltan)
    contadores = {s: int(correlativos[s]) for s in presentes}
    if any(n < 1 for n in contadores.values()):
        raise ValueError("Los correlativos empiezan en 1")
    numeros: dict[int, str] = {}
    rangos: dict[str, dict] = {s: {"desde": n, "hasta": n - 1, "comprobantes": 0} for s, n in contadores.items()}
    for c in comprobantes:
        s = sub_diario(c, config, es_venta)
        n = contadores[s]
        numeros[id(c)] = f"{mes_mm}{n:04d}"
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
