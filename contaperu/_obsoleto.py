"""El mecanismo con que un nombre que cambió sigue resolviendo, y avisa.

Estuvo sin usarse desde que la 2.0 retiró la última ruta de la 0.x hasta que la 3.10 renombró el driver
`asiento_neutral` a `asiento_contable`: ahí volvió a hacer falta, y por eso se había conservado. `RutaObsoleta` es
parte de la API pública —una aplicación la filtra con precisión, sin apagar los avisos de nadie más—:

    warnings.filterwarnings("ignore", category=contaperu.RutaObsoleta)

Las dos decisiones que lo hacen usable, y que conviene no perder:

- **El aviso sale al USAR la ruta vieja, no al importar el módulo.** Por eso `reexportar` devuelve un `__getattr__` de
  módulo en vez de ejecutar nada en el cuerpo: un `import` en el arranque de una aplicación no ensucia su registro.
- **`RETIRO` dice en qué versión desaparece**, y va en el mensaje. Lo que se deprecie ahora se retira en la 7.0, que
  es lo que promete `CLAUDE.md`: lo que se retira avisa durante toda la mayor anterior. **Se mueve con cada mayor que
  cumple lo prometido**, y la 4.0 cumplió: retiró el alias `asiento_neutral`, que era lo único que quedaba avisando.
  Decía «3.0» con el paquete ya en la 3.8, así que el aviso citaba una versión pasada — una promesa de retiro no puede
  sostener nada si el número que da ya quedó atrás, y de ahí sale esta regla. La 5.0 lo movió a la 6.0 sin retirar
  nada, porque llegó sin nadie avisando. Y la 6.0 **volvió a caer en lo mismo**: salió sin moverlo, así que durante
  toda la 6.x este módulo prometía un retiro en «la 6.0», que ya era la versión en curso. Nada lo vigilaba —el único
  test que lo tocaba lo interpolaba en el mensaje que comprobaba—, de modo que la regla de arriba no la hacía cumplir
  nadie. **Desde la 6.2.0 sí**: `tests/test_version.py` exige que `RETIRO` sea mayor que la versión del paquete. Hoy
  dice «7.0», que es la mayor siguiente y donde se retiran los puentes de la reestructuración.

  Y no se confunda con los **valores de catálogo** marcados obsoletos (`estandar/catalogos.json`, `obsoletos`), que la
  5.0 trae y que **no tienen retiro ninguno**: un nombre de Python obsoleto desaparece, un valor publicado del estándar
  no, porque los documentos ya guardados lo llevan dentro.
- **El texto del aviso no supone de qué clase es lo que cambió.** Nació para las rutas de la 0.x y lo decía en la
  cadena; ahora `que` lo dice quien llama, porque un nombre de driver no es una ruta de módulo.

La batería de este repositorio convierte el aviso en error (`[tool.pytest.ini_options] filterwarnings`), así que
ningún test usa una ruta vieja sin decirlo.
"""
from __future__ import annotations

import functools
import importlib
import warnings
from typing import Any, Callable

RETIRO = "7.0"


class RutaObsoleta(DeprecationWarning):
    """Algo que cambió de nombre o de sitio, sigue funcionando y se retira en la versión mayor siguiente.

    Lo usan las rutas de módulo (`reexportar`) y, desde la 3.10, el nombre viejo de un driver (`drivers.ALIAS`)."""


def avisar(vieja: str, nueva: str, *, que: str = "una ruta de la 0.x", nivel: int = 3) -> None:
    """Avisa de que `vieja` se retira, y dice qué usar en su lugar.

    `que` dice QUÉ es lo que cambió —una ruta de módulo, el nombre viejo de un driver— porque el mensaje lo lee una
    persona y «es una ruta de la 0.x» sería falso para cualquier cosa que no lo sea. `nivel` apunta a quien usó lo
    viejo, no a este archivo."""
    warnings.warn(f"`{vieja}` es {que} y se retira en la {RETIRO}: usa `{nueva}`.", RutaObsoleta,
                  stacklevel=nivel)


def resolver(destino: str) -> Any:
    """`"paquete.modulo:atributo.sub"` → el objeto; sin `:`, el módulo."""
    modulo, _, atributo = destino.partition(":")
    objeto: Any = importlib.import_module(modulo)
    for parte in filter(None, atributo.split(".")):
        objeto = getattr(objeto, parte)
    return objeto


def reexportar(modulo: str, destinos: dict[str, str], *, avisa: bool = True,
               nuevas: dict[str, str] | None = None,
               que: str = "una ruta de la 0.x") -> tuple[Callable, Callable]:
    """El `__getattr__` y el `__dir__` de un módulo cuyos nombres viven en otro sitio.

    `destinos` es `{"nombre": "paquete.modulo:atributo"}`. Cada nombre se resuelve al pedirlo, y avisa con
    `RutaObsoleta` si `avisa`. El aviso recomienda `nuevas[nombre]` si está —la ruta pública que la reemplaza, cuando
    no es el propio destino— y el destino si no. Un nombre que no está en `destinos` da el `AttributeError` de
    siempre.

    `que` dice QUÉ es lo que cambió, y se pasa tal cual a `avisar`. Su valor por defecto es de cuando este
    mecanismo solo servía a las rutas de la 0.x; un módulo que cambia de sitio hoy dice que es eso, porque el
    mensaje lo lee una persona y «es una ruta de la 0.x» sería falso."""
    nuevas = nuevas or {}

    def __getattr__(nombre: str) -> Any:
        destino = destinos.get(nombre)
        if destino is None:
            raise AttributeError(f"module {modulo!r} has no attribute {nombre!r}")
        if avisa:
            avisar(f"{modulo}.{nombre}", nuevas.get(nombre) or destino.replace(":", "."), que=que)
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
