"""Lo que el asiento necesita saber antes de armarse: configuración efectiva, clasificación de
cada comprobante (sigla, sub-diario, cuentas) y numeración por sub-diario. Las reglas de negocio y
su porqué, en el docstring del paquete (`__init__.py`).

Las líneas de la partida doble se arman en `motor.py`, en el vocabulario neutral de `pe-ledger`;
`asiento()` se queda aquí como la puerta de siempre hacia las columnas de CONCAR.
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ..modelo import Comprobante, Libro
from ..formato import Opciones
from ..igv import tasa as tasa_de_importes
from .datos import DEFAULTS, OPCIONES, TIPO_BOLETA, TIPO_HONORARIOS


class SinCuenta(Exception):
    """Comprobantes incluidos sin cuenta contable (ni en la fila ni por defecto en el RUC)."""

    def __init__(self, comprobantes: list[Comprobante]):
        super().__init__(f"{len(comprobantes)} comprobante(s) sin cuenta contable")
        self.comprobantes = comprobantes


class TipoSinMapa(Exception):
    """Comprobantes cuyo tipo SUNAT no tiene sigla/sub-diario de CONCAR configurado."""

    def __init__(self, tipos: list[str]):
        super().__init__("Tipos SUNAT sin código CONCAR: " + ", ".join(tipos))
        self.tipos = tipos


class MonedaSinCodigo(Exception):
    """Comprobantes en una moneda que CONCAR no admite (solo MN y US)."""

    def __init__(self, monedas: list[str]):
        super().__init__("Monedas sin código CONCAR: " + ", ".join(monedas))
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


class CorrelativoFaltante(Exception):
    def __init__(self, sub_diarios: list[str]):
        super().__init__("Falta el correlativo de los sub-diarios " + ", ".join(sub_diarios))
        self.sub_diarios = sub_diarios


class CorrelativoDesborda(Exception):
    """Un sub-diario pasaría de 9999: CONCAR numera el asiento con MM + cuatro dígitos (`numerar`),
    y un quinto dígito no cabe en su importación. `sub_diarios` es {sub-diario: hasta dónde llegaría}."""

    def __init__(self, sub_diarios: dict[str, int]):
        super().__init__("; ".join(f"El sub-diario {s} llegaría a {n}: supera los 4 dígitos que admite CONCAR"
                                   for s, n in sub_diarios.items()))
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
    """Configuración CONCAR efectiva, del general al particular:

        DEFAULTS (código)  →  la CUENTA (el estudio)  →  el RUC (excepciones)

    La cuenta (`contab_config.config`) vale para todos sus RUCs; el RUC
    (`contab_clientes.config`) sobreescribe solo las claves que difieran y
    hereda el resto — `merge_config` funde en profundidad, así que la cuenta
    puede poner `cxp.PEN` y el RUC solo `cxp.USD` sin borrarse entre ellos."""
    base = merge_config(DEFAULTS, ((config_cuenta or {}).get("concar") or {}))
    return merge_config(base, ((config_cliente or {}).get("concar") or {}))


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
    return _cuenta_por_moneda(cuentas.get("cxp"), moneda, DEFAULTS["cuentas"]["cxp"]["PEN"])


def resolve_cxp_detraccion_account(cuentas: dict, moneda: str) -> str:
    """La cuenta por pagar de la factura afecta a detracción (421203 en las dos monedas por defecto)."""
    return _cuenta_por_moneda(cuentas.get("cxp_detraccion"), moneda, DEFAULTS["cuentas"]["cxp_detraccion"]["PEN"])


def cuenta_honorarios(cuentas: dict, moneda: str) -> str:
    return _cuenta_por_moneda(cuentas.get("honorarios"), moneda, DEFAULTS["cuentas"]["honorarios"]["PEN"])


def cuenta_tercero(c: Comprobante, contab: dict, venta: bool = False) -> str:
    """La cuenta del total: el cliente en ventas, el proveedor en compras (el recibo por honorarios, la suya).

    Manda la del registro (`Comprobante.cuenta_tercero`) cuando el contador la escribió para ese documento
    —un gasto de representación a la 4699—; si no, la de la configuración por moneda. Vivía dentro de
    `asiento_neutral`; salió aquí el 12-sep-2026 para que la resuelva UNA función para todos los drivers
    —el asiento de CONCAR y el registro de CONTASIS—, como `cuenta_de_fila` resuelve la de la base."""
    propia = (c.cuenta_tercero or "").strip()
    if propia:
        return propia
    moneda = (c.moneda or "PEN").upper()
    cuentas = contab.get("cuentas") or {}
    if venta:
        return _cuenta_por_moneda(cuentas.get("clientes"), moneda, DEFAULTS["cuentas"]["clientes"]["PEN"])
    if c.tipo_cp == TIPO_HONORARIOS:
        return cuenta_honorarios(cuentas, moneda)
    return resolve_cxp_account(cuentas, moneda)


# ── Clasificación de cada comprobante ────────────────────────────────────────

def _mapa(c: Comprobante, contab: dict, tipo: str | None = None) -> dict | None:
    # Solo exige la sigla: el sub-diario tiene general (sub_diario_compras) desde el 29-ago-2026.
    m = (contab.get("tipos") or {}).get(tipo if tipo is not None else c.tipo_cp)
    return m if isinstance(m, dict) and m.get("concar") else None


def tipo_concar(c: Comprobante, contab: dict | None = None) -> str:
    m = _mapa(c, contab or DEFAULTS)
    return str(m["concar"]) if m else ""


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
    m = _mapa(c, contab)
    if not m:
        return ""
    if venta:
        return str(contab.get("sub_diario_ventas") or DEFAULTS["sub_diario_ventas"])
    sd = str(contab.get("sub_diario_detraccion") or "").strip()
    if sd and c.tipo_cp != TIPO_HONORARIOS and tiene_detraccion(c):
        return sd
    return str(m.get("sub_diario") or contab.get("sub_diario_compras") or DEFAULTS["sub_diario_compras"])


def tipos_sin_mapa(comprobantes: list[Comprobante], contab: dict) -> list[str]:
    """Códigos SUNAT presentes que no tienen sigla/sub-diario de CONCAR (en orden de aparición)."""
    vistos: list[str] = []
    for c in comprobantes:
        if not _mapa(c, contab) and c.tipo_cp not in vistos:
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
    return (c.cuenta_contable or "").strip() or str((contab.get("cuentas") or {}).get("gasto") or "").strip()


def cuenta_venta(c: Comprobante, contab: dict) -> str:
    """Ventas: la cuenta de ingreso de la fila o la del RUC; a diferencia del gasto,
    aquí SÍ hay un default real (el habitual)."""
    return (c.cuenta_contable or "").strip() or str((contab.get("cuentas") or {}).get("ventas") or DEFAULTS["cuentas"]["ventas"]).strip()


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
    prefijos = contab["cuentas_con_centro"] if "cuentas_con_centro" in contab else DEFAULTS["cuentas_con_centro"]
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
    return [c for c in comprobantes if not cuenta_de_fila(c, contab, venta)]


def filas_sin_centro(comprobantes: list[Comprobante], contab: dict, venta: bool = False) -> list[Comprobante]:
    """Las filas a las que les falta un centro de costo que SÍ hace falta.

    El centro es obligatorio solo donde de verdad se escribe: en la columna M de las cuentas de
    `cuentas_con_centro` (el contador, 06-sep-2026 y 09-sep-2026). Una cuenta fuera de la lista
    NO bloquea nunca, ni siquiera con `cc_referencia_en_x` encendido: esa X es una referencia, y
    una referencia que se puede dejar en blanco no puede impedir exportar un mes.

    `venta` va opcional a propósito, calcando a `filas_sin_cuenta`: esto es una librería que se
    instala fuera, y un positional obligatorio sería romper su API pública por una regla interna
    de CONCAR. Ojo al llamarla: sin el flag, un libro de ventas resolvería la cuenta como gasto.
    """
    if not contab.get("usa_centros_costo", True):
        return []
    return [c for c in comprobantes
            if not (c.centro_costo or "").strip() and lleva_centro(cuenta_de_fila(c, contab, venta), contab)]


# Qué clave de `faltantes` responde a cada requisito del contrato de driver (`contrato.exige`), en el
# orden en que se comprueban: primero lo que impide clasificar (tipo, moneda), luego lo de cada línea.
REQUISITO_DE = {"tipos_sin_equivalencia": "tipo_cp", "monedas_sin_codigo": "moneda",
                "sin_cuenta": "cuenta_contable", "sin_centro_de_costo": "centro_costo"}


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
    if "cuenta_contable" in exige:
        salida["sin_cuenta"] = filas_sin_cuenta(comprobantes, contab, venta)
    if "centro_costo" in exige:
        salida["sin_centro_de_costo"] = filas_sin_centro(comprobantes, contab, venta)
    return salida


def exigir_requisitos(comprobantes: list[Comprobante], contab: dict, venta: bool = False,
                      exige: frozenset[str] | set[str] = frozenset()) -> None:
    """Hace cumplir `faltantes_para`: la primera falta, en el orden de siempre, detiene la exportación
    con su excepción (tipo → moneda → cuenta → centro). Un tipo sin equivalencia no se inventa."""
    falta = faltantes_para(comprobantes, contab, venta, exige)
    if falta.get("tipos_sin_equivalencia"):
        raise TipoSinMapa(falta["tipos_sin_equivalencia"])
    if falta.get("monedas_sin_codigo"):
        raise MonedaSinCodigo(falta["monedas_sin_codigo"])
    if falta.get("sin_cuenta"):
        raise SinCuenta(falta["sin_cuenta"])
    if falta.get("sin_centro_de_costo"):
        raise SinCentro(falta["sin_centro_de_costo"])


def nombre(libro: Libro, op: Opciones = OPCIONES) -> str:
    return f"CONCAR_{libro.ruc}_{libro.periodo}_{'VENTAS' if libro.es_venta else 'COMPRAS'}{op.extension}"


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


# ── El asiento ───────────────────────────────────────────────────────────────

def tasa_igv(igv: Decimal, base_gravada: Decimal) -> Any:
    """Columna AO: la tasa DEL COMPROBANTE, sacada de su base y su IGV, redondeada a entero.

    Nada escrito a mano (John, 10-sep-2026): la tasa es la de cada comprobante —18, 10.5 o 0— y
    CONCAR solo admite enteros, así que se redondea al exportar (ROUND_HALF_UP, como todo el motor).
    Hasta ese día había un 18 de respaldo para «IGV sin base» y una regla que llevaba el 10.5 al 10:
    las dos suponían una tasa en vez de leerla. Sin IGV la celda va vacía (así la lleva un registro
    real), y sin base de la que leerla también: ese comprobante no llega aquí, la validación lo para
    antes con IGV_NO_CUADRA. OJO: la plantilla describe la columna con «valores validos 0,10,18»
    (`datos.py`), así que un 10.5 % que salga 11 hay que comprobarlo con la primera importación real.
    """
    t = tasa_de_importes(igv, base_gravada)
    return "" if t is None else int(t.to_integral_value(rounding=ROUND_HALF_UP))


def asiento(c: Comprobante, contab: dict, mes: tuple[date, date], numero_comprobante: str,
            op: Opciones = OPCIONES, venta: bool = False) -> list[dict[str, Any]]:
    """Un comprobante → sus filas del Excel de CONCAR (claves 'A'..'AO').

    Se conserva con su firma y su salida de siempre porque es API pública: la usan el portal y los
    drivers de terceros. Desde la 0.7 ya no contiene la lógica: el asiento se arma en líneas
    neutrales (`motor.asiento_neutral`) y se proyecta a CONCAR (`drivers/concar/proyeccion.py`).
    Quien no necesite las columnas de CONCAR debería llamar directamente a `asiento_neutral`.
    """
    # Tardío a propósito: el driver de CONCAR importa este módulo y no puede importarse arriba.
    from ..drivers.concar import proyeccion
    from .motor import asiento_neutral

    # La moneda se comprueba antes que nada, como siempre: un EUR no llega a buscar su cuenta.
    proyeccion.codigo_moneda(c.moneda, contab)
    return proyeccion.filas(c, asiento_neutral(c, contab, mes, numero_comprobante, op, venta), contab)


def mes_del_libro(libro: Libro) -> tuple[date, date]:
    """El primer y el ultimo dia del periodo del libro.

    Es el marco dentro del que cae la fecha de cada asiento: un comprobante extemporaneo
    (emitido en un mes anterior) se asienta el dia 1, y uno posterior, el ultimo dia. La
    fecha del documento se conserva aparte, siempre."""
    return (date(libro.anio, libro.mes, 1),
            date(libro.anio, libro.mes, calendar.monthrange(libro.anio, libro.mes)[1]))
