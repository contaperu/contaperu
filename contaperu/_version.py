"""Los dos números del proyecto, y el único sitio donde se escriben.

Están aquí, en un módulo sin importaciones, por dos motivos:

- **`pyproject.toml` los lee de aquí** (`[tool.hatch.version]`), no al revés. Antes la versión se
  escribía a mano en los dos sitios y se separaron sin que nadie lo notara: llegaron a convivir
  **tres** —`0.3.0` en el empaquetado, `0.2.0` en el código y `0.1.0` en la metadata instalada—,
  mientras el servidor MCP se presentaba ante el Claude del contador con la del medio.
- **Sin ciclos.** `operaciones.py` también necesita `PE_LEDGER`, y no puede pedírselo a `__init__`
  porque `__init__` lo importa a él. Un módulo hoja que no importa nada rompe el nudo.

No leer la versión con `importlib.metadata`: en una instalación editable (`pip install -e`) esa
metadata se congela el día que se instaló y miente hasta que alguien reinstale — es exactamente
como apareció el `0.1.0` de arriba.
"""
from __future__ import annotations

__version__ = "0.7.0"

# La versión del ESTÁNDAR de datos, que es otro reloj: `pe-ledger` es el formato que se publica para
# que otros lo usen y cambia poquísimo, mientras la librería cambia cada vez que se corrige un
# asiento. Confundirlos sería peor que no versionar. Su esquema vive en `estandar/`.
PE_LEDGER = "0.2"
