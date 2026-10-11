"""Cómo se deprecia algo en este motor: una clase de aviso, una función que avisa y la versión en que se retira.

**La 10.0 lo dejó en eso.** Hasta aquí traía además la maquinaria de las rutas de módulo de la 0.x —`resolver`,
`reexportar` y `funcion_obsoleta`—, con cero usuarios desde que la 7.0 retiró las últimas, y la 10.0 la borró con el
resto del andamio. Lo que queda no es andamio sino **protocolo**, y está publicado: el `pyproject.toml` de este
repositorio apunta aquí su `filterwarnings`, `INTEGRAR.md` le dice a quien integra que corra su batería con
`-W error::contaperu._obsoleto.RutaObsoleta`, y la aplicación lo hace. `RutaObsoleta` es parte de la API pública —se
filtra con precisión, sin apagar los avisos de nadie más—:

    warnings.filterwarnings("ignore", category=contaperu.RutaObsoleta)

Si hace falta que un nombre que cambia siga resolviendo, el `__getattr__` de módulo que lo hace son seis líneas y se
escribe entonces, en el módulo que se mueve: es la regla 1 aplicada a nuestras propias herramientas. La decisión que
conviene no perder al escribirlo es la que esa maquinaria tenía dentro: **el aviso sale al USAR la ruta vieja, no al
importar el módulo**, para que un `import` en el arranque de una aplicación no ensucie su registro.

Y la otra:

- **`RETIRO` dice en qué versión desaparece**, y va en el mensaje. Lo que se deprecie ahora se retira en la 10.0, que
  es lo que promete `CLAUDE.md`: lo que se retira avisa durante toda la mayor anterior. **Se mueve con cada mayor que
  cumple lo prometido**, y la 4.0 cumplió: retiró el alias `asiento_neutral`, que era lo único que quedaba avisando.
  Decía «3.0» con el paquete ya en la 3.8, así que el aviso citaba una versión pasada — una promesa de retiro no puede
  sostener nada si el número que da ya quedó atrás, y de ahí sale esta regla. La 5.0 lo movió a la 6.0 sin retirar
  nada, porque llegó sin nadie avisando. Y la 6.0 **volvió a caer en lo mismo**: salió sin moverlo, así que durante
  toda la 6.x este módulo prometía un retiro en «la 6.0», que ya era la versión en curso. Nada lo vigilaba —el único
  test que lo tocaba lo interpolaba en el mensaje que comprobaba—, de modo que la regla de arriba no la hacía cumplir
  nadie. **Desde la 6.2.0 sí**: `tests/test_version.py` exige que `RETIRO` sea mayor que la versión del paquete, y es
  el test que ha movido este número en la 7.0, la 8.0 y la 9.0 — las tres veces en rojo primero, que es su trabajo.

  La 7.0 fue la última que **cumplió** algo: retiró los seis atajos de la raíz que la 6.4.0 había dejado avisando. De
  la 8.0 y la 9.0 este módulo salió vacío, y de la 9.0 hay que decir por qué, porque rompió sin pasar por aquí: el
  parámetro `es_venta` de veinte funciones no se depreció en ninguna 8.x, se sustituyó de golpe. Era deliberado —un
  puente que siguiera aceptando el booleano mantendría vivo justo el camino que la mayor viene a cerrar— y se pudo
  hacer porque el único consumidor fija su versión y es de la casa. **No convierte eso en costumbre**: lo que
  pueda avisar, avisa, y para eso está este módulo.

  Y no se confunda con los **valores de catálogo** marcados obsoletos (`estandar/catalogos.json`, `obsoletos`), que la
  5.0 trae y que **no tienen retiro ninguno**: un nombre de Python obsoleto desaparece, un valor publicado del estándar
  no, porque los documentos ya guardados lo llevan dentro.
- **El texto del aviso no supone de qué clase es lo que cambió.** Nació para las rutas de la 0.x y lo decía en la
  cadena; ahora `que` lo dice quien llama, porque un nombre de driver no es una ruta de módulo.

La batería de este repositorio convierte el aviso en error (`[tool.pytest.ini_options] filterwarnings`), así que
ningún test usa una ruta vieja sin decirlo.
"""
from __future__ import annotations

import warnings

RETIRO = "11.0"


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
