"""La configuración con la que se genera hacia un destino, y la imputación de cada documento.

Dos cosas que llegan **por parámetro** y nunca de un fichero: la configuración contable del contribuyente —lo
general, lo del asiento y lo del sistema de destino, fundidas en este orden— y lo que alguien decidió para cada
comprobante, que llega aparte y se enlaza por `id_externo`.
"""
from __future__ import annotations

from collections import Counter

from ... import asiento as asi
from ... import configuracion as _declaracion
from ... import drivers
from ...configuracion import CLAVES_RETIRADAS, CONFIG_POR_DEFECTO, CONFIGURACION_GENERAL, ConfiguracionInvalida
from ...errores import DocumentoInvalido
from ...modelo import Comprobante

# --- configuración -----------------------------------------------------------------

def errores_de_configuracion(configuracion: dict | None) -> list[str]:
    """Lo que la configuración no cumple, un error por línea con su ruta; lista vacía = se puede aplicar.

    Se valida entera: lo general contra lo que declara el motor y cada sección contra lo que declara su driver, también
    la de un sistema al que hoy no se exporta, porque una clave mal escrita ahí se descubriría el día que se use. Una
    clave de un sistema puesta en la raíz —la forma plana de antes del 13-sep-2026— dice a qué sección va, y una
    retirada, qué la reemplaza."""
    if configuracion is None:
        return []
    if not isinstance(configuracion, dict):
        return _declaracion.validar(configuracion, CONFIGURACION_GENERAL)
    generales = [c.clave for c in CONFIGURACION_GENERAL]
    # Una sección es de un sistema que lleva cuentas y declara algo que configurar: un driver neutral como
    # `asiento_contable` lleva cuentas y no tiene nada suyo, solo lo general.
    sistemas = {nombre: modulo for nombre, modulo in drivers.DRIVERS.items() if drivers.contrato.lleva_cuentas(modulo)
                and (drivers.contrato.configuracion(modulo) or drivers.contrato.columnas_elegibles(modulo))}
    va_en: dict[str, list[str]] = {}
    for nombre, modulo in sistemas.items():
        for campo in drivers.contrato.configuracion(modulo):
            va_en.setdefault(campo.clave, []).append(nombre)
        if drivers.contrato.columnas_elegibles(modulo):
            va_en.setdefault("columnas", []).append(nombre)
    errores: list[str] = []
    for clave, valor in configuracion.items():
        if clave in generales:
            errores += _declaracion.validar({clave: valor}, CONFIGURACION_GENERAL)
        elif clave in sistemas:
            errores += _declaracion.validar(valor, drivers.contrato.configuracion(sistemas[clave]),
                                            drivers.contrato.columnas_elegibles(sistemas[clave]), donde=clave)
        elif clave in CLAVES_RETIRADAS:
            errores.append(f"`{clave}` ya no existe: es {CLAVES_RETIRADAS[clave]}")
        elif clave in va_en:
            errores.append(f"`{clave}` va dentro de la sección de su sistema ({' o '.join(va_en[clave])}), "
                           "no en la raíz")
        elif clave == "imputaciones":
            errores.append("`imputaciones` no va en la configuración: la imputación de cada documento llega en el "
                           "bloque `imputaciones` del documento o en el argumento `imputacion`")
        elif clave in drivers.DRIVERS and drivers.contrato.lleva_cuentas(drivers.DRIVERS[clave]):
            errores.append(f"`{clave}` no tiene sección: ese sistema no tiene nada propio que configurar, solo lo general")
        elif clave in drivers.DRIVERS:
            errores.append(f"`{clave}` no tiene sección: ese sistema no lleva cuentas y no se configura")
        else:
            errores.append(f"`{clave}`: clave desconocida; en la raíz va lo general ({', '.join(generales)}) y una "
                           f"sección por sistema ({', '.join(sistemas)})")
    return errores


