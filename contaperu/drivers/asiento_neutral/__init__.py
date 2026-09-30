"""El nombre viejo del driver `asiento_contable`, que sigue resolviendo y avisa (3.10).

Este módulo no tiene código propio: cada nombre se resuelve en `contaperu.drivers.asiento_contable` al pedirlo, con un
`RutaObsoleta` que dice cuál usar. Se retira en la 4.0 (`_obsoleto.RETIRO`), que es lo que promete `CLAUDE.md`: lo que
se retira avisa durante toda la mayor anterior.

**Por qué es un archivo en disco y no un `__getattr__` en `drivers/__init__.py`.** Un `__getattr__` de paquete (PEP
562) resuelve `from contaperu.drivers import asiento_neutral` y el acceso por atributo, pero **no**
`import contaperu.drivers.asiento_neutral` ni `from contaperu.drivers.asiento_neutral import NOMBRE`: para eso el
módulo tiene que existir. Quien integró con la 1.x pudo escribir cualquiera de las cuatro formas, así que las cuatro
siguen funcionando.

**Y por qué declara `__all__`.** `tests/test_superficie_publica.py` congeló trece nombres públicos de este módulo, y
lee `__all__` si está. Sin él tomaría los nombres del talón —que no tiene ninguno— y los trece contarían como
**quitados**, que es una versión mayor. Con él, la superficie sigue entera sin regenerarse y el test no dispara el
aviso, porque mira la lista y no hace `getattr`.

`Libro`, `OpcionesArchivo` y `OPEN_ACCOUNTING` están en la lista porque se colaron en la superficie como importaciones
del módulo original; se conservan por eso, no porque sean suyos.
"""
from __future__ import annotations

from .. import _obsoleto as _o

_NUEVO = "contaperu.drivers.asiento_contable"

# Los trece que congeló la superficie de la 1.0, cada uno a su sitio en el módulo nuevo.
__all__ = ["CANAL", "CONFIGURACION", "CONTENT_TYPE", "EXIGE", "FORMATOS", "Libro", "NOMBRE", "OPCIONES",
           "OPEN_ACCOUNTING", "OpcionesArchivo", "VOCABULARIO", "desde_lineas", "nombre"]

__getattr__, __dir__ = _o.reexportar(
    __name__,
    {nombre: f"{_NUEVO}:{nombre}" for nombre in __all__},
    nuevas={nombre: f"{_NUEVO}.{nombre}" for nombre in __all__},
)
