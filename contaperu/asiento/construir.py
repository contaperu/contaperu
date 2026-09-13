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
from ..modelo import Comprobante, Libro
from .configuracion import CONFIG_DE_FABRICA
from .imputacion import Imputacion


class SinCuenta(Exception):
    """Comprobantes incluidos sin cuenta contable (ni en su imputación ni por defecto en la configuración)."""

    def __init__(self, comprobantes: list[Comprobante]):
        super().__init__(f"{len(comprobantes)} comprobante(s) sin cuenta contable")
        self.comprobantes = comprobantes


class TipoSinMapa(Exception):
    """Comprobantes cuyo tipo SUNAT no tiene sigla configurada (`tipos.NN.sigla`): no se inventa una."""

    def __init__(self, tipos: list[str]):
        super().__init__("Tipos SUNAT sin sigla configurada: " + ", ".join(tipos))
        self.tipos = tipos


class MonedaSinCodigo(Exception):
    """Comprobantes en una moneda sin código en el sistema de destino (`monedas_codigo`)."""

    def __init__(self, monedas: list[str]):
        super().__init__("Monedas sin código en el sistema de destino: " + ", ".join(monedas))
        self.monedas = monedas


class SinCentro(Exception):
    """Comprobantes sin centro de costo en una cuenta que SÍ lo lleva (columna M de CONCAR).

    La regla es del contador (06-sep-2026: obligatorio donde de verdad se escribe) y hasta el
    11-sep-2026 la aplicaba solo el portal antes de exportar; el driver de CONCAR la hace cumplir
    desde entonces (decisión de John), como la de la cuenta.
    """

    def __init__(self, comprobantes: list[Comprobante]):
        super().__init__(f"{len(comprobantes)} comprobante(s) sin centro de costo en una cuenta que lo lleva")
        self.comprobantes = comprobantes


class RepartoNoCuadra(SinCuenta):
    """Comprobantes cuyo reparto (el de su imputación) no suma la base del asiento. Hereda de `SinCuenta` a
    propósito: es una imputación que no se puede asentar, y quien ya atrapaba la falta de cuenta —la CLI, la
    aplicación— la atrapa sin cambiar nada."""

    def __init__(self, comprobantes: list[Comprobante]):
        Exception.__init__(self, f"{len(comprobantes)} comprobante(s) con un reparto entre cuentas que no suma "
                                 "la base del asiento")
        self.comprobantes = comprobantes


class RepartoNoAdmitido(SinCuenta):
    """Comprobantes con la base repartida entre varias cuentas (un `reparto` en su imputación) para un destino que
    lleva UNA cuenta por documento: CONTASIS arma un asiento por fila (John, 12-sep-2026). Hereda de `SinCuenta`
    por lo mismo que `RepartoNoCuadra`: es una imputación que ese destino no puede llevar."""

    def __init__(self, comprobantes: list[Comprobante]):
        Exception.__init__(self, f"{len(comprobantes)} comprobante(s) con la base repartida entre varias cuentas, "
                                 "y el sistema de destino lleva una sola por documento")
        self.comprobantes = comprobantes


class CorrelativoFaltante(Exception):
    def __init__(self, sub_diarios: list[str]):
        super().__init__("Falta el correlativo de los sub-diarios " + ", ".join(sub_diarios))
        self.sub_diarios = sub_diarios


# ── Configuración por RUC ─────────────────────────────────────────────────────

def merge_config(defaults: dict, overrides: dict) -> dict:
    """Overrides sobre defaults, dict a dict (un sistema anterior lo hacía a 1 nivel: sobreescribir `cxp.USD`
    borraba `cxp.PEN`; aquí se funde en profundidad)."""
    out: dict = {k: (merge_config(v, {}) if isinstance(v, dict) else v) for k, v in (defaults or {}).items()}
    if not isinstance(overrides, dict):
        return out
    for k, v in overrides.items():
        if isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k] = merge_config(out[k], v)
        else:
            out[k] = v
    return out


def config_de(config_cliente: dict | None, config_cuenta: dict | None = None) -> dict:
    """Configuración contable efectiva, del general al particular:

        CONFIG_DE_FABRICA (código)  →  la CUENTA (el estudio)  →  el RUC (excepciones)

    Cada capa trae lo suyo bajo la clave `contabilidad`. La del RUC sobreescribe solo las claves que difieran y
    hereda el resto — `merge_config` funde en profundidad, así que la cuenta puede poner `cxp.PEN` y el RUC solo
    `cxp.USD` sin borrarse entre ellos."""
    base = merge_config(CONFIG_DE_FABRICA, ((config_cuenta or {}).get("contabilidad") or {}))
    return merge_config(base, ((config_cliente or {}).get("contabilidad") or {}))


