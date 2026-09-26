# open-accounting 1.0 — el documento contable universal del Perú

Un solo JSON que sirve para las tres cosas que un contador peruano necesita mover de un sistema a otro:
**qué libro es**, **qué comprobantes lo componen** y **cómo queda el asiento**.

Existe porque hoy no hay ninguno. CONCAR, CONTASIS y SISCONT importan cada uno su propio archivo plano;
una IA que lee un PDF no tiene dónde depositar lo que extrajo; y quien cambia de sistema contable rehace la
integración desde cero. El estándar no reemplaza a ninguno: es el idioma intermedio.

**Esquema formal:** [`open-accounting.schema.json`](open-accounting.schema.json) (JSON Schema draft 2020-12).
Su identificador canónico —el `$id` con el que se cita este estándar desde fuera— es:

```
https://raw.githubusercontent.com/contaperu/contaperu/open-accounting-1.0/estandar/open-accounting.schema.json
```

Cuelga del tag **del estándar** (`open-accounting-1.0`), no del de la librería: la versión del paquete sube
cada vez que se corrige un driver, y un identificador que se mueve bajo los pies de quien lo cita no
sirve como estándar. **El tag `open-accounting-1.0` avanza con cada cambio aditivo** —un valor nuevo de catálogo o un
bloque opcional no suben la versión (ver Versionado)—, así que esa URL devuelve el último esquema compatible con la
1.0; un cambio de significado sube a 2.0 y estrena su propio tag.

**Y la 1.0 es un compromiso:** nada de lo que existe se quita ni cambia de significado hasta una 2.0. Lo que hace
sostenible esa promesa son los catálogos —`rol`, `clase` y `tipos_de_libro` viven fuera del esquema y crecen sin
tocarlo— y las [enmiendas](enmiendas/LEEME.md), donde queda escrito cada cambio con su compatibilidad.

Para comprobar un documento con el motor —lo lee con las mismas reglas que el servidor MCP y dice qué bloquea y qué
falta—:

```bash
python -m contaperu.puertas.cli diagnosticar mi-documento.json
```

---

## Los tres bloques

```json
{
  "open_accounting": "1.0",
  "libro":        { "ruc": "20601234567", "razon_social": "EMPRESA SAC",
                    "periodo": "202601", "tipo": "compra" },
  "comprobantes": [ { "tipo_cp": "01", "serie": "F001", "numero": "00045680", "…": "…" } ],
  "asiento":      [ { "cuenta": "659999", "debe_haber": "D", "importe": "40000.00", "…": "…" } ]
}
```

**`libro`** — la cabecera tributaria. Un RUC, un mes (`AAAAMM`), y `venta` o `compra`. Es obligatoria: sin
saber de quién y de cuándo es, un comprobante suelto no es contabilidad.

**`comprobantes`** — los **registros**: los hechos de cada documento soporte, con los campos tal como los
define SUNAT. Es lo que sale de un XML UBL, de la propuesta del SIRE, de leer un PDF o del archivo de otro
sistema: el documento es el riel, y es el mismo para cualquier entorno. **Las cuentas no van aquí**: llegan
aparte, en la imputación (ver *Documento, imputación y configuración*). Con este bloque basta para un sistema que
importa registros, y para generar el asiento de uno que importa asientos.

**`asiento`** — las líneas de diario, **sin nada de ningún ERP**: cuenta, debe o haber, importe, moneda,
glosa, centro de costo. Es el bloque que permite que un sistema contable consuma el resultado sin saber qué
lo generó. Es opcional: quien ya lo tiene armado lo manda, quien no, lo pide.

---

## Documento, imputación y configuración

**Las cuentas contables viven en la aplicación, no en el documento** (decisión de John, 12-sep-2026). El motor
recibe tres piezas, y cada dato tiene un solo dueño:

| Pieza | Qué lleva | Quién la pone | ¿Cambia por entorno? |
|---|---|---|---|
| **Documento** (`open-accounting`) | Los hechos del comprobante: fechas, serie, contraparte, importes, `condicion_pago`… | Los lectores, desde cualquier input | No |
| **Imputación** | Lo que el entorno decide para cada documento: su cuenta, su centro de costo, la cuenta del total y el reparto | La aplicación, desde la Revisión | Sí |
| **Configuración** | Lo que vale para todo el entorno: lo general (cuentas por defecto, centros de costo, tasas de detracción) en la raíz, y lo de cada sistema contable —sus siglas, sus sub-diarios, en qué columnas va cada dato— en su sección | La aplicación, con lo que declara el motor | Sí |

