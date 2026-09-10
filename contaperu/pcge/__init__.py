"""Plan Contable General Empresarial 2026: el catalogo oficial y la adaptacion de cuentas.

Dos cosas distintas viven aqui:

- **El catalogo** (`catalogo.py` + `catalogo2026.json`): las 1615 cuentas de la norma con su
  nombre y la pagina que lo dice. Es dato, no regla: sirve para poner el nombre en pantalla y
  para que quien proponga una cuenta tenga contra que contrastarla.
- **La adaptacion** (`adaptar.py` + `pcge2026.json`): la tabla de equivalencias entre planes, que
  esta VACIA a proposito. Ninguna regla contable entra sin la cita de la norma que la respalda, y
  ademas este proyecto nace ya en 2026: no hay plan viejo del que traducir.

**Ojo con `cargar`:** hay dos, y hacen cosas distintas. `pcge.cargar()` es el de la tabla de
adaptacion y devuelve `(mapeos, datos)`; el del catalogo es `pcge.catalogo.cargar()` y devuelve el
diccionario de la norma. Confundirlos no revienta, devuelve otra cosa: por eso el submodulo
`catalogo` se exporta con nombre propio y las llamadas al catalogo se escriben `pcge.catalogo.…`.
"""
from . import catalogo
from .adaptar import Informe, Mapeo, TablaInvalida, adaptar, cargar
from .catalogo import buscar, existe, nombre_de, resolver

__all__ = ["Informe", "Mapeo", "TablaInvalida", "adaptar", "cargar", "catalogo",
           "buscar", "existe", "nombre_de", "resolver"]
