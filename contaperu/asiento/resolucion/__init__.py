"""Lo que el asiento necesita saber antes de armarse: configuración efectiva, clasificación de
cada comprobante (sigla, sub-diario, cuentas) y numeración por sub-diario. Las reglas de negocio y
su porqué, en el docstring del paquete (`asiento/__init__.py`).

Las líneas de la partida doble se arman en `motor.py`, en el vocabulario neutral de `open-accounting`;
las columnas de CONCAR, en su driver (`drivers/concar/proyeccion.py`).

Eran 539 líneas con cinco cosas dentro, y desde la 6.5.0 cada una tiene su fichero: lo que dice la
configuración (`configurado`), lo que dice la imputación de cada documento (`imputado`), qué es cada comprobante
(`clasificacion`), qué le falta para un destino que lo exige (`requisitos`) y su numeración (`numeracion`).
Tres de los cortes son los que el propio fichero ya marcaba con sus comentarios de sección; el cuarto parte
«Clasificación», que mezclaba describir un comprobante con decidir que algo le falta. **Lo que se importa no
cambió**: aquí se reexportan los mismos nombres.
"""
from __future__ import annotations

from .configurado import (cuenta_honorarios, cuenta_por_pagar, cuenta_por_pagar_detraccion, etiquetas_sub_diario,
                          fundir_config)
from .imputado import cuenta_tercero, imputacion_de, partes_de
from .clasificacion import (anulada_por_nota, asienta_sin_efecto, con_efecto_contable, con_reparto,
                            correlativos_de_partida, cuentas_del_asiento,
                            equivalencia_tipo, lleva_centro, reparto_no_cuadra,
                            sigla_de_tipo, sigla_documento, sin_efecto_contable,
                            sub_diario, sub_diarios_presentes, tiene_detraccion)
from .requisitos import (comprobantes_anulados_con_deposito, comprobantes_sin_centro, comprobantes_sin_clase,
                         comprobantes_sin_codigo_detraccion, comprobantes_sin_cuenta,
                         cuentas_sin_denominacion, exigir_requisitos, faltantes_para,
                         monedas_sin_codigo, repartos_que_no_cuadran, tipos_sin_sigla)
from .numeracion import limites_del_periodo, numerar, numerar_en_orden

__all__ = ["anulada_por_nota", "asienta_sin_efecto", "comprobantes_anulados_con_deposito", "comprobantes_sin_centro",
           "comprobantes_sin_clase", "comprobantes_sin_codigo_detraccion", "comprobantes_sin_cuenta",
           "con_efecto_contable", "con_reparto", "correlativos_de_partida", "cuenta_honorarios", "cuenta_por_pagar",
           "cuenta_por_pagar_detraccion", "cuenta_tercero", "cuentas_del_asiento", "cuentas_sin_denominacion",
           "equivalencia_tipo", "etiquetas_sub_diario", "exigir_requisitos", "faltantes_para", "fundir_config",
           "imputacion_de", "limites_del_periodo", "lleva_centro", "monedas_sin_codigo", "numerar",
           "numerar_en_orden", "partes_de", "reparto_no_cuadra", "repartos_que_no_cuadran", "sigla_de_tipo",
           "sigla_documento", "sin_efecto_contable", "sub_diario", "sub_diarios_presentes", "tiene_detraccion",
           "tipos_sin_sigla"]
