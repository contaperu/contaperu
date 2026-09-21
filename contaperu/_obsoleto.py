"""El mecanismo con que una ruta que cambió de sitio sigue resolviendo, y avisa.

**Hoy no lo usa nadie**: la 2.0 retiró la última ruta de la 0.x. Se conserva porque `RutaObsoleta` es parte de la API
pública —una aplicación la filtra con precisión, sin apagar los avisos de nadie más— y porque la próxima vez que algo
cambie de sitio, el circuito ya está escrito y probado:

    warnings.filterwarnings("ignore", category=contaperu.RutaObsoleta)

Las dos decisiones que lo hacen usable, y que conviene no perder:

- **El aviso sale al USAR la ruta vieja, no al importar el módulo.** Por eso `reexportar` devuelve un `__getattr__` de
  módulo en vez de ejecutar nada en el cuerpo: un `import` en el arranque de una aplicación no ensucia su registro.
- **`RETIRO` dice en qué versión desaparece**, y va en el mensaje. Lo que se deprecie ahora se retira en la 3.0.

La batería de este repositorio convierte el aviso en error (`[tool.pytest.ini_options] filterwarnings`), así que
ningún test usa una ruta vieja sin decirlo.
"""
from __future__ import annotations

import functools
import importlib
import warnings
from typing import Any, Callable

RETIRO = "3.0"


class RutaObsoleta(DeprecationWarning):
    """Una ruta que cambió de sitio, sigue funcionando y se retira en la versión mayor siguiente."""


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
    no es el propio destino— y el destino si no. Un nombre que no está en `destinos` da el `AttributeError` de
    siempre."""
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