def etiquetas_sub_diario(contab: dict) -> dict[str, str]:
    """{numero: uso} segun la config vigente, para el modal de exportar y el resumen.
    Si el estudio renumera (honorarios → 33), el 33 sale etiquetado. Dos usos con el
    mismo numero se unen con " · " (p. ej. un CONCAR que no separa la detraccion)."""
    tipos = contab.get("tipos") or {}
    usos = [
        (str(contab.get("sub_diario_ventas") or "05"), "Ventas"),
        (str(contab.get("sub_diario_compras") or "11"), "Compras"),
        (str(contab.get("sub_diario_detraccion") or "").strip(), "Compras con detracción"),
        (str((tipos.get(TIPO_BOLETA) or {}).get("sub_diario") or "").strip(), "Boletas de venta"),
        (str((tipos.get(TIPO_HONORARIOS) or {}).get("sub_diario") or "").strip(), "Recibos por honorarios"),
    ]
    out: dict[str, str] = {}
    for num, uso in usos:
        if not num:
            continue
        out[num] = (out[num] + " · " + uso) if num in out else uso
    return out


def _cuenta_por_moneda(valor: Any, moneda: str, fallback: str) -> str:
    if isinstance(valor, dict):
        return str(valor.get((moneda or "").upper()) or valor.get("PEN") or fallback)
    return str(valor) if valor else fallback


def resolve_cxp_account(cuentas: dict, moneda: str) -> str:
    return _cuenta_por_moneda(cuentas.get("cxp"), moneda, CONFIG_DE_FABRICA["cuentas"]["cxp"]["PEN"])


def resolve_cxp_detraccion_account(cuentas: dict, moneda: str) -> str:
    """La cuenta por pagar de la factura afecta a detracción (421203 en las dos monedas por defecto)."""
    return _cuenta_por_moneda(cuentas.get("cxp_detraccion"), moneda, CONFIG_DE_FABRICA["cuentas"]["cxp_detraccion"]["PEN"])


def cuenta_honorarios(cuentas: dict, moneda: str) -> str:
    return _cuenta_por_moneda(cuentas.get("honorarios"), moneda, CONFIG_DE_FABRICA["cuentas"]["honorarios"]["PEN"])


# ── La imputación de cada documento: llega aparte, por `id_externo` (12-sep-2026) ──

def imputacion_de(c: Comprobante, contab: dict) -> Imputacion | None:
    """La imputación de ESTE documento, si la configuración trae una con su `id_externo`; si no, None."""
    ide = (c.id_externo or "").strip()
    valor = (contab.get("imputaciones") or {}).get(ide) if ide else None
    return Imputacion.de(valor) if valor is not None else None


def partes_de(c: Comprobante, contab: dict, venta: bool = False) -> list[tuple[str, str, Decimal | None]]:
    """A qué cuentas va la base del documento: `[(cuenta, centro, importe)]`, con importe None = la base entera.

    Con reparto en su imputación, una parte por cada una. Si no, una sola: la cuenta y el centro de la imputación, y
    la cuenta que no traiga, la de la configuración. Es la única resolución: el asiento, los drivers de registro y
    las faltas de cuenta y de centro leen esto."""
    imp = imputacion_de(c, contab)
    if imp is not None and imp.reparto:
        return [(p.cuenta_contable, p.centro_costo, p.importe) for p in imp.reparto]
    cuenta = (imp.cuenta_contable if imp is not None else "") or cuenta_de_fila(c, contab, venta)
    centro = imp.centro_costo if imp is not None else ""
    return [(cuenta, centro, None)]


def cuenta_tercero(c: Comprobante, contab: dict, venta: bool = False) -> str:
    """La cuenta del total: el cliente en ventas, el proveedor en compras (el recibo por honorarios, la suya).

    Manda la de la imputación del documento cuando el contador la decidió —un gasto de representación a la
    4699—; si no, la de la configuración por moneda. Vivía dentro de `asiento_neutral`; salió aquí el
    12-sep-2026 para que la resuelva UNA función para todos los drivers —el asiento de CONCAR y el registro de
    CONTASIS—, como `partes_de` resuelve la de la base."""
    imp = imputacion_de(c, contab)
    if imp is not None and imp.cuenta_tercero:
        return imp.cuenta_tercero
    moneda = (c.moneda or "PEN").upper()
    cuentas = contab.get("cuentas") or {}
    if venta:
        return _cuenta_por_moneda(cuentas.get("clientes"), moneda, CONFIG_DE_FABRICA["cuentas"]["clientes"]["PEN"])
    if c.tipo_cp == TIPO_HONORARIOS:
        return cuenta_honorarios(cuentas, moneda)
    return resolve_cxp_account(cuentas, moneda)