Lo que se calcula con esas tres —el signo de la nota de crédito, los soles de una factura en dólares, el % de
IGV, el correlativo— **no lo guarda nadie**: lo deriva el driver.

**La configuración la declara el motor y la guarda la aplicación** (John, 13-sep-2026). Su forma es lo general en la
raíz y una sección por sistema contable:

    {"cuentas": {"gasto": "659999"}, "usa_centros_costo": true,
     "concar": {"tipos": {"01": {"sigla": "FT"}},
                "columnas": {"centro_costo": ["centro_costo", "anexo_auxiliar_del_tercero"]}},
     "contasis": {"medio_pago": "001", "columnas": {"centro_costo": ["centro_costo", "centro_costo_2"]}}}

Cada driver declara lo que se configura en su sección y en qué columnas de su archivo puede ir cada dato
(`columnas`): el dato —el centro de costo, por ejemplo— se guarda una vez y cada sistema elige dónde sale. Lo que se
configura, con sus tipos, valores por defecto, patrones y textos, está en el recurso `contaperu://configuracion` del
MCP (y en `contaperu configuracion` por la CLI), y el motor valida contra eso lo que recibe antes de generar: una
clave que no existe se dice, no se ignora.

**La imputación va en el documento, con el `id_externo` del comprobante como llave** (1.0): el bloque
`imputaciones` de la raíz, para que un archivo guardado explique su propio asiento. Sigue valiendo el argumento
`imputacion` de `exportar`, `diagnosticar` y `generar_asiento` (`--imputacion` en la CLI), para quien ya integraba
así, y **las dos formas a la vez se rechazan**: adivinar cuál manda sería elegir en silencio la cuenta de un
comprobante. Por las dos vías es el mismo objeto:

    {"fila-123": {"cuenta_contable": "6011020", "centro_costo": "OBRA01", "cuenta_tercero": "4699"},
     "fila-124": {"reparto": [{"importe": "60.00", "cuenta_contable": "636301", "centro_costo": "SISTEMAS"},
                              {"importe": "40.00", "cuenta_contable": "632201", "centro_costo": "DESARROLLO"}]}}

- **Con `imputaciones` en el documento, cada comprobante necesita su `id_externo`**, que es la llave: el esquema lo
  exige con un condicional —un documento sin imputaciones no lo pide— y el motor añade lo que el esquema no puede
  decir, que ningún `id_externo` esté repetido. **Por el argumento no se exige a todos**, a propósito: ahí se puede
  imputar 3 de 10 comprobantes y que los otros 7 no traigan id. Es la única asimetría entre las dos vías.
- **Una llave que nombra a dos comprobantes se rechaza por las dos vías**, porque el daño es el mismo: la misma
  cuenta se aplicaría a los dos y ninguna de sus líneas diría de cuál viene. Lo que cambia es el alcance — en el
  documento, ningún id puede repetirse; por el argumento, ninguno de los que la imputación nombra.
- **No va en la configuración guardada**: ahí `imputaciones` es un error. La fachada la lee en la puerta
  (`operaciones.con_imputacion`) y se la entrega al núcleo dentro de la configuración aplicada, bajo `imputaciones`.
- **Lo que no trae** sale de la configuración del entorno: el comprobante no lleva cuentas.
- **El reparto divide solo la base** —el gasto o el ingreso—: el IGV y el total son del documento. Sus partes
  suman la base del asiento: el total menos el IGV con línea propia (en compras, la boleta y el recibo por
  honorarios van enteros). Si no, el mes no está listo (`reparto_que_no_cuadra`) y el asiento no se arma.
- **Se rechazan en la puerta** un reparto con cuenta o centro al lado, que no dice cuál manda, y una imputación
  cuyo `id_externo` no es de ningún documento: una llave mal escrita haría salir ese documento con la cuenta por
  defecto, sin aviso.
- **Las cuentas se resuelven una sola vez, en el núcleo** (`asiento.partes_de`, `asiento.cuenta_tercero`), para
  todos los drivers: la que decide la imputación sale igual en el asiento de CONCAR y en la columna de un sistema
  que importa registros.

## Dos familias de salida, un solo documento

- **Registro** — una fila por comprobante, sin asiento: el TXT del SIRE, y los sistemas contables que
  importan su registro de compras y de ventas y arman el asiento ellos mismos (CONTASIS).
- **Asiento** — el núcleo convierte los registros en líneas de diario una sola vez y el driver las traduce:
  el Excel de CONCAR, el CSV y los sistemas que importan asientos.

