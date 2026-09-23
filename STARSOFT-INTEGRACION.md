# STARSOFT Desktop — notas para el driver

> **De qué STARSOFT habla este documento.** Del **de escritorio**, el que importa un archivo. Existe
> además **STARSOFT Web (Gold Edition)**, con **API pública**, y es otro driver: `starsoft_web`, el hito
> A5 de la hoja de ruta, que nadie ha escrito todavía. Casi todo lo que hay aquí le sirve —las siglas,
> los sub-diarios, el destino del IGV, las cuentas—; lo que cambia es a dónde van los datos.

> **Documento de trabajo, no especificación.** Recoge lo observado el 20-sep-2026 en dos vídeos del
> canal *ArchivoExcel*, leyendo sus capturas y su transcripción automática:
>
> - **[C] Compras** — «Importar asientos contables de compras al Star Soft», 22:25 · `youtube.com/watch?v=1HMTMsuQJAA`
> - **[V] Ventas** — «Importar asientos de ventas al Star Soft», 20:16 · `youtube.com/watch?v=iOq8Zh6avj8`
>
> **Desde el 22-sep-2026 la fuente es otra**, y está en la sección de abajo: la documentación de
> STARSOFT, con la tabla de campos y ejemplos de TXT del propio sistema. Lo de los vídeos y las capturas
> se conserva porque explica de dónde salió cada decisión, pero **donde se contradigan, manda el
> manual**. Y ya hay un archivo de este driver importado en STARSOFT (John, 22-sep-2026) — el que
> destapó las tres correcciones.
>
> Lo observado va con su minuto. Lo que sigue sin confirmar, **[por confirmar]**.

## La documentación oficial (22-sep-2026) — **la fuente**

Hasta hoy este documento recogía lo observado en dos vídeos y en capturas de la hoja `PLANTILLA` de
Excel. **Ahora hay documentación de STARSOFT**: «Sistema de Contabilidad · Documentación», en dos
archivos —`CONT_COMPRAS` y `CONT_VENTAS`— con la tabla de campos y, sobre todo, **ejemplos de TXT
sacados del propio sistema** (18 líneas en compras, 12 en ventas).

**Los PDF no están en el repositorio** —son de otra empresa y esto es público y MIT—: están en el
`.gitignore`, y lo que entra es lo que dicen, que es esta sección.

### La regla que la hoja de Excel escondía

**El número del ítem en el manual NO es su posición en la línea del TXT.** Varias columnas dependen de
un «concepto general» de cada instalación, y el manual dice, literal:

> Para las columnas que se habilitan con un concepto general: si el concepto esta en falso, **no
> incluir la columna**.

O sea que no ocupan sitio. La hoja de Excel las tiene todas —por eso las capturas las mostraban— pero
el archivo no. De ahí que el driver escribiera **38 campos en compras y 34 en ventas** cuando los
ejemplos oficiales traen **35 y 27**. Van marcadas abajo.

Lo demás que dicen los «Datos generales»: separador `|`, **un enter al final de la última fila**,
codificación ANSI, **sin ningún TAB**, todo alineado a la izquierda, solo punto decimal, y el nombre
del archivo empieza por `C` en compras.

### Compras — 39 ítems, 35 escritos

| # | Campo | Long. | Oblig. | Qué dice el manual |
|---|---|---|---|---|
| 1 | **CUENTA CONTABLE** | Hasta 18 | Si | A ultimo nivel. Ejemplos del manual: 42120001, 40111000, 62010001 |
| 2 | **ANO Y MES DE PROCESO** | 6 | Si | AAAAMM. Todos los registros, del mismo periodo |
| 3 | **SUBDIARIO** | Hasta 2 | Si | Del mantenimiento de Subdiarios de Contabilidad |
| 4 | **COMPROBANTE** | 4 | Si | Correlativo de 4 digitos, **rellenando con ceros a la izquierda** |
| 5 | **FECHA DEL DOCUMENTO** | Hasta 10 | Si | **Menor o igual al campo 15 y debe corresponder al periodo** |
| 6 | **TIPO DE ANEXO** | Hasta 2 | No | Obligatorio si la cuenta tiene Tipo de Anexo. Proveedores: 03 |
| 7 | **CODIGO DEL PROVEEDOR** | Hasta 11 | No | Obligatorio si la cuenta tiene Tipo de Anexo y el anexo existe |
| 8 | **TIPO DE DOCUMENTO** | Hasta 2 | Si | **El que tiene registrado TU sistema** (FT, BV, NC...) |
| 9 | **SERIE Y NUMERO DEL DOCUMENTO** | Hasta 21 | Si | Los 4 primeros son la serie; si es de 3, un espacio en blanco y el numero desde la quinta |
| 10 | **FECHA DE VENCIMIENTO** | Hasta 10 | No | Si viene, mayor o igual al campo 5 |
| 11 | **IGV** | Hasta 18,2 | Si | **Solo si el campo 1 es una cuenta de Proveedores** |
| 12 | **TASA IGV** | Hasta 10,2 | Si | Valor fijo del IGV vigente (18) |
| 13 | **IMPORTE TOTAL DEL DOCUMENTO** | Hasta 18,2 | Si | En la cuenta de Proveedores, el total; en las demas, el importe de la cuenta |
| 14 | **TIPO DE CONVERSION DEL TIPO DE CAMBIO** | 3 | Si | **Puede ser VTA o ESP.** Sin distinguir por cuenta |
| 15 | **FECHA DE REGISTRO** | Hasta 10 | Si | **Debe corresponder al periodo informado** |
| 16 | **TIPO DE CAMBIO** | Hasta 10,3 | Si | Obligatorio si el campo 14 es ESP |
| 17 | **GLOSA** | Hasta 60 | No | **Hasta 60 caracteres** |
| 18 | **TIPO DE DESTINO DE LA COMPRA** | 3 | Si | 001 gravada . 002 mixta . 003 no gravada . 004 no gravadas . 005 importacion |
| 19 | **PORCENTAJE PARA OPERACIONES MIXTAS** | Hasta 18,2 | No | Solo con destino 002 |
| 20 | **VALOR CIF** | Hasta 18,2 | No | Solo con destino 005 |
| 21 | **TIPO DE DOCUMENTO DE REFERENCIA** | Hasta 2 | No | Obligatorio si el campo 8 es nota de credito o debito |
| 22 | **SERIE Y NUMERO DEL DOC. DE REFERENCIA** | Hasta 21 | No | Misma regla de serie que el campo 9 |
| 23 | **CENTRO DE COSTO** | Hasta 10 | No | Obligatorio si la cuenta lo tiene configurado |
| 24 | **AFECTO A DETRACCION** | 1 | No | 1 si lo es; si no, 0 o en blanco |
| 25 | **NUMERO DE DETRACCION** | Hasta 17 | No | Solo si esta afecto a detraccion |
| 26 | **FECHA DE DETRACCION** | Hasta 10 | No | Solo si esta afecto a detraccion |
| 27 | **FECHA DEL DOC. DE REFERENCIA** | Hasta 10 | No | Obligatorio si el campo 8 es nota de credito o debito |
| 28 | **GLOSA DEL MOVIMIENTO** | Hasta 60 | No |  |
| 29 | **DOC. ANULADO** | 1 | Si | Poner 0 o dejarlo en blanco |
| 30 | **IGV POR APLICAR** | 1 | No | 0 o 1 |
| 31 | **CODIGO DE LA DETRACCION** | 5 | No | Solo si esta afecto a detraccion |
| 32 | **IMPORTACION** | 1 | No | 0 o 1 |
| 33 | **DEBE O HABER** | 1 | Si | D o H |
| 34 | **TASA DE DETRACCION** | Hasta 18,2 | No | Solo si esta afecto a detraccion |
| 35 | **IMPORTE DE DETRACCION** | Hasta 18,2 | No | Solo si esta afecto a detraccion |
| 36 | **NRO. DE FILE** · **no se escribe** | Hasta 12 | No | solo si el concepto general `PERS_SETOURS` es verdadero |
| 37 | **OTROS TRIBUTOS** · **no se escribe** | Hasta 18,2 | No | solo si `DATOS_ADIC_COM_TXT` es verdadero |
| 38 | **IMP. A LA BOLSA DE PLASTICO** · **no se escribe** | Hasta 18,2 | No | solo con el check de impuesto a la bolsa. Y solo en la fila de la cuenta de proveedores (42) |
| 39 | **TIPO OPERACION DE DETRACCION** · **no se escribe** | 2 | No | solo si `IMPDX_TIPOPE_DETRAC` es verdadero |

