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
from .documento import (MAXIMO_APLICACIONES, MAXIMO_COMPROBANTES, MAXIMO_MOVIMIENTOS, aplicaciones_de,
                        comprobantes_de, documento, extractos_de,
                        imputaciones_de_movimientos_de, libro_de, movimientos_de, lineas_de, serie_numero,
                        version_del_documento)
from .entradas import (MAXIMO_CLAVES_PREVIAS, MAXIMO_PARTIDAS_PREVIAS, bytes_de, claves_previas_de,
                       fecha_de, partidas_previas_de)
from .pasos import normalizar_detracciones, preparar, preparar_tesoreria, revisar

__all__ = ["MAXIMO_APLICACIONES", "MAXIMO_CLAVES_PREVIAS", "MAXIMO_COMPROBANTES", "MAXIMO_MOVIMIENTOS",
           "MAXIMO_PARTIDAS_PREVIAS", "partidas_previas_de",
           "aplicaciones_de", "bytes_de",
           "claves_previas_de", "comprobantes_de", "extractos_de", "imputaciones_de_movimientos_de",
           "movimientos_de",
           "config_aplicada", "configuracion_por_defecto", "con_imputacion", "describir_configuracion",
           "documento", "errores_de_configuracion", "fecha_de", "imputacion_del_documento", "libro_de",
           "lineas_de", "normalizar_detracciones", "preparar", "preparar_tesoreria", "revisar", "serie_numero",
           "version_del_documento"]