Un sistema nuevo solo elige familia: el documento del que sale es el mismo. En el contrato de drivers
(`contaperu/drivers/contrato.py`), la familia registro son las formas `linea` y `desde_comprobantes`, y la
familia asiento, `construir` y `desde_lineas`.

---

## La identidad de un comprobante

Un comprobante es el mismo, venga por donde venga, si coinciden el RUC y el tipo del libro (`libro.ruc`, `libro.tipo`)
y su tipo, su serie y su número (`tipo_cp`, `serie`, `numero`; el número sin ceros a la izquierda: «00000123» es
«123»). **En compras entra también el documento del proveedor** (`contraparte_doc`): cada proveedor numera por su
cuenta, y dos pueden repetir serie y número. **En ventas no entra el del cliente**: la serie y el número los numera el
propio contribuyente y no se repiten, y el cliente de una boleta muchas veces ni se conoce; `comparar_sire` lo deja
fuera por la misma razón. **El periodo no forma parte de la identidad**: un comprobante ya anotado en otro mes sigue
siendo el mismo, y por eso SUNAT lo rechaza (error 452).

Es la clave con la que el motor detecta duplicados —dentro del lote y contra `claves_previas`, lo ya anotado en otros
periodos del mismo RUC, que viaja como `[tipo_cp, serie, numero, contraparte_doc]`— y la que devuelve de cada
comprobante al asentar y al exportar.

## Las cinco reglas que hay que entender

**1. Los importes van siempre en positivo.** Una nota de crédito no lleva importes negativos: lleva
`tipo_cp: "07"`. El signo —o la inversión del debe y el haber— lo pone el driver de salida, porque cada ERP
lo expresa distinto. Esto evita el error más común al integrar: restar dos veces.

**2. Los importes viajan como texto.** `"total": "4956.00"`, no `4956.0`. Un `float` de JSON no representa
exactamente los céntimos y la contabilidad no perdona el redondeo. Se acepta un número por compatibilidad,
pero quien produce el documento debería mandar texto.

**3. Las fechas son `AAAA-MM-DD`.** Sin hora, sin zona horaria. Una factura no tiene hora contable.

**4. El código SUNAT manda.** `tipo_cp` es el de la Tabla 10 (`01` factura, `03` boleta, `07` nota de
crédito…), nunca la sigla del ERP de destino. La traducción a `FT`, `BV` o lo que use cada sistema es
trabajo del driver, y un tipo sin equivalente **detiene la exportación en vez de inventarse una**.

**5. Lo que no se entiende, se transporta.** `datos_originales` es un objeto libre donde el productor guarda lo
suyo. El núcleo lo lleva de un extremo al otro y no lo interpreta, salvo las cuatro claves que escribe su propio
lector de XML (`lectores/xml_ubl.py`) y que lee la validación (`validar.py`): `anticipo`, `emisor`, `adquirente` y
`gratuitas`. Un productor que las escriba les da ese mismo sentido.

---

## La detracción, que ocurre en dos tiempos

Es el caso peruano que rompe cualquier modelo que asuma que un asiento se cierra de una sola vez. Cuando se
registra la compra **todavía no se ha depositado la detracción**, así que no existe el número de constancia;
el depósito en el Banco de la Nación ocurre días después, y solo entonces se conoce.

El estándar lo resuelve con un bloque de estado dentro del comprobante:

```json
"detraccion": {
  "codigo": "027",              "porcentaje": 4,
  "monto": "198.00",            "cuenta": "00-123-456789",
  "estado": "PROVISIONADO",     "nro_constancia": "", "fecha_constancia": ""
}
```

- **`PROVISIONADO`** (por defecto) — la compra está registrada, la detracción se debe. El asiento se genera
  igual, con un número de documento comodín en la línea de la detracción.
- **`PAGADO`** — se depositó. Se inyectan `nro_constancia` y `fecha_constancia`. **El asiento ya importado no se
  regenera**: en un destino que suma lo que importa, como CONCAR, volver a importarlo duplica los asientos. Qué
  registra el segundo tiempo —el pago de la detracción, con su constancia— es una decisión contable que entrará con
  su fuente y un archivo real aceptado (hitos D1 y D6 de la hoja de ruta), no una regeneración.

El paso de uno a otro es una operación aparte, sin estado: entra el documento provisional y el archivo de
constancias, sale el documento actualizado.

