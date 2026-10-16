"""Leer un campo de algo que puede venir como objeto o como diccionario.

**Las dos formas circulan**: dentro del motor viajan objetos y de fuera llegan dicts de JSON, que es lo que
manda un ERP. Tratarlas distinto es como nacieron los tres defectos que la revisión de consistencia del
11-oct-2026 encontró, y de ahí que esto exista como una sola función y no como una costumbre.

**Estaba escrita cuatro veces**: `asiento/movimiento.py` (`_campo`), `asiento/indice.py` (`_de`),
`tesoreria/imputaciones.py` (`_campo`) y `aplicaciones.py` (`_campo`) — la misma línea en cuatro sitios, y
**dos de ellas con un docstring que citaba los tres defectos nacidos justamente de no tenerla en uno**. La
cuarta apareció al buscar las otras tres, que es lo que suele pasar: lo que se copia una vez se copia otra.

**Por qué en `modelo/` y no en `asiento/comun.py`**, que es donde parecería: `asiento/movimiento.py` importa
`tesoreria`, así que `tesoreria/imputaciones.py` no puede importar de `asiento` sin cerrar un ciclo, y la
tercera copia habría sobrevivido. `modelo` está por debajo de los dos. No se reexporta en `modelo/__init__`
—su `__all__` es la superficie congelada y esto es maquinaria interna—, así que se pide por su módulo.
"""
from __future__ import annotations

from typing import Any


def campo(cosa: Any, nombre: str) -> Any:
    """El campo `nombre` de `cosa`, venga como objeto o como dict. Ausente es `None` en los dos casos."""
    return cosa.get(nombre) if isinstance(cosa, dict) else getattr(cosa, nombre, None)