### Ventas — 34 ítems, 27 escritos

| # | Campo | Long. | Oblig. | Qué dice el manual |
|---|---|---|---|---|
| 1 | **CUENTA CONTABLE** | Hasta 18 | Si | A ultimo nivel. Ejemplos del manual: 12120001, 40111000, 70410001 |
| 2 | **ANO Y MES PROCESO** | 6 | Si | AAAAMM |
| 3 | **SUBDIARIO** | Hasta 2 | Si |  |
| 4 | **COMPROBANTE** | 4 | Si | Correlativo de 4 digitos con ceros a la izquierda |
| 5 | **FECHA DE REGISTRO** | Hasta 10 | Si | **Debe corresponder al periodo informado** |
| 6 | **TIPO ANEXO** | Hasta 2 | No | Clientes: 02 |
| 7 | **CODIGO CLIENTE** | Hasta 11 | No |  |
| 8 | **TIPO DE DOCUMENTO** | Hasta 2 | Si | El que tiene registrado TU sistema |
| 9 | **NUMERO DE DOCUMENTO** | Hasta 21 | Si | 4 primeros la serie; si tiene 3, un espacio; **sin serie, cuatro espacios** |
| 10 | **NUM. DE DOC. FINAL** · **no se escribe** | Hasta 21 | No | solo si `DATOS_ADIC_VTAS_TXT` es verdadero. Para BV (03), TK (12) y codigo SUNAT 99 |
| 11 | **FECHA DE EMISION DEL DOCUMENTO** | Hasta 10 | Si | **Menor o igual al campo 5 y debe corresponder al periodo** |
| 12 | **DOCUMENTO DE REFERENCIA** | Hasta 2 | No | Obligatorio en nota de credito o debito |
| 13 | **NUMERO DE DOC. DE REFERENCIA** | Hasta 21 | No |  |
| 14 | **IGV** | Hasta 18,2 | Si | **Solo si el campo 1 es una cuenta de Clientes (12)**; en las demas, en blanco |
| 15 | **VALOR ISC** · **no se escribe** | Hasta 18,2 | No | solo si `MIGRA_ISC_TXT` es verdadero |
| 16 | **OTROS TRIBUTOS** · **no se escribe** | Hasta 18,2 | No | solo si `DATOS_ADIC_VTAS_TXT` es verdadero |
| 17 | **TASA DEL IGV** | Hasta 10,2 | Si | Solo en la cuenta de Clientes; valor fijo (18) |
| 18 | **IMPORTE** | Hasta 18,2 | Si | En Clientes, el total del documento; en las demas, el de la cuenta |
| 19 | **CONVERSION DE TIPO DE CAMBIO** | 3 | Si | VTA o ESP. En las demas cuentas **puede** estar en blanco |
| 20 | **TIPO DE CAMBIO** | Hasta 10,3 | Si | Obligatorio si el campo 19 es ESP |
| 21 | **GLOSA** | Hasta 60 | No | Hasta 60 caracteres |
| 22 | **GLOSA DE MOVIMIENTO** | Hasta 60 | No |  |
| 23 | **DOCUMENTO ANULADO** | 1 | Si | 0 no anulado . 1 anulado |
| 24 | **DEBE / HABER** | 1 | Si | D o H |
| 25 | **RUC DEL CLIENTE** | 11 | No | Solo si el campo 1 es una cuenta de Clientes |
| 26 | **RAZON SOCIAL DEL CLIENTE** | Hasta 50 | No | Idem |
| 27 | **CENTRO DE COSTO** | Hasta 10 | No | Si la cuenta lo tiene configurado |
| 28 | **FECHA DE VENCIMIENTO** | Hasta 10 | No | Si viene, mayor o igual al campo 11 |
| 29 | **FECHA DEL DOC. REFERENCIA** | Hasta 10 | No |  |
| 30 | **EXPORTACION** | 1 | Si | 0 local . 1 exportacion |
| 31 | **NRO. DE FILE** · **no se escribe** | Hasta 12 | No | solo si `PERS_SETOURS` es verdadero |
| 32 | **EXONERADO** · **no se escribe** | Hasta 18,2 | No | solo si `EXONERADO_TXT` es verdadero. Y solo en la fila de Clientes |
| 33 | **OTROS CARGOS** · **no se escribe** | Hasta 18,2 | No | solo si `OTROS_CARGOS_VTA` es verdadero. Y solo en la fila de Clientes |
| 34 | **IMP. A LA BOLSA DE PLASTICO** · **no se escribe** | Hasta 18,2 | No | solo con el check de impuesto a la bolsa. Y solo en la fila de Clientes |

### Las dos fechas, que estaban cruzadas

Es lo otro que el manual corrigió, y **solo se nota con un comprobante extemporáneo**. En compras el
campo 5 es la del DOCUMENTO —la emisión— y el 15 la de REGISTRO, que «debe corresponder al periodo»;
en ventas están al revés (5 registro, 11 emisión). Hasta la 2.3 el driver escribía la del asiento en la
del documento y la emisión en la de registro: con una factura de julio anotada en agosto, el campo 5
salía **mayor** que el 15 y el 15 **no era del periodo**, rompiendo las dos reglas a la vez. Dentro de
su propio mes las dos fechas coinciden y no se veía.

### Un asiento oficial, entero

El primero de los ejemplos del manual de compras — tres líneas, 35 campos:

```
40111000|202101|04|0001|06/01/21|03|PROV001|FT|001 000005||||85.42|VTA|06/01/21|2.807|FT  001-000005  /|001|0.00|0.00||||0||||EXAMENES MEDICOS|0|0||0|D|0.00|0.00
42120001|202101|04|0001|06/01/21|03|PROV001|FT|001 000005||85.42|18.00|560.00|VTA|06/01/21|2.807|FT  001-000005  /|001|0.00|0.00||||0||||EXAMENES MEDICOS|0|0||0|H|0.00|0.00
63920101|202101|04|0001|06/01/21|03|PROV001|FT|001 000005||||474.58|VTA|06/01/21|2.807|FT  001-000005  /|001|0.00|0.00|||070103|0||||EXAMENES MEDICOS|0|0||0|D|0.00|0.00
```

Tres cosas se leen ahí y zanjan otras tantas dudas: **`VTA` va en las tres líneas** y no solo en la del
proveedor; **el IGV y su tasa van solo en la del proveedor** (42120001); y la línea acaba en
`|D|0.00|0.00`, o sea **35 campos**.

### La detracción NO es un asiento: son campos de la fila del proveedor

