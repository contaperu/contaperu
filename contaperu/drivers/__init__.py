"""Registro de drivers de salida. Un driver traduce el asiento al formato que importa
un sistema contable concreto.

Cada driver expone:

- `NOMBRE`, `OPCIONES` (los valores por defecto de formato), `FORMATOS`
  ({'venta': …, 'compra': …} — el identificador de la salida que produce)
- `nombre(libro, op)` → el nombre del archivo
- y **o bien** `linea(comprobante, libro, idx, op)` → una línea de un archivo de texto,
  **o bien** `construir(libro, comprobantes, **params) -> (bytes, resumen)` para un archivo
  binario entero, que además declara `CONTENT_TYPE`.
- opcionalmente `EXCLUYE_TIPOS`: los comprobantes que este destino no debe llevar.

Dar de alta un driver = un paquete más aquí y una entrada en `DRIVERS`. Ningún otro archivo
del núcleo cambia. Ver `CONTRIBUTING.md`.

Los dos que vienen de serie salen de la contabilidad peruana real:

- **`sire`** — el TXT que se sube a SUNAT para reemplazar la propuesta del Registro de Ventas
  (RVIE) o de Compras (RCE). Es lo que la norma exige hoy: el PLE quedó reemplazado por el SIRE
  para estos dos registros.
- **`concar`** — el Excel de asientos que importa CONCAR, uno de los sistemas contables más
  usados del país.
"""
from __future__ import annotations

from types import ModuleType

from . import concar, csv, sire
from ..formato import Opciones

DRIVERS: dict[str, ModuleType] = {sire.NOMBRE: sire, concar.NOMBRE: concar, csv.NOMBRE: csv}
DRIVER_DEFAULT = "sire"

__all__ = ["DRIVERS", "DRIVER_DEFAULT", "Opciones", "concar", "csv", "formato", "obtener", "sire"]


def obtener(nombre: str) -> ModuleType:
    try:
        return DRIVERS[nombre]
    except KeyError:
        raise ValueError(f"Driver desconocido: {nombre!r}. Disponibles: {', '.join(DRIVERS)}") from None


def formato(nombre: str, tipo_libro: str) -> str:
    """'sire' + 'venta' → 'sire_rvie': el identificador de lo que se acaba de producir."""
    formatos = obtener(nombre).FORMATOS
    if tipo_libro not in formatos:
        raise ValueError(f"El driver {nombre!r} no genera libros de tipo {tipo_libro!r}")
    return formatos[tipo_libro]