**Y el `estado` no se lee: se deduce** (3.2). Es un campo informativo, para que se vea en una pantalla o en un
informe, y quien lee el documento no puede comprobarlo. Lo que se comprueba son los dos datos que no se pueden
inventar: una detracción cuenta como **pagada cuando tiene un `nro_constancia` que no es el número comodín Y una
`fecha_constancia`**. Con el número y sin la fecha el depósito está a medias —el archivo del sistema contable ya
lleva el número de verdad y la detracción sigue contando como pendiente, que es lo que hace que alguien vuelva a
poner el día—, y un `estado` que diga `PAGADO` sin constancia no convierte en pagada una detracción que no lo está. **El monto se deposita siempre en soles**, incluso si la factura
está en dólares: por eso `monto` es en soles aunque el resto del comprobante esté en otra moneda.

**La tabla de detracciones vive en el motor.** El código, el nombre y la tasa de cada detracción, con su fuente, los
trae el motor, y la API los entrega en `catalogos_sunat`. El ERP que lo integra puede sobreescribirla en su
configuración: cambiar una tasa o un nombre, o sumar un código. Una detracción cuyo código no está en esa tabla queda
en blanco en todas las operaciones, así un código que no existe, como un «000», nunca provisiona una detracción.

---

## Las líneas del asiento, para quien escribe un driver

Desde la librería 0.7 el asiento **nace** en estas líneas y cada sistema contable es una traducción de
ellas (el Excel de CONCAR incluido). Por eso cada línea dice lo que un driver necesita para traducir sin
adivinar:

- **`clase`** — qué es la cuenta de esta línea: `activo`, `pasivo`, `patrimonio`, `ingreso` o `gasto`.
  **Obligatoria desde la 1.0**, y derivada del **primer dígito de la cuenta**, que es el elemento del PCGE: 1, 2 y 3
  activo; 4 pasivo; 5 patrimonio; 6 y 9 gasto; 7 ingreso. No sale del rol — en una compra de mercadería el rol es
  `principal` y la línea es un activo—, y los elementos 8 y 0 no tienen clase, así que una imputación a una de esas
  cuentas no genera asiento. Son los cinco valores que QuickBooks, Xero, Merge y Rutter comparten, y por eso son lo
  único que un ERP de fuera entiende sin conocer el PCGE. **Con `clase`, `debe_haber` e `importe` se puede
  contabilizar una línea aunque no se conozca su `rol`**: es la regla de degradación que permite que el catálogo de
  roles crezca sin romper a nadie.
- **`rol`** — qué papel cumple: `principal` (el gasto en compras, el ingreso en ventas), `igv`,
  `retencion_4ta`, `tercero` (el proveedor o el cliente), `detraccion_tercero` y `detraccion`. Un ERP
  que pida el IGV en una columna aparte encuentra esa línea por su rol, no por su cuenta, que la elige
  cada empresa.
- **`documento.tipo_cp`** y **`referencia.tipo_cp`** — el código SUNAT (Tabla 10). Es el que manda
  (regla 4). `documento.tipo` sigue llevando la sigla del ERP por compatibilidad. La línea `detraccion`
  no lleva `tipo_cp`: su documento es la constancia pendiente, no un comprobante de SUNAT.
- **`detraccion.codigo`** — el código SUNAT del bien o servicio (Catálogo 54), al lado del interno.
- **`glosa`** es **la misma en todas las líneas del comprobante** y va entera, sin prefijos: qué es cada línea
  lo dicen su `rol` y su cuenta, no un texto. Cortarla al largo que admite cada ERP es trabajo del driver.
  (Hasta la 2.1 del motor las líneas derivadas anteponían `IGV - `, `RET 4TA - ` o `DETRACCION - `.)
- **`tasa_igv`** es la del comprobante como texto (`"18"`, `"10.5"`). Si un ERP solo admite enteros,
  redondea él.
- **Sin vocabulario legacy, para un ERP.** `sub_diario`, `correlativo` y `documento.tipo` son vocabulario de un
  sistema legacy como CONCAR, y ya eran opcionales. El motor entrega también un perfil **neutral** (driver
  `asiento_neutral`): las mismas líneas, con las mismas cuentas, sentidos e importes, sin esos campos y con la
  detracción sobre el propio comprobante en vez del documento comodín.

Son campos **opcionales añadidos**, así que no cambian la versión del estándar (ver *Versionado*): un
consumidor que no los conozca los ignora. La excepción es `clase`, que es obligatoria desde la 1.0 — y es lo que
permite que el resto pueda degradar.

---

## Campos que conviene mirar dos veces