def config_aplicada(configuracion: dict | None = None, driver: str = "") -> dict:
    """La configuración con la que se genera hacia `driver`: lo general con sus valores por defecto debajo, y encima la
    sección de ese sistema con los suyos, todo plano, como lo lee el núcleo. Sin `driver` —o con uno que no lleva
    cuentas, como el SIRE—, solo lo general.

    **Las cuentas se apilan en tres capas**, y el orden es lo que hace que esto funcione: las de fábrica del PCGE,
    encima las que declare el sistema al que se exporta (`contrato.cuentas_por_defecto`, 2.5) y encima del todo las
    que la empresa guardó. Así un sistema que numera a ocho dígitos no escribe una cuenta de seis en su archivo
    **aunque la empresa nunca haya abierto la pantalla de configuración**, que es justo cuando pasaba: lo que falta se
    rellena solo, y hasta la 2.5 se rellenaba con la de CONCAR. Y la empresa sigue mandando sobre las dos.

    Se guarda con lo general en la raíz y una sección por sistema (John, 13-sep-2026): `{"cuentas": {...},
    "concar": {"tipos": {...}, "columnas": {...}}, "contasis": {"medio_pago": "003"}}`, fundida en profundidad sobre
    los valores por defecto (una empresa puede cambiar solo `cuentas.cxp.USD` y hereda el resto). Se valida entera
    (`errores_de_configuracion`) y un error la detiene con `ConfiguracionInvalida`: una clave que nadie lee exportaría
    con el valor de fábrica sin avisar. Lo que devuelve es para generar; la forma que se guarda, con sus valores por
    defecto, la da `configuracion_por_defecto`."""
    errores = errores_de_configuracion(configuracion)
    if errores:
        raise ConfiguracionInvalida(errores)
    guardada = configuracion or {}
    general = {k: v for k, v in guardada.items() if k not in drivers.DRIVERS}
    if not driver:
        return asi.fundir_config(CONFIG_POR_DEFECTO, general)
    modulo = drivers.obtener(driver)
    de_fabrica = asi.fundir_config(CONFIG_POR_DEFECTO,
                                   {"cuentas": drivers.contrato.cuentas_por_defecto(modulo)})
    aplicada = asi.fundir_config(de_fabrica, general)
    return {**aplicada, **asi.fundir_config(drivers.contrato.seccion_por_defecto(modulo), guardada.get(driver) or {})}


def configuracion_por_defecto(driver: str = "") -> dict:
    """La configuración de partida en la forma en que se guarda: lo general y la sección de cada sistema que se
    configura, con sus valores por defecto. Se puede cambiar y volver a pasar tal cual.

    **Con `driver`, la de quien lleva ESE sistema**: lo general con las cuentas de ese sistema y solo su sección, igual
    que `describir_configuracion`. Es con lo que una aplicación siembra una empresa nueva, y por eso el parámetro
    existe: sembrar la de todos daba a un contribuyente de STARSOFT las cuentas de CONCAR."""
    if driver:
        modulo = drivers.obtener(driver)
        salida = asi.fundir_config(CONFIG_POR_DEFECTO, {"cuentas": drivers.contrato.cuentas_por_defecto(modulo)})
        seccion = drivers.contrato.seccion_por_defecto(modulo)
        if seccion:
            salida[driver] = seccion
        return salida
    salida = asi.fundir_config(CONFIG_POR_DEFECTO, {})
    for nombre, modulo in drivers.DRIVERS.items():
        seccion = drivers.contrato.seccion_por_defecto(modulo)
        if seccion:
            salida[nombre] = seccion
    return salida


def describir_configuracion(driver: str = "") -> dict:
    """Qué se configura, en JSON: lo general y, por cada sistema que se configura, sus campos —tipo, valor por defecto,
    patrón, título y ayuda— y en qué columnas de su archivo puede ir cada dato. Es lo que una aplicación construida
    con el motor le pide para pintar su pantalla de configuración, en vez de copiarla. Con `driver`, lo general y solo
    la sección de ese sistema."""
    general = _declaracion.describir(CONFIGURACION_GENERAL)
    if driver:
        return {"general": general, **drivers.contrato.describir(drivers.obtener(driver))}
    return {"general": general,
            "sistemas": {nombre: drivers.contrato.describir(modulo) for nombre, modulo in drivers.DRIVERS.items()
                         if drivers.contrato.seccion_por_defecto(modulo)}}


