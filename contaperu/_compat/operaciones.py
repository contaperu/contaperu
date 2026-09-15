"""`contaperu.operaciones` de la 0.10: las mismas firmas y los mismos valores por defecto, sobre el pipeline de la 1.0.

Se llega aquí por `contaperu.operaciones`, que avisa con `RutaObsoleta`. Lo nuevo es `contaperu.api`: el documento
primero, todo lo demás por su nombre, y `driver` sin valor por defecto.
"""
from __future__ import annotations

from .. import asiento as asi  # noqa: F401  (nombres que la 0.10 dejaba ver)
from .. import configuracion as _declaracion  # noqa: F401
from .. import detracciones, drivers, partida_doble, pcge, validar  # noqa: F401
from .._version import OPEN_ACCOUNTING  # noqa: F401
from ..asiento.faltas import CONTADOR, FALTAS, PROVEEDOR, SISTEMA  # noqa: F401
from ..configuracion import (CLAVES_RETIRADAS, CONFIG_POR_DEFECTO, CONFIGURACION_GENERAL,  # noqa: F401
                             ConfiguracionInvalida)
from ..errores import DocumentoInvalido  # noqa: F401
from ..lectores import archivos as lectura_archivos, sire_txt  # noqa: F401
from ..modelo import Comprobante, Libro, serie_y_numero  # noqa: F401
from ..pipeline import armado, diagnostico, lectura, preparacion, salida
from ..pipeline.diagnostico import PEDIR_A  # noqa: F401
from ..pipeline.preparacion import (MAXIMO_COMPROBANTES, comprobantes_de, con_imputacion,  # noqa: F401
                                    config_aplicada, configuracion_por_defecto, describir_configuracion, documento,
                                    errores_de_configuracion, libro_de)
from . import generar as gen  # noqa: F401


def leer_xml(contenido: str, libro: dict, es_base64: bool = False) -> dict:
    return lectura.leer_xml(contenido, libro, es_base64)


def leer_propuesta_sire(contenido: str, libro: dict, es_base64: bool = False) -> dict:
    return lectura.leer_propuesta_sire(contenido, libro, es_base64)


def revisar(doc: dict, configuracion: dict | None = None) -> dict:
    return preparacion.revisar(doc, configuracion)


def cuadrar(lineas: list[dict]) -> dict:
    return partida_doble.cuadra(lineas).a_dict()


def generar_asiento(doc: dict, configuracion: dict | None = None, correlativos: dict | None = None,
                    incluir_observados: bool = False, imputacion: dict | None = None, driver: str = "concar") -> dict:
    return armado.generar_asiento(doc, driver=driver, configuracion=configuracion, correlativos=correlativos,
                                  incluir_observados=incluir_observados, imputacion=imputacion)


def exportar(doc: dict, driver: str = "concar", configuracion: dict | None = None,
             correlativos: dict | None = None, incluir_observados: bool = False,
             fecha: str | None = None, imputacion: dict | None = None) -> dict:
    return salida.exportar(doc, driver=driver, configuracion=configuracion, correlativos=correlativos,
                           incluir_observados=incluir_observados, fecha=fecha, imputacion=imputacion)


def diagnosticar(doc: dict, configuracion: dict | None = None, correlativos: dict | None = None,
                 driver: str = "concar", imputacion: dict | None = None) -> dict:
    return diagnostico.diagnosticar(doc, driver=driver, configuracion=configuracion, correlativos=correlativos,
                                    imputacion=imputacion)


def adaptar_pcge(lineas: list[dict]) -> dict:
    adaptadas, informe = pcge.adaptar(lineas)
    return {"asiento": adaptadas, "informe": informe.a_dict()}