**Una compra con detracción sale con las mismas TRES filas que una sin ella** (John, 22-sep-2026, contra
el manual). Los seis ejemplos oficiales llevan tres filas por comprobante y **ninguno tiene detracción**,
así que no hay uno que calcar; lo que lo zanja es la tabla de campos, donde la detracción ocupa seis:

| # | Campo | Qué lleva |
|---|---|---|
| 24 | AFECTO A DETRACCION | `1`. **Va en las tres filas**: es del comprobante, no de la línea |
| 25 | NUMERO DE DETRACCION | el del vóucher, o el **comodín `999999999`** mientras no se haya depositado |
| 26 | FECHA DE DETRACCION | la del depósito; **en blanco** si no consta — una fecha inventada es peor que ninguna |
| 31 | CODIGO DE LA DETRACCION | el del Catálogo 54 de SUNAT (`027`), no el interno de CONCAR (`02702`) |
| 34 | TASA DE DETRACCION | el porcentaje |
| 35 | IMPORTE DE DETRACCION | lo detraído, ya redondeado al sol por el núcleo |

Los cinco últimos van **solo en la fila del proveedor**, como el IGV y su tasa.

En CONCAR el traslado a la cuenta de detracciones son **dos líneas más** —el proveedor al debe y `421203`
al haber—, y hasta la 2.4 este driver las escribía porque proyectaba tal cual lo que el núcleo le daba.
STARSOFT no las quiere: registra el depósito por su cuenta. **Las líneas siguen existiendo en el asiento
del motor**, que es el mismo para todos los destinos; lo que cambia es lo que este driver proyecta
(`datos.ROLES_DE_LA_DETRACCION`).

`01 E001-871` · total 4956.00 · base 4200.00 · IGV 756.00 · detracción `027` al 4 % = 198.00, tal como lo
genera el motor:

```
40111000|202608|04|0001|10/08/2026|03|20602222226|FT|E00100000871|27/08/2026|||756.00|VTA|10/08/2026||FT E001-00000871 /|001|0.00|0.00||||1||||SERVICIO DE TRANSPORTE DE MATERIALES|0|0||0|D|0.00|0.00
42120001|202608|04|0001|10/08/2026|03|20602222226|FT|E00100000871|27/08/2026|756.00|18.00|4956.00|VTA|10/08/2026||FT E001-00000871 /|001|0.00|0.00||||1||||SERVICIO DE TRANSPORTE DE MATERIALES|0|0|027|0|H|4.00|198.00
62010001|202608|04|0001|10/08/2026|03|20602222226|FT|E00100000871|27/08/2026|||4200.00|VTA|10/08/2026||FT E001-00000871 /|001|0.00|0.00||||1||||SERVICIO DE TRANSPORTE DE MATERIALES|0|0||0|D|0.00|0.00
```

El asiento cuadra con esas tres: 756 + 4200 al debe contra 4956 al haber. Lo detraído no mueve cuentas.

### Cuatro detalles de forma que los ejemplos oficiales zanjaron (2.5)

Salieron de comparar nuestra línea con la del manual campo a campo, y los cuatro los decidió John el
22-sep-2026:

| Qué | Antes | Ahora |
|---|---|---|
| **El orden de las filas de una COMPRA** | gasto, IGV, proveedor (el del asiento del motor) | **IGV, proveedor, gasto**, el de sus dieciocho ejemplos. En VENTAS no cambia: sus doce van cliente, IGV, ingreso, que ya era el nuestro |
| **La columna `GLOSA`** (17 en compras) | el concepto, igual que `GLOSA MOVIMIENTO` | el **documento** (`FT E001-00000871 /`), con el concepto al lado. Es lo que hacen los treinta ejemplos; la decisión contraria del 21-sep-2026 queda revertida |
| **La tasa del IGV** | `18` | `18.00`, con dos decimales, en los dos libros |
| **Los importes que no aplican** en compras: `% mixtas`, `valor CIF`, `tasa` e `importe de detracción` | vacíos | `0.00`. **Solo en compras**: los ejemplos de ventas dejan los suyos en blanco |

Con eso, una fila nuestra es estructuralmente idéntica a una suya. La única diferencia que queda es el
campo 16, **tipo de cambio**: sus ejemplos lo traen siempre y nosotros solo cuando lo hay, porque el manual
lo exige únicamente si el campo 14 es `ESP`.

### Con qué cuentas nace una empresa que lleva STARSOFT

STARSOFT numera a **ocho dígitos**, y las de fábrica del motor son las del PCGE a seis (`configuracion.py`),
que es como numeran CONCAR y CONTASIS. Hasta la 2.5 eso no se podía decir por sistema: un contribuyente de
STARSOFT que no hubiera abierto la pantalla de configuración exportaba su asiento con el `421201` de CONCAR,
sin error en ninguna parte y con el archivo rechazado en la suya. Desde la 2.5 el driver las declara
(`datos.CUENTAS_POR_DEFECTO`), y se apilan en tres capas: fábrica, sistema, empresa.

**Cuatro constan en el manual** y las demás se **deducen** de su patrón: la subcuenta del PCGE de cuatro
dígitos más un correlativo de cuatro (`4212` → `42120001`); las de raíz de cinco —el IGV y la renta de 4ta,
que en el PCGE son `40111` y `40172`— completan con tres.

| Cuenta | PCGE (lo general) | STARSOFT | De dónde |
|---|---|---|---|
| Facturas por pagar PEN | 421201 | `42120001` | **manual** (compras, campo 1) |
| Facturas por pagar USD | 421202 | `42120002` | deducida |
| Detracciones por pagar | 421203 | `42120003` | deducida |
| Honorarios por pagar PEN | 424101 | `42410001` | deducida |
| Honorarios por pagar USD | 424102 | `42410002` | deducida |
| Renta de 4ta retenida | 401721 | `40172100` | deducida |
| IGV | 401111 | `40111000` | **manual** (los dos libros) |
| Clientes PEN | 121201 | `12120001` | **manual** (ventas, campo 1) |
| Clientes USD | 121202 | `12120002` | deducida |
| Ingreso por defecto | 701101 | `70410001` | **manual** (ventas, campo 1) |

**`gasto` no se declara, a propósito.** En lo general va vacía —es el comodín «63/65», que no es una
cuenta— y lo que trae el manual (`62010001`) es una cuenta de gasto real. Los propios ejemplos oficiales lo
demuestran: el asiento de arriba imputa a `63920101` y la tabla de campos pone `62010001`. Una cuenta de
gasto depende del comprobante, así que de respaldo imputaría en silencio toda compra a la que nadie le puso
cuenta. El comodín que evita que la exportación se bloquee es de la **aplicación**, que lo siembra y el
contador lo ve en su pantalla; un respaldo del motor actúa sin que nadie lo haya escrito.

⚠️ **Una discrepancia anotada, para que no reaparezca.** La cuenta de ingreso del manual es `70410001`, y
las capturas del aplicativo (los asientos típicos de ventas, más abajo) usan `70410100`. Manda el manual,
que es la fuente. Además la de ingreso varía con el tipo de venta —`70610100` exonerada, `70510100`
mixta—, así que es un punto de partida como el `701101` de lo general, no una regla.

## Lo esencial

1. STARSOFT ofrece **dos vías de carga, TXT y Excel**. **Se usa la del TXT** (John, 22-sep-2026), que el
   motor envuelve en un ZIP. Hasta ese día se había elegido la de Excel, y el driver escribía un CSV
   provisional mientras no se conocía la plantilla.
