"""Preparar un documento: del diccionario del estándar al libro y los comprobantes del modelo, la configuración con la
que se genera hacia un destino y la imputación de cada documento.

Todo es puro: no lee disco, no sale a la red, no guarda nada. Los documentos son los del estándar (`estandar/LEEME.md`);
la configuración contable del contribuyente y la imputación de cada documento entran por parámetro.
"""
from __future__ import annotations

import base64
from datetime import date
from typing import Any

from .. import asiento as asi
from .. import configuracion as _declaracion
from .. import detracciones, drivers, validar
from .._version import OPEN_ACCOUNTING
from ..configuracion import CLAVES_RETIRADAS, CONFIG_POR_DEFECTO, CONFIGURACION_GENERAL, ConfiguracionInvalida
from ..errores import DocumentoInvalido
from ..modelo import Comprobante, Libro, clave_de, serie_y_numero

# Tope de seguridad. Un mes de una PYME son decenas o cientos de comprobantes; muchos miles en
# una sola llamada es casi siempre un error de quien llama, y conviene decirlo en vez de
# quedarse pensando.
MAXIMO_COMPROBANTES = 5000
# Y el de lo ya anotado en otros periodos: años de un RUC con mucho movimiento caben holgados.
MAXIMO_CLAVES_PREVIAS = 50000


# --- conversión entre el estándar y el modelo --------------------------------------

def libro_de(doc: dict) -> Libro:
    datos = doc.get("libro")
    if not isinstance(datos, dict):
        raise DocumentoInvalido("Falta el bloque `libro`: sin RUC, periodo y tipo no hay contabilidad.")
    try:
        return Libro(ruc=datos.get("ruc", ""), razon_social=datos.get("razon_social", ""),
                     periodo=datos.get("periodo", ""), tipo=datos.get("tipo", ""))
    except ValueError as e:
        raise DocumentoInvalido(str(e)) from None


def comprobantes_de(doc: dict) -> list[Comprobante]:
    crudos = doc.get("comprobantes") or []
    if not isinstance(crudos, list):
        raise DocumentoInvalido("`comprobantes` tiene que ser una lista.")
    if len(crudos) > MAXIMO_COMPROBANTES:
        raise DocumentoInvalido(
            f"{len(crudos)} comprobantes en una sola llamada; el tope es {MAXIMO_COMPROBANTES}. "
            "Divídelo por periodo o por lote.")
    try:
        return [Comprobante.de_dict(c) for c in crudos]
    except (ValueError, TypeError) as e:
        raise DocumentoInvalido(f"Un comprobante no se pudo leer: {e}") from None


def documento(libro: Libro, comprobantes: list[Comprobante] | None = None,
              lineas: list[dict] | None = None, **extra) -> dict:
    """Arma un documento `open-accounting` con lo que se le dé."""
    doc: dict[str, Any] = {
        "open_accounting": OPEN_ACCOUNTING,
        "libro": {"ruc": libro.ruc, "razon_social": libro.razon_social,
                  "periodo": libro.periodo, "tipo": libro.tipo},
    }
    if comprobantes is not None:
        doc["comprobantes"] = [c.a_dict() for c in comprobantes]
    if lineas is not None:
        doc["asiento"] = lineas
    doc.update(extra)
    return doc


def serie_numero(c: Comprobante) -> str:
    return serie_y_numero(c.serie, c.numero)


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
    # `asiento_neutral` lleva cuentas y no tiene nada suyo, solo lo general.
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
            errores.append("`imputaciones` no va en la configuración: la imputación de cada documento llega aparte "
                           "(`imputacion`)")
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
    aplicada = asi.fundir_config(CONFIG_POR_DEFECTO, {k: v for k, v in guardada.items() if k not in drivers.DRIVERS})
    if not driver:
        return aplicada
    modulo = drivers.obtener(driver)
    return {**aplicada, **asi.fundir_config(drivers.contrato.seccion_por_defecto(modulo), guardada.get(driver) or {})}


