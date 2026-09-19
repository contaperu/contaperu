# 0003 · `linea.estado`: en qué punto del circuito está esa línea

| | |
|---|---|
| **Estado** | reservada |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | — |
| **Test** | — |

## Motivación

Una línea propuesta, una exportada y una que el destino ya importó son tres cosas distintas, y hoy el
documento no las distingue.

**Falta el caso real:** el motor nunca escribiría `importado` —no tiene estado ni sale a preguntar—, así que el campo
solo sirve cuando exista un sistema que lo mantenga.

## Fuente

`REFERENCIAS.md`: el `status` de Merge y Codat, y el `approvalStatus` de NetSuite.

## Especificación

Campo `estado` en la línea: `propuesto | exportado | importado | anulado`, opcional.

**Ojo al nombre, que ya significa otras dos cosas:** `estado` existe en el comprobante (`ok | observada | duplicada`,
que es validación) y en la detracción (`PROVISIONADO | PAGADO`, que son sus dos tiempos). Si esta enmienda entra, su
especificación tiene que nombrar las tres.