2. La plantilla la publica **el propio STARSOFT**; el aplicativo de los vídeos solo la rellena.
3. El asiento va **una fila por cuenta**, con el debe/haber en su propia columna.
4. **Máximo 4 cuentas contables por asiento** **[C 5:25]**.
5. El **tipo de asiento** (1-5) es **interno de la macro y NO viaja al archivo**. Lo que sí viaja, y
   es obligatorio, es el **`DESTINO`** (columna `R`): la clasificación del crédito fiscal.
6. **Las cuentas, los proveedores y los comprobantes tienen que existir ya en STARSOFT**, o la
   importación falla. El archivo no los crea.

## Las tres hojas del aplicativo

Definidas por John (20-sep-2026):

| Hoja | Qué es |
|---|---|
| `PARAMETROS` | **La configuración.** Los asientos típicos y las cuentas de cada uno: con esto se generan los asientos |
| `DATA` | **Donde el usuario pone los comprobantes, en filas.** Es la entrada |
| `PLANTILLA` | **Los asientos finales.** Es lo que hay que producir, y lo único que STARSOFT lee |

**Para el motor solo existe `PLANTILLA`**: `DATA` es lo que ya tiene en el documento
`open-accounting`, y `PARAMETROS` es lo que sería su configuración.

## Hoja `PARAMETROS` — andamiaje de la macro, NO del motor

> **Esta hoja no se traduce al driver.** Es la tabla con la que la macro de Excel averigua qué cuentas
> poner en cada asiento, y **nada de ella llega al archivo que STARSOFT importa**: en las columnas de
> `PLANTILLA` no hay ninguna de «tipo de asiento» (John, 20-sep-2026; verificado contra las columnas
> de los dos libros, más abajo). El motor de `contaperu` ya sabe distinguir una venta gravada de una
> exonerada, de una nota de crédito y de una mixta a partir del propio comprobante — que es justo lo
> que esta hoja le da a la macro, que no sabe contabilidad.
>
> Se documenta por dos motivos: **las cuentas** que usa sí son configuración del contribuyente, y
> **la glosa de 60 caracteres** es un límite real del formato — que desde la 2.6 se resuelve **cortando**
> al escribir, no deteniendo la exportación (John, 22-sep-2026).

**Estructura real, leída de la captura de `PARAMETROS` de ventas** (`P Ventas SS V0124.xlsm`):

| Col. | Cabecera | Qué lleva |
|---|---|---|
| A | `TIPO` | El código, 1-4 — **interno de la macro** |
| B | `TIPO ASIENTO` | La descripción: `VENTA DE MERCADERÍA`, `VENTA EXONERADA`… |
| C | `GLOSA DEL MOVIMIENTO` | **«Máximo 60 caracteres»**, escrito en la propia cabecera |
| D | `T. CONVERS` | `VTA` en las cuatro filas |
| E · F | `CUENTA` · `D/H` | **CTA ACTIVO** |
| G · H | `CUENTA2` · `D/H2` | **CTA INGRESO** |
| I · J | `CUENTA3` · `D/H3` | **CTA IGV** |
| K · L | `CUENTA4` · `D/H4` | **CTA NO GRAVAD** |

**Cuatro pares de (cuenta, debe/haber)** — de ahí sale el límite de 4 cuentas por asiento, y aquí se
ve el porqué: no hay columnas para una quinta. Las cuentas van **a 8 dígitos**.

**Aviso del vídeo [C 2:44-2:58]:** «las cuentas deben estar registradas en el sistema contable
STARSOFT; de lo contrario, al momento de hacer la carga va a generar un error en la importación».

### Los asientos típicos de compras — leídos de la captura (`P Compras SS V0124.xlsm`)

Misma estructura que ventas, con las cabeceras de rol cambiadas: **CTA PASIVO · CTA GTO/ACT · CTA IGV
· CTA NO GRAVAD**. Y **son cinco**, no cuatro:

| Tipo | Descripción | Glosa | CTA PASIVO | CTA GTO/ACT | CTA IGV | CTA NO GRAVAD |
|---|---|---|---|---|---|---|
| **1** | COMPRA DE MERCADERÍA | CELULARES | `42120001` **H** | `6011100` **D** | `40111000` **D** | — |
| **2** | DEVOLUC DE MERCADERÍA | CELULARES | `42120001` **D** | `65600600` **H** | `40111000` **H** | — |
| **3** | COMPRA NO GRAVADA | NO GRAVADA | `42120001` **H** | — | — | `65600600` **D** |
| **4** | COMPRA MIXTA | MIXTA | `42120001` **H** | `65600600` **D** | `40111000` **D** | `65600600` **D** |
| **5** | COMPRA DESTINO MIXTO - OPR 002 | VARIOS | `42120001` **H** | `6011100` **D** | `4011600` **D** | `6411100` **D** |

**El tipo 5 es el interesante, y da una pista contable.** Se llama «OPR 002» porque acompaña a
`DESTINO = 2` (gravada destinada a mixtas), y usa **dos cuentas distintas de las demás**: el IGV va a
`4011600` en vez de `40111000`, y la cuarta cuenta es `6411100` — una cuenta del elemento **64,
tributos**. Es decir: **la parte del IGV que no da derecho a crédito fiscal se lleva a gasto.** Eso es
el prorrateo, y es exactamente para lo que existe la columna `PORC OPE MIXTA`.

### Los asientos típicos de ventas — leídos de la captura

| Tipo | Descripción | Glosa | CTA ACTIVO | CTA INGRESO | CTA IGV | CTA NO GRAVAD |
|---|---|---|---|---|---|---|
| **1** | VENTA DE MERCADERÍA | CELULARES | `12120001` **D** | `70410100` **H** | `40111000` **H** | — |
| **2** | VENTA EXONERADA | EXONERADA | `12120001` **D** | — | — | `70610100` **H** |
| **3** | DEVOLUC MERCADERÍA | CELULARES | `12120001` **H** | `70911111` **D** | `40111000` **D** | — |
| **4** | VENTA MIXTA | MIXTA | `12120001` **D** | `70410100` **H** | `40111000` **H** | `70510100` **H** |

**Un detalle contable que la narración no decía y la captura sí:** la devolución **no es una simple
reversión con las mismas cuentas**. El activo y el IGV sí se dan la vuelta (`12120001` pasa a H,
`40111000` a D), pero **la cuenta de ingreso cambia**: de `70410100` a **`70911111`**, que es la de
devoluciones sobre ventas (PCGE `7091`). Si el motor arma la nota de crédito revirtiendo signos sobre
la misma cuenta, no produce lo que este contribuyente espera. **[por confirmar contra el PCGE y con
un contador]**

> **La numeración NO coincide entre libros**: la devolución es `2` en compras y `3` en ventas.
> Confirma que el código es **interno de la macro** y no significa nada fuera de ella. Y las cuentas
> del ejemplo «son referenciales»: cada empresa pone las suyas **[C 5:30]**.

## Hoja `DATA` — lo que el usuario rellena (compras)

**Cabecera del lote [C 5:58-6:17]:**

| | |
|---|---|
| Año y mes de registro | En el ejemplo, `2025` `7` |
| **Sub-diario de compras** | **`4`** por defecto, «según el sistema contable» |
| Correlativo de vouchers | **Siempre empieza en `1`**. El driver lo escribe a cuatro dígitos (`0001`),
que es el ancho con el que numera el motor (John, 21-sep-2026). ⚠️ Excel, al abrir el CSV para revisarlo,
lo mostrará como `1`: el archivo es correcto, engaña el visor. **[por confirmar]** que STARSOFT acepte el
texto con ceros; si no, se quita el `zfill` de `proyeccion.voucher`. |

**Por comprobante [C 7:19-12:32]:**

