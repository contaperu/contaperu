# 0004 · `medio_pago`: el código de medio de pago de SUNAT

| | |
|---|---|
| **Estado** | reservada |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | — |
| **Test** | — |

## Motivación

El registro de CONTASIS pide un medio de pago (`001` depósito en cuenta, y los demás de la tabla de
SUNAT).

**Falta una decisión antes que un caso:** hay que saber si es dato de **cada documento** —y entonces va en el
comprobante— o un valor del contribuyente que vale para todos, y entonces ya cabe en la configuración de su sección.

## Fuente

Tabla de medios de pago de SUNAT; el registro de CONTASIS (`docs/contasis/LEEME.md` de la aplicación).

## Especificación

Campo `medio_pago` en el comprobante, código de SUNAT en texto, opcional.
