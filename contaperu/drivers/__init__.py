"""Registro de drivers de salida. Un driver traduce el asiento —o el registro— al formato que
importa un sistema contable concreto. Lo que tiene que exponer está en `contrato.py`.

Los cuatro que vienen de serie salen de la contabilidad peruana real:

- **`sire`** — el TXT que se sube a SUNAT para reemplazar la propuesta del Registro de Ventas
  (RVIE) o de Compras (RCE). Es lo que la norma exige hoy: el PLE quedó reemplazado por el SIRE
  para estos dos registros.
- **`concar`** — el Excel de asientos que importa CONCAR, uno de los sistemas contables más
  usados del país.
- **`contasis`** — el registro de compras o de ventas en Excel que importa CONTASIS, que arma el
  asiento él mismo: una fila por comprobante. Escrito contra su plantilla oficial y un registro que
  CONTASIS importó; pendiente de que importe un archivo generado.
- **`csv`** — las líneas de diario neutrales, para quien todavía no tiene driver.

**Drivers de terceros, sin tocar este repositorio.** Un paquete instalado que declare en su
`pyproject.toml`

    [project.entry-points."contaperu.drivers"]
    siscont = "contaperu_siscont"

aparece aquí solo, con su `NOMBRE`, en la CLI, en la fachada y en el servidor MCP. Es lo que permite
que la comunidad mantenga el driver de su ERP a su ritmo. Dos reglas: los de serie ganan ante un
nombre repetido, y un driver que no cumple el contrato —o que revienta al importarse— se ignora con
un `AvisoDriver` en vez de tumbar el registro entero. Para entrar AL repositorio sigue haciendo falta
un archivo real aceptado por ese ERP (ver `CONTRIBUTING.md`).
"""
from __future__ import annotations

import warnings
from importlib.metadata import entry_points
from types import ModuleType

from . import concar, contasis, contrato, csv, sire
from ..formato import Opciones

GRUPO = "contaperu.drivers"
DE_SERIE: dict[str, ModuleType] = {sire.NOMBRE: sire, concar.NOMBRE: concar, csv.NOMBRE: csv,
                                   contasis.NOMBRE: contasis}
DRIVER_POR_DEFECTO = "sire"

__all__ = ["DE_SERIE", "DRIVERS", "DRIVER_POR_DEFECTO", "GRUPO", "AvisoDriver", "Opciones", "concar", "contasis",
           "contrato", "csv", "de_terceros", "formato_de", "obtener", "recargar", "sire"]


class AvisoDriver(UserWarning):
    """Un driver de terceros no se pudo registrar. No detiene nada: ese driver no aparece."""


def de_terceros() -> dict[str, ModuleType]:
    """Los drivers de los paquetes instalados que se declaran en el grupo `contaperu.drivers`."""
    encontrados: dict[str, ModuleType] = {}
    for entrada in entry_points(group=GRUPO):
        try:
            modulo = entrada.load()
        except Exception as e:     # código ajeno: cualquier fallo al importarlo es suyo, no del registro
            warnings.warn(f"El driver {entrada.name!r} no se pudo importar: {e}", AvisoDriver, stacklevel=2)
            continue
        problemas = contrato.incumplimientos(modulo)
        if problemas:
            warnings.warn(f"El driver {entrada.name!r} no cumple el contrato: {'; '.join(problemas)}",
                          AvisoDriver, stacklevel=2)
            continue
        if modulo.NOMBRE in DE_SERIE or modulo.NOMBRE in encontrados:
            warnings.warn(f"El driver {entrada.name!r} se llama {modulo.NOMBRE!r}, que ya está registrado; "
                          "se ignora", AvisoDriver, stacklevel=2)
            continue
        encontrados[modulo.NOMBRE] = modulo
    return encontrados


# Se muta en sitio y no se reasigna: quien hizo `from contaperu.drivers import DRIVERS` ve lo mismo.
DRIVERS: dict[str, ModuleType] = {}


def recargar() -> dict[str, ModuleType]:
    """Vuelve a buscar los drivers de terceros (p. ej. tras instalar uno sin reiniciar)."""
    DRIVERS.clear()
    DRIVERS.update(DE_SERIE)
    DRIVERS.update(de_terceros())
    return DRIVERS


recargar()


def obtener(nombre: str) -> ModuleType:
    try:
        return DRIVERS[nombre]
    except KeyError:
        raise ValueError(f"Driver desconocido: {nombre!r}. Disponibles: {', '.join(DRIVERS)}") from None


def formato_de(nombre: str, tipo_libro: str) -> str:
    """'sire' + 'venta' → 'sire_rvie': el identificador de lo que se acaba de producir."""
    formatos = obtener(nombre).FORMATOS
    if tipo_libro not in formatos:
        raise ValueError(f"El driver {nombre!r} no genera libros de tipo {tipo_libro!r}")
    return formatos[tipo_libro]
