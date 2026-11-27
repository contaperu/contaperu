"""La base para publicar el motor —y lo de quien lo integra— como herramientas para un agente de IA.

**Congelada desde la 16.2** con sus firmas, como `contaperu.api`: sus nombres no cambian hasta la 17.0. Nació
provisional en la 16.0 y se congeló cuando su primer integrador la había adoptado entera, con lo que esa adopción
enseñó ya dentro (`Servidor.declarar`, los títulos aparte de las pistas). El reparto:

- `contaperu.agentes` no importa el SDK del protocolo ni pydantic: es el catálogo —qué operación va en qué
  herramienta, con qué modo, qué arriesga, a quién se publica y qué nombre se retiró—, el despacho de los modos, la
  traducción de nombres y el recorte de listas. Se sostiene igual con cualquier versión del SDK.
- `contaperu.agentes.servidor` es la proyección sobre el SDK (`MCPServer`), y es lo único que cambia cuando cambie su
  versión mayor: el servidor por el que pasa cada llamada, `registrar`, y las fábricas del servidor del motor.

El catálogo de las herramientas del motor es `DEL_MOTOR`, derivado de `api.OPERACIONES`. Y el kit de vigilantes de lo
que un servidor publica —la foto, el peso, los topes, las reglas y los nombres fantasma— es `agentes.vigilancia`.
"""
from __future__ import annotations

from .catalogo import MIRA, PERFILES, Catalogo, CatalogoInvalido, Ficha, Herramienta, Retirada, Riesgo, nombre_valido
from .del_motor import DEL_MOTOR, catalogo_del_motor
from .despacho import SIN_VALOR, EntradaInvalida, operacion_del_modo, recortar, solo_los_de_su_modo

__all__ = ["DEL_MOTOR", "MIRA", "PERFILES", "SIN_VALOR", "Catalogo", "CatalogoInvalido", "EntradaInvalida", "Ficha",
           "Herramienta", "Retirada", "Riesgo", "catalogo_del_motor", "nombre_valido", "operacion_del_modo",
           "recortar", "solo_los_de_su_modo"]