def imputacion_del_documento(doc: dict, imputacion: dict | None,
                             comprobantes: list[Comprobante]) -> dict | None:
    """La imputación que hay que usar: la del bloque `imputaciones` del documento, o la del argumento.

    Desde la 1.0 la imputación viaja DENTRO del documento (John, 18-sep-2026), para que un archivo guardado
    explique su propio asiento; el argumento se conserva para quien ya integraba así. **Las dos a la vez se
    rechazan**: adivinar cuál manda sería elegir en silencio la cuenta de un comprobante.

    Y cuando viene del documento se exige lo que el esquema exige —cada comprobante con su `id_externo`— más lo que
    el esquema no puede decir: que ningún `id_externo` esté repetido, porque entonces la llave deja de ser una llave.
    **Las dos comprobaciones valen solo por esta vía**, a propósito: por el argumento se puede imputar 3 de 10
    comprobantes y que los otros 7 no traigan id, y exigirlo ahí sería cambiar en silencio lo que ya funciona.
    Es la única asimetría entre las dos vías."""
    del_documento = (doc or {}).get("imputaciones") if isinstance(doc, dict) else None
    if del_documento and imputacion:
        raise DocumentoInvalido("La imputación llega dos veces: en `imputaciones` del documento y en el argumento "
                                "`imputacion`. Manda una sola.")
    if del_documento is not None and not isinstance(del_documento, dict):
        raise DocumentoInvalido("`imputaciones` del documento es un objeto: {id_externo: {cuenta_contable, "
                                "centro_costo, cuenta_tercero, reparto}}.")
    if del_documento:
        ids = [(c.id_externo or "").strip() for c in comprobantes]
        sin_id = [f"{c.tipo_cp} {c.serie}-{c.numero}" for c in comprobantes if not (c.id_externo or "").strip()]
        if sin_id:
            raise DocumentoInvalido("Con `imputaciones` en el documento, cada comprobante necesita su `id_externo`, "
                                    "que es la llave con la que se casan. Sin él: " + ", ".join(sin_id) + ".")
        repetidos = sorted(i for i, veces in Counter(ids).items() if veces > 1)
        if repetidos:
            raise DocumentoInvalido("Dos comprobantes comparten `id_externo`, que es la llave de la imputación: "
                                    + ", ".join(repetidos) + ".")
    return del_documento or imputacion


def con_imputacion(config: dict, imputacion: dict | None, comprobantes: list[Comprobante]) -> dict:
    """La imputación de cada documento se lee aquí, al preparar, para que un error de forma se diga con su motivo, y
    se le entrega al núcleo dentro de la configuración, que es lo que ya recibe todo el asiento. Llega por el bloque
    `imputaciones` del documento o por el argumento (`imputacion_del_documento`).

    Una imputación cuyo `id_externo` no es de ningún documento se rechaza: una llave mal escrita haría salir ese
    documento con la cuenta por defecto, sin error y sin aviso. Lo que se exige de más cuando la imputación viene
    dentro del documento está en `imputacion_del_documento`."""
    if not imputacion:
        return config
    if not isinstance(imputacion, dict):
        raise DocumentoInvalido("`imputacion` es un objeto: {id_externo: {cuenta_contable, centro_costo, "
                                "cuenta_tercero, reparto}}.")
    try:
        leida = {str(k): asi.Imputacion.de(v) for k, v in imputacion.items()}
    except ValueError as e:
        raise DocumentoInvalido(f"Una imputación no se pudo leer: {e}") from None
    ids = Counter((c.id_externo or "").strip() for c in comprobantes)
    huerfanas = sorted(set(leida) - set(ids))
    if huerfanas:
        raise DocumentoInvalido("La imputación habla de documentos que no están (id_externo): "
                                + ", ".join(huerfanas) + ".")
    # Una llave que nombra a DOS comprobantes aplicaría la misma cuenta a los dos, y cada línea saldría con un
    # `documento.id_externo` que no distingue de cuál es. Se comprueba por las dos vías —aquí— porque el daño es el
    # mismo: por la vía del documento se exige además que NINGÚN id se repita, aunque no lo nombre la imputación
    # (`imputacion_del_documento`), que es lo que el esquema pide con su condicional.
    repetidas = sorted(llave for llave in leida if ids[llave] > 1)
    if repetidas:
        raise DocumentoInvalido("La imputación nombra un `id_externo` que comparten dos comprobantes, así que la misma "
                                "cuenta se aplicaría a los dos: " + ", ".join(repetidas) + ".")
    return {**config, "imputaciones": leida}


