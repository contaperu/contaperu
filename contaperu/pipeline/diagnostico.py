"""Diagnosticar: todo lo que hay que mirar de un mes ANTES de exportarlo, en una sola respuesta.

No añade ninguna regla contable: reúne comprobaciones que ya existen (`validar.revisar`, `asiento.faltantes_para`,
`contrato.no_caben`, la numeración por sub-diario) y las cuenta por su serie-número, con a quién pedirle cada cosa.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from .. import asiento as asi
from .. import drivers
from ..tributos import detracciones, validar
from ..asiento.faltas import CONTADOR, FALTA, FALTAS, PROVEEDOR, SISTEMA  # noqa: F401  (PROVEEDOR: reservado)
from ..drivers import contrato
from ..modelo import Comprobante, Libro
from .preparacion import (claves_previas_de, comprobantes_de, con_imputacion, config_aplicada,
                          errores_de_configuracion, imputacion_del_documento, libro_de, preparar_tesoreria)
from .preparacion import serie_numero as _serie_numero
from .seleccion import fuera_de

# --- lo que puede impedir asentar el dinero -----------------------------------------
#
# Las cinco faltas de tesorería con el texto que lee una persona y a quién pedírsela, que es lo que `asiento.FALTAS`
# da para un comprobante. **Están aquí y no en esa tabla**, y el porqué lo escribe `asiento/faltas.py`: aquélla
# reparte faltas por comprobante —las cuenta por su serie-número y las reparte entre `bloqueantes` y `avisos`— y un
# movimiento no tiene ni una cosa ni la otra. Lo que comparten es el trato, no la tabla.
#
# Se teclean por la `clave` de su excepción y no a mano, para que renombrar una las renombre en los dos sitios; el
# orden es el de la comprobación (`asiento.FALTAS_DEL_MOVIMIENTO`). El texto va detrás de un número —«2 movimiento(s)
# sin imputación»— y **se trae su propio sustantivo**, porque no siempre es el movimiento: lo que se nombra es lo que
# hay que arreglar, y para la 104 que falta eso es la cuenta.
#
# A quién: `contador` las cuatro primeras, con el mismo criterio de abajo —la contrapartida la decide él, la 104 la
# declara el contribuyente en su plan, cuál de las dos patas declara el traspaso es suyo y una cuenta del elemento 8
# es un error de imputación—. `sistema` la quinta: es haber elegido un destino de vocabulario legacy para un libro
# que todavía no tiene sub-diario, y lo que se cambia es el driver, como en `libro_que_el_destino_no_lleva`.
FALTAS_DEL_DINERO: dict[str, tuple[str, str]] = {
    asi.LibroQueTodaviaNoSeNumera.clave: (
        "libro(s) que el motor todavía no sabe numerar: su sub-diario espera el archivo real que lo pida", SISTEMA),
    asi.TraspasoEnDosPatas.clave: (
        "traspaso(s) declarados por sus dos movimientos, que contarían el dinero dos veces", CONTADOR),
    asi.MovimientoSinImputar.clave: ("movimiento(s) sin imputación, así que no hay con qué saldarlos", CONTADOR),
    asi.SinCuentaDeEfectivo.clave: ("cuenta(s) de efectivo sin resolver", CONTADOR),
    asi.CuentaSinClase.clave: (
        "cuenta(s) de un elemento sin clase contable (el 8 y el 0 del PCGE no la tienen)", CONTADOR),
}


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
    # y las del dinero, que tienen la suya por lo que dice el bloque de arriba
    **{clave: pedir_a for clave, (_, pedir_a) in FALTAS_DEL_DINERO.items()},
    # una configuración que no cumple lo declarado se arregla donde se configura
    "configuracion_invalida": SISTEMA,
    # y elegir un destino que no lleva ese libro también: lo que se cambia es el driver, no el mes
    "libro_que_el_destino_no_lleva": SISTEMA,
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
    "EMISOR_NO_COINCIDE": CONTADOR, "FACTURA_CON_NOTA_DE_CREDITO": CONTADOR,
    "FACTURA_ANULADA_SIN_NOTA": CONTADOR,
    "GRATUITAS": CONTADOR, "IGV_TASA_REDUCIDA": CONTADOR,
    "MEDIO_PAGO_DESCONOCIDO": CONTADOR, "NOMBRE_FALTA": CONTADOR,
    "PERIODO_ANTERIOR": CONTADOR, "RETENCION_NO_APLICA": CONTADOR, "RETENCION_TASA": CONTADOR,
    "SIRE_SIN_DETALLE": CONTADOR, "TIPO_CP_DESCONOCIDO": CONTADOR,
    "TIPO_NOTA_DESCONOCIDO": CONTADOR, "TIPO_NOTA_NO_APLICA": CONTADOR, "TOTAL_CERO": CONTADOR,
    "TOTAL_CERO_EN_LA_PROPUESTA": CONTADOR,
}


# Los dos cubos en que el diagnóstico reparte una detracción, por su estado. **Es por donde la distinción viaja**:
# el estándar declaraba un campo `detraccion.estado` con los dos valores y lo retiró en la 2.0 —nadie lo escribía y
# las cadenas no salían del motor—, así que lo que un ERP lee son estos dos nombres y no el estado.
CUBOS_DE_LA_DETRACCION: dict[str, str] = {detracciones.PROVISIONADO: "detracciones_pendientes",
                                          detracciones.PAGADO: "detracciones_pagadas"}


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


# La única falta que bloquea sin colgar de un requisito del destino: ver el comentario dentro de `que_falta`.
SIN_REQUISITO_QUE_BLOQUEA = "anulada_con_deposito"


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
        # `anulada_con_deposito` no cuelga de ningún requisito y aun así bloquea: no es que al destino le falte un
        # dato, es que dos hechos del documento se contradicen. Las demás sin requisito (`sin_correlativo`, `no_cabe`)
        # siguen fuera de este bucle, la segunda con su propia vuelta justo abajo.
        if clave != SIN_REQUISITO_QUE_BLOQUEA and (not falta.requisito or falta.requisito not in exige):
            continue
        if not faltantes.get(clave):
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


def _libro_que_el_destino_no_lleva(libro: Libro, driver: str, exige: frozenset[str], todos: list[Comprobante],
                                   modulo: Any) -> dict:
    """El diagnóstico de un mes cuyo libro ese destino no lleva: no hay nada que medir, y lo que falta no es del mes.

    Hermano de `_sin_configuracion` y por el mismo motivo: la forma de la respuesta no cambia, cambia lo que dice.
    La diferencia con `exportar` —que sí **lanza** `LibroQueElDestinoNoLleva`— es la de siempre entre preguntar y
    hacer: ésta describe. Y el `pedir_a` es `sistema` porque elegir el destino es configuración, no una decisión
    contable: lo que hay que cambiar es el driver, o llevar ese libro a otro sitio."""
    lleva = sorted(getattr(modulo, "FORMATOS", {}))
    return {
        "libro": {"ruc": libro.ruc, "periodo": libro.periodo, "tipo": libro.tipo},
        "driver": driver,
        "exige": sorted(exige),
        "listo_para_exportar": False,
        "por_que_no": [f"el destino {driver!r} no lleva libros de tipo {libro.tipo!r}"],
        "que_falta": [{"motivo": "libro_que_el_destino_no_lleva", "comprobantes": [],
                       "texto": f"{driver} lleva {', '.join(lleva)}",
                       "pedir_a": PEDIR_A["libro_que_el_destino_no_lleva"]}],
        "errores_de_configuracion": [],
        # Se cuenta lo que el documento trae y nada más: sin un destino que lo lleve no se ha mirado ni un
        # comprobante, y afirmar que alguno «saldría» sería falso.
        "totales": {"comprobantes": len(todos), "saldrian": 0, "excluidos": sum(1 for c in todos if c.excluida),
                    "fuera_del_destino": 0, "sin_efecto_contable": 0, "con_error": 0, "con_aviso": 0},
        "bloqueantes": [], "avisos": [], "faltantes": {}, "detracciones_pendientes": [], "detracciones_pagadas": [],
        "resumen_por_contraparte": {}, "sub_diarios": {}, "saldrian": [],
    }


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
        # Con la configuración rota no se ha mirado ningún comprobante, así que los contadores que dependen de mirarlos
        # van en cero — incluido `sin_efecto_contable`, que se decide con la configuración aplicada.
        "totales": {"comprobantes": len(todos), "saldrian": 0, "excluidos": sum(1 for c in todos if c.excluida),
                    "fuera_del_destino": 0, "sin_efecto_contable": 0, "con_error": 0, "con_aviso": 0},
        "bloqueantes": [], "avisos": [], "faltantes": {}, "detracciones_pendientes": [], "detracciones_pagadas": [],
        "resumen_por_contraparte": {}, "sub_diarios": {}, "saldrian": [],
    }


def _del_dinero(doc: dict, libro: Libro, modulo: Any, driver: str, *, configuracion: dict | None,
                **_del_registro) -> dict:
    """El diagnóstico de un libro de tesorería: cuánto dinero trae el mes y qué impediría asentarlo (12.12).

    **Hasta la 12.11 este camino no existía y el libro se diagnosticaba en vacío**: el driver neutral declara
    `tesoreria` en sus `FORMATOS` desde la 12.10, así que la respuesta pasaba el muro de «ese destino no lleva ese
    libro» y seguía por la ruta del comprobante, donde `comprobantes_de` devuelve lista vacía. Contestaba todos los
    contadores en cero y «no hay comprobantes que exportar» sin haber mirado ni un movimiento: cierto por
    casualidad y engañoso, que es lo peor que puede hacer una operación que existe para que nadie exporte a ciegas.
    Sus dos hermanas —`armado.generar_asiento` y `salida.exportar_archivo`— bifurcaban desde la 12.9 y la 12.10.

    **Describe lo que el asiento hace cumplir**, como en el otro camino: las cinco faltas salen de
    `asiento.faltantes_de_movimientos`, que es la misma comprobación que `lineas_e_indice_de_movimientos` hace al
    armar, contestada entera en vez de parando en la primera. Por eso el `motivo` de `que_falta` es la `clave` de
    la excepción con la que `exportar` se niega.

    **Y lo que no es de un movimiento no sale en cero: no sale.** `excluida`, `estado` y `observaciones` son campos
    del comprobante, y la detracción, el sub-diario y la contraparte también; rellenar sus contadores con ceros
    diría «se miró y no hay» donde la verdad es «aquí eso no existe» — que es exactamente el fallo que esto
    arregla, en pequeño. Tampoco sale `exige`: lo que un driver exige (`contrato.exige`) está escrito sobre
    comprobantes y **ninguno de esos requisitos se comprueba aquí**, así que publicar la lista haría creer que sí.
    El hueco está declarado en `armado._asiento_de_movimientos`.

    Lo que el mes tiene —cuánto entró por cuenta, qué no cuadra contra lo que el banco declaró— no se repite aquí:
    eso es `api.revisar_tesoreria`, que mira el dinero. Ésta contesta una sola pregunta, la de siempre: **¿sale?**
    """
    # El bloque crudo, sin construir un movimiento: para contar las filas que trae el documento basta, y
    # `preparar_tesoreria` —que sí los construye— lanza si no hay ninguno, porque va a hacer y no a mirar.
    crudos = doc.get("movimientos") or []
    if libro.tipo not in getattr(modulo, "FORMATOS", {}):
        lleva = sorted(getattr(modulo, "FORMATOS", {}))
        return _sin_mirar_el_dinero(
            libro, driver, crudos, [f"el destino {driver!r} no lleva libros de tipo {libro.tipo!r}"],
            [{"motivo": "libro_que_el_destino_no_lleva", "movimientos": [],
              "texto": f"{driver} lleva {', '.join(lleva)}", "pedir_a": PEDIR_A["libro_que_el_destino_no_lleva"]}])
    errores = errores_de_configuracion(configuracion)
    if errores:
        return _sin_mirar_el_dinero(
            libro, driver, crudos, [f"la configuración tiene {len(errores)} {'error' if len(errores) == 1 else 'errores'}"],
            [{"motivo": "configuracion_invalida", "movimientos": [],
              "texto": "la configuración no cumple lo que declaran el motor y su sistema",
              "pedir_a": PEDIR_A["configuracion_invalida"]}], errores)
    if not crudos:
        return _sin_mirar_el_dinero(libro, driver, crudos, ["no hay movimientos que exportar"], [])

    libro, movimientos, config = preparar_tesoreria(doc, configuracion, driver)
    faltan = asi.faltantes_de_movimientos(libro, movimientos, config, vocabulario=contrato.vocabulario(modulo))
    hay = [(clave, cuales) for clave, cuales in faltan.items() if cuales]
    por_que_no = [f"{len(cuales)} {FALTAS_DEL_DINERO[clave][0]}" for clave, cuales in hay]
    # **Todo o nada**, y es la diferencia de fondo con un comprobante: uno con errores se queda fuera y los demás
    # salen, pero el asiento de un libro de tesorería se arma entero o no se arma —`lineas_e_indice_de_movimientos`
    # se niega—, así que lo que saldría con una sola falta encima es nada.
    saldrian = [] if por_que_no else [asi.nombre_de_movimiento(m) for m in movimientos]
    return {
        "libro": {"ruc": libro.ruc, "periodo": libro.periodo, "tipo": libro.tipo},
        "driver": driver,
        "listo_para_exportar": not por_que_no,
        "por_que_no": por_que_no,
        "que_falta": [{"motivo": clave, "texto": FALTAS_DEL_DINERO[clave][0], "movimientos": cuales,
                       "pedir_a": PEDIR_A[clave]} for clave, cuales in hay],
        "errores_de_configuracion": [],
        # Las relecturas se cuentan porque el mes las trae y el asiento no las lleva: `preparar_tesoreria` descarta
        # el movimiento repetido —bajar dos veces el mismo extracto es lo normal— y callarlo dejaría una resta que
        # nadie puede explicar. Es la misma cuenta que hace el resumen de la exportación.
        "totales": {"movimientos": len(crudos), "repetidos": len(crudos) - len(movimientos),
                    "saldrian": len(saldrian)},
        "faltantes": faltan,
        "saldrian": saldrian,
    }


def _sin_mirar_el_dinero(libro: Libro, driver: str, crudos: list, por_que_no: list[str], que_falta: list[dict],
                         errores: list[str] | None = None) -> dict:
    """La respuesta de un mes de tesorería del que no se ha mirado ni un movimiento, con su razón.

    Lo que `_libro_que_el_destino_no_lleva` y `_sin_configuracion` son en el otro camino, en uno solo porque aquí
    las dos razones —y la de un mes vacío— dicen lo mismo de los contadores: las filas que el documento trae se
    cuentan, porque contarlas no es mirarlas, y lo demás va en cero porque de verdad no se comprobó."""
    return {
        "libro": {"ruc": libro.ruc, "periodo": libro.periodo, "tipo": libro.tipo},
        "driver": driver,
        "listo_para_exportar": False,
        "por_que_no": por_que_no,
        "que_falta": que_falta,
        "errores_de_configuracion": list(errores or []),
        "totales": {"movimientos": len(crudos), "repetidos": 0, "saldrian": 0},
        "faltantes": {},
        "saldrian": [],
    }


def diagnosticar(doc: dict, *, driver: str, configuracion: dict | None = None, correlativos: dict | None = None,
                 imputacion: dict | None = None, claves_previas: Any = None) -> dict:
    """Todo lo que hay que mirar de un mes ANTES de exportarlo, en una sola respuesta.

    Pura y sin estado. **No lanza** por lo que le falte al mes: lo describe. Tampoco por una configuración que no se
    puede aplicar: la dice en `errores_de_configuracion`. Solo rechaza un documento que no es un documento (sin
    `libro`, o comprobantes ilegibles).
    """
    libro = libro_de(doc)
    modulo = drivers.obtener(driver)
    # **El dispatch por origen, igual que en `armado.generar_asiento` y en `salida.exportar_archivo`**: una sola vez
    # por puerta y ni un `if es_tesoreria` más adentro. Va lo primero porque de él depende QUÉ se mira y, por tanto,
    # qué forma tiene la respuesta: un libro de tesorería no tiene comprobantes que contar (12.12). Por tabla y no
    # por un `if` desde la 13.1.
    return CAMINOS_DEL_DIAGNOSTICO[libro.rasgos.origen](
        doc, libro, modulo, driver, configuracion=configuracion, correlativos=correlativos,
        imputacion=imputacion, claves_previas=claves_previas)


def _del_registro(doc: dict, libro: Libro, modulo: Any, driver: str, *, configuracion: dict | None,
                  correlativos: dict | None, imputacion: dict | None, claves_previas: Any) -> dict:
    """Lo que hay que mirar de un libro que sale de sus comprobantes: una compra, una venta."""
    todos = comprobantes_de(doc)
    previas = claves_previas_de(claves_previas)
    opciones = getattr(modulo, "OPCIONES", None)

    def _serie_numero(c: Comprobante) -> str:
        # Como en la línea del asiento de ese destino (hito 0.8): el mismo comprobante se nombra igual en los dos.
        return asi.serie_numero_de(c, opciones)

    # Lo que ESE destino exige (`contrato.exige`): decide qué faltante deja el mes «no listo». El CSV
    # no exige centro ni moneda con código; CONCAR, los dos; el SIRE, nada de esto.
    exige = contrato.exige(modulo)
    # Antes que nada: si ese destino no lleva este tipo de libro, no hay nada que diagnosticar y lo que se dice es
    # eso. Iba sin comprobarse, así que un libro de tesorería contra CONCAR contestaba «no hay comprobantes que
    # exportar» —cierto y engañoso: no es que falten, es que ese destino no lleva ese libro—. `exportar` lo
    # corrigió en la 9.1 comprobándolo antes de preparar; aquí **no se lanza**, porque esta operación describe y no
    # exige (su docstring: «No lanza por lo que le falte al mes: lo describe»).
    if libro.tipo not in getattr(modulo, "FORMATOS", {}):
        return _libro_que_el_destino_no_lleva(libro, driver, exige, todos, modulo)
    errores = errores_de_configuracion(configuracion)
    if errores:
        return _sin_configuracion(libro, driver, exige, todos, errores)
    config = con_imputacion(config_aplicada(configuracion, driver), imputacion_del_documento(doc, imputacion, todos), todos)
    detracciones.normalizar(todos, config)
    validar.revisar(todos, libro, previas, config=config)
    rasgos = libro.rasgos

    excluidos = [c for c in todos if c.excluida]
    fuera = fuera_de([c for c in todos if not c.excluida], getattr(modulo, "EXCLUYE_TIPOS", None))
    candidatos = [c for c in todos if not c.excluida and c not in fuera]
    con_error = [c for c in candidatos if c.tiene_errores]
    con_aviso = [c for c in candidatos if c.observaciones and not c.tiene_errores]
    # Los que no llevan asiento porque no mueven dinero (`asiento.sin_efecto_contable`): siguen en el registro, pero no
    # se les pide cuenta ni centro. Se cuentan para que una pantalla pueda decir «3 dados de baja» en vez de callarlos.
    sin_asiento = [c for c in candidatos if c not in asi.con_efecto_contable(candidatos, config)]

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
    codigos = ("sin_sigla", "sin_codigo_de_moneda", "sin_denominacion")   # se dicen por su código, no por comprobante
    faltantes: dict[str, Any] = {clave: cuales if clave in codigos else [_serie_numero(c) for c in cuales]
                                 for clave, cuales in asi.faltantes_para(candidatos, config, rasgos, mirar).items()}
    if contrato.lleva_cuentas(modulo) and callable(getattr(modulo, "no_caben", None)):
        faltantes["no_cabe"] = {motivo: [_serie_numero(c) for c in lista] for motivo, lista
                                in contrato.no_caben(modulo, libro, candidatos, config).items()}
    sub_diarios: dict[str, Any] = {}
    if legacy:
        con_equivalencia = [c for c in candidatos if c.tipo_cp not in faltantes["sin_sigla"]]
        presentes = asi.sub_diarios_presentes(con_equivalencia, config, rasgos)
        corr = asi.correlativos_de_partida(con_equivalencia, config, rasgos, correlativos)
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
    # Y la contradicción entre «anulada» y «su detracción ya se depositó» bloquea SIEMPRE, sea lo que sea que el
    # destino exija: no es un requisito de un formato, son dos hechos del documento que no pueden ser los dos
    # verdaderos. Una factura marcada como anulada deja de provisionar su detracción en el núcleo, para cualquier
    # driver, así que la contradicción tiene que pararse para cualquier driver.
    if faltantes.get(SIN_REQUISITO_QUE_BLOQUEA):
        por_que_no.append(f"{len(faltantes[SIN_REQUISITO_QUE_BLOQUEA])} {FALTA[SIN_REQUISITO_QUE_BLOQUEA].texto}")

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
    donde = CUBOS_DE_LA_DETRACCION
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
        # `sin_efecto_contable` (3.5.0) es su propia casilla y no se suma a `fuera_del_destino`, que significa otra
        # cosa: «este destino no lleva ese tipo de comprobante». Estos sí salen en el registro —el correlativo de SUNAT
        # los necesita—; lo que no tienen es asiento, así que no piden cuenta ni gastan vóucher. Con
        # `asentar_sin_efecto_contable` encendido la casilla se queda en 0, porque entonces sí se asientan.
        "totales": {"comprobantes": len(todos), "saldrian": len(saldrian), "excluidos": len(excluidos),
                    "fuera_del_destino": len(fuera), "sin_efecto_contable": len(sin_asiento),
                    "con_error": len(con_error), "con_aviso": len(con_aviso)},
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


# **Qué se mira en un libro, dicho por la tabla** (13.1), igual que `armado.CAMINOS_DEL_ASIENTO` y
# `salida.CAMINOS_DEL_ARCHIVO`. Aquí el despacho decide además **la forma de la respuesta**, que desde la 13.0 es
# un `oneOf` de dos: por eso era el `if` más caro de los tres y el que más se nota al quitarlo.
CAMINOS_DEL_DIAGNOSTICO = {"comprobantes": _del_registro, "movimientos": _del_dinero}
