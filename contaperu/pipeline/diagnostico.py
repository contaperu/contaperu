"""Diagnosticar: todo lo que hay que mirar de un mes ANTES de exportarlo, en una sola respuesta.

No añade ninguna regla contable: reúne comprobaciones que ya existen (`validar.revisar`, `asiento.faltantes_para`,
`contrato.no_caben`, la numeración por sub-diario) y las cuenta por su serie-número, con a quién pedirle cada cosa.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from .. import asiento as asi
from .. import detracciones, drivers, validar
from ..asiento.faltas import CONTADOR, FALTAS, PROVEEDOR, SISTEMA  # noqa: F401  (PROVEEDOR: reservado)
from ..drivers import contrato
from ..modelo import Comprobante, Libro
from .preparacion import (claves_previas_de, comprobantes_de, con_imputacion, config_aplicada,
                          errores_de_configuracion, imputacion_del_documento, libro_de)
from .preparacion import serie_numero as _serie_numero
from .seleccion import fuera_de

# --- a quién se le pide lo que falta ------------------------------------------------

# Quién resuelve cada cosa que `diagnosticar` puede encontrar. No es una regla contable: las reglas
# ya existen (`validar.py`, `asiento.faltantes_para`); esto solo dice a quién preguntar, para que un
# agente no adivine (la idea viene del *Accounting agent* de Intuit, ver `REFERENCIAS.md`). El criterio:
# **contador** = se decide mirando el documento o el plan de cuentas; **sistema** = configuración del
# destino o un dato público que no está en el papel (el T.C. lo publica SUNAT). **`proveedor` queda
# reservado**: el motor ve un documento y no puede afirmar que lo que falta esté en el papel del
# proveedor; entrará con un caso real (la constancia de detracción conciliada, por ejemplo).
# `tests/test_diagnosticar.py` recorre `validar.py` y comprueba que ningún código se quede fuera.
PEDIR_A: dict[str, str] = {
    # lo que falta para el destino (claves de `faltantes`): lo dice su tabla, `asiento.FALTAS`
    **{falta.clave: falta.pedir_a for falta in FALTAS},
    # una configuración que no cumple lo declarado se arregla donde se configura
    "configuracion_invalida": SISTEMA,
    # errores de la validación
    "ANIO_DUA_FALTA": CONTADOR, "CONTRAPARTE_FALTA": CONTADOR, "DNI_INVALIDO": CONTADOR,
    "DSCTO_MAYOR_QUE_BASE": CONTADOR, "DUPLICADO": CONTADOR, "DUPLICADO_PERIODO_ANTERIOR": CONTADOR,
    "FECHA_FALTA": CONTADOR, "FECHA_POSTERIOR": CONTADOR, "IGV_NO_CUADRA": CONTADOR,
    "MONEDA_INVALIDA": CONTADOR, "NOTA_SIN_FECHA_REF": CONTADOR, "NOTA_SIN_REFERENCIA": CONTADOR,
    "NUMERO_FALTA": CONTADOR, "RETENCION_MAYOR": CONTADOR, "RUC_INVALIDO": CONTADOR, "SERIE_FALTA": CONTADOR,
    "TC_FALTA": SISTEMA, "TOTAL_NO_CUADRA": CONTADOR, "VENCIMIENTO_FALTA": CONTADOR,
    "XML_DE_OTRO_RUC": CONTADOR, "XML_PARA_OTRO_RUC": CONTADOR,
    # avisos (no bloquean; están para que la tabla sea completa)
    "ADQUIRENTE_NO_COINCIDE": CONTADOR, "ANTICIPO": CONTADOR, "BOLETA_SIN_DOC": CONTADOR,
    "COMPRA_BOLETA": CONTADOR, "CREDITO_FISCAL_FUERA_DE_PLAZO": CONTADOR, "DETRACCION_TASA_DISTINTA": CONTADOR,
    "EMISOR_NO_COINCIDE": CONTADOR, "GRATUITAS": CONTADOR, "IGV_TASA_REDUCIDA": CONTADOR, "NOMBRE_FALTA": CONTADOR,
    "PERIODO_ANTERIOR": CONTADOR, "RETENCION_NO_APLICA": CONTADOR, "RETENCION_TASA": CONTADOR,
    "SIRE_SIN_DETALLE": CONTADOR, "TIPO_CP_DESCONOCIDO": CONTADOR, "TOTAL_CERO": CONTADOR,
}


def detraccion_pendiente(c: Comprobante, config: dict | None = None) -> bool:
    """¿La detracción de este comprobante espera todavía su constancia del Banco de la Nación?

    La regla vive en `detracciones.estado_de` desde la 3.2 y aquí solo se pregunta: un comprobante está pendiente
    mientras no tenga un número de constancia distinto del comodín **y** la fecha del depósito. Hasta la 3.1 la
    pregunta se respondía aquí y bastaba el número —y el `estado` que trajera el documento contaba—, que es lo que
    dejaba pasar un mes con vóuchers pegados sin fecha.
    """
    return detracciones.esta_pendiente(c, config)


def _de_la_detraccion(c: Comprobante, serie_numero: Any) -> dict:
    """Una detracción como se cuenta en el diagnóstico. **La misma forma esté pagada o pendiente**: quien pinta las
    dos listas no aprende dos formas, y en una pendiente que ya trae número se ve que lo que falta es la fecha."""
    d = c.detraccion or {}
    return {"serie_numero": serie_numero(c), "codigo": str(d.get("codigo") or ""),
            "monto": str(d.get("monto") or ""), "nro_constancia": str(d.get("nro_constancia") or ""),
            "fecha_constancia": str(d.get("fecha_constancia") or "")}


def que_falta(con_error: list[Comprobante], candidatos: list[Comprobante], faltantes: dict,
              exige: frozenset[str], serie_numero: Any = _serie_numero) -> list[dict]:
    """Lo que bloquea la exportación a ESE destino, agrupado por motivo y con a quién pedírselo.

    Un agente redacta «faltan cuentas contables en E001-871 y E001-872», no dos preguntas: por eso va
    por motivo. Solo lo que bloquea: los errores de la validación y los faltantes que el driver exige.
    """
    salida: list[dict] = []
    por_codigo: dict[str, list[str]] = {}
    textos: dict[str, str] = {}
    for c in con_error:
        for o in c.observaciones:
            if o.nivel == "error":
                por_codigo.setdefault(o.codigo, []).append(serie_numero(c))
                textos.setdefault(o.codigo, o.texto)
    for codigo in sorted(por_codigo):
        salida.append({"motivo": codigo, "texto": textos[codigo], "comprobantes": por_codigo[codigo],
                       "pedir_a": PEDIR_A.get(codigo, CONTADOR)})
    for falta in FALTAS:
        clave = falta.clave
        if not falta.requisito or falta.requisito not in exige or not faltantes.get(clave):
            continue
        if clave == "sin_sigla":
            cuales = [serie_numero(c) for c in candidatos if c.tipo_cp in faltantes[clave]]
            texto = f"{falta.texto}: {', '.join(faltantes[clave])}"
        elif clave == "sin_codigo_de_moneda":
            cuales = [serie_numero(c) for c in candidatos if c.moneda in faltantes[clave]]
            texto = f"{falta.texto}: {', '.join(faltantes[clave])}"
        else:
            cuales, texto = list(faltantes[clave]), falta.texto
        salida.append({"motivo": clave, "texto": texto, "comprobantes": cuales, "pedir_a": falta.pedir_a})
    for motivo, cuales in (faltantes.get("no_cabe") or {}).items():
        salida.append({"motivo": "no_cabe", "texto": motivo, "comprobantes": cuales, "pedir_a": PEDIR_A["no_cabe"]})
    return salida


def _sin_configuracion(libro: Libro, driver: str, exige: frozenset[str], todos: list[Comprobante],
                       errores: list[str]) -> dict:
    """El diagnóstico de un mes cuya configuración no se puede aplicar: sin ella no hay nada que medir, así que dice eso
    —cada error con su ruta— y a quién pedírselo, con la forma de siempre."""
    return {
        "libro": {"ruc": libro.ruc, "periodo": libro.periodo, "tipo": libro.tipo},
        "driver": driver,
        "exige": sorted(exige),
        "listo_para_exportar": False,
        "por_que_no": [f"la configuración tiene {len(errores)} {'error' if len(errores) == 1 else 'errores'}"],
        "que_falta": [{"motivo": "configuracion_invalida", "comprobantes": [],
                       "texto": "la configuración no cumple lo que declaran el motor y su sistema",
                       "pedir_a": PEDIR_A["configuracion_invalida"]}],
        "errores_de_configuracion": errores,
        "totales": {"comprobantes": len(todos), "saldrian": 0, "excluidos": sum(1 for c in todos if c.excluida),
                    "fuera_del_destino": 0, "con_error": 0, "con_aviso": 0},
        "bloqueantes": [], "avisos": [], "faltantes": {}, "detracciones_pendientes": [], "detracciones_pagadas": [],
        "resumen_por_contraparte": {}, "sub_diarios": {}, "saldrian": [],
    }


def diagnosticar(doc: dict, *, driver: str, configuracion: dict | None = None, correlativos: dict | None = None,
                 imputacion: dict | None = None, claves_previas: Any = None) -> dict:
    """Todo lo que hay que mirar de un mes ANTES de exportarlo, en una sola respuesta.

    Pura y sin estado. **No lanza** por lo que le falte al mes: lo describe. Tampoco por una configuración que no se
    puede aplicar: la dice en `errores_de_configuracion`. Solo rechaza un documento que no es un documento (sin
    `libro`, o comprobantes ilegibles).
    """
    libro = libro_de(doc)
    todos = comprobantes_de(doc)
    previas = claves_previas_de(claves_previas)
    modulo = drivers.obtener(driver)
    opciones = getattr(modulo, "OPCIONES", None)

    def _serie_numero(c: Comprobante) -> str:
        # Como en la línea del asiento de ese destino (hito 0.8): el mismo comprobante se nombra igual en los dos.
        return asi.serie_numero_de(c, opciones)

    # Lo que ESE destino exige (`contrato.exige`): decide qué faltante deja el mes «no listo». El CSV
    # no exige centro ni moneda con código; CONCAR, los dos; el SIRE, nada de esto.
    exige = contrato.exige(modulo)
    errores = errores_de_configuracion(configuracion)
    if errores:
        return _sin_configuracion(libro, driver, exige, todos, errores)
    config = con_imputacion(config_aplicada(configuracion, driver), imputacion_del_documento(doc, imputacion, todos), todos)
    detracciones.normalizar(todos, config)
    validar.revisar(todos, libro, previas)
    es_venta = libro.es_venta

    excluidos = [c for c in todos if c.excluida]
    fuera = fuera_de([c for c in todos if not c.excluida], getattr(modulo, "EXCLUYE_TIPOS", None))
    candidatos = [c for c in todos if not c.excluida and c not in fuera]
    con_error = [c for c in candidatos if c.tiene_errores]
    con_aviso = [c for c in candidatos if c.observaciones and not c.tiene_errores]

    # Lo que se mira: lo que ese destino exige y, además, lo que solo informa —la cuenta y el centro a todo el que lleva
    # cuentas, el tipo y la moneda al que arma asientos—, con la misma regla que hace cumplir el núcleo
    # (`asiento.faltantes_para`). El reparto que un destino no admite aparece solo si lo exige, y lo que su formato no
    # puede llevar, si el driver lo declara (`no_caben`).
    mirar = set(exige)
    if contrato.lleva_cuentas(modulo):
        mirar |= {"cuenta_contable", "centro_costo"}
    # El tipo con sigla, la moneda con código y los sub-diarios son vocabulario legacy: a un driver neutral no se le miran.
    legacy = contrato.arma_asientos(modulo) and contrato.vocabulario(modulo) != "neutral"
    if legacy:
        mirar |= {"tipo_cp", "moneda"}
    codigos = ("sin_sigla", "sin_codigo_de_moneda")      # se dicen por su código, no por comprobante
    faltantes: dict[str, Any] = {clave: cuales if clave in codigos else [_serie_numero(c) for c in cuales]
                                 for clave, cuales in asi.faltantes_para(candidatos, config, es_venta, mirar).items()}
    if contrato.lleva_cuentas(modulo) and callable(getattr(modulo, "no_caben", None)):
        faltantes["no_cabe"] = {motivo: [_serie_numero(c) for c in lista] for motivo, lista
                                in contrato.no_caben(modulo, libro, candidatos, config).items()}
    sub_diarios: dict[str, Any] = {}
    if legacy:
        con_equivalencia = [c for c in candidatos if c.tipo_cp not in faltantes["sin_sigla"]]
        presentes = asi.sub_diarios_presentes(con_equivalencia, config, es_venta)
        corr = asi.correlativos_de_partida(con_equivalencia, config, es_venta, correlativos)
        faltantes["sin_correlativo"] = [s for s in presentes if s not in (correlativos or {})]
        etiquetas = asi.etiquetas_sub_diario(config)
        sub_diarios = {s: {"etiqueta": etiquetas.get(s, s), "comprobantes": n, "empieza_en": corr[s]}
                       for s, n in presentes.items()}

    por_que_no: list[str] = []
    if not candidatos:
        por_que_no.append("no hay comprobantes que exportar")
    if con_error:
        por_que_no.append(f"{len(con_error)} comprobantes con observaciones que bloquean")
    for falta in FALTAS:
        # Solo lo que el destino exige deja el mes «no listo»; lo demás sigue en `faltantes`, informando.
        if falta.requisito in exige and faltantes.get(falta.clave):
            por_que_no.append(f"{len(faltantes[falta.clave])} {falta.texto}")
    # Lo que no cabe en el formato del destino lo declara el propio driver: siempre bloquea.
    for motivo, cuales in (faltantes.get("no_cabe") or {}).items():
        por_que_no.append(f"{len(cuales)} {motivo}")

    # Por contraparte y por moneda: soles y dólares no se suman. `total` y `moneda` son los de la primera moneda en que
    # aparece la contraparte, y `por_moneda` los trae todos.
    por_contraparte: dict[str, dict] = {}
    for c in candidatos:
        clave = c.contraparte_doc or "(sin documento)"
        r = por_contraparte.setdefault(clave, {"nombre": c.contraparte_nombre, "comprobantes": 0, "total": "",
                                               "moneda": c.moneda, "por_moneda": {}})
        r["comprobantes"] += 1
        r["por_moneda"][c.moneda] = (r["por_moneda"].get(c.moneda, Decimal("0.00"))
                                     + (c.total if not c.es_nota_credito else -c.total))
    for r in por_contraparte.values():
        r["por_moneda"] = {moneda: str(total) for moneda, total in r["por_moneda"].items()}
        r["total"] = r["por_moneda"][r["moneda"]]
    # Lo que saldría: la misma lista que se cuenta en `totales`.
    saldrian = [_serie_numero(c) for c in candidatos if not c.tiene_errores]

    por_estado: dict[str, list[dict]] = {"detracciones_pendientes": [], "detracciones_pagadas": []}
    donde = {detracciones.PROVISIONADO: "detracciones_pendientes", detracciones.PAGADO: "detracciones_pagadas"}
    for c in candidatos:
        clave = donde.get(detracciones.estado_de(c, config))
        if clave:
            por_estado[clave].append(_de_la_detraccion(c, _serie_numero))

    return {
        "libro": {"ruc": libro.ruc, "periodo": libro.periodo, "tipo": libro.tipo},
        "driver": driver,
        "exige": sorted(exige),
        "listo_para_exportar": not por_que_no,
        "por_que_no": por_que_no,
        "que_falta": que_falta(con_error, candidatos, faltantes, exige, _serie_numero),
        "errores_de_configuracion": [],
        "totales": {"comprobantes": len(todos), "saldrian": len(saldrian), "excluidos": len(excluidos),
                    "fuera_del_destino": len(fuera), "con_error": len(con_error), "con_aviso": len(con_aviso)},
        "bloqueantes": [{"serie_numero": _serie_numero(c),
                         "observaciones": [o.a_dict() for o in c.observaciones if o.nivel == "error"]}
                        for c in con_error],
        "avisos": [{"serie_numero": _serie_numero(c),
                    "observaciones": [o.a_dict() for o in c.observaciones if o.nivel == "aviso"]}
                   for c in con_aviso],
        "faltantes": faltantes,
        # Las dos caras de la detracción (3.2). Hasta la 3.1 solo salían las pendientes, y una aplicación que
        # quisiera enseñar «7 pendientes · 12 pagadas» tenía que deducir las pagadas por su cuenta, con la regla
        # copiada. `estado_de` se pregunta UNA vez por comprobante y reparte.
        **por_estado,
        "resumen_por_contraparte": por_contraparte,
        "sub_diarios": sub_diarios,
        "saldrian": saldrian,
    }
