"""Los pasos de un mes, en el orden en que se dan: revisar, normalizar las detracciones y preparar lo que un
driver necesita.

Cada uno recibe un documento del estándar y devuelve otro: así se pueden dar de uno en uno, repetir, o saltarse
el que no haga falta. `preparar` es el que juntan `generar_asiento` y `exportar`, y por eso vive aquí y no en
cada uno.
"""
from __future__ import annotations

from typing import Any

from ... import drivers
from ...errores import DocumentoInvalido
from ...modelo import Comprobante, Libro
from ...tributos import detracciones, validar
from .configuracion import con_imputacion, config_aplicada, imputacion_del_documento
from .documento import comprobantes_de, documento, libro_de, serie_numero
from .entradas import claves_previas_de

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
    # **Se ASIGNA**, y hasta la 5.3.1 no se hacía: el valor de retorno se tiraba, así que por esta ruta la
    # configuración se quedaba sin `imputaciones` mientras que la de `diagnosticar` sí las lleva. Las dos veían
    # documentos distintos. No se notaba porque nada de lo que corre después la miraba; el aviso de la factura
    # anulada sí, y la marca vive justo ahí.
    config = con_imputacion(config, imputacion_del_documento(doc, imputacion, comprobantes), comprobantes)
    limpiadas = detracciones.normalizar(comprobantes, config)
    validar.revisar(comprobantes, libro, previas, config=config)
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


def _los_que_van(comprobantes: list[Comprobante], driver: str) -> list[Comprobante]:
    """De los que no se excluyeron, los que ESE destino lleva de verdad: sin los tipos que descarta por su formato.

    Es la misma regla que aplica el driver al generar (`seleccion.fuera_de`), traída aquí para decidir qué puede
    bloquear una exportación. Sin `driver` —o con uno que no existe— no se descarta nada: no hay destino que opine."""
    if not driver or driver not in drivers.DRIVERS:
        return comprobantes
    tipos = getattr(drivers.obtener(driver), "EXCLUYE_TIPOS", None)
    return [c for c in comprobantes if c.tipo_cp not in (tipos or frozenset())]


def preparar(doc: dict, configuracion: dict | None, incluir_observados: bool, imputacion: dict | None = None,
             driver: str = "", claves_previas: Any = None) -> tuple[Libro, list[Comprobante], dict]:
    """El libro, **todos** los comprobantes del documento —revisados— y la configuración aplicada hacia `driver` con
    la imputación dentro. Sin `incluir_observados`, un comprobante con observaciones que bloquean detiene todo.

    **Devuelve todos, incluidos los excluidos y los duplicados**, y quien llama vuelve a seleccionar: lo hacen los
    dos (`salida.generar` y `armado.generar_asiento`), porque el resumen de una exportación **cuenta** lo que se dejó
    fuera. Hasta la 1.2.0 se filtraban aquí, y entonces `exportar_archivo` devolvía `resumen.excluidos` siempre en 0
    mientras la ruta de la 0.x lo contaba bien: el mismo documento, dos respuestas según la puerta.

    **Y lo que bloquea se mira sobre lo que ESE destino lleva de verdad.** Un error en un comprobante que el driver
    descarta por su tipo (`EXCLUYE_TIPOS`) no puede impedir el archivo: el recibo por honorarios no va en el TXT del
    SIRE, así que su retención mal puesta no tiene por qué impedir declarar a SUNAT. Hasta la 1.2.0 se miraba antes
    de aplicar esa regla, así que por la API pública sí lo impedía — otra vez, distinto según la puerta.

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
    config = con_imputacion(config_aplicada(configuracion, driver), imputacion_del_documento(doc, imputacion, todos), todos)
    detracciones.normalizar(todos, config)
    validar.revisar(comprobantes, libro, previas, config=config)
    if not incluir_observados:
        con_error = [c for c in _los_que_van(comprobantes, driver) if c.tiene_errores]
        if con_error:
            raise DocumentoInvalido(
                f"{len(con_error)} comprobantes tienen observaciones que bloquean. "
                "Corrígelos, o pide `incluir_observados` si sabes lo que haces.")
    return libro, todos, config