| Columna | Notas |
|---|---|
| Fecha de registro | |
| Fecha de documento | |
| Fecha de vencimiento | Si la hay |
| **Tipo de documento** | **`FT`**, «las iniciales de factura» **[C 7:34]** |
| Serie | `F136` en el ejemplo |
| Número | `431`. Ojo: Excel puede convertirlo a fecha; se corrige con formato general |
| **Código del proveedor** | **Tiene que estar en los ANEXOS de STARSOFT** o la carga falla **[C 7:55]** |
| Centro de costo | Opcional; si el gasto no va a uno, se omite |
| Base imponible | |
| IGV | |
| Importe no gravado | |
| Importe total | |
| Tipo de cambio referencial | Se puede omitir |
| **DESTINO** | Ver la tabla de abajo. «Es muy importante registrarla» |
| Operaciones mixtas | El **porcentaje de prorrateo del IGV**; solo cuando `DESTINO = 2` |
| Valor CIF | Solo cuando `DESTINO = 5` (importación) |
| Fecha / tipo / serie / número de doc. referencial | Solo en NC y ND, apuntando al comprobante que modifican |
| Afecto a detracción | `1` sí · blanco o `0` no |
| Número de detracción | El de la operación **en la entidad financiera** |
| Fecha de detracción | |
| Código de detracción | El tipo de operación afecta |
| Tasa de detracción | |
| Importe de detracción | |
| Documento anulado | Blanco o `0` por defecto |
| **IGV por aplicar** | `0` o `1`. `1` = el IGV está **pendiente de aplicación** |
| **Importación** | `0` o `1` |
| **Número de file** | En blanco |
| **Tipo de asiento** | El código de `PARAMETROS` |

### La columna `DESTINO` **[C 8:46-9:10]**

Es la clasificación del crédito fiscal, y no tiene equivalente en CONCAR:

| Valor | Significado |
|---|---|
| **1** | Operaciones gravadas destinadas a operaciones gravadas |
| **2** | Operaciones gravadas destinadas a operaciones **mixtas** (activa el prorrateo) |
| **3** | Operaciones gravadas destinadas a operaciones **no gravadas** |
| **4** | Operaciones **no gravadas** |
| **5** | **Importación** (activa el valor CIF) |

## Hoja `PLANTILLA` — las columnas del asiento

### ⚠️ Dos códigos que van de 1 a 5 y NO son lo mismo

Esta es la confusión más fácil de cometer en todo el documento:

| | **TIPO DE ASIENTO** | **DESTINO** |
|---|---|---|
| Dónde vive | `PARAMETROS` (1-5 en compras, 1-4 en ventas) | Columna **`R`** de `PLANTILLA` |
| ¿Viaja a STARSOFT? | **NO.** No existe tal columna en el archivo | **SÍ.** Es obligatoria (John, 20-sep-2026) |
| Qué significa | Qué cuentas usar | La clasificación tributaria del crédito fiscal |
| Quién lo decide | El contador lo escribe en `DATA`; la macro busca sus cuentas | Sale del tipo de operación del comprobante |

**Cómo funciona de verdad** (John, 20-sep-2026): el usuario indica el **tipo de operación** —gravada,
no gravada, inafecta— y de ahí **la macro genera internamente el código** y resuelve las cuentas. El
código en sí es andamiaje; lo que sale al archivo son **las cuentas ya elegidas** y **el `DESTINO`**.

**Para el motor esto es una buena noticia y una tarea:**

- **La buena noticia:** no hace falta un catálogo de asientos típicos. El motor ya sabe si un
  comprobante es gravado, exonerado o inafecto —lo lleva el documento `open-accounting`— y ya sabe
  qué cuentas poner, por `configuracion` e `imputacion`. Es lo mismo que hace con CONCAR.
- **La tarea:** el motor **sí tiene que calcular el `DESTINO`**, porque esa columna es obligatoria y
  hoy no existe en ningún otro driver. Es el único concepto nuevo de verdad que trae STARSOFT.

### Compras — cabeceras reales, leídas de la captura

Las letras cuadran desde la `M`, que en la captura está seleccionada con el IGV de la segunda línea
(`M3 = 167.3`). **De la `A` a la `E` quedan fuera de cuadro**; son las cinco que la narración nombra
primero, y encajan justo en ese hueco.

| Col. | Cabecera | Notas |
|---|---|---|
| A | Cuenta contable | **[inferida de la narración]** |
| B | Periodo tributario | **[inferida]** |
| C | Sub-diario | **[inferida]** — `4` en compras, `03` en ventas |
| D | Voucher | **[inferida]** — el correlativo, empieza en `1` |
| E | Fecha | **[inferida]** |
| **F** | `TIPO ANEXO` | `03` en el ejemplo |
| **G** | `CODIGO PROVEEDOR` | `20100018200` — es el **RUC**, y tiene que existir en los anexos |
| **H** | `TIPO DOCUMENTO` | `FT` |
| **I** | `NRO DOCUMENTO` | `F13600000431` — **serie y número pegados y con ceros**: `F136` + `00000431` |
| **J** | `FECHA VENCIMIENTO` | `01/07/2025` |
| **K** | `IGV` | `167.3` — **solo en la línea del total**, vacío en las demás |
| **L** | `TASA IGV` | `18` — ídem |
| **M** | `IMPORTE` | **El de esa línea**: `929.49` base · `167.3` IGV · `1096.79` total |
| **N** | `CONV` | `VTA` |
| **O** | `FECHA REGISTRO` | `01/07/2025` |
| **P** | `TIPO CAMBIO` | `3.274` |
| **Q** | `GLOSA` | `FT F136-00000431` — **el tipo + serie-número, aquí SÍ con guion** |
| **R** | **`DESTINO`** | **`001`** — con ceros a la izquierda, tres dígitos. **Se usa siempre** |
| **S** | `PORC OPE MIXTA` | Vacío salvo `DESTINO = 2` |
| **T** | `VALOR CIF` | Vacío salvo `DESTINO = 5` |
| **U** | `TIPO DOC REF` | Solo NC/ND |
| **V** | `NRO DOC REF` | Solo NC/ND |
| **W** | `CEN…` (centro de costo) | Cortada en la captura |

**Y lo que NO aparece por ninguna parte: una columna «TIPO ASIENTO».** Verificado sobre la cabecera
real, no sobre la narración.

**Tres detalles de formato que solo se ven en la captura y que el driver tiene que respetar:**

1. **`NRO DOCUMENTO` va concatenado** (`F136431`) y la **glosa lleva el guion** (`FT F136-431`): dos
   formas del mismo dato en la misma fila. **El número va SIN ceros a la izquierda**, como en CONCAR y
   en el SIRE — ✅ **zanjado por John el 22-sep-2026**, viéndolo dentro de su STARSOFT: en la columna
   Documento del asiento salía `E00100000105` y lo quiere `E001105`. Hasta la 2.5 se rellenaba a ocho,
   leído de una captura de la hoja PLANTILLA; pero eso era cómo guarda los números **esa** instalación,
   no lo que el formato exige. **La serie sí se rellena a cuatro**, y no es lo mismo: ahí el hueco marca
   dónde empieza el número («si es de 3, un espacio en blanco y el numero desde la quinta»).
2. **`IGV` y `TASA IGV` solo van en la línea del importe total**, no repetidos en las tres.
3. **`DESTINO` va con ceros a tres dígitos** (`001`, no `1`).

### Ventas **[V 11:46-13:07]**