def configuracion_por_defecto() -> dict:
    """La configuración de partida en la forma en que se guarda: lo general y la sección de cada sistema que se
    configura, con sus valores por defecto. Se puede cambiar y volver a pasar tal cual."""
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


def con_imputacion(config: dict, imputacion: dict | None, comprobantes: list[Comprobante]) -> dict:
    """La imputación de cada documento llega APARTE del documento, por `id_externo` (John, 12-sep-2026: las
    cuentas viven en la aplicación, no en el riel). Se lee aquí, al preparar, para que un error de forma se diga
    con su motivo, y se le entrega al núcleo dentro de la configuración, que es lo que ya recibe todo el asiento.

    Una imputación cuyo `id_externo` no es de ningún documento se rechaza: una llave mal escrita haría salir ese
    documento con la cuenta por defecto, sin error y sin aviso."""
    if not imputacion:
        return config
    if not isinstance(imputacion, dict):
        raise DocumentoInvalido("`imputacion` es un objeto: {id_externo: {cuenta_contable, centro_costo, "
                                "cuenta_tercero, reparto}}.")
    try:
        leida = {str(k): asi.Imputacion.de(v) for k, v in imputacion.items()}
    except ValueError as e:
        raise DocumentoInvalido(f"Una imputación no se pudo leer: {e}") from None
    huerfanas = sorted(set(leida) - {(c.id_externo or "").strip() for c in comprobantes})
    if huerfanas:
        raise DocumentoInvalido("La imputación habla de documentos que no están (id_externo): "
                                + ", ".join(huerfanas) + ".")
    return {**config, "imputaciones": leida}


# --- lo que llega por parámetro ----------------------------------------------------

def claves_previas_de(claves: Any) -> list[tuple[str, str, str, str]]:
    """Lo ya anotado en otros periodos del mismo RUC, como lo compara la validación: cada clave viaja en JSON como
    `[tipo_cp, serie, numero, contraparte_doc]` y se normaliza igual que la del comprobante (`modelo.clave_de`), así que
    «00000123» es «123». En ventas el cliente no cuenta (`estandar/LEEME.md`, «La identidad de un comprobante»)."""
    if claves is None:
        return []
    if isinstance(claves, (str, bytes, dict)) or not isinstance(claves, (list, tuple)):
        raise DocumentoInvalido("`claves_previas` es una lista de [tipo_cp, serie, numero, contraparte_doc].")
    if len(claves) > MAXIMO_CLAVES_PREVIAS:
        raise DocumentoInvalido(f"{len(claves)} claves previas en una sola llamada; el tope es {MAXIMO_CLAVES_PREVIAS}. "
                                "Pasa solo las del RUC y de los periodos en que se pueden repetir.")
    normalizadas = []
    for clave in claves:
        if (not isinstance(clave, (list, tuple)) or len(clave) != 4
                or not all(parte is None or isinstance(parte, (str, int)) for parte in clave)):
            raise DocumentoInvalido(f"Una clave previa no se pudo leer ({clave!r}): es [tipo_cp, serie, numero, "
                                    "contraparte_doc].")
        normalizadas.append(clave_de(*("" if parte is None else str(parte) for parte in clave)))
    return normalizadas


def bytes_de(contenido: str, es_base64: bool) -> bytes:
    if es_base64:
        try:
            return base64.b64decode(contenido, validate=True)
        except Exception as e:
            raise DocumentoInvalido(f"El contenido no es base64 válido: {e}") from None
    return contenido.encode("utf-8")


def fecha_de(fecha: str | None) -> str | None:
    """La fecha de una exportación la pone quien llama —el núcleo no mira el reloj— y solo se
    comprueba que sea una fecha (`AAAA-MM-DD`): es una anotación, no un dato contable."""
    if fecha in (None, ""):
        return None
    try:
        return date.fromisoformat(str(fecha)).isoformat()
    except ValueError:
        raise DocumentoInvalido(f"`fecha` tiene que ser AAAA-MM-DD, no {fecha!r}.") from None


