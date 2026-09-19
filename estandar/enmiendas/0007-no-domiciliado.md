# 0007 · `no_domiciliado`: el comprobante que emite un sujeto sin domicilio en el Perú

| | |
|---|---|
| **Estado** | reservada |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | — |
| **Test** | — |

## Motivación

Un proveedor del exterior no emite un comprobante de la Tabla 10: emite su propio documento, y el
registro necesita su número.

**Falta el caso real:** el registro de CONTASIS lo pide, pero no hay todavía un mes real con no domiciliados que haya
entrado a un sistema de destino.

## Fuente

El registro de CONTASIS; el registro de compras de SUNAT para operaciones con no domiciliados.

## Especificación

Campo `no_domiciliado` en el comprobante, texto, opcional: el número del comprobante del exterior.
