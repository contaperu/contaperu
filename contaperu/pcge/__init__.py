"""Plan Contable General Empresarial 2026: el catalogo oficial y la adaptacion de cuentas.

Dos cosas distintas viven aqui:

- **El catalogo** (`catalogo.py` + `catalogo2026.json`): las 1615 cuentas de la norma con su
  nombre y la pagina que lo dice. Es dato, no regla: sirve para poner el nombre en pantalla y
  para que quien proponga una cuenta tenga contra que contrastarla.
- **La adaptacion** (`adaptar.py` + `pcge2026.json`): la tabla de equivalencias entre planes, que
  esta VACIA a proposito. Ninguna regla contable entra sin la cita de la norma que la respalda, y
  ademas este proyecto nace ya en 2026: no hay plan viejo del que traducir.

**Cada uno se carga con su nombre:** `pcge.cargar_equivalencias()` lee la tabla de adaptacion y devuelve
`(mapeos, datos)`; `pcge.cargar_catalogo()` lee la norma y devuelve su diccionario. Hasta el 12-sep-2026 las dos se
llamaban `cargar`, y confundirlas no reventaba: devolvia otra cosa.
"""
from . import catalogo, clases
from .adaptar import Informe, Mapeo, TablaInvalida, adaptar, cargar_equivalencias
from .catalogo import buscar, cargar_catalogo, existe, nombre_de, resolver
from .clases import ELEMENTOS, clase_de, elemento

__all__ = ["ELEMENTOS", "Informe", "Mapeo", "TablaInvalida", "adaptar", "cargar_equivalencias", "catalogo",
           "buscar", "cargar_catalogo", "clase_de", "clases", "elemento", "existe", "nombre_de", "resolver"]