# --- los pasos de un mes -----------------------------------------------------------

def revisar(doc: dict, configuracion: dict | None = None, imputacion: dict | None = None,
            claves_previas: Any = None) -> dict:
    """Aplica las reglas deterministas y devuelve el documento con `estado` y `observaciones` puestos, más un resumen
    de lo que hay que mirar. Con `imputacion`, además comprueba que cada una hable de un documento que está; con
    `claves_previas`, que ningún comprobante esté ya anotado en otro periodo."""
    libro = libro_de(doc)
    comprobantes = comprobantes_de(doc)
    previas = claves_previas_de(claves_previas)
    config = config_aplicada(configuracion)
    con_imputacion(config, imputacion, comprobantes)
    limpiadas = detracciones.normalizar(comprobantes, config)
    validar.revisar(comprobantes, libro, previas)
    errores = [c for c in comprobantes if c.tiene_errores]
    avisos = [c for c in comprobantes if c.observaciones and not c.tiene_errores]
    salida = documento(libro, comprobantes)
    salida["_revision"] = {
        "comprobantes": len(comprobantes),
        "con_error": len(errores),
        "con_aviso": len(avisos),
        "detracciones_descartadas": len(limpiadas),
        "bloqueantes": [
            {"serie_numero": serie_numero(c),
             "observaciones": [o.a_dict() for o in c.observaciones if o.nivel == "error"]}
            for c in errores
        ],
    }
    return salida


def normalizar_detracciones(doc: dict, configuracion: dict | None = None) -> dict:
    """Contrasta la detracción de cada comprobante con la tabla de detracciones —la del motor, con lo que sobreescribe el
    ERP— y deja en blanco la que no reconozca."""
    comprobantes = comprobantes_de(doc)
    config = config_aplicada(configuracion)
    limpiadas = detracciones.normalizar(comprobantes, config)
    salida = documento(libro_de(doc), comprobantes)
    salida["_detracciones"] = {
        "revisadas": sum(1 for c in comprobantes if c.detraccion) + len(limpiadas),
        "descartadas": len(limpiadas),
        "codigos_reconocidos": sorted(detracciones.codigos_de(config)),
    }
    return salida


def preparar(doc: dict, configuracion: dict | None, incluir_observados: bool, imputacion: dict | None = None,
             driver: str = "", claves_previas: Any = None) -> tuple[Libro, list[Comprobante], dict]:
    """El libro, los comprobantes que no se excluyeron —revisados— y la configuración aplicada hacia `driver` con la
    imputación dentro. Sin `incluir_observados`, un comprobante con observaciones que bloquean detiene todo.

    Como `revisar` y `diagnosticar`, deja en blanco la detracción cuyo código no reconoce la tabla (decisión de John,
    15-sep-2026): un mismo documento da la misma respuesta por cualquier operación. Una factura con un código que no
    está pasa al sub-diario de compras en vez del de detracciones, como el caso `detraccion_codigo_sin_tasa` al exportar
    a CONCAR desde la 1.1."""
    libro = libro_de(doc)
    todos = comprobantes_de(doc)
    previas = claves_previas_de(claves_previas)
    comprobantes = [c for c in todos if not c.excluida]
    if not comprobantes:
        raise DocumentoInvalido("No hay comprobantes que procesar.")
    config = con_imputacion(config_aplicada(configuracion, driver), imputacion, todos)
    detracciones.normalizar(todos, config)
    validar.revisar(comprobantes, libro, previas)
    if not incluir_observados:
        con_error = [c for c in comprobantes if c.tiene_errores]
        if con_error:
            raise DocumentoInvalido(
                f"{len(con_error)} comprobantes tienen observaciones que bloquean. "
                "Corrígelos, o pide `incluir_observados` si sabes lo que haces.")
    return libro, comprobantes, config
