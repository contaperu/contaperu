# 0021 · `contrapartida` y `tesoreria`: los dos papeles que el catálogo no sabía nombrar

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 1.0 (aditivo: no sube la versión, avanza el tag). El catálogo de roles pasa a su `1.1` |
| **Test** | `tests/test_vocabulario.py::test_el_motor_no_escribe_todos_los_roles_del_catalogo` |

## Motivación

El catálogo de roles tenía seis valores y los seis eran de compras y ventas, que son los libros que el motor genera.
Eso bastó mientras el estándar solo transportara lo que el motor produce. Pero el estándar se publica para que
**cualquier ERP** ponga su asiento en él, y un ERP asienta cosas que el motor no origina.

El caso real llegó el 1-oct-2026: **un Libro Diario 5.1 de un mes, presentado y aceptado por SUNAT con sus
constancias de recepción**. De sus 1 441 asientos, **595 no referencian ningún registro de compras ni de ventas**, y
sus cuentas dicen de qué son — `79` ×1486, `42` ×1326, `91` ×1087, `41` ×792, `10` ×360, `39` y `68` en la
depreciación. Cuatro familias: el asiento de destino, los pagos y cobranzas, la planilla y la depreciación.

Al intentar escribir cualquiera de esos asientos en el estándar aparecen **dos líneas que ningún rol sabe nombrar**:

- **La otra cara de un hecho que no se le debe a nadie.** En una depreciación, la `39` frente al gasto de la `68`; en
  un asiento de destino, la `79` frente a la cuenta del elemento 9. No es un `tercero` —nadie puede cobrarla— ni es el
  `principal`, que es el hecho mismo.
- **El dinero moviéndose.** La `10` al cobrar o al pagar. Tampoco es un `tercero`: el tercero es a quién se le paga, no
  de dónde sale.

Sin esos dos valores, quien produce un asiento de depreciación o de pago tiene que dejar su `rol` vacío. El documento
sigue siendo válido —`rol` no es obligatorio, y con `clase`, `debe_haber` e `importe` se contabiliza igual— pero el
destino pierde la única pista que le dice qué es cada línea sin conocer el plan de cuentas de esa empresa, que es
justo para lo que el `rol` existe.

## Fuente

**El rol es lo que este estándar aporta y no está en ninguna norma**, así que lo que una enmienda de rol necesita no
es una resolución sino un caso real (`estandar/LEEME.md`, «Quién gobierna los catálogos»). El caso es el libro
descrito arriba: un Libro Diario del formato 5.1 de la RS 234-2006, presentado y aceptado. El archivo vive solo en
`privado/`, de lectura, y no entra al repositorio; de él salen los conteos y nada más.

Para **`tesoreria`**, además, el catálogo que lo acompaña ya tiene su norma: la **Tabla 1 del Anexo 3 de la
RS 169-2015/SUNAT, «Tipo de medio de pago»**, los 22 códigos que entraron con la [enmienda 0004](0004-medio-de-pago.md)
y que viven en `contaperu/datos/sunat/catalogos.json`.

## Especificación

1. **Dos valores nuevos en el catálogo `roles`** de `estandar/catalogos.json`, que pasa a su versión `1.1`:
   - **`contrapartida`** — la otra cara de un hecho que no se le debe a nadie: la depreciación acumulada frente a su
     gasto, la cuenta de destino frente a la `79`, una provisión.
   - **`tesoreria`** — el dinero moviéndose: caja, banco o equivalente, al cobrar o al pagar.
2. **`medio_pago` baja del comprobante a la línea**, opcional, con el mismo patrón de tres dígitos
   (`"^$|^[0-9]{3}$"`) y el mismo catálogo que ya usa en el comprobante. Es de la línea de rol `tesoreria`: el
   comprobante dice con qué se paga la operación y la línea dice con qué se movió el dinero. Completa el bloque que
   abrió la 0004, que dejó el catálogo publicado y la línea sin él.
3. **`medio_pago` NO entra en la huella del asiento** (`asiento/huella.py`, `SIN`). Es la promesa que la 0004 escribió
   al entrar —«el medio de pago no cambia ningún asiento ni ningún importe»— y que hasta hoy se cumplía sola porque el
   campo vivía en la `Cabecera`, que no se hashea. En la línea hay que declararlo.
4. **El motor no emite ninguno de los dos.** Genera compras y ventas, y de un comprobante no sale ni una depreciación
   ni un pago. Son vocabulario para quien produce ese asiento. La distinción queda en el código con dos nombres:
   `asiento.ROLES` es lo que un driver tiene que **entender** —los ocho— y `asiento.ROLES_DEL_MOTOR` lo que el motor
   **escribe** —los seis—.
5. **Quien no conozca un rol nuevo no se rompe**: lo contabiliza con `clase`, `debe_haber` e `importe`, que es la regla
   de degradación que permite que este catálogo crezca sin tocar la versión del documento.

## Qué NO hace

- **No toca el esquema del comprobante ni el de la imputación**, y en la línea solo añade un campo opcional. La versión
  del estándar **no se mueve**: avanza su tag.
- **No marca `igv` ni `retencion_4ta` como reemplazados**, aunque el modelo al que va este catálogo los sustituya (ver
  abajo). Son lo que el motor escribe en cada asiento, y marcarlos hoy diría a quien integra que no use justo lo que
  recibe en todos los documentos.
- **No mueve ninguna huella.** Lo comprobado: las tres literales de `tests/test_huella.py`, las del snapshot del
  documento y el Excel de CONCAR celda a celda siguen idénticos.
- **No añade `recorte`, `impuesto` ni `retencion`.** Ver abajo.

## Qué rompe

**Nada.** Ningún valor se quita, ninguno cambia de significado, ningún campo pasa a ser obligatorio y el motor emite
exactamente las mismas líneas que antes. Un documento de ayer vale hoy y significa lo mismo.

## Hacia dónde va el catálogo, dicho a propósito

> **Esto ya pasó.** Lo de abajo se escribió el 1-oct-2026 anunciando tres renombrados, y los tres entraron ese mismo
> día con la 5.0: [enmienda 0022](0022-el-tributo-en-su-bloque.md). Se deja tal cual, porque es el registro de lo que
> se sabía al escribir esta enmienda.

Para que quien integre no se lo encuentre de golpe. El principio al que va este catálogo es **un rol dice qué hace la
línea; el tributo, cuando lo hay, va en su bloque** — que es lo que `detraccion` ya hace con su código y su tasa, y lo
que `igv` y `retencion_4ta` no hacen porque meten el tributo en el nombre. El modelo completo son siete papeles:
`principal`, `tercero`, `recorte`, `contrapartida`, `tesoreria`, `impuesto` y `retencion`.

Faltan tres, y no han entrado por dos motivos que conviene dejar escritos:

- **Un rol genérico no entra antes que el catálogo que lo hace genérico.** `retencion` sin el código de su tributo no
  puede decir «de 4ta»: sería *peor* que `retencion_4ta`, y un valor publicado no se retira nunca. Y para `impuesto`
  hace falta que el **Catálogo 05** entre antes como catálogo con su fuente — hoy son nueve constantes sueltas de
  `catalogos.py`, que solo consume el lector de XML. *(Esta enmienda decía «tres constantes sueltas del lector de XML»:
  eran nueve y no viven en el lector. Corregido al contarlas de verdad en la 5.0.)*
- **Los tres son renombrados, e invalidan todas las huellas guardadas.** Así que entran los tres a la vez, con el motor
  adoptándolos, en una versión mayor. Moverlas dos veces sería el doble de daño por el mismo beneficio.