# ── Clasificación de cada comprobante ────────────────────────────────────────

def equivalencia_tipo(c: Comprobante, contab: dict, tipo: str | None = None) -> dict | None:
    """La equivalencia del tipo SUNAT en la configuración (`tipos.NN`) si tiene sigla; si no, None. Solo exige la
    sigla: el sub-diario tiene general (`sub_diario_compras`) desde el 29-ago-2026."""
    m = (contab.get("tipos") or {}).get(tipo if tipo is not None else c.tipo_cp)
    return m if isinstance(m, dict) and m.get("sigla") else None


def sigla_documento(c: Comprobante, contab: dict | None = None) -> str:
    """La sigla con la que el sistema de destino llama al tipo del comprobante (en CONCAR, su Tabla General 06)."""
    m = equivalencia_tipo(c, contab or CONFIG_DE_FABRICA)
    return str(m["sigla"]) if m else ""


def _num(v: Any) -> Decimal:
    try:
        return Decimal(str(v if v not in (None, "") else 0))
    except Exception:
        return Decimal(0)


def tiene_detraccion(c: Comprobante) -> bool:
    d = c.detraccion if isinstance(c.detraccion, dict) else {}
    return bool(str(d.get("codigo") or "").strip()) or _num(d.get("porcentaje")) > 0


def sub_diario(c: Comprobante, contab: dict, venta: bool = False) -> str:
    """Por USO: ventas → sub_diario_ventas; compras con detracción → sub_diario_detraccion;
    un tipo con registro propio (boletas 13, honorarios 15) → el suyo; el resto → sub_diario_compras.
    Estas cuatro fuentes son lo que una aplicación deja configurar."""
    m = equivalencia_tipo(c, contab)
    if not m:
        return ""
    if venta:
        return str(contab.get("sub_diario_ventas") or CONFIG_DE_FABRICA["sub_diario_ventas"])
    sd = str(contab.get("sub_diario_detraccion") or "").strip()
    if sd and c.tipo_cp != TIPO_HONORARIOS and tiene_detraccion(c):
        return sd
    return str(m.get("sub_diario") or contab.get("sub_diario_compras") or CONFIG_DE_FABRICA["sub_diario_compras"])


def tipos_sin_mapa(comprobantes: list[Comprobante], contab: dict) -> list[str]:
    """Códigos SUNAT presentes que no tienen sigla configurada (en orden de aparición)."""
    vistos: list[str] = []
    for c in comprobantes:
        if not equivalencia_tipo(c, contab) and c.tipo_cp not in vistos:
            vistos.append(c.tipo_cp)
    return vistos


def monedas_sin_codigo(comprobantes: list[Comprobante], contab: dict) -> list[str]:
    codigos = contab.get("monedas_codigo") or {}
    vistas: list[str] = []
    for c in comprobantes:
        m = (c.moneda or "PEN").upper()
        if not codigos.get(m) and m not in vistas:
            vistas.append(m)
    return vistas


def cuenta_gasto(c: Comprobante, contab: dict) -> str:
    return str((contab.get("cuentas") or {}).get("gasto") or "").strip()


def cuenta_venta(c: Comprobante, contab: dict) -> str:
    """Ventas: la cuenta de ingreso del RUC; a diferencia del gasto, aquí SÍ hay un default real (el habitual)."""
    return str((contab.get("cuentas") or {}).get("ventas") or CONFIG_DE_FABRICA["cuentas"]["ventas"]).strip()


def cuenta_de_fila(c: Comprobante, contab: dict, venta: bool = False) -> str:
    """La cuenta que acaba en la columna K de la línea principal.

    Existe para que la regla del centro de costo (`lleva_centro`) mire EXACTAMENTE la misma
    cuenta que se escribe, y no una segunda resolución que se desincronice con el tiempo.
    """
    return cuenta_venta(c, contab) if venta else cuenta_gasto(c, contab)


