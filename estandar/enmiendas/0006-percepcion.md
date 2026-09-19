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
