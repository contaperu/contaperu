"""La API del SIRE como funciones puras: armar la petición, leer el estado de un ticket, clasificar un error.

**El núcleo puede saber la URL; lo que no puede es llamarla.** Saber es un dato; llamar es entrada y salida. El
catálogo `datos/sunat/sire_api.json` describe las once operaciones desde el 21-sep-2026 —ruta, método, parámetros
obligatorios, código de proceso, el protocolo TUS, los tickets, los límites y la tabla de errores—, y su propia nota
lo dice: «esto NO es un cliente, es la descripción de una API ajena». Lo que faltaba no eran los datos: eran las
funciones que los usan, probadas. Eso es este paquete.

Quien envía es otro, y el reparto es el mismo de siempre: el motor sabe **qué dice** el SIRE y quien lo integra sabe
**cómo viaja** — el socket, los reintentos, el reloj del ticket, el almacén de credenciales. Y las credenciales no
cruzan nunca: el token viaja con quien envía, no por aquí. Ni se guarda, ni se pide, ni se nombra.

## Lo que hay aquí, y lo que todavía no

Está lo que **el catálogo sostiene con su fuente**, que es verificable sin red y sin una sola respuesta real:

- `peticion(operacion, …)` — el método, la URL y los parámetros de cada una de las once, validando lo obligatorio.
- `estado_de_ticket(codigo)` — qué significa un código de estado y si hay que seguir sondeando.
- `clasificar_error(cod, errores)` — el 422 de SUNAT, con su trampa, y si lo que llegó es idempotente o reintentable.

**No está el lector de la forma de cada respuesta**, y es a propósito. Eso no lo sostiene el catálogo: lo sostendría
una respuesta real, y hoy no hay ninguna guardada. Ni en este repositorio ni en la aplicación, cuyo catálogo tiene un
campo `verificado` —«la fecha en que se comprobó EN VIVO contra producción»— vacío en las doce operaciones del SIRE.
Los lectores que la aplicación usa en producción están escritos contra el manual, y traerlos aquí tal cual no
rompería nada: **congelaría un mapeo no comprobado en el repositorio abierto**, con la solidez aparente que da estar
en un motor con tests. Primero la evidencia, después la mudanza.

## Por qué el SIRE no tiene ambiente de pruebas, y qué se hace entonces

Lo dice el catálogo (`limites.ambiente_de_pruebas`): «NO EXISTE para el SIRE. El e-beta de SUNAT es solo para probar
estructuras XML de comprobantes. Toda prueba del SIRE es contra producción con un RUC real: conviene empezar por las
lecturas, que son idempotentes, y no escribir nada sin un acto explícito». De ahí el `grada` de cada operación —siete
de lectura, dos de escritura, dos declarativas—, que no es una anotación: es lo que decide con qué cuidado se la
llama. `grada(operacion)` lo publica para que quien envíe pueda negarse solo.
"""
from __future__ import annotations

from .catalogo import (CODIGOS_DE_LIBRO, GRADAS, OPERACIONES, cod_libro_de, libros, operaciones, sire_api)
from .errores import SireRechaza, clasificar_error
from .peticiones import grada, peticion
from .tickets import ESTADOS_DE_TICKET, estado_de_ticket

__all__ = ["CODIGOS_DE_LIBRO", "ESTADOS_DE_TICKET", "GRADAS", "OPERACIONES", "SireRechaza", "clasificar_error",
           "cod_libro_de", "estado_de_ticket", "grada", "libros", "operaciones", "peticion", "sire_api"]
