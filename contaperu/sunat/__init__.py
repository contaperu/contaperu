"""La API del SIRE como funciones puras: armar la petición, leer el estado de un ticket, clasificar un error.

**El núcleo puede saber la URL; lo que no puede es llamarla.** Saber es un dato; llamar es entrada y salida. El
catálogo `datos/sunat/sire_api.json` describe once operaciones desde el 21-sep-2026, doce desde el 01-nov-2026 y quince desde la 15.4.0 —las
inconsistencias por comprobante, su resumen y el reporte de casillas del 621, del manual; las dos primeras se
midieron en la 15.4.1 y la 15.4.2, que trajeron también el grupo de errores `sin_datos`—
—ruta, método, parámetros obligatorios, código de proceso, el protocolo TUS, los tickets, los estados de un periodo,
los límites y la tabla de errores—, y su propia nota
lo dice: «esto NO es un cliente, es la descripción de una API ajena». Lo que faltaba no eran los datos: eran las
funciones que los usan, probadas. Eso es este paquete.

Quien envía es otro, y el reparto es el mismo de siempre: el motor sabe **qué dice** el SIRE y quien lo integra sabe
**cómo viaja** — el socket, los reintentos, el reloj del ticket, el almacén de credenciales. Y las credenciales no
cruzan nunca: el token viaja con quien envía, no por aquí. Ni se guarda, ni se pide, ni se nombra.

## Lo que hay aquí, y lo que todavía no

Está lo que **el catálogo sostiene con su fuente**, que es verificable sin red y sin una sola respuesta real:

- `peticion(operacion, …)` — el método —el de su libro, si el catálogo lo da así—, la URL y los parámetros de cada una,
  validando lo obligatorio.
- `estado_de_ticket(codigo)` — qué significa un código de estado y si hay que seguir sondeando.
- `estado_de_periodo(codigo)` — si un mes ya se generó, o sea, si hay algo DECLARADO que bajar con `registro_pedir`.
- `verificado(operacion, registro=…)` — si esa operación se midió contra producción para ese libro, y cuándo. Lo
  declarado entró en ventas sin medir (15.2.0) y se midió el mismo día (15.2.1).
- `clasificar_error(cod, errores)` — el 422 de SUNAT, con su trampa, y si lo que llegó es idempotente o reintentable.

**Un lector de respuesta solo entra después de medir.** Escribirlo contra el manual congelaría un mapeo no comprobado
en el repositorio abierto, con la solidez aparente que da estar en un motor con tests: primero la evidencia, después la
mudanza. Las operaciones **`verificado`** —medidas contra producción, la fecha al lado— son la evidencia, y de ahí
salió lo que hay:

- `periodos` dio los códigos de `estado_de_periodo`, y `registro_pedir`, `excluidos` y `no_incluidos` traen formatos
  que `comprobantes.sire_txt` ya leía: no necesitan lector propio.
- `leer_inconsistencias(datos)` y `leer_casillas(datos)` (15.5.0) leen lo que contestan `inconsistencias_comprobante`
  y `casillas`, medidas el 01-nov-2026 en un mes sin presentar y en uno presentado. Las dos formas reales contradicen
  al manual, y el lector dice en su docstring cómo.

Lo medido era de un RUC real y no entra aquí: las pruebas usan archivos sintéticos con la misma forma.

## Por qué el SIRE no tiene ambiente de pruebas, y qué se hace entonces

Lo dice el catálogo (`limites.ambiente_de_pruebas`): «NO EXISTE para el SIRE. El e-beta de SUNAT es solo para probar
estructuras XML de comprobantes. Toda prueba del SIRE es contra producción con un RUC real: conviene empezar por las
lecturas, que son idempotentes, y no escribir nada sin un acto explícito». De ahí el `grada` de cada operación —ocho
de lectura, dos de escritura, dos declarativas—, que no es una anotación: es lo que decide con qué cuidado se la
llama. `grada(operacion)` lo publica para que quien envíe pueda negarse solo.
"""
from __future__ import annotations

from .catalogo import (CODIGOS_DE_LIBRO, GRADAS, OPERACIONES, cod_libro_de, libros, operaciones, sire_api)
from .errores import SireRechaza, clasificar_error
from .periodos import ESTADOS_DE_PERIODO, estado_de_periodo
from .peticiones import grada, peticion, verificado
from .respuestas import leer_casillas, leer_inconsistencias
from .tickets import ESTADOS_DE_TICKET, estado_de_ticket

__all__ = ["CODIGOS_DE_LIBRO", "ESTADOS_DE_PERIODO", "ESTADOS_DE_TICKET", "GRADAS", "OPERACIONES", "SireRechaza",
           "clasificar_error", "cod_libro_de", "estado_de_periodo", "estado_de_ticket", "grada", "leer_casillas",
           "leer_inconsistencias", "libros", "operaciones", "peticion", "sire_api", "verificado"]
