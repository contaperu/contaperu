"""Los errores de la API: todos heredan de `ErrorContaperu` y llevan una `clave` estable.

`problema(error)` los dice como un «problem details» del RFC 9457 (`application/problem+json`): es lo que responde la
puerta HTTP, y sirve igual a cualquier aplicación que quiera guardar o enseñar un rechazo con la misma forma.

**Y desde la 15.16 dice también CUÁLES comprobantes** (`comprobantes`). Un `NoExportable` los lleva desde siempre
—`SinCuenta`, `SinCentro`, `NoCabe`…— y `problema` solo copiaba `errores`, así que por HTTP y por MCP llegaba «3
comprobante(s) sin centro de costo» y nada con qué encontrarlos. Van dichos para que quien integra los case con los
suyos sin reimplementar nada: su `id_externo`, que es su propia llave; su nombre, el mismo de `errores_de`; y sus
`partes`, normalizadas como la clave del motor, que es lo que devuelve `leer_nombre_del_comprobante`.
"""
from __future__ import annotations

from ..asiento.faltas import (NoExportable, RepartoNoAdmitido, RepartoNoCuadra, SinCentro, SinCodigoDeMoneda,
                              SinCodigoDetraccion, SinCorrelativo, SinCuenta, SinSigla)
from ..comprobantes.nombre import PARTES, nombre_del_comprobante
from ..configuracion import ConfiguracionInvalida
from ..drivers.concar import CorrelativoDesborda
from ..drivers.contrato import NoCabe
from ..drivers.sire import CampoCambiaDeSigno
from ..errores import DocumentoInvalido, ErrorContaperu, ErroresBloqueantes
from ..tributos.igv import IgvImposible, TotalImposible
from ..lectores.sire_txt import SireInvalido
from ..lectores.xml_ubl import XmlInvalido
from ..modelo import Comprobante
from ..contable.partida_doble import Descuadre
from ..pcge.adaptar import TablaInvalida

__all__ = ["CampoCambiaDeSigno", "ConfiguracionInvalida", "CorrelativoDesborda", "Descuadre", "DocumentoInvalido", "ErrorContaperu",
           "ErroresBloqueantes", "IgvImposible", "NoCabe", "NoExportable", "RepartoNoAdmitido", "RepartoNoCuadra",
           "SinCentro", "SinCodigoDeMoneda", "SinCodigoDetraccion", "SinCorrelativo", "SinCuenta", "SinSigla",
           "SireInvalido",
           "TablaInvalida", "TotalImposible", "XmlInvalido", "problema"]

# Lo que se pidió no se puede hacer con estos datos: el documento, la configuración o el mes no dan.
NO_PROCESABLE = 422
ERROR_INTERNO = 500


def _comprobante_del_problema(c: Comprobante) -> dict:
    """Un comprobante como lo cita un rechazo: su nombre, sus partes normalizadas y el `id_externo` con que lo conoce
    quien lo mandó (`""` si no lo dio)."""
    return {"comprobante": nombre_del_comprobante(c), "partes": dict(zip(PARTES, c.clave)), "id_externo": c.id_externo}


def problema(error: BaseException) -> dict:
    """El error como «problem details» (RFC 9457): `status`, `title`, `detail` y, como miembros propios, `clave`
    —si el error los trae— `errores` y `comprobantes`, los que el motor se negó a exportar, cada uno con su nombre,
    sus `partes` y su `id_externo`. Un error que no es del motor no enseña su texto: puede llevar rutas o datos
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
    # Solo si hay alguno: un `NoExportable` lleva la lista vacía cuando lo que falta es un código —una sigla, una
    # moneda—, y una lista vacía diría «ningún comprobante» donde la verdad es «no es cosa de un comprobante».
    comprobantes = [c for c in getattr(error, "comprobantes", None) or [] if isinstance(c, Comprobante)]
    if comprobantes:
        salida["comprobantes"] = [_comprobante_del_problema(c) for c in comprobantes]
    return salida
