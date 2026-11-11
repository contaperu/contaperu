"""La API del SIRE como funciones puras: armar la petición, leer el estado de un ticket, clasificar un error.

**El núcleo puede saber la URL; lo que no puede es llamarla.** Saber es un dato; llamar es entrada y salida. El
catálogo `datos/sunat/sire_api.json` describe las operaciones del SIRE —cuántas son lo dice él (`operaciones()`), y no
se escribe aquí: este párrafo decía «quince» cuando ya eran veinte— con su ruta, método, parámetros obligatorios,
código de proceso, el protocolo TUS, los tickets, los estados de un periodo, los límites y la tabla de errores, y su
propia nota lo dice: «esto NO es un cliente, es la descripción de una API ajena». Lo que faltaba no eran los datos: eran las
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
- `leer_resumen(datos, registro=…)` (15.8.0) lee lo que contesta `resumen`, medido el 10-nov-2026 en los dos libros:
  una fila por tipo de comprobante con sus importes, y el total.

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
from .peticiones import (TIPOS_DEL_REGISTRO_NO_DOMICILIADOS, CuerpoInvalido, cuerpo_para_quitar_no_domiciliados,
                         grada, peticion, verificado)
from .respuestas import COLUMNAS_DEL_RESUMEN, leer_casillas, leer_inconsistencias, leer_resumen
from .tickets import ESTADOS_DE_TICKET, estado_de_ticket

__all__ = ["CODIGOS_DE_LIBRO", "ESTADOS_DE_PERIODO", "ESTADOS_DE_TICKET", "GRADAS", "OPERACIONES", "SireRechaza",
           "TIPOS_DEL_REGISTRO_NO_DOMICILIADOS", "CuerpoInvalido", "clasificar_error", "cod_libro_de",
           "cuerpo_para_quitar_no_domiciliados", "estado_de_periodo", "estado_de_ticket", "grada", "leer_casillas",
           "leer_inconsistencias", "leer_resumen", "COLUMNAS_DEL_RESUMEN", "libros", "operaciones", "peticion", "sire_api", "verificado"]