`TIPO DOCUMENTO` · `NRO DOCUMENTO` · `NRO DOC FINAL` · `FECHA EMISION` · `DOC REFERENCIA` ·
`NRO DOC REF` · `IGV` · `TASA IGV` · `OTROS TRIB` · `IMPORTE` · `CONV TIPO` (`VTA`) · `CAMBIO` ·
`GLOSA` · `GLOSA MOVIMIENTO` · *anulado* · *debe/haber* · `RUC CLIENTE` · `RAZON SOCIAL` ·
`CENTRO COSTO` · *fecha de vencimiento* · *fecha, serie y número de referencia* · *exportación*

> **Compras y ventas no comparten juego de columnas.** Ventas lleva `RUC CLIENTE` y `RAZON SOCIAL`;
> compras, `código de proveedor`. **Son dos plantillas y dos proyecciones.**

### La cabecera REAL de la hoja `PLANTILLA` de compras · **[capturas de John, 21-sep-2026]**

Las 38 columnas, leídas de cuatro capturas de la hoja abierta en Excel con datos dentro.

| | | | | | |
|---|---|---|---|---|---|
| **A** `CTA CONTABLE` | **B** `AÑO Y MES PROCESO` | **C** `SUBDIARIO` | **D** `COMPROBANTE` | **E** `FECHA DOCUMENTO` | **F** `TIPO ANEXO` |
| **G** `CODIGO PROVEEDOR` | **H** `TIPO DOCUMENTO` | **I** `NRO DOCUMENTO` | **J** `FECHA VENCIMIENTO` | **K** `IGV` | **L** `TASA IGV` |
| **M** `IMPORTE` | **N** `CONV` | **O** `FECHA REGISTRO` | **P** `TIPO CAMBIO` | **Q** `GLOSA` | **R** `DESTINO` |
| **S** `PORC OPE MIXTA` | **T** `VALOR CIF` | **U** `TIPO DOC REF` | **V** `NRO DOC REF` | **W** `CENTRO DE COSTOS` | **X** `DETRACCION` |
| **Y** `NRO DOC DETRACCION` | **Z** `FECHA DETRACCION` | **AA** `FECHA DOC REF` | **AB** `GLOSA MOVIMIENTO` | **AC** `DOCUMENTO ANULADO` | **AD** `IGV POR APLICAR` |
| **AE** `CODIGO DETRACCION` | **AF** `IMPORTACION` | **AG** `DEBE / HABER` | **AH** `TASA DETRACCION` | **AI** `IMPORTE DETRACCION` | **AJ** `NRO FILE` |
| **AK** `OTROS TRIBUTOS` | **AL** `IMP BOLSA` | | | | |

**Lo que corrigió:** faltaban **`DETRACCION` (`X`)**, **`NRO DOC DETRACCION` (`Y`)**, **`FECHA DETRACCION`
(`Z`)** y **`FECHA DOC REF` (`AA`)**, así que **desde la `X` todo estaba corrido cuatro posiciones**; y al final
aparecen `OTROS TRIBUTOS` e `IMP BOLSA`. Eran 32 columnas y son 38. Los nombres pasan a ser los de la hoja:
`CTA CONTABLE`, `AÑO Y MES PROCESO`, `FECHA DOCUMENTO`, `CENTRO DE COSTOS`, `DOCUMENTO ANULADO`,
`DEBE / HABER`, `NRO FILE`.

**Lo que confirman los datos:**

| Qué | Lo que se ve |
|---|---|
| Sub-diario de compras | **`04`**, con su cero — como dijo John y al revés de lo que se dedujo del vídeo |
| `COMPROBANTE` | `0001`, `0002`, `0003`… cuatro dígitos |
| `TIPO ANEXO` | `03` en todas las filas |
| `DOCUMENTO ANULADO` e `IMPORTACION` | `0` en todas las filas |
| `NRO DOCUMENTO` | `F13600000431`, pero también `020 00044419` y `050 00010197`: **la serie se rellena a 4** |
| `GLOSA` | `FT F136-00000431 /`, `TK 020 -00044419 /` — mismo formato que en ventas |
| `IGV` y `TASA IGV` | **solo en la fila del total**, la del proveedor |
| `DESTINO` | `001`, `002`, `004` — con sus tres dígitos |
| `IGV POR APLICAR` | `0` en todas las filas: el IGV no está pendiente de aplicación |
| `FECHA DOCUMENTO` (`E`) y `FECHA REGISTRO` (`O`) | son **dos fechas distintas**, en dos columnas |

**Lo que sigue abierto:**

- **`PORC OPE MIXTA` sale con `60`** en una compra de destino `002` (uso mixto). De dónde sale ese 60 no consta:
  el estándar no tiene el porcentaje de la operación mixta, así que la columna va declarada y vacía.
- **`NRO DOC DETRACCION` y `FECHA DETRACCION`** van vacías: la constancia del depósito no se conoce al
  provisionar, se paga días después.
- **Las fechas van en `DD/MM/AAAA`**, no en el ISO del estándar. Lo dicen las dos fuentes —la hoja y el TXT— y
  el driver las traduce desde la 2.3; hasta entonces salían `2025-07-01` y nadie lo había mirado. Se aplica por
  la CLASE declarada de cada columna, así que una columna de fecha nueva sale bien sola.

- **El `TIPO CAMBIO` va en TODAS las filas, sea en soles o en dólares** (John, 21-sep-2026), y la hoja lo
  confirma: `3.274`, `3.281`, `3.261`… en comprobantes en PEN. Desde la 2.2 la línea del asiento transporta el
  tipo de cambio del comprobante venga en la moneda que venga, y STARSOFT lo escribe siempre.

  **Lo que el motor no hace es inventarlo**: si el comprobante no trae tipo de cambio, la columna sale vacía. El
  motor no tiene tabla de tipos de cambio ni sale a la red, así que el T.C. del día de una operación en soles
  tiene que llegar en el comprobante. En la hoja del vídeo lo puso quien la llenó.

### La cabecera REAL de la hoja `PLANTILLA` de ventas · **[capturas de John, 21-sep-2026]**

Las 34 columnas, leídas de cuatro capturas de la hoja abierta en Excel **con datos dentro**. Es la fuente más
fuerte que tiene este documento: no es la narración de un vídeo, es el archivo. El driver se calcó de aquí.

| | | | | | | |
|---|---|---|---|---|---|---|
| **A** `CTA CONTABLE` | **B** `AÑO Y MES PROCESO` | **C** `SUBDIARIO` | **D** `COMPROBANTE` | **E** `FECHA REGISTRO` | **F** `TIPO ANEXO` | **G** `CODIGO CLIENTE` |
| **H** `TIPO DOCUMENTO` | **I** `NRO DOCUMENTO` | **J** `NRO DOC FINAL` | **K** `FECHA EMISION` | **L** `DOC REFERENCIA` | **M** `NRO DOC REF` | **N** `IGV` |
| **O** `VALOR ISC` | **P** `OTROS TRIB` | **Q** `TASA IGV` | **R** `IMPORTE` | **S** `CONV` | **T** `TIPO CAMBIO` | **U** `GLOSA` |
| **V** `GLOSA MOVIMIENTO` | **W** `DOCUMENTO ANULADO` | **X** `DEBE / HABER` | **Y** `RUC CLIENTE` | **Z** `RAZON SOCIAL` | **AA** `CENTRO DE COSTOS` | **AB** `FECHA VENCIMIENTO` |
| **AC** `FECHA DOC REFERENCIA` | **AD** `EXPORTACION` | **AE** `NRO FILE` | **AF** `EXONERADO` | **AG** `OTROS CARGOS` | **AH** `IMP BOLSA` | |

**Lo que corrigió del mapa levantado del vídeo:**

- Faltaban **`TIPO ANEXO` (`F`)** y **`CODIGO CLIENTE` (`G`)**, así que de la `G` en adelante todo estaba
  corrido una posición. Eran 25 columnas y son 34.
