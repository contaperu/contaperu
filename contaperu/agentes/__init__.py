"""La base para publicar el motor —y lo de quien lo integra— como herramientas para un agente de IA.

**Provisional en la 16.0**: sus nombres pueden cambiar en una 16.x hasta que la adopte su primer integrador, y
entonces se congelan con sus firmas, como `contaperu.api`. Lo que no cambia es el reparto:

- `contaperu.agentes` no importa el SDK del protocolo ni pydantic: es el catálogo —qué operación va en qué
  herramienta, con qué modo, qué arriesga, a quién se publica y qué nombre se retiró—, el despacho de los modos, la
  traducción de nombres y el recorte de listas. Se sostiene igual con cualquier versión del SDK.
- la proyección sobre el SDK (`MCPServer`) irá en `contaperu.agentes.servidor`, y será lo único que cambie cuando cambie
  su versión mayor.

El catálogo de las herramientas del motor es `DEL_MOTOR`, derivado de `api.OPERACIONES`. Y el kit de vigilantes de lo
que un servidor publica —la foto, el peso, los topes, las reglas y los nombres fantasma— es `agentes.vigilancia`.
"""
from __future__ import annotations

from .catalogo import MIRA, PERFILES, Catalogo, CatalogoInvalido, Ficha, Herramienta, Retirada, Riesgo, nombre_valido
from .del_motor import DEL_MOTOR
from .despacho import SIN_VALOR, EntradaInvalida, operacion_del_modo, recortar, solo_los_de_su_modo

__all__ = ["DEL_MOTOR", "MIRA", "PERFILES", "SIN_VALOR", "Catalogo", "CatalogoInvalido", "EntradaInvalida", "Ficha",
           "Herramienta", "Retirada", "Riesgo", "nombre_valido", "operacion_del_modo", "recortar",
           "solo_los_de_su_modo"]