def lleva_centro(cuenta: str, contab: dict) -> bool:
    """¿Esta cuenta lleva el centro de costo en la columna M?

    En CONCAR la marca «C. Costo habilitado» vive en cada cuenta del plan; aquí se declara por
    prefijo en `cuentas_con_centro`. Distinguir AUSENTE de VACÍA importa: sin la clave (un dict
    armado a mano, un consumidor viejo) valen los prefijos de fábrica; con la lista vacía, el
    estudio está diciendo que ninguna cuenta lo lleva. Un `or []` confundiría los dos casos.
    """
    if not contab.get("usa_centros_costo", True):
        return False
    prefijos = contab["cuentas_con_centro"] if "cuentas_con_centro" in contab else CONFIG_DE_FABRICA["cuentas_con_centro"]
    cuenta = (cuenta or "").strip()
    return bool(cuenta) and any(cuenta.startswith(p) for p in (str(x).strip() for x in (prefijos or [])) if p)


def sub_diarios_presentes(comprobantes: list[Comprobante], contab: dict, venta: bool = False) -> dict[str, int]:
    """{sub_diario: cuántos comprobantes} en el orden en que aparecen."""
    out: dict[str, int] = {}
    for c in comprobantes:
        s = sub_diario(c, contab, venta)
        if s:
            out[s] = out.get(s, 0) + 1
    return out


def filas_sin_cuenta(comprobantes: list[Comprobante], contab: dict, venta: bool = False) -> list[Comprobante]:
    """Las filas sin cuenta: basta con que a una parte de su base le falte (`partes_de`). Una parte del reparto
    no toma la cuenta por defecto: repartir entre la misma cuenta no reparte nada."""
    return [c for c in comprobantes if not all(cuenta for cuenta, _, _ in partes_de(c, contab, venta))]


def filas_sin_centro(comprobantes: list[Comprobante], contab: dict, venta: bool = False) -> list[Comprobante]:
    """Las filas a las que les falta un centro de costo que SÍ hace falta.

    El centro es obligatorio solo donde de verdad se escribe: en la columna M de las cuentas de
    `cuentas_con_centro` (el contador, 06-sep-2026 y 09-sep-2026). Una cuenta fuera de la lista
    NO bloquea nunca, ni siquiera con `centro_como_referencia` encendido: esa X es una referencia, y
    una referencia que se puede dejar en blanco no puede impedir exportar un mes.

    `venta` va opcional a propósito, calcando a `filas_sin_cuenta`: esto es una librería que se
    instala fuera, y un positional obligatorio sería romper su API pública por una regla interna
    de CONCAR. Ojo al llamarla: sin el flag, un libro de ventas resolvería la cuenta como gasto.
    """
    if not contab.get("usa_centros_costo", True):
        return []

    def falta(c: Comprobante) -> bool:
        # Cada parte de la base con su cuenta y su centro (`partes_de`): basta con que a una le falte.
        return any(not (centro or "").strip() and lleva_centro(cuenta, contab)
                   for cuenta, centro, _ in partes_de(c, contab, venta))

    return [c for c in comprobantes if falta(c)]


def reparto_no_cuadra(c: Comprobante, contab: dict, venta: bool = False) -> bool:
    """¿El reparto de su imputación deja de sumar la base del asiento? Sin tolerancia, como la partida doble:
    un reparto que no cuadra da un asiento que no cuadra."""
    imp = imputacion_de(c, contab)
    if imp is None or not imp.reparto:
        return False
    return sum((p.importe for p in imp.reparto), Decimal("0.00")) != base_imputable(c, venta)


def repartos_que_no_cuadran(comprobantes: list[Comprobante], contab: dict, venta: bool = False) -> list[Comprobante]:
    return [c for c in comprobantes if reparto_no_cuadra(c, contab, venta)]


def con_reparto(comprobantes: list[Comprobante], contab: dict) -> list[Comprobante]:
    """Los que reparten su base entre varias cuentas (`reparto` en su imputación): lo que no admite un destino que
    exige `cuenta_unica`."""
    return [c for c in comprobantes if (imp := imputacion_de(c, contab)) is not None and imp.reparto]


# Qué clave de `faltantes` responde a cada requisito del contrato de driver (`contrato.exige`), en el
# orden en que se comprueban: primero lo que impide clasificar (tipo, moneda), luego lo de cada línea.
REQUISITO_DE = {"tipos_sin_equivalencia": "tipo_cp", "monedas_sin_codigo": "moneda",
                "reparto_no_admitido": "cuenta_unica",
                "sin_cuenta": "cuenta_contable", "reparto_no_cuadra": "cuenta_contable",
                "sin_centro_de_costo": "centro_costo"}


