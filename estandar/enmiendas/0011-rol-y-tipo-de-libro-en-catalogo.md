# 0011 · `rol` y `libro.tipo` salen del esquema a catálogos publicados

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | cambio de significado (sube a 1.0) |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 1.0 |
| **Test** | `tests/test_vocabulario.py::test_el_esquema_ya_no_los_enumera` |

## Motivación

Los dos eran **enums cerrados dentro del esquema**, así que cualquier valor nuevo costaba una
versión del estándar. Es lo que hizo caer la propuesta del libro de honorarios, y es lo que le pasaría a los roles del
banco o de las letras de cambio el día que entren.

Y estaban **repetidos**: `ROLES` en `asiento/motor.py` y `TIPOS_LIBRO` en `modelo.py`, sin ningún test que comparara
las copias con el enum del esquema.

## Fuente

`API-DE-REGISTRO.md`, «El papel de cada línea». ISO 20022 saca sus códigos a catálogos externos «para
añadir sin cambiar la versión del mensaje»; los tipos de documento de EN 16931 (`BT-3`) viven en una lista mantenida
aparte de la norma; el SAF-T noruego terminó sacando la clasificación del esquema a una tabla.

## Especificación

`linea.rol` y `libro.tipo` pasan de `enum` a `type: string`, validados contra
[`catalogos.json`](../catalogos.json), publicado junto al esquema y citable por la URL del tag. Los valores no cambian:
los seis roles de compras y ventas y los dos tipos de libro.

**Y no degradan igual.** Un `rol` desconocido no rompe el documento: se contabiliza con `clase`, `debe_haber` e
`importe`. Un `libro.tipo` desconocido **sigue siendo un error** —quien recibe un registro que no conoce no puede
adivinar qué hacer con él—, y lo rechaza el modelo, no el esquema; quien degrada es el destino, con el driver que no lo
declara en sus `FORMATOS` rechazándolo limpio.

De aquí sale la **regla de versionado en tres niveles** del estándar: un valor de catálogo no sube la versión, un
bloque opcional tampoco, y solo cambiar lo que ya existe la sube.