- La `D` se llama **`COMPROBANTE`**, no `VOUCHER`.
- `ANULADO` es **`DOCUMENTO ANULADO`**, `CENTRO COSTO` es **`CENTRO DE COSTOS`**, `DEBE HABER` es
  **`DEBE / HABER`**, `CUENTA` es **`CTA CONTABLE`** y `PERIODO` es **`AÑO Y MES PROCESO`**.
- Aparecen `VALOR ISC`, `OTROS TRIB`, `FECHA DOC REFERENCIA`, `NRO FILE`, `EXONERADO`, `OTROS CARGOS` e
  `IMP BOLSA`, que no constaban.

**Lo que confirman los datos de la hoja:**

| Qué | Lo que se ve |
|---|---|
| Sub-diario de ventas | `03`, con su cero |
| `COMPROBANTE` | `0030`, `0031`, `0032`… cuatro dígitos |
| `TIPO ANEXO` | `02` en todas las filas |
| `DOCUMENTO ANULADO` | `0` en todas las filas |
| `EXPORTACION` | `0` en todas las filas |
| Siglas | `BV` boleta, `FT` factura, **`CC` nota de crédito** |
| `NRO DOCUMENTO` | 12 caracteres: `F00100000202` y `001 00036207` — **la serie se rellena a 4 con espacio** |
| `GLOSA` | `BV 001 -00036207 /` en esta hoja. **El driver NO la usa así**: desde la 2.2 las dos columnas de glosa llevan el concepto (John, 21-sep-2026), y el tipo y el número ya viajan en sus propias columnas |
| `IGV` y `TASA IGV` | **solo en la fila del cliente**, la primera del asiento |
| El orden de las líneas | **cliente · IGV · ingreso**. Lo dicen esta hoja y un TXT de otro generador, y desde la 2.2 es el del motor |
| `RUC CLIENTE` y `RAZON SOCIAL` | **solo en la fila del cliente**, no repetidos |
| `CODIGO CLIENTE` | en TODAS las filas, también el genérico `99999999999` de las boletas |
| `NRO DOC FINAL` | solo en boletas: el último número del rango |
| `FECHA DOC REFERENCIA` | solo en la nota de crédito |

**Lo que sigue abierto:**

- **`VALOR ISC`, `OTROS TRIB`, `EXONERADO`, `OTROS CARGOS` e `IMP BOLSA`** van declaradas y vacías: existen y no
  consta cómo se llenan. En la captura están en blanco **incluso en la venta EXONERADA**, que es el caso donde
  más se esperaría un número.
- **La plantilla de COMPRAS sigue levantada del vídeo** y espera su propia captura. Por eso sus cabeceras no
  coinciden con estas (`CUENTA` frente a `CTA CONTABLE`): cada una se calca de SU fuente.

## La forma del asiento

**Compras [C 13:10-13:56]** — base y IGV al debe, total al haber:

| Fila | Qué | Posición |
|---|---|---|
| 1 | Base imponible (valor sin IGV) | **Debe** |
| 2 | IGV | **Debe** |
| 3 | Importe total | **Haber** |

**Ventas [V 12:06-12:20]** — el espejo:

| Fila | Qué | Ejemplo | Posición |
|---|---|---|---|
| 1 | Total (cuenta `12`) | 110,00 | **Debe** |
| 2 | IGV | 16,78 | **Haber** |
| 3 | Base (cuenta `70`) | 93,22 | **Haber** |

## STARSOFT frente a CONCAR

| | **CONCAR** (en el motor hoy) | **STARSOFT** (observado) |
|---|---|---|
| Factura | `FT` | **`FT`** ✅ **[C 7:34]** |
| Boleta | `BV` | **`BV`** (John, 20-sep-2026) |
| **Nota de crédito** | **`NC`** | **`CC`** ⚠️ **[V 14:05]** |
| **Nota de débito** | **`ND`** | **`CD`** ⚠️ **[manual de compras, 2 ejemplos: «penalidad por daños» con referencia a una `FT`]** |
| Recibo por honorarios | `RH` | **[por confirmar]** |
| Ticket | `TK` | **`TK`** ✅ **[manual de compras, 3 ejemplos: un ticket de combustible]** |
| Recibo de servicios públicos | `RC` | **`RC`** ✅ **[manual de compras, 3 ejemplos: un recibo de Claro]** |
| Boleta de anticipo | `BA` | **[por confirmar]** |
| **Sub-diario de compras** | **`11`** | **`4`** ⚠️ **[C 6:08]** |
| **Sub-diario de ventas** | **`05`** | **`03`** ⚠️ (John, 20-sep-2026) |
| Sub-diario de detracción | `10` | **[por confirmar]** |
| Sub-diario propio | `15` honorarios · `13` boletas | **[por confirmar]** |
| Tipo de doc. de detracción | `DR` | **[por confirmar]** |
| Monedas | `PEN→MN` · `USD→US` (rechaza `ME`) | **[por confirmar]** |
| Tipo de conversión | `V` (con T.C. propio pasa a `C`) | `venta` / `VTA` |
| Columnas | **41**, verificadas celda a celda | ~28+ **[por confirmar]** |
| Centro de costo | **Obligatorio** donde toca | Opcional |
| Correlativo | `correlativos` por sub-diario | «Voucher», empieza en `1` |
| Límite de cuentas | — | **Máximo 4 por asiento** |
| Glosa | — | **Máximo 60 caracteres** |

**Las tres siglas confirmadas dan la clave: `FT` y `BV` coinciden con CONCAR, pero `NC` pasa a `CC`.**
Es decir, **no se puede reutilizar la tabla de CONCAR ni tampoco escribir una nueva a ciegas**:
coincide en parte y diverge donde menos se espera. Hay que sacarla entera de la plantilla real.

**Columnas que STARSOFT tiene y CONCAR no:** **`DESTINO`** (los cinco valores, y el único concepto
realmente nuevo) · `PORC OPE MIXTA` (prorrateo) · `VALOR CIF` · IGV por aplicar · importación ·
número de file · tipo de anexo · número de detracción (el de la entidad financiera).

**Y una que NO tiene, aunque lo pareciera:** el tipo de asiento. Es de la macro, no del formato.

**La diferencia de fondo:** en CONCAR el asiento sale de las reglas contables, que el motor ya tiene.
En STARSOFT el contador **elige una plantilla de asiento típico** y el sistema la aplica. Hay que
decidir cuál gana:

- **Que el motor arme el asiento** (como con CONCAR) y el driver solo traduzca el código de tipo.
- **Que el tipo sea configuración** del contribuyente, como las siglas.

**RESUELTO (John, 20-sep-2026): gana el motor.** El tipo de asiento **no viaja en el archivo** —no
hay tal columna en `PLANTILLA`, ni en compras ni en ventas—, así que STARSOFT nunca lo ve y no puede
recalcular nada con él. Recibe las líneas ya armadas: cuenta, importe y posición. Es **exactamente lo
que el motor ya hace para CONCAR**.

Lo que sí hay que traducir de `PARAMETROS` son **las cuentas**, y eso el motor ya lo tiene resuelto por
otra vía: la `configuracion` del contribuyente y la `imputacion` de cada comprobante. El driver no
necesita un catálogo de asientos típicos.


## ¿Lo que produce el motor sirve para STARSOFT? — comprobado el 20-sep-2026

Generado con `contaperu 1.3.0` sobre una compra y una venta equivalentes a las de los vídeos.
**La respuesta corta: sí, y con mucho menos hueco del esperado.**

### El asiento coincide línea por línea

