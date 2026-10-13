# 0031 · `aplicaciones[]`: cuánto de esto cancela aquello

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | **aditivo**: un bloque opcional nuevo en la raíz. Un documento 3.2 sigue valiendo tal cual |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 3.3 |
| **Test** | `tests/test_aplicaciones.py` (las dos caras, las clases que caben en cada una, lo que `propuesto` significa, y el aviso de lo que no está en el documento) y `estandar/conformidad/esquema.json` (una aplicación de cada clase y sus negativos) |

## Motivación

**Los tres libros del motor son islas.** `libro.tipo` vale `compra`, `venta` o `tesoreria`, y lo único que los une
es `movimiento.referencias`, que va en una sola dirección —del dinero al comprobante— y cuyo `importe` es
opcional. Con eso no se puede contestar la pregunta que llega siempre: **si una factura está por cobrar o
cobrada**. Y hay tres enlaces más que existen a medias y que nadie recorre:

| El enlace | Está | Se recorre |
|---|---|---|
| Una nota de crédito nombra su factura (`ref_tipo_cp`, `ref_serie`, `ref_numero`) | **sí**, lo trae el documento | **no**: `anulada_por_nota` es una marca que pone el contador a mano, porque «solo la nota apunta hacia atrás» |
| Un movimiento nombra lo que cancela (`referencias`) | **sí**, cerrado desde la 3.0 | **no**: nadie lo puebla, y su importe es opcional |
| La línea del asiento nombra su documento (`documento{}`) | **sí**, en una dirección | la vuelta es la [enmienda 0001](0001-id-en-destino.md), `reservada` |

Y el caso real que lo destraba **no hay que inventarlo: ya está en producción, fuera del motor.** La aplicación
que integra ContaPerú lo resolvió sola, y lo dice en su propia superficie: *«`pendiente` se DERIVA: es el total
menos lo que otros pagos dicen cancelar. No hay columna de estado»*, y *«lo que convierte una candidata en un
hecho es que una persona la elija»*. O sea: **la derivación y la frontera hecho/conjetura están implementadas allá
porque el contrato del motor se detiene en `referencias`.** Esta enmienda trae el sustantivo a su sitio.

## Fuente

**La investigación del 12-oct-2026**, el cuarto escalón de [`REFERENCIAS.md`](../../REFERENCIAS.md): la aplicación
de un pago a un documento comparada en ocho sistemas. Todos modelan lo mismo, y de ahí salen las tres reglas que
esta enmienda obedece:

1. **La aplicación es un registro aparte con su importe**, no un campo del documento ni una marca. Es N a N: un
   pago cancela varias facturas y una factura la cancelan varios pagos. **Tres pagos para una factura son tres
   registros, y el tercero no es especial** — nada necesita saber cuál la cierra.
2. **Vive a nivel de línea**, no de documento: la línea de diario en Odoo (`account.partial.reconcile`), el
   `PaymentLine` en SAF-T, el *link* de la línea del pago en Codat.
3. **El saldo se deriva de la suma y no se guarda.** ERPNext no tiene columna de estado: suma importes con signo
   agrupados por `against_voucher`. GnuCash deriva de `gnc_lot_get_balance()`. Y Odoo escarmentó dos veces por
   tener un marcador al lado del número.

Y la fuente **interna** que decide la forma: el estándar ya hizo este mismo corte entre el hecho y la decisión,
dos veces. `movimiento` es lo que dice el papel y `imputaciones_de_movimientos` lo que decide el ERP
([enmiendas 0025](0025-una-sola-entrada-para-tesoreria.md) y [0027](0027-la-imputacion-de-un-movimiento.md)).
**`aplicaciones` es a `referencias` lo que `imputaciones_de_movimientos` es a `movimiento`.**

## Especificación

Un bloque nuevo en la raíz, `aplicaciones[]`, **opcional**. Cada entrada:

| Campo | Obligatorio | Qué es |
|---|---|---|
| `de` | **sí** | lo que paga: `{clase, datos}` con clase `movimiento` o `comprobante` |
| `a` | **sí** | lo que se cancela: `{clase, datos}` con clase `comprobante` o `tributo` |
| `importe` | **sí** | cuánto de `de` se aplica a `a`. Positivo, como todo importe del estándar |
| `moneda` | **sí** | ISO 4217. **Va aquí aunque esté en los documentos**, porque una aplicación puede nombrar un comprobante de otro mes que no viaja en este documento: tiene que bastarse |
| `fecha` | **sí** | cuándo se aplicó. Sin ella no se puede situar en el tiempo, y todo origen real la tiene: la del pago, la de la nota, el día en que alguien lo decidió |
| `origen` | **sí** | `declarado`, `manual` o `propuesto` |

Las **claves de `datos`** por clase son las mismas que ya valida `referencia_de_pago`, más la del dinero:

| clase | claves | Dónde cabe |
|---|---|---|
| `comprobante` | `tipo_cp`, `serie`, `numero`, `contraparte_doc` (la 4-tupla de `Comprobante.clave`) | en `de` y en `a` |
| `movimiento` | `id_externo` | solo en `de` |
| `tributo` | `codigo` (Catálogo 05), `periodo` | solo en `a` |

**`origen` es lo que convierte la doctrina en una regla comprobable.** `declarado` es lo que afirma el papel —una
constancia de detracción nombra su comprobante—; `manual` es lo que decidió una persona; `propuesto` es lo que
propuso `conciliar` y **nadie ha confirmado**. Y la regla: **una aplicación `propuesto` no cuenta para ningún
saldo.** Así «`conciliar` propone y nunca confirma» deja de ser un docstring y pasa a ser algo que un test puede
poner en rojo.

**Un comprobante de otro mes se nombra igual que uno de este**, y eso funciona porque `Comprobante.clave` **no
lleva el periodo a propósito**: un comprobante se anota una sola vez por RUC (el error 452 de SUNAT), así que la
misma identidad lo reconoce entre periodos. Es lo que hace posible una factura de enero pagada en marzo.

**Lo que nombra una aplicación no tiene que estar en el documento, y por eso no se exige.** Se **avisa**: el motor
dice cuáles nombran algo que no viaja aquí, con el mismo trato que `CUENTA_BANCARIA_SIN_IDENTIFICADOR` —lo que
impide un paso posterior se dice, no se para—.

## Qué NO hace

- **No admite `libre` ni `cuenta_propia`**, que sí son clases de `referencia_de_pago`. Una aplicación existe para
  reducir un saldo, y solo un documento o un tributo tiene saldo: contra un texto libre no se puede derivar nada,
  y un traspaso entre cuentas propias no cancela nada —ya se declara en `imputacion.cuenta_propia`—.
- **No retira `movimiento.referencias`.** Siguen siendo lo que el papel afirma, y son la fuente de la que
  `conciliar` partirá. Las dos cosas conviven por lo mismo que conviven `movimiento` y su imputación.
- **No lleva glosa.** La del libro vive en la imputación del movimiento ([enmienda 0029](0029-la-glosa-de-un-movimiento.md)), y
  el motor todavía no arma el asiento de tesorería: una glosa aquí sería una clave que nadie lee, que es
  exactamente lo que el contrato de drivers paró con `sub_diario_bancos`.
- **No lleva `id_externo` propio.** Nada va indexado por una aplicación, y el documento es una foto y no una base
  de datos. El día que algo necesite nombrarla, entra con su caso.
- **No suma nada.** Derivar el pendiente de un comprobante es la versión siguiente: esta enmienda cierra que el
  documento **pueda decirlo**.
- **No convierte monedas.** Dos aplicaciones en monedas distintas sobre el mismo comprobante no se suman: ninguna
  clave suma dos monedas, igual que en `resumen` desde la 3.4.0.