| Campo | Cuidado |
|---|---|
| `base_gravada`, `igv` | El importe **neto** de la operación, tras cualquier descuento. Así lo dan el `TaxableAmount` y el `TaxAmount` del XML, y así cuadra el total: base + IGV + no gravados + cargos. |
| `dscto_base`, `dscto_igv` | **No suman ni restan.** Dicen qué parte de la base y del IGV informa el registro en sus columnas de descuento (SIRE ventas, campos 16 y 18). Una nota de crédito de descuento global va **entera** ahí —así la registra SUNAT— y entonces valen lo mismo que `base_gravada` e `igv`. |
| `retencion` | Es la **retención de renta de 4ta** que muestra un recibo por honorarios. **No** es la retención del IGV del 3 %, que no entra en ningún asiento y que las IAs confunden constantemente con una detracción. |
| `destino_igv` | Solo compras. `DG` gravadas, `DGNG` mixtas, `DNG` no gravadas. Decide qué columnas usa el registro que se declara. |
| `condicion_pago` | `contado` o `credito`: lo que **declara** el documento. En la factura electrónica viene en `PaymentTerms FormaPago`, y una factura con cuotas es a crédito. Vacío no significa contado: significa que el documento no lo dice. |
| `medio_pago` | **Con qué** se pagó, que es otra pregunta que `condicion_pago`: un código de tres dígitos del catálogo de medios de pago de SUNAT (`001` depósito en cuenta, `003` transferencia, `005` tarjeta de débito… `999` otros). Vacío = el documento no lo dice, y entonces quien exporta usa el que tenga configurado el contribuyente. Un código que el catálogo no tenga **no invalida el documento**: se avisa y se respeta, porque SUNAT puede añadir uno. |
| `id_externo` | El id con el que la aplicación que produce el documento conoce ese comprobante (su fila). Es la llave de su imputación: sin él, al documento no le llega ninguna. |
| `tipo_cambio` | El que **publica SUNAT para la fecha de emisión**, con 3 decimales. No el del día del pago. |
| `serie` | Vacía en los comprobantes que no la llevan (recibo de servicios públicos, tipo `14`). Que esté vacía no es un error. |
| `contraparte_doc` | Puede ir vacío en boletas a consumidor final. |
| `origen` | Trazabilidad, no lógica: `xml` es un dato leído de la fuente oficial; `vision` lo leyó una IA de una foto y merece revisión humana. |
| `confianza` | De 0 a 1. Solo tiene sentido por debajo de 1 en lo que leyó una IA. |

---

## Versionado

`open_accounting` es la versión del estándar, no la de la librería. **Y ninguno de los dos números puede ser
prefijo del otro**, que es lo que de verdad los confunde: `"1.0"` es prefijo de `"1.0.0"`, así que la librería saltó
a `1.1.0` en la misma tanda en que el estándar llegó a `1.0`, y `tests/test_version.py` pone la batería en rojo si
alguien lo intenta de otra forma.

La regla del versionado, en **tres niveles** (1.0):

| Cambio | Ejemplo | ¿Sube la versión? |
|---|---|---|
| **Un valor nuevo en un catálogo** | Un rol `percepcion`; un libro `honorario` | **No.** Se publica el catálogo con su fecha, y quien no conoce el valor degrada con `clase` |
| **Un bloque opcional nuevo** | `movimientos[]` del banco; `plan_de_cuentas` | **No.** Quien no lo entiende lo ignora |
| **Cambiar lo que ya existe** | Volver obligatorio un campo, quitarlo, cambiar su significado | **Sí** |

Con esa regla, un hecho nuevo entra como **bloque propio** y nunca como valor forzado en el enum de otro: un
movimiento bancario no tiene tipo de comprobante, ni serie, ni IGV, y meterlo como «tipo de libro» rompería a todo el
que espera `comprobantes[]`. Es lo que hacen QuickBooks con un recurso por hecho y EN 16931 con su lista externa de
tipos de documento.

- Las claves que empiezan con `_` son anotaciones de quien produce el archivo. Se transportan y se ignoran;
  nunca llevan datos con significado contable.

`0.1` es la primera versión publicada y se deriva de un modelo que lleva un año generando el Excel de CONCAR
y el TXT del SIRE de empresas reales — no de un diseño en papel. Lo que falte, faltará porque nadie lo ha
necesitado todavía; se añade con un caso real detrás, no por si acaso.

**`0.2` (11-sep-2026) cambia el significado de dos campos**, y por eso sube: `base_gravada` e `igv` pasan a ser
siempre netos y `dscto_base`/`dscto_igv` dejan de restarse del total. En `0.1` el descuento se restaba de una
base bruta, pero el XML de SUNAT da la base ya neta, así que una nota de crédito de descuento global salía
contada dos veces. Un documento `0.1` sin descuentos significa exactamente lo mismo en `0.2`.

