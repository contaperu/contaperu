"""Preparar un documento: del diccionario del estándar al libro y los comprobantes del modelo, la configuración con la
que se genera hacia un destino y la imputación de cada documento.

Todo es puro: no lee disco, no sale a la red, no guarda nada. Los documentos son los del estándar (`estandar/LEEME.md`);
la configuración contable del contribuyente y la imputación de cada documento entran por parámetro.

Era un fichero de 443 líneas con cuatro cosas dentro —la conversión entre el estándar y el modelo, la
configuración, lo que llega por parámetro y los pasos de un mes—, y desde la 6.5.0 cada una tiene su fichero.
Los cortes son los que el propio fichero ya marcaba con sus comentarios de sección. **Lo que se importa no
cambió**: aquí se reexportan los mismos nombres.
"""
from __future__ import annotations

from .configuracion import (con_imputacion, config_aplicada, configuracion_por_defecto,
                            describir_configuracion, errores_de_configuracion, imputacion_del_documento)
from .documento import (MAXIMO_COMPROBANTES, comprobantes_de, documento, libro_de,
                        lineas_de, serie_numero, version_del_documento)
from .entradas import MAXIMO_CLAVES_PREVIAS, bytes_de, claves_previas_de, fecha_de
from .pasos import normalizar_detracciones, preparar, revisar

__all__ = ["MAXIMO_CLAVES_PREVIAS", "MAXIMO_COMPROBANTES", "bytes_de", "claves_previas_de", "comprobantes_de",
           "config_aplicada", "configuracion_por_defecto", "con_imputacion", "describir_configuracion",
           "documento", "errores_de_configuracion", "fecha_de", "imputacion_del_documento", "libro_de",
           "lineas_de", "normalizar_detracciones", "preparar", "revisar", "serie_numero",
           "version_del_documento"]
