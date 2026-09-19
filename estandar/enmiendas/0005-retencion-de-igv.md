# 0005 · `retencion_igv`: la retención del 3 % del régimen de retenciones

| | |
|---|---|
| **Estado** | reservada |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | — |
| **Test** | — |

## Motivación

Un agente de retención designado por SUNAT retiene el 3 % del IGV al pagar, y el XML lo trae. Sin el
campo, ese dato se pierde o viaja en `datos_originales`.

**Falta el caso real**, y hay que tener claro qué se espera de él: **no entra en ningún asiento** de compras ni de
ventas, tampoco en el neutral, porque no es un hecho del comprobante sino del pago. El campo existiría para
transportar el dato a quien sí lleve el asiento de tesorería, no para que el motor lo contabilice.

## Fuente

Régimen de Retenciones del IGV (SUNAT); el XML de la factura electrónica lo trae en `PaymentTerms`
`Retencion`.

## Especificación

Campo `retencion_igv` en el comprobante: `{porcentaje, monto}`, opcional.

**No es `retencion`**, que es la retención de renta de 4ta categoría que muestra un recibo por honorarios y que **sí**
entra al asiento con su rol. Confundirlas es un error contable, y por eso los dos nombres se separan.
