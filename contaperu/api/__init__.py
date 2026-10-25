"""La API pública de ContaPerú: lo que una aplicación usa, estable durante toda la 14.x.

    from contaperu import api

    diagnostico = api.diagnosticar(documento, driver="concar", configuracion=config, imputacion=imputacion)
    if diagnostico["listo_para_exportar"]:
        resultado = api.exportar(documento, driver="concar", configuracion=config, imputacion=imputacion)

Documento `open-accounting` entra, diccionario sale; el documento va primero y todo lo demás por su nombre. Lo que está
en `__all__` sigue su firma hasta la 15.0 (`tests/test_superficie_publica.py`): en una versión menor pueden llegar
parámetros opcionales, claves nuevas en las respuestas y anotaciones `_*`, nunca quitarse.

Debajo de la API está el nivel de extensión —`modelo`, `asiento`, `drivers.contrato`…—, para quien escribe un driver o
trabaja con los objetos del modelo. `pipeline` y `puertas` son internos.
"""
from __future__ import annotations

from .._obsoleto import RutaObsoleta
from .._version import OPEN_ACCOUNTING, __version__
from ..asiento.faltas import FALTAS
from ..modelo import Comprobante, Libro, Observacion, rasgos_de, serie_y_numero
from ..pipeline.preparacion import MAXIMO_CLAVES_PREVIAS, MAXIMO_COMPROBANTES
from ..pipeline.salida import Exportado
from ..pipeline.seleccion import errores_de, fuera_de, seleccionar
from .documento import documento_de
from .instrucciones import CAMINO, INSTRUCCIONES, PRESENTACION, REGLAS
from .errores import (CampoCambiaDeSigno, ConfiguracionInvalida, CorrelativoDesborda, Descuadre, DocumentoInvalido, ErrorContaperu,
                      ErroresBloqueantes, IgvImposible, NoCabe, NoExportable, RepartoNoAdmitido, RepartoNoCuadra,
                      SinCentro, SinCodigoDeMoneda, SinCodigoDetraccion, SinCorrelativo, SinCuenta, SinSigla,
                      SireInvalido, TablaInvalida,
                      TotalImposible, XmlInvalido, problema)
from .operaciones import (adaptar_pcge, buscar_cuenta_pcge, campos_del_ple, campos_del_sire, catalogo_pcge, catalogos_api_sire, catalogos_del_estandar, catalogos_sunat, comparar_sire,
                          campos_del_comprobante, config_aplicada, cronogramas_de_vencimiento, cuadrar,
                          revisar_tesoreria, validar_cuentas_bancarias,
                          estado_de_cuenta, por_cuenta, regimenes_tributarios, resumen,
                          describir_configuracion, diagnosticar, drivers_disponibles, errores_de_configuracion,
                          esquema_diagnostico, esquema_open_accounting, exportar, exportar_archivo, generar_asiento, leer_archivos,
                          leer_propuesta_sire, leer_xml, normalizar_detracciones, revisar, configuracion_por_defecto, contrato_openconta,
                          verificar_documento, verificar_driver)
from .tabla import OPERACIONES, Operacion

__all__ = [
    # Los rasgos de un tipo de libro, que es como una puerta sabe POR DÓNDE entra un libro sin adivinarlo por una
    # clave de la respuesta. `puertas` solo puede importar `api` (`tests/test_frontera.py`), así que hasta la 13.1
    # la consola miraba si `totales` traía `movimientos` — un dato de la forma para deducir un hecho del libro.
    "rasgos_de",
    # operaciones
    "leer_xml", "leer_propuesta_sire", "leer_archivos", "documento_de", "revisar", "normalizar_detracciones",
    "diagnosticar", "generar_asiento", "exportar", "exportar_archivo", "cuadrar", "buscar_cuenta_pcge", "adaptar_pcge",
    "resumen", "por_cuenta", "estado_de_cuenta", "campos_del_comprobante", "revisar_tesoreria",
    "validar_cuentas_bancarias",
    "configuracion_por_defecto", "describir_configuracion", "config_aplicada", "errores_de_configuracion",
    "drivers_disponibles",
    "catalogos_sunat",
    "catalogos_api_sire", "campos_del_ple", "campos_del_sire", "catalogo_pcge", "catalogos_del_estandar", "esquema_open_accounting", "esquema_diagnostico", "comparar_sire",
    "regimenes_tributarios", "cronogramas_de_vencimiento",
    "contrato_openconta", "verificar_documento", "verificar_driver",
    # la tabla que exponen las puertas
    "OPERACIONES", "Operacion",
    # lo que se le dice a un agente: las REGLAS del dominio, que no nombran ninguna herramienta, y el
    # texto entero de este servidor. Quien monta su propia capa de agente se trae `REGLAS`.
    "REGLAS", "CAMINO", "PRESENTACION", "INSTRUCCIONES",
    # QUÉ SALE EN EL ARCHIVO, antes de generarlo (14.2.0). Quien integra el motor tiene que poder decirle a
    # su contador cuántos comprobantes van a entrar, cuáles quedan fuera porque ese destino no lleva su tipo
    # —el recibo por honorarios no va al TXT del SIRE— y cuáles lo bloquean, y tiene que poder decirlo ANTES
    # de generar. Hasta la 14.1 esa respuesta solo existía dentro de `pipeline`, que es interno por contrato,
    # así que la única salida era reimplementarla: la app en producción lo hizo, y su copia se apartó de ésta
    # sin que nadie lo notara. Dos códigos respondiendo «¿qué sale?» es lo que hace que una pantalla prometa
    # un número y el archivo traiga otro.
    #
    # `etiqueta`, que vive en el mismo módulo, NO se publica: no decide nada —da formato a un nombre— y su
    # dependencia, `serie_y_numero`, ya está aquí desde siempre.
    "seleccionar", "fuera_de", "errores_de",
    # lo que devuelve o recibe
    "Exportado", "Comprobante", "Libro", "Observacion", "FALTAS", "serie_y_numero", "MAXIMO_COMPROBANTES",
    "MAXIMO_CLAVES_PREVIAS",
    # errores
    "ErrorContaperu", "DocumentoInvalido", "ConfiguracionInvalida", "ErroresBloqueantes", "NoExportable", "NoCabe",
    "SinCuenta", "SinCentro", "SinCodigoDetraccion", "SinSigla", "SinCodigoDeMoneda", "SinCorrelativo",
    "RepartoNoCuadra",
    "RepartoNoAdmitido", "CorrelativoDesborda", "CampoCambiaDeSigno", "Descuadre", "XmlInvalido", "SireInvalido", "IgvImposible",
    "TotalImposible", "TablaInvalida", "problema",
    # versiones y avisos
    "RutaObsoleta", "OPEN_ACCOUNTING", "__version__",
]
