# 0014 · `tipo_nota`: por qué se emitió una nota de crédito o de débito

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 1.0 (aditivo: no sube la versión, avanza el tag) |
| **Test** | `tests/test_catalogos.py::test_el_catalogo_de_una_nota_lo_elige_su_tipo_de_comprobante` |

## Motivación

El dato **ya entraba al motor y se tiraba**. El lector de XML lee `cac:DiscrepancyResponse/cbc:ResponseCode` desde la
1.x y lo dejaba en `datos_originales["motivo_nota"]["codigo"]`, la bolsa cruda que el núcleo transporta y nadie mira.
La propuesta del SIRE lo trae en su propia columna —«Tipo de Nota»— y el lector la descartaba: estaba incluso en el
fixture de pruebas del repositorio, el `09` de la fila `NOTA`, y se caía al leer.

Lo que no había era la otra mitad: **qué significa cada código**. Sin catálogo, el dato no se podía validar, ni
mostrar, ni pedir a un ERP, así que no había forma de que una aplicación dijera «esta nota es un descuento global» y
otra «esta anula la factura».

## Fuente

El campo lo definen los dos anexos del SIRE, y los dos **citan el mismo catálogo en vez de tener uno propio**:

- **Campo 34 del Anexo N.° 2 de la RS 112-2021/SUNAT** (propuesta del RVIE, ventas): «Tipo de Nota de Crédito o Nota
  de Débito. De acuerdo con el catálogo No. 09 y 10 del Anexo 8 de la Resolución de Superintendencia 097-2012/SUNAT y
  normas modificatorias». Longitud 2, **numérico**.
- **Campo 39 del Anexo 8 de la RS 040-2022/SUNAT, §8.4** (propuesta del RCE, compras): el mismo texto. Longitud 2,
  **alfanumérico**.

Y el catálogo en sí es de la factura electrónica, el `cbc:ResponseCode` del XML:

- **Catálogo No. 09, «Códigos de tipo de nota de crédito electrónica»**, 13 códigos, con el texto vigente del Anexo III
  de la RS 193-2020/SUNAT, que lo amplió desde 9:
  <https://www.sunat.gob.pe/legislacion/superin/2020/anexo3-193-2020.pdf>
- **Catálogo No. 10, «Códigos de Tipo de nota de débito electrónica»**, 3 códigos, republicado sin cambios por el
  Anexo V de la RS 318-2017/SUNAT: <https://www.sunat.gob.pe/legislacion/superin/2017/anexosV-318-2017.pdf>

Las dos tablas viajan en el motor (`catalogos.MOTIVOS_NOTA_CREDITO` y `MOTIVOS_NOTA_DEBITO`, y en `catalogos_sunat`
por la API y por el recurso `contaperu://catalogos/sunat`), cada una con su fuente.

## Especificación

Campo **`tipo_nota` en el comprobante**, opcional: texto de hasta **dos caracteres**. El catálogo que le toca **lo
elige el tipo de comprobante**: el 09 para una nota de crédito (`07`, `87`) y el 10 para una de débito (`08`, `88`).
Vacío significa **que el documento no lo dice**, que es lo habitual.

**Son dos catálogos y no uno, y los códigos colisionan**: el `01` es «anulación de la operación» en el de crédito e
«intereses por mora» en el de débito. Juntarlos obligaría a inventar un prefijo, y un catálogo con códigos inventados
deja de ser el de SUNAT.

**Sin patrón numérico, a propósito.** Los dos anexos describen el mismo campo con formatos distintos —numérico en
ventas, alfanumérico en compras—, así que el estándar admite los dos y solo limita la longitud. El motor completa a
dos dígitos lo que llegue con uno (`"9"` → `"09"`), y **solo si es dígito**: no se le impone una forma que la norma no
pide.

**Un código que no esté en el catálogo no invalida el documento**: se avisa (`TIPO_NOTA_DESCONOCIDO`, nivel aviso) y
**el valor se respeta**. El motivo es el de siempre: SUNAT amplía estas tablas —al 09 le añadió cuatro códigos en
2020— y nadie debería quedarse sin cerrar su mes por un dato que no cambia ningún importe. Un comprobante que no es
nota y trae motivo también avisa (`TIPO_NOTA_NO_APLICA`), y tampoco se le borra el valor.

**Y no existe ningún `TIPO_NOTA_FALTA`.** Una nota sin motivo no es un defecto: la norma dice que el campo «no es
considerado para la construcción del archivo de texto (txt)», y el propio TXT que este motor genera manda esa columna
vacía. Avisar de su ausencia observaría un mes entero por un dato que el archivo no pide.

**No se escribe en el TXT del SIRE**, ni en ventas ni en compras. En ventas la regla es la citada arriba; en compras
la nota del Anexo 11 dice que los campos 38 al 41 «deberán mostrarse vacíos», y vacíos quiere decir vacíos. Un test
comprueba que dos comprobantes iguales, uno con motivo y otro sin él, producen la línea **byte a byte idéntica**.

Sí llega al driver en la cabecera del comprobante (`asiento.Cabecera.tipo_nota`), que es la regla de
`tests/test_cabecera.py`: es un hecho tributario del documento, y uno que no llegue ahí es uno que el próximo driver
descubre que se cayó por el camino.

## Lo que el `01` del Catálogo 09 NO dice

Dice que la nota **anula el comprobante que referencia**, no que la nota esté anulada. Es la confusión más fácil de
este campo y por eso queda escrita: **ninguna regla del motor lee `tipo_nota` para hablar de anulación**. En el
registro real con el que se hizo esta enmienda, las cinco notas con motivo `01` estaban vivas y con importes, y las
dos que SUNAT daba de baja llevaban motivo `09` («disminución en el valor»).
