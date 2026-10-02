# 0023 · `anulada_por_nota`: la factura anulada no provisiona su detracción

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar + motor |
| **Versión** | `open-accounting` **1.0** (no sube: un campo opcional en la imputación). Avanza su tag |
| **Test** | `tests/test_detracciones.py::test_marcada_como_anulada_la_factura_no_provisiona_y_el_par_cuadra` |

## Motivación

El caso real, encontrado importando notas de crédito en un CONCAR de verdad (John, 2-oct-2026): **una factura de
compra con detracción da cinco líneas y su nota de crédito da tres, así que el par no cuadra.**

```
E001-209   631101 D 2900.00  principal      E001-13   631101 H 2900.00  principal
E001-209   401111 D  522.00  impuesto       E001-13   401111 H  522.00  impuesto
E001-209   421201 H 3422.00  tercero        E001-13   421201 D 3422.00  tercero
E001-209   421201 D  137.00  recorte                  ← sin contrapartida
999999999  421203 H  137.00  detraccion               ← sin contrapartida
```

La nota de crédito no lleva detracción —SUNAT no detrae una nota— así que revierte las tres líneas de la operación y
no las dos del depósito. Quedan 137 soles colgados, y **dicen algo falso**: que se le debe ese dinero al Banco de la
Nación por una factura anulada, un depósito que nunca se hizo.

## Fuente

Dos cosas distintas, y conviene separarlas.

**El hecho contable** —que una detracción provisionada de una factura anulada no es una obligación— no necesita
norma: es la propia definición del asiento provisional, que el motor ya documenta («la constancia no existe todavía al
provisionar», `asiento/motor.py`).

**Que SUNAT no lo dice, que es lo que obliga a que lo diga el contador, sí está medido.** Sobre un **SIRE RCE de
setiembre de 2026** presentado y aceptado (27 filas: 23 facturas y 4 notas de crédito), comparando las cuatro
facturas que tienen nota contra las otras diecinueve:

- **Ninguna de las 41 columnas las distingue.** Ni una.
- Los tres candidatos —**CAR SUNAT** (campo 4), **CAR original** (37) y **estado del comprobante** (40)— van
  **vacíos en las veintitrés**.
- El enlace existe **solo en la fila de la nota** (campos 28, 29, 30 y 32: fecha, tipo, serie y número del documento
  modificado), apuntando hacia atrás. La factura no se puede marcar sola.
- El **motivo del Catálogo 09** —cuyo `01` significa «anulación de la operación» del comprobante referenciado— **no
  viaja en el RCE**: `tipo_nota` llega vacío en las cuatro. Ese dato está en el XML de la factura electrónica.

El archivo vive solo en `privado/`, de lectura, y de él salen los conteos y nada más.

## Especificación

1. **Campo `anulada_por_nota` en la imputación**, booleano, opcional, de fábrica `false`: que esta factura de compra
   quedó anulada por una nota de crédito.
2. **Está en la IMPUTACIÓN y no en el comprobante**, y es lo que esta enmienda decide de verdad. El comprobante es lo
   que dice el papel, y una factura impresa no dice que más tarde se anulara —la misma frontera que
   `CAMPOS_DEL_SISTEMA` traza y que la [enmienda 0015](0015-estado-del-comprobante-en-sunat.md) defiende para
   `estado_sunat`—. La imputación es donde vive lo que decide el contador, y tiene el precedente exacto al lado:
   **`detraccion_codigo`** entró ahí porque SUNAT afirma que hay detracción y no dice cuál. Aquí es lo mismo, un paso
   más allá: SUNAT no dice nada.
3. **Lo único que cambia: la factura no emite sus dos líneas de detracción** —`recorte` y `detraccion`—. Las otras
   tres salen igual, porque su nota de crédito las revierte, y el par cuadra a cero.
4. **No cambia el registro.** El comprobante sigue entero en el que se declara a SUNAT, que necesita su fila. Es la
   doctrina que `sin_efecto_contable` ya tiene escrita: el asiento es una cosa y el registro es otra.
5. **La contradicción se para.** Marcada como anulada **y** con constancia de depósito de verdad —`nro_constancia`
   que no es el comodín y con su fecha, es decir `estado: PAGADO`—, el dinero salió: suprimir esas líneas esconderría
   un pago real. Los dos hechos no pueden ser los dos verdaderos y el motor no elige: falla diciendo cuál es el
   comprobante (`AnuladaConDeposito`). Es la primera falta del motor que **bloquea sin colgar de ningún requisito del
   destino**, porque no es que a un formato le falte un dato.
6. **El estado se deduce**, nunca se cree: de la constancia y de su fecha, no de lo que el bloque declare. Un
   productor no consigue que el motor se crea un depósito que no documentó.
7. **Y el motor avisa cuando puede deducirlo.** Si una nota de crédito del mismo lote referencia una factura y anula
   su **total exacto**, la factura recibe un aviso que nombra la nota. Es el primer cruce de dos comprobantes del
   motor. **Avisa y no decide**: una nota puede ser un descuento o una corrección, y una nota parcial no lo dispara.

## Qué NO hace

- **No decide por su cuenta.** Sin el campo, el asiento sale exactamente como antes. El aviso informa; la marca
  manda.
- **No sube la versión del estándar.** Un campo opcional en la imputación es aditivo: un documento sin él significa
  lo mismo que antes. Avanza su tag.
- **No toca la nota de crédito**, que sigue dando sus tres líneas.
- **No resuelve la detracción ya depositada.** Anular una factura cuya detracción se depositó es contabilidad
  distinta —hay que recuperar el depósito— y no una línea de menos: se para, no se resuelve.
- **No mira el motivo del Catálogo 09.** El `01` dice que la nota anula el comprobante que referencia, pero el RCE no
  lo trae y el repositorio ya tiene escrito que en un mes real cinco notas con motivo `01` estaban vivas y con
  importes. Entraría con su propio caso.

## Qué rompe

**Nada.** El campo es opcional y de fábrica `false`; sin él todo sale como antes, y hay test de eso. Las huellas no se
mueven: la marca es de la imputación y no de la línea.

Lo que sí cambia, para quien lo use: el asiento de esa factura pasa de cinco líneas a tres, que es el objeto del
cambio.

## Lo que se aprendió por el camino

- **Un enlace de una sola dirección no se puede leer desde el otro lado.** Parecía que bastaría buscar la columna
  adecuada del RCE; no hay ninguna, y eso solo se supo comparando las cuatro facturas con nota contra las otras
  diecinueve, campo por campo. La pregunta correcta la hizo John: «¿y cómo va a saber el contador que la factura que
  está ingresando tiene NC?».
- **Pedirle al documento que diga de más es peor que pedirle al contador que decida.** La tentación era deducirlo del
  importe y aplicarlo solo; se quedó en aviso, porque una nota de crédito que anula el total puede seguir siendo un
  descuento total y no una anulación.
- **Una guarda puede valer más que la función que guarda.** La supresión es una línea; lo que la hace segura es
  negarse cuando la detracción ya se depositó.