**Dentro de la `0.2`** (12-sep-2026) entran dos campos opcionales del comprobante, `condicion_pago` e
`id_externo`, y **`cuenta_contable` y `centro_costo` pasan a legado**: se siguen aceptando, pero la imputación
—que llega aparte— manda sobre ellos. Nada cambia de significado: un documento sin imputación se exporta
exactamente igual que antes. Quitarlos del comprobante sí cambiaría la forma del estándar, y por eso salen en la
`0.3`.

**`1.0` (18-sep-2026) es la primera versión estable, y trae tres cosas.** La **imputación viaja dentro del
documento** (bloque `imputaciones` de la raíz, llaveado por `id_externo`), para que un archivo guardado explique su
propio asiento; cada **línea del asiento lleva su `clase`** —`activo`, `pasivo`, `patrimonio`, `ingreso`, `gasto`—,
derivada del primer dígito de su cuenta, para que una línea suelta se entienda sin mirar `libro.tipo`; y **`rol` y
`libro.tipo` salen del esquema a catálogos publicados**, para que un valor nuevo no cueste una versión. La línea gana
además `documento.id_externo`, el enlace con el comprobante que la originó. **El motor no acepta documentos de la
0.3**: un documento que se declare así se rechaza diciendo qué cambió.

**`0.3` (12-sep-2026) cambia el nombre y la forma.** El estándar se llamaba `pe-ledger` y pasa a llamarse
`open-accounting`: la clave del documento es `open_accounting`, y el esquema, `open-accounting.schema.json`. Salen del
comprobante `cuenta_contable` y `centro_costo`, que llegan solo en la imputación, y `datos_raw` pasa a
`datos_originales`. Un documento que todavía trae cuenta o centro en el comprobante se rechaza, en vez de perderlos
en silencio.

---

## Anotaciones que produce el motor

Las claves que empiezan con `_` son anotaciones: se transportan, se ignoran y nunca llevan datos con
significado contable. Dos las escribe el propio motor (desde la 0.8.0 de la librería):

