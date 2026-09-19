# 0002 · `dimensiones`: los ejes analíticos más allá del centro de costo

| | |
|---|---|
| **Estado** | reservada |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | — |
| **Test** | — |

## Motivación

El centro de costo es el primer eje analítico y hoy el único. Un ERP puede querer además el área, el
proyecto o la obra, y forzarlos dentro del centro de costo los pierde.

**Falta el caso real:** el CONTASIS de John no los usa, y la segunda columna de centro de costos de ese registro
resultó ser el **mismo** centro del documento en otra columna, no una dimensión distinta.

## Fuente

`REFERENCIAS.md`: Xero `Tracking[]` (dos ejes por línea), QuickBooks `ClassRef`, NetSuite departamento, clase y ubicación.

## Especificación

Campo `dimensiones` en el comprobante y en la línea: `[{tipo, codigo}]`, opcional. El `centro_costo` sigue
siendo el primer eje y no se mueve. Como son decisiones de cada entorno y no hechos del comprobante, la parte del
comprobante llegaría por la imputación.
