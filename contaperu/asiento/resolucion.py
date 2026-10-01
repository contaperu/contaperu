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
from ..configuracion import CONFIG_POR_DEFECTO, por_defecto
from ..detracciones import (MARCA_SIRE, codigos_de, con_el_codigo_del_contador, monto_detraccion,
                            normalizar_una)
from ..igv import base_imputable, igv_del_asiento
from ..pcge import clase_de as _clase_de
from ..modelo import CENTIMO, Comprobante, Libro, a_decimal
from .configuracion import CONFIGURACION_DEL_ASIENTO, MONEDAS_CODIGO
from .faltas import FALTAS, SinCorrelativo, SinSigla
from .imputacion import Imputacion


# ── La configuración ──────────────────────────────────────────────────────────

# Los valores por defecto de lo que lee el asiento: el respaldo cuando la configuración que llega no trae una clave.
_DEL_ASIENTO = por_defecto(CONFIGURACION_DEL_ASIENTO)


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

    Con reparto en su imputación, una parte por cada una. Si no, una sola: la cuenta y el centro que traiga su
    imputación. Es la única resolución: el asiento, los drivers de registro y las faltas de cuenta y de centro leen
    esto.

    **Sin imputación no hay cuenta** (3.0): la configuración de la empresa ya no suple la del comprobante, así que
    `comprobantes_sin_cuenta` lo cuenta y `exigir_requisitos` detiene la exportación. Es a propósito — una compra
    imputada a un comodín que nadie eligió es un asiento mal hecho que nadie mira—."""
    imputacion = imputacion_de(c, config)
    if imputacion is not None and imputacion.reparto:
        return [(p.cuenta_contable, p.centro_costo, p.importe) for p in imputacion.reparto]
    cuenta = imputacion.cuenta_contable if imputacion is not None else ""
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


def sigla_de_tipo(tipo_cp: str | None, config: dict | None = None) -> str:
    """La sigla con la que un sistema legacy llama a un tipo de la Tabla 10 (en CONCAR, su Tabla General 06), o vacío
    si no la configuró.

    La LLAMA el driver, desde la 4.0: la línea del comprobante lleva el código de SUNAT (`documento.tipo_cp`) y la
    sigla la escribe quien conoce su tabla, en la columna que le toque. Vive aquí, y no en cada driver, porque el mapa
    (`tipos`) es configuración del asiento y la regla es una: un tipo sin sigla no se inventa —detiene la exportación
    antes de llegar al formato (`tipos_sin_sigla`)—."""
    equivalencia = (config or _DEL_ASIENTO).get("tipos") or {}
    fila = equivalencia.get(tipo_cp)
    return str(fila["sigla"]) if isinstance(fila, dict) and fila.get("sigla") else ""


def sigla_documento(c: Comprobante, config: dict | None = None) -> str:
    """La sigla con la que el sistema de destino llama al tipo del comprobante (en CONCAR, su Tabla General 06)."""
    return sigla_de_tipo(c.tipo_cp, config or _DEL_ASIENTO)


def tiene_detraccion(c: Comprobante) -> bool:
    d = c.detraccion if isinstance(c.detraccion, dict) else {}
    return bool(str(d.get("codigo") or "").strip()) or a_decimal(d.get("porcentaje")) > 0


def sin_efecto_contable(c: Comprobante) -> bool:
    """¿Este comprobante no mueve dinero? Total, IGV y retención en cero, y sin detracción.

    Es lo que decide que no pida cuenta contable ni centro, que no gaste un número de vóucher y que no produzca líneas
    de asiento —salvo que la configuración diga lo contrario (`asentar_sin_efecto_contable`, apagado de fábrica)—.

    **Decide por el importe y no por lo que SUNAT diga del comprobante**, y eso es el punto: el «Est. Comp» del SIRE
    viene sin tabla de valores publicada, así que apoyarse en él sería inventarle un significado, mientras «no mueve
    dinero» se comprueba mirando el documento. De paso atrapa más de lo que lo trajo: un comprobante en cero que
    llegue de un XML, de una foto o dictado por un ERP tampoco tiene asiento que armar, y no trae estado ninguno.

    Queda FUERA a propósito el caso raro de total cero con IGV distinto de cero —existe: una nota de crédito real que
    SUNAT tiene con la base sin declarar—. Ese conserva su asiento y su aviso de descuadre, porque ahí sí hay algo
    que mirar.

    Lo que esto NO cambia: el comprobante **sigue en el registro** que se declara a SUNAT. El asiento es una cosa y el
    registro es otra, y el correlativo de SUNAT necesita su fila —por eso los da de baja en cero en vez de quitarlos—.
    """
    return c.total == 0 and c.igv == 0 and c.retencion == 0 and not tiene_detraccion(c)


def asienta_sin_efecto(config: dict | None = None) -> bool:
    """¿La configuración pide asentar igual lo que no mueve dinero? De fábrica, no."""
    return bool((config or {}).get("asentar_sin_efecto_contable", False))


def con_efecto_contable(comprobantes: list[Comprobante], config: dict | None = None) -> list[Comprobante]:
    """Los que llevan asiento: todos, si la configuración lo pide; si no, los que mueven dinero."""
    if asienta_sin_efecto(config):
        return list(comprobantes)
    return [c for c in comprobantes if not sin_efecto_contable(c)]


def sub_diario(c: Comprobante, config: dict, es_venta: bool = False) -> str:
    """Por USO: ventas → sub_diario_ventas; compras con detracción → sub_diario_detraccion;
    un tipo con registro propio (boletas 13, honorarios 15) → el suyo; el resto → sub_diario_compras.
    Estas cuatro fuentes son lo que una aplicación deja configurar."""
    equivalencia = equivalencia_tipo(c, config)
    if not equivalencia:
        return ""
    if es_venta:
        return str(config.get("sub_diario_ventas") or _DEL_ASIENTO["sub_diario_ventas"])
    de_detraccion = str(config.get("sub_diario_detraccion") or "").strip()
    if de_detraccion and c.tipo_cp != TIPO_HONORARIOS and tiene_detraccion(c):
        return de_detraccion
    return str(equivalencia.get("sub_diario") or config.get("sub_diario_compras")
               or _DEL_ASIENTO["sub_diario_compras"])


def tipos_sin_sigla(comprobantes: list[Comprobante], config: dict) -> list[str]:
    """Códigos SUNAT presentes que no tienen sigla configurada (en orden de aparición)."""
    vistos: list[str] = []
    for c in comprobantes:
        if not equivalencia_tipo(c, config) and c.tipo_cp not in vistos:
            vistos.append(c.tipo_cp)
    return vistos


def monedas_sin_codigo(comprobantes: list[Comprobante], config: dict) -> list[str]:
    codigos = config.get(MONEDAS_CODIGO) or {}
    vistas: list[str] = []
    for c in comprobantes:
        moneda = (c.moneda or "PEN").upper()
        if not codigos.get(moneda) and moneda not in vistas:
            vistas.append(moneda)
    return vistas


# `_cuenta_de_respaldo` murió en la 3.0 (John, 23-sep-2026): daba la cuenta de la configuración cuando la imputación
# no traía ninguna —la de ingreso tenía hasta un valor de fábrica, `701101`— y con eso una venta sin cuenta salía
# imputada sola y el mes se daba por listo. **La cuenta del comprobante es de su imputación o no hay**, que es lo que
# el estándar dice desde que la imputación viaja aparte. Si reaparece en un grep, es código revivido.


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


def comprobantes_sin_codigo_detraccion(comprobantes: list[Comprobante], config: dict) -> list[Comprobante]:
    """Las compras que SUNAT marcó con detracción y a las que todavía les falta el código del Catálogo 54.

    Mira la anotación `_marca_sire`, que es la afirmación de SUNAT, y no la detracción a secas: una detracción con un
    código que el contribuyente no reconoce ya se blanquea desde antes (`detracciones.normalizar`) y es otra regla,
    con otro caso real. Y usa `normalizar_una` para decidir si el código sirve, en vez de repetir aquí la prueba: una
    segunda copia de esa regla acabaría diciendo algo distinto.

    Las ventas nunca entran: el RVIE no tiene columna de detracción, así que el lector solo marca compras."""
    codigos = codigos_de(config)
    return [c for c in comprobantes
            if isinstance(c.detraccion, dict) and c.detraccion.get(MARCA_SIRE)
            and normalizar_una(con_el_codigo_del_contador(c, config), codigos) is None]


def cuentas_del_asiento(c: Comprobante, config: dict, es_venta: bool = False) -> list[str]:
    """TODAS las cuentas que tocarán las líneas del asiento de este comprobante: la de la base (una por parte si va
    repartida), la del IGV, la de la retención de 4ta, la del tercero y la de la detracción.

    Existe porque las faltas se calculan **antes** de armar el asiento, y hasta la 1.0 solo miraban la base: una
    cuenta sin clase en la del tercero o en la del IGV —que vienen de la imputación y de la configuración— pasaba el
    diagnóstico y salía en un documento que el propio esquema rechaza. Quién decide qué líneas hay es
    `motor.lineas_del_comprobante`, que no se puede llamar desde aquí porque él importa esto; lo que ata las dos
    listas es un test (`tests/test_clases.py`), no la buena voluntad."""
    cuentas_config = config.get("cuentas") or {}
    por_defecto = CONFIG_POR_DEFECTO["cuentas"]
    moneda = (c.moneda or "PEN").upper()
    es_honorarios = not es_venta and c.tipo_cp == TIPO_HONORARIOS
    cuentas = [cuenta for cuenta, _, _ in partes_de(c, config, es_venta)]
    if igv_del_asiento(c, es_venta) > 0:
        cuentas.append(str(cuentas_config.get("igv") or por_defecto["igv"]))
    total = a_decimal(c.total).quantize(CENTIMO)
    retenido = min(a_decimal(c.retencion).quantize(CENTIMO), total) if es_honorarios else Decimal(0)
    if retenido > 0:
        cuentas.append(str(cuentas_config.get("retencion_4ta") or por_defecto["retencion_4ta"]))
    cuentas.append(cuenta_tercero(c, config, es_venta))
    if not es_venta and not es_honorarios and tiene_detraccion(c):
        _, detraido = monto_detraccion(c, config)
        if detraido > 0:
            cuentas.append(cuenta_por_pagar_detraccion(cuentas_config, moneda))
    return [cuenta for cuenta in cuentas if cuenta]


def cuentas_sin_denominacion(comprobantes: list[Comprobante], config: dict, es_venta: bool = False) -> list[str]:
    """Las cuentas que el asiento va a tocar y que la empresa **no ha dicho cómo se llaman**
    (`configuracion.denominacion_cuentas`), ordenadas y sin repetir.

    Se dice por CUENTA y no por comprobante, como la sigla o el código de moneda: lo que falta no es de un documento
    sino del plan de la empresa, y la lista con la que se arregla es la de cuentas a completar.

    Lo pide el detalle del plan contable del PLE (formato 5.3), cuyo campo 3 es obligatorio. El motor conoce el nombre
    de la divisionaria del PCGE —`101` es «Caja»— y **no sirve**: el catálogo llega hasta cinco dígitos y la empresa
    desagrega hasta donde quiera, así que de `101101` solo sabría decir «Caja» donde la empresa escribe «CAJA CHICA
    M.N.». Inventarlo sería declararle a SUNAT una denominación que el contribuyente no usa."""
    denominaciones = config.get("denominacion_cuentas") or {}
    faltan = {cuenta for c in comprobantes for cuenta in cuentas_del_asiento(c, config, es_venta)
              if not str(denominaciones.get(cuenta) or "").strip()}
    return sorted(faltan)


def comprobantes_sin_clase(comprobantes: list[Comprobante], config: dict, es_venta: bool = False) -> list[Comprobante]:
    """Las filas que tocarían una cuenta cuyo elemento del PCGE no tiene clase contable: el 8 (saldos intermediarios
    de gestión) y el 0 (cuentas de orden). Se miran **todas** las cuentas de su asiento (`cuentas_del_asiento`), no
    solo la de la base: basta con que una no tenga clase para que el asiento no se pueda armar, porque esa línea
    saldría sin `clase` y la clase es obligatoria desde la 1.0."""
    return [c for c in comprobantes
            if any(not _clase_de(cuenta) for cuenta in cuentas_del_asiento(c, config, es_venta))]


def comprobantes_sin_centro(comprobantes: list[Comprobante], config: dict, es_venta: bool = False) -> list[Comprobante]:
    """Las filas a las que les falta un centro de costo que SÍ hace falta.

    El centro es obligatorio solo donde de verdad se escribe: en la columna M de las cuentas de
    `cuentas_con_centro` (el contador, 06-sep-2026 y 09-sep-2026). Una cuenta fuera de la lista
    NO bloquea nunca, ni siquiera con la X de su línea elegida como referencia: una referencia que se
    puede dejar en blanco no puede impedir exportar un mes.

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

    **Lo que no mueve dinero no se le pide a nadie** (`sin_efecto_contable`): un comprobante dado de baja por SUNAT
    llega con todos sus importes en cero y no hay cuenta, centro ni reparto que ponerle. Se filtra aquí, en el único
    sitio donde se decide qué le falta a una imputación, y no en cada regla por separado. La sigla y el código de
    moneda **sí se le siguen pidiendo**: los escribe también un driver de registro, que no arma ningún asiento.
    """
    de_la_imputacion = con_efecto_contable(comprobantes, config)
    salida: dict[str, list] = {}
    if "tipo_cp" in exige:
        salida["sin_sigla"] = tipos_sin_sigla(comprobantes, config)
    if "moneda" in exige:
        salida["sin_codigo_de_moneda"] = monedas_sin_codigo(comprobantes, config)
    if "cuenta_unica" in exige:
        salida["reparto_no_admitido"] = con_reparto(de_la_imputacion, config)
    if "cuenta_contable" in exige:
        salida["sin_cuenta"] = comprobantes_sin_cuenta(de_la_imputacion, config, es_venta)
        salida["sin_clase"] = comprobantes_sin_clase(de_la_imputacion, config, es_venta)
        salida["reparto_que_no_cuadra"] = repartos_que_no_cuadran(de_la_imputacion, config, es_venta)
    if "centro_costo" in exige:
        salida["sin_centro"] = comprobantes_sin_centro(de_la_imputacion, config, es_venta)
    if "denominacion" in exige:
        salida["sin_denominacion"] = cuentas_sin_denominacion(de_la_imputacion, config, es_venta)
    if "detraccion" in exige:
        salida["sin_codigo_detraccion"] = comprobantes_sin_codigo_detraccion(de_la_imputacion, config)
    return salida


def exigir_requisitos(comprobantes: list[Comprobante], config: dict, es_venta: bool = False,
                      exige: frozenset[str] | set[str] = frozenset()) -> None:
    """Hace cumplir `faltantes_para`: la primera falta, en el orden de `FALTAS` (tipo → moneda → reparto no admitido →
    cuenta → reparto que no cuadra → centro), detiene la exportación con su excepción. Un tipo sin sigla no se
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
