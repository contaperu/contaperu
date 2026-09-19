"""La API pública de ContaPerú (1.0): lo que una aplicación usa, estable durante toda la 1.x.

    from contaperu import api

    diagnostico = api.diagnosticar(documento, driver="concar", configuracion=config, imputacion=imputacion)
    if diagnostico["listo_para_exportar"]:
        resultado = api.exportar(documento, driver="concar", configuracion=config, imputacion=imputacion)

Documento `open-accounting` entra, diccionario sale; el documento va primero y todo lo demás por su nombre. Lo que está
en `__all__` sigue su firma hasta la 2.0 (`tests/test_superficie_publica.py`): en una versión menor pueden llegar
parámetros opcionales, claves nuevas en las respuestas y anotaciones `_*`, nunca quitarse.

Debajo de la API está el nivel de extensión —`modelo`, `asiento`, `drivers.contrato`…—, para quien escribe un driver o
trabaja con los objetos del modelo. `pipeline` y `puertas` son internos.
"""
from __future__ import annotations

from .._obsoleto import RutaObsoleta
from .._version import OPEN_ACCOUNTING, __version__
from ..asiento.faltas import FALTAS
from ..modelo import Comprobante, Libro, Observacion, serie_y_numero
from ..pipeline.preparacion import MAXIMO_CLAVES_PREVIAS, MAXIMO_COMPROBANTES
from ..pipeline.salida import Exportado
from .documento import documento_de
from .errores import (CampoCambiaDeSigno, ConfiguracionInvalida, CorrelativoDesborda, Descuadre, DocumentoInvalido, ErrorContaperu,
                      ErroresBloqueantes, IgvImposible, NoCabe, NoExportable, RepartoNoAdmitido, RepartoNoCuadra,
                      SinCentro, SinCodigoDeMoneda, SinCorrelativo, SinCuenta, SinSigla, SireInvalido, TablaInvalida,
                      TotalImposible, XmlInvalido, problema)
from .operaciones import (adaptar_pcge, buscar_cuenta_pcge, catalogo_pcge, catalogos_del_estandar, catalogos_sunat, comparar_sire, cuadrar,
                          describir_configuracion, diagnosticar, drivers_disponibles, errores_de_configuracion,
                          esquema_diagnostico, esquema_open_accounting, exportar, exportar_archivo, generar_asiento, leer_archivos,
                          leer_propuesta_sire, leer_xml, normalizar_detracciones, revisar, configuracion_por_defecto, contrato_openconta,
                          verificar_driver)
from .tabla import OPERACIONES, Operacion

__all__ = [
    # operaciones
    "leer_xml", "leer_propuesta_sire", "leer_archivos", "documento_de", "revisar", "normalizar_detracciones",
    "diagnosticar", "generar_asiento", "exportar", "exportar_archivo", "cuadrar", "buscar_cuenta_pcge", "adaptar_pcge",
    "configuracion_por_defecto", "describir_configuracion", "errores_de_configuracion", "drivers_disponibles",
    "catalogos_sunat", "catalogo_pcge", "catalogos_del_estandar", "esquema_open_accounting", "esquema_diagnostico", "comparar_sire",
    "contrato_openconta", "verificar_driver",
    # la tabla que exponen las puertas
    "OPERACIONES", "Operacion",
    # lo que devuelve o recibe
    "Exportado", "Comprobante", "Libro", "Observacion", "FALTAS", "serie_y_numero", "MAXIMO_COMPROBANTES",
    "MAXIMO_CLAVES_PREVIAS",
    # errores
    "ErrorContaperu", "DocumentoInvalido", "ConfiguracionInvalida", "ErroresBloqueantes", "NoExportable", "NoCabe",
    "SinCuenta", "SinCentro", "SinSigla", "SinCodigoDeMoneda", "SinCorrelativo", "RepartoNoCuadra",
    "RepartoNoAdmitido", "CorrelativoDesborda", "CampoCambiaDeSigno", "Descuadre", "XmlInvalido", "SireInvalido", "IgvImposible",
    "TotalImposible", "TablaInvalida", "problema",
    # versiones y avisos
    "RutaObsoleta", "OPEN_ACCOUNTING", "__version__",
]
