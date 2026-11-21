# 0035 · El `comprobante` de una parte del reparto: una 42 se lleva por documento

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | **aditiva**: una parte del `reparto` gana un bloque opcional, `comprobante`. Quien no lo use escribe y lee exactamente lo de antes, y un documento 4.1 vale igual |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 4.2 |
| **Test** | `tests/test_pago_de_facturas.py` (la línea de cada parte con el documento de su factura, la del banco con el vóucher, y la validación del bloque) y los casos de `estandar/conformidad/esquema.json` |

## Motivación

Pagarle a un proveedor es revertir su 42 contra el banco: DEBE la cuenta por pagar, HABER la 104. El motor lo arma
desde la 12.9, y la contrapartida llega en la imputación del movimiento —una cuenta, o un `reparto` cuando un cargo
paga varias facturas—. Pero la línea de cada parte llevaba **el documento del vóucher** (enmienda
[0032](0032-el-documento-de-una-linea-de-tesoreria.md)), y eso basta para un gasto y no para una cuenta por pagar:

- **Una 42 se lleva por documento.** En CONCAR la cuenta corriente del proveedor casa la provisión de la compra con
  su pago por el tipo, la serie y el número de la factura. Una 42 que lleva el vóucher del banco no cancela nada:
  deja la factura abierta y el pago como un saldo suelto.
- **Lo medido en un pago real** que un CONCAR aceptó (sub-diario de bancos, 21-nov-2026): cada línea del proveedor
  lleva SU factura —tipo, serie-número, fecha de emisión y vencimiento—, una por documento y nunca agrupada por
  proveedor aunque se paguen varias del mismo, y solo la línea del banco lleva el vóucher.
- **`movimiento.referencias[]` no sirve para esto**, y la razón es de fondo: dice lo que el PAPEL afirma que se
  cancela —un hecho del banco—, mientras que qué factura paga cada parte es una decisión de quien arma el pago, la
  misma clase de dato que la cuenta. Por eso va al lado de la cuenta, en la parte, y no en el movimiento.

## Fuente

- El dato es de quien arma el pago, y el precedente es la propia imputación: la cuenta de un gasto llega en ella
  desde la 1.0 porque el papel no la dice, y la factura que cancela una parte, tampoco.
- Para nombrar el comprobante, **la 4-tupla con la que ya lo nombra una referencia de clase `comprobante`**
  (`tipo_cp`, `serie`, `numero`, `contraparte_doc`), más las dos fechas que la línea de su compra ya lleva. No se
  inventa una forma nueva de decir qué factura es.
- Para la cuenta corriente por documento: el pago real aceptado por CONCAR que se midió columna a columna (fuera del
  repositorio: son datos reales de un contribuyente), y el plan de cuentas, donde la 42 es «Cuentas por pagar
  comerciales — Terceros», un saldo con cada proveedor que se compone de documentos.

## Especificación

Dentro de `imputaciones_de_movimientos.<id>.reparto[]`, cada parte admite:

| Campo | Qué lleva |
|---|---|
| `comprobante.tipo_cp` | **obligatorio**: el tipo de la Tabla 10 |
| `comprobante.numero` | **obligatorio** |
| `comprobante.serie` | la serie, si la tiene |
| `comprobante.contraparte_doc` | el documento del tercero. Si la parte trae el suyo, **tienen que ser el mismo** |
| `comprobante.fecha_emision` | AAAA-MM-DD |
| `comprobante.fecha_vencimiento` | AAAA-MM-DD; sin ella, la emisión |

Nada más: una clave que no sea de éstas se rechaza nombrándola, y el importe es el de la parte.

Y lo que cambia en el asiento: **la línea de una parte con `comprobante` lleva en `linea.documento` el de esa
factura** —`tipo_cp`, `serie_numero` escrito con la misma regla de ceros que la línea de su compra, `fecha_emision` y
`fecha_vencimiento`— en vez del vóucher; su `contraparte_doc` cae al del comprobante si la parte no lo trae. La línea
del banco sigue con el documento del vóucher, como dice la 0032, y una parte sin `comprobante` también.

Cuánto poner en cada parte no lo dice el estándar sino el motor: `api.por_pagar` da, de cada compra, la cuenta del
proveedor y lo que la compra le dejó en ella —el total menos la retención de 4ta y la detracción—, con la misma regla
que su asiento, para que el pago cancele exactamente lo que la compra provisionó.

**Quien no conozca esto no se rompe**: el bloque es opcional, y un productor que reparta sin él escribe y recibe
exactamente lo de antes.