- **`_exportacion`** — en la respuesta de `exportar`: `{driver, archivo, huella, fecha, comprobantes, motor}`. La **huella** es el
  sha256 del contenido del asiento que salió: las líneas neutrales, en su orden, **sin el `correlativo`, la `clase` ni
  el `documento.id_externo`**, serializadas con `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.
  Los tres quedan fuera porque no cambian el contenido contable: el correlativo arranca en otro número tras un
  «deshacer», la clase se deriva de la cuenta —que sí entra— y el `id_externo` es el id del sistema que produjo el
  comprobante, que la aplicación recrea justo al reexportar. Responde «¿este
  contenido ya salió?» —la misma exportación repetida tras un «deshacer» arranca en otro número y lleva la
  misma huella—, que es lo que hace falta para avisar de un lote repetido: el Excel de CONCAR se suma al
  importarlo dos veces. Un registro tributario (el TXT del SIRE) no la lleva: no hay asiento. La `fecha`
  (`AAAA-MM-DD`) la pone quien llama; el motor no mira el reloj. La fórmula es contrato: cambiarla se anuncia.
- **`_asiento.huella`** — en la respuesta de `generar_asiento`, la misma huella de esas líneas.
- **`comprobantes`** — en `_exportacion` y en `_asiento` (desde la 1.0), lo que salió de cada comprobante: su
  `identidad` («La identidad de un comprobante»), el tramo `lineas` `[desde, hasta)` de las líneas del asiento que le
  tocan y la `huella` de ese tramo. Los tramos son una partición exacta y cada uno cuadra. Un registro que no arma
  asiento —el TXT del SIRE, el de CONTASIS— lleva solo la identidad.
- **`motor`** — en `_exportacion` y en `_asiento` (desde la 1.0), la versión de la librería que produjo la respuesta.
  No entra en ninguna huella: la misma tanda exportada con otra versión sigue siendo la misma tanda.

Un productor que guarde un documento puede copiar `_exportacion` en su raíz tal cual: el esquema admite ahí
cualquier clave `_`. Dentro de un comprobante o de una línea, no.

## Nombres reservados

Tres campos que `REFERENCIAS.md` propone y que **no** entran hasta que haya un caso real detrás (11-sep-2026).
El nombre está tomado —el día que entren, entran así— y mientras tanto un productor los lleva en `datos_originales`,
que el motor transporta sin interpretar. **Cada uno tiene su enmienda** en
[`enmiendas/`](enmiendas/LEEME.md), donde está lo que se espera de él y qué caso real le falta:

| Dónde | Nombre | Qué será |
|---|---|---|
| línea | `id_en_destino` | El id con el que el sistema de destino conoce ese asiento (Merge `remote_id`, Rutter `platform_id`). Se llamaba `id_externo` hasta el 18-sep-2026, y se renombró antes de existir para que no se confunda con `linea.documento.id_externo`, que es el id del sistema que **produjo** el comprobante ([enmienda 0001](enmiendas/0001-id-en-destino.md)) |
| comprobante, línea | `dimensiones` | `[{tipo, codigo}]`: área, proyecto, obra… más allá del `centro_costo`, que sigue siendo la primera (Xero `Tracking[]`) |
| línea | `estado` | `propuesto \| exportado \| importado \| anulado`; el núcleo nunca escribiría `importado`. Ojo: `estado` ya existe en el comprobante (`ok \| observada \| duplicada`) y en la detracción (`PROVISIONADO \| PAGADO`) con otro sentido |

Lo que sí entró de esa propuesta: `_exportacion` (arriba), `EXIGE` en el contrato de driver y `pedir_a` en
`diagnosticar` (`ARQUITECTURA.md`).

Y tres que pide el registro de CONTASIS (12-sep-2026) y que esperan un caso real o una decisión —el cuarto, `medio_pago`, **entró el 25-sep-2026** ([enmienda 0004](enmiendas/0004-medio-de-pago.md)): la decisión que le faltaba era si es dato del documento o valor del contribuyente, y la respuesta fue las dos cosas—:

| Dónde | Nombre | Qué será |
|---|---|---|
| comprobante | `retencion_igv` | `{porcentaje, monto}`: la retención del IGV del 3 %, que el XML trae en `PaymentTerms Retencion`. **No es `retencion`**, que es la renta de 4ta |
| comprobante | `percepcion` | El régimen de percepciones del IGV |
| comprobante | `no_domiciliado` | El número del comprobante que emite un sujeto no domiciliado |

Lo que ya sale en la segunda columna de centro de costos de CONTASIS es el **mismo** centro del documento, si la
sección `contasis` la elige en `columnas.centro_costo` (13-sep-2026, `drivers/contasis/datos.py`): el mismo dato en
otra columna, no una dimensión. Un segundo centro **distinto** y el código de presupuesto irían en `dimensiones`, el
nombre ya reservado de la tabla de arriba, y como son decisiones de cada entorno, en la imputación y no en el
documento. El CONTASIS de John no los usa (12-sep-2026), así que sigue reservado.

---

## Los catálogos, y cómo degrada cada uno

Tres cosas que este estándar inventa —los **roles** de una línea, las cinco **clases** contables y los **tipos de
libro**— viven en [`catalogos.json`](catalogos.json), junto a este archivo, con su fuente y su versión. Se citan por
la URL del tag igual que el esquema, así que un ERP de fuera los lee sin instalar nada:

```
https://raw.githubusercontent.com/contaperu/contaperu/open-accounting-1.0/estandar/catalogos.json
```

**Por qué están fuera del esquema** (1.0): eran enums cerrados, así que el día que entre un hecho nuevo —los
movimientos del banco, las letras de cambio— sus roles costarían una versión del estándar. Con el catálogo no cuestan
ninguna. **Abrirlos no es que crezcan:** los seis roles son los de compras y ventas, y no se añade ninguno hasta que
aparezca el hecho que lo necesite.

**Y no degradan igual, que es lo que hay que tener claro:**

| | Si llega un valor que no conozco |
|---|---|
| **`rol`** | **No rompe nada.** La línea se contabiliza con `clase`, `debe_haber` e `importe`. Es la regla de degradación, y es la que permite que el catálogo crezca sin romper a ningún ERP ya integrado |
| **`libro.tipo`** | **Sigue siendo un error**: quien recibe un registro que no conoce no puede adivinar qué hacer con él. Quien degrada es el destino — el driver que no lo declara en sus `FORMATOS` lo rechaza limpio, diciendo qué libros lleva |

---

**Si vienes de la 0.3**, la guía de migración está en [`MIGRAR-A-1.0.md`](MIGRAR-A-1.0.md): son tres cambios en el
documento y uno en la clave de versión.

---

## Cómo compruebas que lo que produces es correcto

Cuatro piezas. La de arriba entró en la 3.1 y es la que faltaba para quien **no usa el motor**: hasta
entonces el esquema estaba publicado y la única forma de correrlo era clonar el repositorio.

| Pieza | Qué comprueba |
|---|---|
| `contaperu verificar-documento mi-documento.json` | **Un documento tuyo contra ESTE estándar**: su esquema y sus catálogos, sin armar ni exportar nada |
| `python -m contaperu.puertas.cli diagnosticar mi-mes.json` | **Un documento tuyo**: qué bloquea, qué falta y a quién pedírselo |
| `contaperu verificar-driver mi_paquete.mi_driver` | **Un driver propio** contra el contrato, antes de registrarlo |
| [`conformidad/esquema.json`](conformidad/esquema.json) | **Que tus documentos son conformes**, con un validador y nada más: sin el motor y en cualquier lenguaje |
| [`conformidad/diagnosticar.json`](conformidad/diagnosticar.json) | **Que ESTE motor decide bien**. No es para comprobar el tuyo: mira abajo |

La conformidad son dos juegos de casos, publicados con el tag del estándar:

- [`conformidad/esquema.json`](conformidad/esquema.json) — casos `{description, data, valid}` con la forma de la
  *JSON Schema Test Suite*, para correrlos con **cualquier validador de draft 2020-12** y sin el motor. Es lo que
  permite que un ERP en otro lenguaje los use tal cual.
- [`conformidad/diagnosticar.json`](conformidad/diagnosticar.json) — casos con su documento, su configuración, su
  destino y lo que se espera: si el mes queda listo, qué falta y a quién pedírselo. **Estos no son portables, y
  conviene saberlo antes de intentarlo**: nombran drivers del motor y lo que esperan está escrito contra la forma de
  la respuesta de `api.diagnosticar`, que es superficie del paquete y no del estándar. Comprueban que ESTE motor
  decide bien; para comprobar el tuyo están los de esquema, y lo demás lo decide tu contabilidad, no la nuestra.

**Los corre la batería de este repositorio**: si el motor no pasa su propia conformidad, no la pasa nadie. Y casi todos
los casos salen de algo que se equivocó de verdad al escribir la 1.0 — el recibo por honorarios con el importe en la
casilla equivocada, la factura en dólares sin tipo de cambio, el `detraccion: false` de relleno, la cuenta de un
elemento sin clase.

**Y desde la 3.1 viajan dentro del paquete**, en `contaperu/estandar/conformidad/`: hasta entonces solo estaban en el
repositorio y en el sdist, así que quien instalaba `contaperu` no los tenía y la única forma de correrlos era clonar.
Ofrecerlos para comprobar lo que produces y no ponerlos donde se instala era la mitad de la promesa.

---

## Quién gobierna los catálogos

Mientras `rol` y `libro.tipo` eran enums cerrados dentro del esquema, quien quisiera un valor nuevo tenía que abrir un
PR y discutirlo. Al sacarlos a catálogos publicados esa conversación **desaparece**, así que hay que reponerla a
propósito: un catálogo abierto sin gobierno es una invitación a que cada ERP invente sus propios valores y el estándar
deje de serlo.

| | |
|---|---|
| **Quién aprueba** | John, mientras el repositorio sea suyo. Dicho, no sobreentendido: quien integra necesita saber a quién le pregunta |
| **Cómo se propone** | Un aviso con **el caso real detrás** —un archivo de verdad de un sistema de verdad, anonimizado—, y su [enmienda](enmiendas/LEEME.md) |
| **Qué se responde** | Si entra, entra como valor de catálogo con su fecha; si no, se dice por qué. Un catálogo que crece sin criterio es un enum con más pasos |

**Y la regla que protege a quien ya integró: un valor publicado no se quita ni cambia de significado.** Si resulta
equivocado, se marca como obsoleto y entra otro al lado. Es lo que hacen las listas de códigos de ISO 20022 y de
EN 16931, y la razón de que sus mensajes sobrevivan décadas.

**Lo que no se gobierna** son los catálogos de **SUNAT** —tipos de comprobante, documentos de identidad, monedas,
detracciones, el PCGE—: no se proponen ni se discuten, se copian de la norma con su fuente y su fecha. Cuando SUNAT
cambia una tasa o añade un código, el catálogo lo refleja y ya. Lo que se gobierna es solo lo que este estándar
inventa: los **roles**, las **clases** y los **tipos de libro**.

---

## Lo que este estándar **no** intenta ser

- **No es un plan de cuentas.** Las cuentas son las del contribuyente; el estándar solo las transporta.
- **No es un formato de factura electrónica.** Eso es UBL 2.1, y SUNAT ya lo define. `open-accounting` empieza
  donde la factura termina.
- **No es un libro electrónico.** El TXT del SIRE y los Excel de CONCAR y de CONTASIS son salidas, no el estándar.
- **No lleva estado.** No hay identificadores de base de datos, ni usuarios, ni empresas: un documento
  `open-accounting` se entiende solo, en cualquier máquina, sin consultar nada.
