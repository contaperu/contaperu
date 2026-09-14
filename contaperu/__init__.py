"""ContaPerú — núcleo contable abierto del Perú.

Lee los comprobantes que emite SUNAT, arma la partida doble y los exporta al formato que pide
cada sistema contable. **Sin estado**: ni base de datos, ni archivos, ni sesiones, ni red. Todo
entra por parámetro y sale por retorno, así que cada llamada se explica sola y se puede repetir
mil veces con el mismo resultado.

El camino completo, de un XML a un Excel de asientos:

    from contaperu import Libro, lectores, validar, drivers, generar

    libro = Libro(ruc="20601234567", razon_social="MI EMPRESA SAC",
                  periodo="202601", tipo="compra")
    lote = lectores.archivos.Lote()
    lectores.archivos.expandir("comprobantes.zip", datos, lote=lote)
    res = lectores.archivos.convertir_xml(lote, libro)
    comprobantes = lectores.archivos.ordenar(res.comprobantes)
    validar.revisar(comprobantes, libro)
    exp = generar.generar(libro, comprobantes, "concar",
                          config=configuracion, correlativos={"11": 1})

El estándar de datos que habla es `open-accounting`; su esquema está en `estandar/`.

**Importar el paquete no carga nada más** (1.0): cada submódulo se importa la primera vez que se pide
(`contaperu.asiento`, `contaperu.drivers`…). Así `import contaperu.modelo` no arrastra los drivers ni openpyxl.
"""
from __future__ import annotations

import importlib

# Los dos números viven en `_version.py`, que es de donde los lee también `pyproject.toml`:
# escribirlos a mano en dos sitios ya los separó una vez (ver el docstring de ese módulo).
from ._version import OPEN_ACCOUNTING, __version__

_SUBMODULOS = frozenset({
    "asiento", "catalogos", "comparar_sire", "configuracion", "detracciones", "drivers", "errores", "formato",
    "generar", "igv", "lectores", "modelo", "operaciones", "partida_doble", "pcge", "validar",
})
_NOMBRES = {
    "Comprobante": "contaperu.modelo", "Libro": "contaperu.modelo", "Observacion": "contaperu.modelo",
    "ErrorContaperu": "contaperu.errores", "RutaObsoleta": "contaperu._obsoleto",
}

__all__ = [
    "Comprobante", "Libro", "Observacion", "ErrorContaperu", "RutaObsoleta",
    "asiento", "catalogos", "detracciones", "drivers", "formato", "generar", "lectores",
    "operaciones", "partida_doble", "pcge", "validar", "OPEN_ACCOUNTING", "__version__",
]


def __getattr__(nombre: str):
    if nombre in _SUBMODULOS:
        return importlib.import_module(f"{__name__}.{nombre}")
    if nombre in _NOMBRES:
        return getattr(importlib.import_module(_NOMBRES[nombre]), nombre)
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _SUBMODULOS | set(_NOMBRES))