**Compra** — el motor produce exactamente el asiento tipo 1 de STARSOFT:

| | Motor `contaperu` | STARSOFT `PARAMETROS` tipo 1 |
|---|---|---|
| 1 | `60111000` **D** `929.49` — rol `principal`, clase `gasto` | CTA GTO/ACT **D** |
| 2 | `401111` **D** `167.31` — rol `igv`, clase `pasivo` | CTA IGV **D** |
| 3 | `421201` **H** `1096.80` — rol `tercero`, clase `pasivo` | CTA PASIVO **H** |

**Venta** — igual, contra el tipo 1 de ventas:

| | Motor `contaperu` | STARSOFT `PARAMETROS` tipo 1 |
|---|---|---|
| 1 | `121201` **D** `110.00` — rol `tercero`, clase `activo` | CTA ACTIVO **D** |
| 2 | `70410100` **H** `93.22` — rol `principal`, clase `ingreso` | CTA INGRESO **H** |
| 3 | `401111` **H** `16.78` — rol `igv`, clase `pasivo` | CTA IGV **H** |

Mismo número de líneas, mismo orden, mismas posiciones y mismos roles. Los códigos de cuenta que
difieren son **configuración del contribuyente**, que el motor ya recibe por `configuracion` e
`imputacion`. **El `rol` de cada línea (`principal`, `igv`, `tercero`) es precisamente el mapa a las
cabeceras de `PARAMETROS`** (CTA GTO/ACT, CTA IGV, CTA PASIVO): el driver no tiene que adivinar nada.

### Cobertura, columna por columna

**✅ Sale directo del documento** — 18 de las ~28:

| Columna STARSOFT | De dónde sale |
|---|---|
| Cuenta contable | `linea.cuenta` |
| Periodo tributario | `libro.periodo` (`202507`) |
| Fecha | `linea.fecha` |
| `TIPO DOCUMENTO` | `linea.documento.tipo` → ya da **`FT`** |
| `FECHA VENCIMIENTO` | `linea.documento.fecha_vencimiento` |
| `IGV` · `TASA IGV` | `comprobante.igv` · `linea.tasa_igv` (`18`) |
| `IMPORTE` | `linea.importe` |
| Posición D/H | `linea.debe_haber` |
| `CODIGO PROVEEDOR` | `linea.contraparte_doc` (el RUC) |
| Centro de costo | `linea.centro_costo` / `anexo_auxiliar` |
| `TIPO CAMBIO` | `linea.tipo_cambio` |
| `GLOSA` | `linea.glosa` |
| `TIPO DOC REF` · `NRO DOC REF` | `linea.referencia`, y `ref_tipo_cp` / `ref_serie` / `ref_numero` |
| Los 6 campos de detracción | `comprobante.detraccion`: `codigo`, `porcentaje`, `monto`, `nro_constancia`, `fecha_constancia`, `estado` |
| `NRO DOC FINAL` (ventas) | `comprobante.numero_final` — para boletas consolidadas |
| Exportación (ventas) | `comprobante.exportacion` |

**El hallazgo grande: `DESTINO` ya existe en el estándar.** `comprobante.destino_igv`, con enum
`DG` · `DGNG` · `DNG` y la descripción «Solo compras: gravadas, mixtas, no gravadas». Mapea casi 1:1:

| STARSOFT | Significado | `destino_igv` |
|---|---|---|
| `001` | Gravadas → gravadas | **`DG`** |
| `002` | Gravadas → mixtas | **`DGNG`** |
| `003` | Gravadas → no gravadas | **`DNG`** |
| `004` | No gravadas | sin base gravada (se deduce) |
| `005` | Importación | `anio_dua` / `cod_dep_aduanera` presentes (se deduce) |

**⚠️ Necesita traducción en el driver** — no falta el dato, falta la forma:

| Columna | El motor da | STARSOFT espera |
|---|---|---|
| Sub-diario | `11` compras · `05` ventas (CONCAR) | **`4`** · **`03`** — va a su sección de configuración |
| Voucher | `070001` (formato CONCAR: mes + correlativo) | **`0001`** — sin el mes, con sus cuatro dígitos |
| `NRO DOCUMENTO` | `F136-431` | **`F136431`** — pegado y sin ceros (la serie sí se rellena a 4) |
| `DESTINO` | `DG` | **`001`** — numérico a 3 dígitos |
| `CONV` | — | **`VTA`** — constante de configuración |
| `GLOSA` | `CELULARES` (el concepto) | `FT F136-00000431` (tipo + documento) |

**❌ No existe en el estándar, y hay que decidir qué hacer:**

| Columna | Qué es | Propuesta |
|---|---|---|
| `TIPO ANEXO` | `03` en el ejemplo | Configuración del contribuyente |
| `PORC OPE MIXTA` | El % de prorrateo del IGV cuando `DESTINO = 2` | **Es un dato contable que decide el contador.** Iría en la imputación, como la cuenta |
| `IGV POR APLICAR` | `0`/`1`, IGV pendiente de aplicación | Configuración, o por comprobante |
| `NUMERO DE FILE` | Siempre vacío en los vídeos | Constante vacía |
| `FECHA REGISTRO` | La del registro contable | El parámetro `fecha` que `exportar` ya recibe |
| `VALOR CIF` | Solo importaciones | Hay `anio_dua` y `cod_dep_aduanera`, pero no el CIF. **[por confirmar]** |

### Conclusión

**No hay ningún impedimento de fondo.** El motor produce el asiento con la forma que STARSOFT espera,
y el estándar `open-accounting` ya lleva los datos tributarios peruanos que este formato pide
—`destino_igv`, la detracción completa, la referencia de la NC, `numero_final`, `exportacion`—.

Lo que falta es **un driver que traduzca**, del mismo tamaño que el de CONCAR: su tabla de siglas y
sub-diarios, su formato de número de documento, su glosa y su mapa de `destino_igv` a `001-005`.

Los seis campos de la última tabla son la única deuda real, y solo dos importan de verdad:
**`PORC OPE MIXTA`** —que es una decisión del contador y pide sitio en la imputación— y **`VALOR CIF`**.

## Lo que falta

1. **Las plantillas oficiales** (compras y ventas, `.xlsx` vacías con su cabecera).
2. **Un archivo aceptado por STARSOFT** de cada libro.
3. **Completar la tabla de siglas y sub-diarios** — la columna derecha de la comparación.
4. **Qué hace STARSOFT con el tipo de asiento al importar**: ¿arma o solo clasifica?
5. **Formato de los datos**: fecha (`dd/mm/aaaa` en el vídeo), separador decimal, longitudes, y si el
   número de comprobante va con ceros a la izquierda.
6. **Un ejemplo con moneda extranjera** y **otro con detracción completa**.

## Lo que ya está hecho y no hay que rehacer

- `contaperu/drivers/contrato.py` — `exige`, `no_caben` y la declaración de configuración. Ojo: **los 60
  caracteres de glosa NO entran por `no_caben`** desde la 2.6 — se CORTAN al escribir, como en CONCAR y
  CONTASIS. `no_caben` es para lo que el sistema RECHAZA, no para lo que recorta.
- `contaperu/drivers/kit/` — escribir `.xlsx` sin decidir contabilidad.
- `contaperu/drivers/concar/datos.py` — el modelo de cómo se declaran siglas, sub-diarios y columnas.
- `contaperu/drivers/contasis/` — la forma: `.xlsx` legacy, plantilla fuera de Git, tests que se saltan
  solos cuando no está.
- `API-DE-REGISTRO.md` — la **API REST** de STARSOFT Gold Edition. Otro camino, mismo vocabulario.
