"""Los dos números del proyecto, y el único sitio donde se escriben.

Están aquí, en un módulo sin importaciones, por dos motivos:

- **`pyproject.toml` los lee de aquí** (`[tool.hatch.version]`), no al revés. Antes la versión se
  escribía a mano en los dos sitios y se separaron sin que nadie lo notara: llegaron a convivir
  **tres** —`0.3.0` en el empaquetado, `0.2.0` en el código y `0.1.0` en la metadata instalada—,
  mientras el servidor MCP se presentaba ante el Claude del contador con la del medio.
- **Sin ciclos.** `operaciones.py` también necesita `OPEN_ACCOUNTING`, y no puede pedírselo a `__init__`
  porque `__init__` lo importa a él. Un módulo hoja que no importa nada rompe el nudo.

No leer la versión con `importlib.metadata`: en una instalación editable (`pip install -e`) esa
metadata se congela el día que se instaló y miente hasta que alguien reinstale — es exactamente
como apareció el `0.1.0` de arriba.
"""
from __future__ import annotations

__version__ = "3.0.0"

# La versión del ESTÁNDAR de datos, que es otro reloj: `open-accounting` es el formato que se publica para
# que otros lo usen y cambia poquísimo, mientras la librería cambia cada vez que se corrige un
# asiento. Confundirlos sería peor que no versionar. Su esquema vive en `estandar/`.
#
# Y desde que el estándar llegó a su 1.0 hay una regla más, que `tests/test_estandar.py` hace cumplir:
# **ninguno de los dos números puede ser prefijo del otro**. El riesgo nunca fue que se parecieran, sino
# que `"1.0"` es prefijo de `"1.0.0"` — ahí es donde un lector, o un grep, los confunde. Por eso la
# librería saltó a `1.1.0` en la misma tanda en que el estándar llegó a `1.0`, y por eso el test se pone
# rojo si alguien intenta publicar un estándar cuya versión sea prefijo de la del paquete: la separación
# deja de depender de que nos acordemos.
OPEN_ACCOUNTING = "1.0"