def faltantes_para(comprobantes: list[Comprobante], contab: dict, venta: bool = False,
                   exige: frozenset[str] | set[str] = frozenset()) -> dict[str, list]:
    """Lo que les falta a estos comprobantes para un destino que EXIGE eso — solo las claves exigidas.

    No lanza: describe. Es la misma comprobación que `exigir_requisitos` hace cumplir, y la que
    `diagnosticar` cuenta por serie-número; una sola lista de reglas para las tres.
    """
    salida: dict[str, list] = {}
    if "tipo_cp" in exige:
        salida["tipos_sin_equivalencia"] = tipos_sin_mapa(comprobantes, contab)
    if "moneda" in exige:
        salida["monedas_sin_codigo"] = monedas_sin_codigo(comprobantes, contab)
    if "cuenta_unica" in exige:
        salida["reparto_no_admitido"] = con_reparto(comprobantes, contab)
    if "cuenta_contable" in exige:
        salida["sin_cuenta"] = filas_sin_cuenta(comprobantes, contab, venta)
        salida["reparto_no_cuadra"] = repartos_que_no_cuadran(comprobantes, contab, venta)
    if "centro_costo" in exige:
        salida["sin_centro_de_costo"] = filas_sin_centro(comprobantes, contab, venta)
    return salida


def exigir_requisitos(comprobantes: list[Comprobante], contab: dict, venta: bool = False,
                      exige: frozenset[str] | set[str] = frozenset()) -> None:
    """Hace cumplir `faltantes_para`: la primera falta, en el orden de siempre, detiene la exportación
    con su excepción (tipo → moneda → reparto no admitido → cuenta → reparto que no cuadra → centro). Un tipo
    sin equivalencia no se inventa."""
    falta = faltantes_para(comprobantes, contab, venta, exige)
    if falta.get("tipos_sin_equivalencia"):
        raise TipoSinMapa(falta["tipos_sin_equivalencia"])
    if falta.get("monedas_sin_codigo"):
        raise MonedaSinCodigo(falta["monedas_sin_codigo"])
    if falta.get("reparto_no_admitido"):
        raise RepartoNoAdmitido(falta["reparto_no_admitido"])
    if falta.get("sin_cuenta"):
        raise SinCuenta(falta["sin_cuenta"])
    if falta.get("reparto_no_cuadra"):
        raise RepartoNoCuadra(falta["reparto_no_cuadra"])
    if falta.get("sin_centro_de_costo"):
        raise SinCentro(falta["sin_centro_de_costo"])


# ── Numeración: MM + correlativo de 4 dígitos por sub-diario ──────────────────

def numerar(comprobantes: list[Comprobante], contab: dict, periodo: str,
            correlativos: dict[str, int], venta: bool = False) -> tuple[dict[int, str], dict[str, dict]]:
    """Asigna a cada comprobante (por `id()` del objeto) su número `MMNNNN`, en el orden
    recibido (el natural del registro). Devuelve también el rango usado por sub-diario,
    que es lo que se recuerda para proponer el siguiente."""
    mes_mm = str(periodo)[4:6]
    sin_mapa = tipos_sin_mapa(comprobantes, contab)
    if sin_mapa:
        raise TipoSinMapa(sin_mapa)
    presentes = sub_diarios_presentes(comprobantes, contab, venta)
    faltan = [s for s in presentes if s not in correlativos]
    if faltan:
        raise CorrelativoFaltante(faltan)
    contadores = {s: int(correlativos[s]) for s in presentes}
    if any(n < 1 for n in contadores.values()):
        raise ValueError("Los correlativos empiezan en 1")
    numeros: dict[int, str] = {}
    rangos: dict[str, dict] = {s: {"desde": n, "hasta": n - 1, "n": 0} for s, n in contadores.items()}
    for c in comprobantes:
        s = sub_diario(c, contab, venta)
        n = contadores[s]
        numeros[id(c)] = f"{mes_mm}{n:04d}"
        rangos[s]["hasta"] = n
        rangos[s]["n"] += 1
        contadores[s] = n + 1
    for s, r in rangos.items():
        r["desde_cod"], r["hasta_cod"] = f"{mes_mm}{r['desde']:04d}", f"{mes_mm}{r['hasta']:04d}"
        r["desborda"] = r["hasta"] > 9999
    return numeros, rangos


def mes_del_libro(libro: Libro) -> tuple[date, date]:
    """El primer y el ultimo dia del periodo del libro.

    Es el marco dentro del que cae la fecha de cada asiento: un comprobante extemporaneo
    (emitido en un mes anterior) se asienta el dia 1, y uno posterior, el ultimo dia. La
    fecha del documento se conserva aparte, siempre."""
    return (date(libro.anio, libro.mes, 1),
            date(libro.anio, libro.mes, calendar.monthrange(libro.anio, libro.mes)[1]))
