# STARSOFT — notas para el driver

> **Documento de trabajo, no especificación.** Recoge lo observado el 20-sep-2026 en dos vídeos del
> canal *ArchivoExcel*, leyendo sus capturas y su transcripción automática:
>
> - **[C] Compras** — «Importar asientos contables de compras al Star Soft», 22:25 · `youtube.com/watch?v=1HMTMsuQJAA`
> - **[V] Ventas** — «Importar asientos de ventas al Star Soft», 20:16 · `youtube.com/watch?v=iOq8Zh6avj8`
>
> **Nada de aquí entra en el motor todavía**: falta la plantilla real y un archivo que STARSOFT haya
> aceptado, que es la regla del repositorio para cualquier driver (`CONTRIBUTING.md`).
>
> Lo observado va con su minuto. Lo que sigue sin confirmar, **[por confirmar]**.

## Lo esencial

1. STARSOFT ofrece **dos vías de carga, TXT y Excel**. **Se usa la de Excel** (John, 20-sep-2026).
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
> **la glosa de 60 caracteres** es un límite real del formato.

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

1. **`NRO DOCUMENTO` va concatenado y con ceros** (`F13600000431`), mientras la **glosa lleva el guion**
   (`FT F136-00000431`). Son dos formas del mismo dato en la misma fila. Ojo: choca con la regla de
   John para CONCAR y el SIRE —«al archivo va el número SIN ceros a la izquierda»—, así que **esta es
   propia de STARSOFT**. **[por confirmar con la plantilla]**
2. **`IGV` y `TASA IGV` solo van en la línea del importe total**, no repetidos en las tres.
3. **`DESTINO` va con ceros a tres dígitos** (`001`, no `1`).

### Ventas **[V 11:46-13:07]**

`TIPO DOCUMENTO` · `NRO DOCUMENTO` · `NRO DOC FINAL` · `FECHA EMISION` · `DOC REFERENCIA` ·
`NRO DOC REF` · `IGV` · `TASA IGV` · `OTROS TRIB` · `IMPORTE` · `CONV TIPO` (`VTA`) · `CAMBIO` ·
`GLOSA` · `GLOSA MOVIMIENTO` · *anulado* · *debe/haber* · `RUC CLIENTE` · `RAZON SOCIAL` ·
`CENTRO COSTO` · *fecha de vencimiento* · *fecha, serie y número de referencia* · *exportación*

> **Compras y ventas no comparten juego de columnas.** Ventas lleva `RUC CLIENTE` y `RAZON SOCIAL`;
> compras, `código de proveedor`. **Son dos plantillas y dos proyecciones.**

### La cabecera REAL de la hoja `PLANTILLA` de ventas · **[captura de John, 21-sep-2026]**

Leída de una captura de la hoja abierta en Excel, con datos dentro, que es la fuente más fuerte que tiene
este documento: no es la narración de un vídeo, es el archivo.

| | | | | | | | |
|---|---|---|---|---|---|---|---|
| **A** | **B** | **C** | **D** | **E** | **F** | **G** | **H** |
| `CTA CONTABLE` | `AÑO Y MES PROCESO` | `SUBDIARIO` | `COMPROBANTE` | `FECHA REGISTRO` | `TIPO ANEXO` | `CODIGO CLIENTE` | `TIPO DOCUMENTO` |

| | | | | | | | |
|---|---|---|---|---|---|---|---|
| **I** | **J** | **K** | **L** | **M** | **N** | **O** | **P** |
| `NRO DOCUMENTO` | `NRO DOC FINAL` | `FECHA EMISION` | `DOC REFERENCIA` | `NRO DOC REF` | `IGV` | `VALOR ISC` | `OTROS TRIB` |

**Lo que confirma:**

- **`TIPO ANEXO` SÍ está en ventas, en la `F`**, con valor `02` en todas las filas. El vídeo no la mostraba y
  este documento la daba por inexistente.
- **El sub-diario de ventas es `03`**, escrito con su cero.
- **La columna `D` lleva cuatro dígitos**: `0030`, `0031`, `0032`… Confirma que el correlativo va con ceros.
- **Las siglas**: `BV` boleta, `FT` factura y **`CC` nota de crédito**, que era lo que más dudas daba.

**Lo que contradice, y sigue abierto:**

- **La `D` se llama `COMPROBANTE`**, no `VOUCHER` (como decía la captura de compras) ni `CORRELATIVO`.
- **Falta `CODIGO CLIENTE` en la `G`**: el driver lleva el RUC del cliente al final, en `RUC CLIENTE`. Desde
  la `G` en adelante, el mapa de este documento y el del driver están **corridos una posición**.
- **`VALOR ISC` y `OTROS TRIB`** existen y el driver no las tiene.
- **El número del documento ocupa 12 caracteres**: `F00100000202` para una factura, pero `001 00036207` para
  una boleta. La serie se rellena a **4 caracteres** (`001` + espacio) y el número a 8 con ceros. El driver
  hoy pega la serie tal cual, así que una boleta saldría con 11 caracteres y no 12.

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
| Nota de débito | `ND` | **[por confirmar]** |
| Recibo por honorarios | `RH` | **[por confirmar]** |
| Ticket | `TK` | **[por confirmar]** |
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
| `NRO DOCUMENTO` | `F136-431` | **`F13600000431`** — pegado y con ceros |
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

- `contaperu/drivers/contrato.py` — `exige`, `no_caben` y la declaración de configuración. **El límite
  de 4 cuentas y los 60 caracteres de glosa entran por ahí**, que es justo para lo que existe.
- `contaperu/drivers/kit/` — escribir `.xlsx` sin decidir contabilidad.
- `contaperu/drivers/concar/datos.py` — el modelo de cómo se declaran siglas, sub-diarios y columnas.
- `contaperu/drivers/contasis/` — la forma: `.xlsx` legacy, plantilla fuera de Git, tests que se saltan
  solos cuando no está.
- `API-DE-REGISTRO.md` — la **API REST** de STARSOFT Gold Edition. Otro camino, mismo vocabulario.
