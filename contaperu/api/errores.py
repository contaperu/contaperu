"""Los errores de la API: todos heredan de `ErrorContaperu` y llevan una `clave` estable.

`problema(error)` los dice como un «problem details» del RFC 9457 (`application/problem+json`): es lo que responde la
puerta HTTP, y sirve igual a cualquier aplicación que quiera guardar o enseñar un rechazo con la misma forma.
"""
from __future__ import annotations

from ..asiento.faltas import (NoExportable, RepartoNoAdmitido, RepartoNoCuadra, SinCentro, SinCodigoDeMoneda,
                              SinCorrelativo, SinCuenta, SinSigla)
from ..configuracion import ConfiguracionInvalida
from ..drivers.concar import CorrelativoDesborda
from ..drivers.contrato import NoCabe
from ..errores import DocumentoInvalido, ErrorContaperu, ErroresBloqueantes
from ..igv import IgvImposible, TotalImposible
from ..lectores.sire_txt import SireInvalido
from ..lectores.xml_ubl import XmlInvalido
from ..partida_doble import Descuadre
from ..pcge.adaptar import TablaInvalida

__all__ = ["ConfiguracionInvalida", "CorrelativoDesborda", "Descuadre", "DocumentoInvalido", "ErrorContaperu",
           "ErroresBloqueantes", "IgvImposible", "NoCabe", "NoExportable", "RepartoNoAdmitido", "RepartoNoCuadra",
           "SinCentro", "SinCodigoDeMoneda", "SinCorrelativo", "SinCuenta", "SinSigla", "SireInvalido",
           "TablaInvalida", "TotalImposible", "XmlInvalido", "problema"]

# Lo que se pidió no se puede hacer con estos datos: el documento, la configuración o el mes no dan.
NO_PROCESABLE = 422
ERROR_INTERNO = 500


def problema(error: BaseException) -> dict:
    """El error como «problem details» (RFC 9457): `status`, `title`, `detail` y, como miembros propios, `clave` y
    —si el error los trae— `errores`. Un error que no es del motor no enseña su texto: puede llevar rutas o datos
    internos, y quien llama no puede hacer nada con él."""
    if isinstance(error, ErrorContaperu):
        clave = error.clave or "no_exportable"
        salida = {"type": "about:blank", "status": NO_PROCESABLE, "title": "El motor no puede hacerlo",
                  "detail": str(error), "clave": clave}
    elif isinstance(error, ValueError):
        salida = {"type": "about:blank", "status": NO_PROCESABLE, "title": "El motor no puede hacerlo",
                  "detail": str(error), "clave": "valor_invalido"}
    else:
        return {"type": "about:blank", "status": ERROR_INTERNO, "title": "Error interno",
                "detail": "El motor falló al procesar la petición.", "clave": "error_interno"}
    errores = getattr(error, "errores", None)
    if isinstance(errores, list):
        salida["errores"] = errores
    return salida
