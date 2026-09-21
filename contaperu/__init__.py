"""ContaPerú — núcleo contable abierto del Perú.

Lee los comprobantes que emite SUNAT, arma la partida doble y los exporta al formato que pide
cada sistema contable. **Sin estado**: ni base de datos, ni archivos, ni sesiones, ni red. Todo
entra por parámetro y sale por retorno, así que cada llamada se explica sola y se puede repetir
mil veces con el mismo resultado.

El camino completo, de un ZIP de XML a un Excel de asientos, por la API pública (`contaperu.api`):

    from contaperu import api

    libro = {"ruc": "20601234567", "razon_social": "MI EMPRESA SAC", "periodo": "202601", "tipo": "compra"}
    documento = api.leer_xml(zip_en_base64, libro, es_base64=True)
    diagnostico = api.diagnosticar(documento, driver="concar", configuracion=configuracion)
    exp = api.exportar_archivo(documento, driver="concar", configuracion=configuracion, correlativos={"11": 1})

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
    "api", "asiento", "catalogos", "comparar_sire", "configuracion", "detracciones", "drivers", "errores", "igv",
    "lectores", "modelo", "partida_doble", "pcge", "pipeline", "puertas", "validar",
})
_NOMBRES = {
    "Comprobante": "contaperu.modelo", "Libro": "contaperu.modelo", "Observacion": "contaperu.modelo",
    "ErrorContaperu": "contaperu.errores", "RutaObsoleta": "contaperu._obsoleto",
}

__all__ = [
    "Comprobante", "Libro", "Observacion", "ErrorContaperu", "RutaObsoleta",
    "api", "asiento", "catalogos", "detracciones", "drivers", "lectores",
    "partida_doble", "pcge", "validar", "OPEN_ACCOUNTING", "__version__",
]


def __getattr__(nombre: str):
    if nombre in _SUBMODULOS:
        return importlib.import_module(f"{__name__}.{nombre}")
    if nombre in _NOMBRES:
        return getattr(importlib.import_module(_NOMBRES[nombre]), nombre)
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _SUBMODULOS | set(_NOMBRES))
