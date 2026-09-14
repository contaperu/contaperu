"""Las rutas de la 0.x que siguen funcionando en la 1.x, y el aviso con que lo dicen.

La 1.0 fija una API pública (`contaperu.api`) y promete que lo que una aplicación importaba en la 0.10 sigue resolviendo
hasta la 2.0 (`tests/test_compat_superficie.py`). Lo que cambió de sitio avisa con `RutaObsoleta`, una subclase de
`DeprecationWarning` que una aplicación puede silenciar con precisión:

    warnings.filterwarnings("ignore", category=contaperu.RutaObsoleta)

El aviso sale al USAR la ruta vieja, no al importar el módulo: un `import contaperu.operaciones` en el arranque de una
aplicación no ensucia su registro. La batería de este repositorio convierte el aviso en error
(`[tool.pytest.ini_options] filterwarnings`), así que ningún test usa una ruta vieja sin decirlo.
"""
from __future__ import annotations

import functools
import importlib
import warnings
from typing import Any, Callable

RETIRO = "2.0"


class RutaObsoleta(DeprecationWarning):
    """Una ruta de la 0.x que sigue funcionando y se retira en la 2.0."""


def avisar(vieja: str, nueva: str, *, nivel: int = 3) -> None:
    """Avisa de que `vieja` se retira, y dice qué usar en su lugar. `nivel` apunta a quien llamó a la ruta vieja."""
    warnings.warn(f"`{vieja}` es una ruta de la 0.x y se retira en la {RETIRO}: usa `{nueva}`.", RutaObsoleta,
                  stacklevel=nivel)


def resolver(destino: str) -> Any:
    """`"paquete.modulo:atributo.sub"` → el objeto; sin `:`, el módulo."""
    modulo, _, atributo = destino.partition(":")
    objeto: Any = importlib.import_module(modulo)
    for parte in filter(None, atributo.split(".")):
        objeto = getattr(objeto, parte)
    return objeto


def reexportar(modulo: str, destinos: dict[str, str], *, avisa: bool = True,
               nuevas: dict[str, str] | None = None) -> tuple[Callable, Callable]:
    """El `__getattr__` y el `__dir__` de un módulo cuyos nombres viven en otro sitio.

    `destinos` es `{"nombre": "paquete.modulo:atributo"}`. Cada nombre se resuelve al pedirlo, y avisa con
    `RutaObsoleta` si `avisa`. El aviso recomienda `nuevas[nombre]` si está —la ruta pública que la reemplaza, cuando
    el destino es la copia de la 0.x en `_compat`— y el propio destino si no. Un nombre que no está en `destinos` da el
    `AttributeError` de siempre."""
    nuevas = nuevas or {}

    def __getattr__(nombre: str) -> Any:
        destino = destinos.get(nombre)
        if destino is None:
            raise AttributeError(f"module {modulo!r} has no attribute {nombre!r}")
        if avisa:
            avisar(f"{modulo}.{nombre}", nuevas.get(nombre) or destino.replace(":", "."))
        return resolver(destino)

    def __dir__() -> list[str]:
        return sorted(destinos)

    return __getattr__, __dir__


def funcion_obsoleta(nueva: Callable, *, vieja: str, reemplazo: str) -> Callable:
    """`nueva`, envuelta para que avise como `vieja` al llamarse."""
    @functools.wraps(nueva)
    def envoltorio(*args, **kwargs):
        avisar(vieja, reemplazo)
        return nueva(*args, **kwargs)

    return envoltorio
