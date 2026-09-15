"""`contaperu.generar` de la 0.10: las mismas firmas, sobre `pipeline.salida` de la 1.0.

Se llega aquí por `contaperu.generar`, que avisa con `RutaObsoleta`. Lo nuevo es `contaperu.api.exportar_archivo`, que
devuelve el mismo `Exportado`.
"""
from __future__ import annotations

from .. import configuracion as _declaracion  # noqa: F401  (nombres que la 0.10 dejaba ver)
from .. import drivers, partida_doble  # noqa: F401
from ..asiento.huella import huella  # noqa: F401
from ..asiento.motor import lineas_del_libro  # noqa: F401
from ..asiento.resolucion import exigir_requisitos, fundir_config  # noqa: F401
from ..configuracion import CONFIG_POR_DEFECTO, CONFIGURACION_GENERAL, ConfiguracionInvalida  # noqa: F401
from ..drivers import contrato  # noqa: F401
from ..errores import ErroresBloqueantes  # noqa: F401
from ..drivers.kit import Opciones
from ..modelo import Comprobante, Libro, serie_y_numero  # noqa: F401
from ..pipeline import salida as _salida
from ..pipeline.salida import Exportado  # noqa: F401
from ..pipeline.seleccion import errores_de, etiqueta, fuera_de, seleccionar  # noqa: F401

# El driver por defecto de la 0.10. La 1.0 no supone ninguno.
_POR_DEFECTO = "sire"


def lineas_de_texto(libro: Libro, comprobantes: list[Comprobante], driver: str = _POR_DEFECTO,
                    opciones: Opciones | None = None) -> list[str]:
    return _salida.lineas_de_texto(libro, comprobantes, driver, opciones)


def generar(libro: Libro, comprobantes: list[Comprobante], driver: str = _POR_DEFECTO,
            opciones: Opciones | None = None, incluir_errores: bool = False, config: dict | None = None,
            correlativos: dict[str, int] | None = None) -> Exportado:
    return _salida.generar(libro, comprobantes, driver, opciones, incluir_errores, config, correlativos)
