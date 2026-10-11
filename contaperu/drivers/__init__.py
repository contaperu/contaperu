"""Registro de drivers de salida. Un driver traduce el asiento —o el registro— al formato que
importa un sistema contable concreto. Lo que tiene que exponer está en `contrato.py`.

Los seis que vienen de serie, por grupo de destino —SIRE, legacy y ERP—, salen de la contabilidad peruana real:

- **`sire`** — el TXT que se sube a SUNAT para reemplazar la propuesta del Registro de Ventas
  (RVIE) o de Compras (RCE). Es lo que la norma exige hoy: el PLE quedó reemplazado por el SIRE
  para estos dos registros.
- **`concar`** — el Excel de asientos que importa CONCAR, uno de los sistemas contables más
  usados del país.
- **`contasis`** — el registro de compras o de ventas en Excel que importa CONTASIS, que arma el
  asiento él mismo: una fila por comprobante. Escrito contra su plantilla oficial y aceptado:
  CONTASIS importó los archivos que genera (13-sep-2026).
- **`starsoft`** — el TXT de palotes que importa STARSOFT Desktop. Escrito contra su documentación oficial y
  **aceptado**: STARSOFT importó los archivos que genera (7-oct-2026), y de ese mes salieron el nombre que
  empieza por `C` y el TXT sin el ZIP que lo envolvía.
- **`csv`** — las líneas de diario en columnas, para quien todavía no tiene driver.
- **`asiento_contable`** — el documento del estándar completo: el libro, sus comprobantes y su asiento, sin vocabulario
  legacy (sin siglas, sub-diarios ni correlativos). Es la salida para un ERP nuevo, que parte del estándar en vez de
  reimplementar el IGV, y desde la 3.10 se llama así: antes era `asiento_neutral`, que decía de qué se libraba en
  lugar de qué es. El nombre viejo resolvió toda la 3.x y la 4.0 lo retiró.

**`asiento_contable` no es la carpeta `contaperu/asiento/`.** Esa arma el asiento —decide cuentas, sentidos,
importes y orden, y es contabilidad peruana—; este lo **escribe** tal como salió, sin traducirlo. La forma del
asiento estándar vive en `estandar/open-accounting.schema.json`; `ARQUITECTURA.md` §«Dónde vive el asiento
estándar» lo cuenta con las tres capas y su acoplamiento medido.

**Drivers de terceros, sin tocar este repositorio.** Un paquete instalado que declare en su
`pyproject.toml`

    [project.entry-points."contaperu.drivers"]
    siscont = "contaperu_siscont"

aparece aquí solo, con su `NOMBRE`, en la CLI, en la api y en el servidor MCP. Declara su `CANAL` —`legacy` si es un
sistema contable instalado que importa un archivo, `sunat` si es un registro o un libro que se presenta a SUNAT,
`erp` si entrega el formato neutral del estándar— y la forma `desde_lineas` o `desde_comprobantes`
(`contrato/`). Es lo que permite
que la comunidad mantenga el driver de su ERP a su ritmo. Dos reglas: los de serie ganan ante un
nombre repetido, y un driver que no cumple el contrato —o que revienta al importarse— se ignora con
un `AvisoDriver` en vez de tumbar el registro entero. Para entrar AL repositorio sigue haciendo falta
un archivo real aceptado por ese ERP (ver `CONTRIBUTING.md`).
"""
from __future__ import annotations

import warnings
from importlib.metadata import entry_points
from types import ModuleType

from ..errores import ErrorContaperu
from . import asiento_contable, concar, contasis, contrato, csv, ple, ple_plan, sire, starsoft
from .kit import Opciones

GRUPO = "contaperu.drivers"
DE_SERIE: dict[str, ModuleType] = {sire.NOMBRE: sire, concar.NOMBRE: concar, csv.NOMBRE: csv,
                                   contasis.NOMBRE: contasis, starsoft.NOMBRE: starsoft,
                                   asiento_contable.NOMBRE: asiento_contable, ple.NOMBRE: ple, ple_plan.NOMBRE: ple_plan}
DRIVER_POR_DEFECTO = "sire"

__all__ = ["DE_SERIE", "DRIVERS", "DRIVER_POR_DEFECTO", "GRUPO", "AvisoDriver",
           "LibroQueElDestinoNoLleva", "Opciones",
           "asiento_contable", "concar", "contasis", "contrato", "csv", "de_terceros",
           "formato_de", "obtener", "ple", "ple_plan", "recargar", "sire", "starsoft"]


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
        # Hasta la 3.10 aquí avisaban dos promesas que decían «la 2.0» con el paquete en la 3.10: un driver sin
        # CANAL y uno con la forma `construir`. La 4.0 las cobró, y las dos las comprueba ya `contrato`:
        # sin canal es un incumplimiento, y `construir` no es una forma, así que el driver no carga.
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
    """El módulo de un driver por su nombre, o el `ValueError` que dice cuáles hay.

    Hasta la 10.0 pasaba por aquí una tabla `ALIAS` que resolvía el nombre viejo de un driver avisando con
    `RutaObsoleta`. **Estaba vacía desde la 4.0**, que retiró el único que hubo, y «el circuito se queda para el
    próximo» duró seis mayores sin uno. Se fue con el resto del andamio: si vuelve a hacer falta, son cuatro líneas.

    Y la razón por la que iría aquí y no en el registro conviene no perderla, porque es lo que hacía que valiera la
    pena: **es el único sitio por donde pasan las cuatro puertas** —la librería, la CLI, HTTP y el MCP llegan todas a
    `pipeline`, y `pipeline` llega aquí—, así que un alias puesto en este punto los cubre a los cuatro y no ensucia
    la lista de destinos que ese mismo registro publica."""
    try:
        return DRIVERS[nombre]
    except KeyError:
        raise ValueError(f"Driver desconocido: {nombre!r}. Disponibles: {', '.join(DRIVERS)}") from None


class LibroQueElDestinoNoLleva(ErrorContaperu, ValueError):
    """Un tipo de libro que el catálogo publica y este destino no declara en sus `FORMATOS`.

    Es la degradación que el estándar promete para un tipo de libro, y es distinta de la de un `rol`: un rol
    desconocido no rompe nada —la línea se contabiliza por su cuenta, su sentido y su importe—, pero **un libro
    desconocido no se puede adivinar**, así que la degradación es del destino y tiene que decir qué sí lleva.

    Hereda de `ValueError` además de `ErrorContaperu` porque eso era antes, y quien lo atrape por ahí sigue
    atrapándolo."""

    clave = "libro_que_el_destino_no_lleva"

    def __init__(self, driver: str, tipo_libro: str, lleva):
        super().__init__(f"El driver {driver!r} no lleva libros de tipo {tipo_libro!r}: "
                         f"lleva {', '.join(sorted(lleva))}")
        self.driver = driver
        self.tipo = tipo_libro
        self.lleva = tuple(sorted(lleva))


def formato_de(nombre: str, tipo_libro: str) -> str:
    """'sire' + 'venta' → 'sire_rvie': el identificador de lo que se acaba de producir."""
    formatos = obtener(nombre).FORMATOS
    if tipo_libro not in formatos:
        raise LibroQueElDestinoNoLleva(nombre, tipo_libro, formatos)
    return formatos[tipo_libro]
