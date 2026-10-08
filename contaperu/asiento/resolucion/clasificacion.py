"""Qué es cada comprobante: su sigla, si mueve dinero, a qué sub-diario va, si su cuenta lleva centro de costo y
qué cuentas tocará su asiento.

Todo lo de aquí **describe**: ninguna función decide que algo falta —eso es `requisitos`— ni escribe nada. La
clasificación es la misma para cualquier destino, y por eso la leen tanto el motor como los drivers de registro.
"""
from __future__ import annotations

from decimal import Decimal

from ...catalogos import TIPO_HONORARIOS
from ...configuracion import CONFIG_POR_DEFECTO
from ...modelo import CENTIMO, Comprobante, a_decimal
from ...tributos.detracciones import monto_detraccion
from ...tributos.igv import base_imputable, igv_del_asiento
from .configurado import _DEL_ASIENTO, cuenta_por_pagar_detraccion
from .imputado import cuenta_tercero, imputacion_de, partes_de


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


def anulada_por_nota(c: Comprobante, config: dict) -> bool:
    """¿El contador marcó esta factura como anulada por una nota de crédito? (1.2)

    Lo lee de su imputación, que es donde vive lo que decide el contador y no lo que dice el papel. SUNAT no lo da:
    ninguna columna del RCE marca la factura, solo la nota apunta hacia atrás."""
    imputacion = imputacion_de(c, config)
    return bool(imputacion and imputacion.anulada_por_nota)


def cuentas_del_asiento(c: Comprobante, config: dict, es_venta: bool = False) -> list[str]:
    """TODAS las cuentas que tocarán las líneas del asiento de este comprobante: la de la base (una por parte si va
    repartida), la del IGV, la de la retención de 4ta, la del tercero y la de la detracción.

    Existe porque las faltas se calculan **antes** de armar el asiento, y hasta la 1.0 solo miraban la base: una
    cuenta sin clase en la del tercero o en la del IGV —que vienen de la imputación y de la configuración— pasaba el
    diagnóstico y salía en un documento que el propio esquema rechaza. Quién decide qué líneas hay es
    `motor.lineas_del_comprobante`, que no se puede llamar desde aquí porque él importa esto; lo que ata las dos
    listas es un test (`tests/test_clases.py`), no la buena voluntad.

    Ese lazo estuvo roto entre la 5.3 y la 5.3.1: `anulada_por_nota` entró en la condición de allí y no en la de
    aquí, así que una factura anulada seguía declarando la cuenta por pagar de la detracción y el PLE pedía su
    denominación (`cuentas_sin_denominacion`) para una cuenta que ninguna línea toca. El test no lo cazó porque
    ninguno de sus casos llevaba la marca; ahora sí."""
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
    if not es_venta and not es_honorarios and tiene_detraccion(c) and not anulada_por_nota(c, config):
        _, detraido = monto_detraccion(c, config)
        if detraido > 0:
            cuentas.append(cuenta_por_pagar_detraccion(cuentas_config, moneda))
    return [cuenta for cuenta in cuentas if cuenta]


def reparto_no_cuadra(c: Comprobante, config: dict, es_venta: bool = False) -> bool:
    """¿El reparto de su imputación deja de sumar la base del asiento? Sin tolerancia, como la partida doble:
    un reparto que no cuadra da un asiento que no cuadra."""
    imputacion = imputacion_de(c, config)
    if imputacion is None or not imputacion.reparto:
        return False
    return sum((p.importe for p in imputacion.reparto), Decimal("0.00")) != base_imputable(c, es_venta)


def con_reparto(comprobantes: list[Comprobante], config: dict) -> list[Comprobante]:
    """Los que reparten su base entre varias cuentas (`reparto` en su imputación): lo que no admite un destino que
    exige `cuenta_unica`."""
    return [c for c in comprobantes if (imputacion := imputacion_de(c, config)) is not None and imputacion.reparto]
