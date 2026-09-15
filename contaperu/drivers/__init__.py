"""Registro de drivers de salida. Un driver traduce el asiento —o el registro— al formato que
importa un sistema contable concreto. Lo que tiene que exponer está en `contrato.py`.

Los cinco que vienen de serie, por grupo de destino —SIRE, legacy y ERP—, salen de la contabilidad peruana real:

- **`sire`** — el TXT que se sube a SUNAT para reemplazar la propuesta del Registro de Ventas
  (RVIE) o de Compras (RCE). Es lo que la norma exige hoy: el PLE quedó reemplazado por el SIRE
  para estos dos registros.
- **`concar`** — el Excel de asientos que importa CONCAR, uno de los sistemas contables más
  usados del país.
- **`contasis`** — el registro de compras o de ventas en Excel que importa CONTASIS, que arma el
  asiento él mismo: una fila por comprobante. Escrito contra su plantilla oficial y aceptado:
  CONTASIS importó los archivos que genera (13-sep-2026).
- **`csv`** — las líneas de diario en columnas, para quien todavía no tiene driver.
- **`open_accounting`** — el documento del estándar con su asiento, sin vocabulario legacy (sin siglas, sub-diarios ni
  correlativos): la salida para un ERP nuevo, que parte del estándar en vez de reimplementar el IGV.

**Drivers de terceros, sin tocar este repositorio.** Un paquete instalado que declare en su
`pyproject.toml`

    [project.entry-points."contaperu.drivers"]
    siscont = "contaperu_siscont"

aparece aquí solo, con su `NOMBRE`, en la CLI, en la api y en el servidor MCP. Declara su `CANAL` —`legacy` si es un
sistema contable instalado que importa un archivo, `tributario` si es un registro que se presenta a SUNAT,
`intercambio` si es un formato neutral— y la forma `desde_lineas` o `desde_comprobantes` (`contrato.py`). Es lo que permite
que la comunidad mantenga el driver de su ERP a su ritmo. Dos reglas: los de serie ganan ante un
nombre repetido, y un driver que no cumple el contrato —o que revienta al importarse— se ignora con
un `AvisoDriver` en vez de tumbar el registro entero. Para entrar AL repositorio sigue haciendo falta
un archivo real aceptado por ese ERP (ver `CONTRIBUTING.md`).
"""
from __future__ import annotations

import warnings
from importlib.metadata import entry_points
from types import ModuleType

from . import concar, contasis, contrato, csv, open_accounting, sire
from .kit import Opciones

GRUPO = "contaperu.drivers"
DE_SERIE: dict[str, ModuleType] = {sire.NOMBRE: sire, concar.NOMBRE: concar, csv.NOMBRE: csv,
                                   contasis.NOMBRE: contasis, open_accounting.NOMBRE: open_accounting}
DRIVER_POR_DEFECTO = "sire"

__all__ = ["DE_SERIE", "DRIVERS", "DRIVER_POR_DEFECTO", "GRUPO", "AvisoDriver", "Opciones", "concar", "contasis",
           "contrato", "csv", "de_terceros", "formato_de", "obtener", "open_accounting", "recargar", "sire"]


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
        if not contrato.declara_canal(modulo):
            warnings.warn(f"El driver {entrada.name!r} no declara CANAL ({', '.join(contrato.CANALES)}): se trata como "
                          f"{contrato.CANAL_POR_DEFECTO!r}; en la 2.0 será obligatorio", AvisoDriver, stacklevel=2)
        if contrato.forma(modulo) == "construir":
            warnings.warn(f"El driver {entrada.name!r} usa la forma `construir`, que se retira en la 2.0: `desde_lineas` "
                          "recibe las líneas ya armadas y el índice de cada comprobante", AvisoDriver, stacklevel=2)
        encontrados[modulo.NOMBRE] = modulo
    return encontrados


class _Registro(dict):
    """Los drivers registrados: los de serie y los de terceros.

    Los de terceros se buscan la primera vez que alguien mira el registro, no al importar el paquete (1.0): leer los
    metadatos de lo instalado es trabajo que un `import contaperu.drivers` no tiene por qué pagar. Se muta en sitio y
    no se reasigna: quien hizo `from contaperu.drivers import DRIVERS` ve lo mismo."""

    _listo = False

    def _asegurar(self) -> None:
        if not self._listo:
            recargar()

    def __getitem__(self, clave):
        self._asegurar()
        return super().__getitem__(clave)

    def __contains__(self, clave) -> bool:
        self._asegurar()
        return super().__contains__(clave)

    def __iter__(self):
        self._asegurar()
        return super().__iter__()

    def __len__(self) -> int:
        self._asegurar()
        return super().__len__()

    def __repr__(self) -> str:
        self._asegurar()
        return super().__repr__()

    def __eq__(self, otro) -> bool:
        self._asegurar()
        return super().__eq__(otro)

    __hash__ = None

    def get(self, clave, defecto=None):
        self._asegurar()
        return super().get(clave, defecto)

    def keys(self):
        self._asegurar()
        return super().keys()

    def values(self):
        self._asegurar()
        return super().values()

    def items(self):
        self._asegurar()
        return super().items()

    def copy(self) -> dict[str, ModuleType]:
        self._asegurar()
        return dict(super().items())


DRIVERS: dict[str, ModuleType] = _Registro()


def recargar() -> dict[str, ModuleType]:
    """Vuelve a buscar los drivers de terceros (p. ej. tras instalar uno sin reiniciar)."""
    DRIVERS._listo = True
    dict.clear(DRIVERS)
    dict.update(DRIVERS, DE_SERIE)
    dict.update(DRIVERS, de_terceros())
    return DRIVERS


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
