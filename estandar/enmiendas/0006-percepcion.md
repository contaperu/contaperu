# 0006 · `percepcion`: el régimen de percepciones del IGV

| | |
|---|---|
| **Estado** | reservada |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | — |
| **Test** | — |

## Motivación

En el régimen de percepciones el vendedor **cobra de más**: añade un porcentaje al comprador, que es un
pago a cuenta de su IGV. Pasa con los combustibles, con ciertas importaciones y con una lista de bienes.

**Falta el caso real.** Es el espejo de la retención y tiene el mismo problema para un modelo extranjero: el total que
cambia de manos no es el total de la operación.

## Fuente

Régimen de Percepciones del IGV (SUNAT).

## Especificación

Campo `percepcion` en el comprobante, opcional. Si entra, su rol en el asiento sería un valor nuevo del
catálogo de roles, que no sube la versión del estándar.

## Nota de la 2.0 del estándar (10-oct-2026)

La especificación de arriba dice que el papel de la percepción «sería un valor nuevo del catálogo de roles, que no
sube la versión del estándar». **Sigue siendo cierto y por otra razón**: desde la 2.0 el papel de una línea no es
un campo, se deriva de lo que trae. Así que lo que la percepción necesitaría no es un valor en un documento, sino
un tramo en la regla —y un tramo que la identifique por su propio bloque, como ya hacen el impuesto, la retención y
la detracción—. Eso tampoco sube la versión.
