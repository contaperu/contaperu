# pe-ledger 0.2 — el documento contable universal del Perú

Un solo JSON que sirve para las tres cosas que un contador peruano necesita mover de un sistema a otro:
**qué libro es**, **qué comprobantes lo componen** y **cómo queda el asiento**.

Existe porque hoy no hay ninguno. CONCAR, CONTASIS y SISCONT importan cada uno su propio archivo plano;
una IA que lee un PDF no tiene dónde depositar lo que extrajo; y quien cambia de sistema contable rehace la
integración desde cero. El estándar no reemplaza a ninguno: es el idioma intermedio.

**Esquema formal:** [`pe-ledger.schema.json`](pe-ledger.schema.json) (JSON Schema draft 2020-12).
Su identificador canónico —el `$id` con el que se cita este estándar desde fuera— es:

```
https://raw.githubusercontent.com/contaperu/contaperu/pe-ledger-0.2/estandar/pe-ledger.schema.json
```

Cuelga del tag **del estándar** (`pe-ledger-0.2`), no del de la librería: la versión del paquete sube
cada vez que se corrige un driver, y un identificador que se mueve bajo los pies de quien lo cita no
sirve como estándar. **El tag `pe-ledger-0.2` avanza con cada cambio aditivo** —un campo opcional nuevo no
sube la versión (ver Versionado)—, así que esa URL devuelve el último esquema compatible con la 0.2; un cambio
de significado sube a 0.3 y estrena su propio tag.

```bash
python -m contaperu.cli validar mi-documento.json
```

---

## Los tres bloques

```json
{
  "pe_ledger": "0.2",
  "libro":        { "ruc": "20601234567", "razon_social": "EMPRESA SAC",
                    "periodo": "202601", "tipo": "compra" },
  "comprobantes": [ { "tipo_cp": "01", "serie": "F001", "numero": "00045680", "…": "…" } ],
  "asiento":      [ { "cuenta": "659999", "debe_haber": "D", "importe": "40000.00", "…": "…" } ]
}
```

**`libro`** — la cabecera tributaria. Un RUC, un mes (`AAAAMM`), y `venta` o `compra`. Es obligatoria: sin
saber de quién y de cuándo es, un comprobante suelto no es contabilidad.

**`comprobantes`** — los **registros**: cada documento soporte con los campos tal como los define SUNAT, más
la imputación contable que el contador decide para ese documento (la cuenta de la base, la del total, el
centro de costo). Es lo que sale de un XML UBL, de la propuesta del SIRE o de leer un PDF. Con este bloque
basta: un sistema que importa registros sale de él directamente, y a uno que importa asientos se le genera.

**`asiento`** — las líneas de diario, **sin nada de ningún ERP**: cuenta, debe o haber, importe, moneda,
glosa, centro de costo. Es el bloque que permite que un sistema contable consuma el resultado sin saber qué
lo generó. Es opcional: quien ya lo tiene armado lo manda, quien no, lo pide.

---

## Dónde va cada dato

El registro, la configuración del contribuyente y el driver de salida nunca guardan lo mismo: cada dato
tiene un solo dueño.

| Si el dato… | Va en | Ejemplo |
|---|---|---|
| Está impreso en el documento o en su XML | **el registro** | fecha, serie, importes, `condicion_pago` |
| Lo decide el contador para ESE documento | **el registro**, opcional; si falta, la configuración | `cuenta_contable`; `cuenta_tercero` cuando no es la de siempre |
| Es igual para todo el contribuyente | **la configuración** (fuera del documento) | la cuenta por pagar en soles, la del IGV, las siglas de CONCAR |
| Se calcula con lo anterior | **nadie lo guarda**: lo deriva el driver | el signo de la nota de crédito, los soles de una factura en dólares, el % de IGV, el correlativo |

**Las cuentas se resuelven una sola vez, en el núcleo** (`asiento.cuenta_de_fila` y `asiento.cuenta_tercero`),
para todos los drivers. Si un registro manda su total a la `4699`, esa cuenta sale igual en el asiento de
CONCAR y en la columna de un sistema que importa registros. Ningún driver elige una cuenta.

## Dos familias de salida, un solo documento

- **Registro** — una fila por comprobante, sin asiento: el TXT del SIRE, y los sistemas contables que
  importan su registro de compras y de ventas y arman el asiento ellos mismos (CONTASIS, en construcción).
- **Asiento** — el núcleo convierte los registros en líneas de diario una sola vez y el driver las traduce:
  el Excel de CONCAR, el CSV y los sistemas que importan asientos.

Un sistema nuevo solo elige familia: el documento del que sale es el mismo.

---

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

**5. Lo que no se entiende, se transporta.** `datos_raw` es un objeto libre donde el productor guarda lo
suyo. El núcleo lo lleva de un extremo al otro y no lo lee jamás.

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
- **`PAGADO`** — se depositó. Se inyectan `nro_constancia` y `fecha_constancia`, y el asiento puede
  regenerarse con el número real.

El paso de uno a otro es una operación aparte, sin estado: entra el documento provisional y el archivo de
constancias, sale el documento actualizado. **El monto se deposita siempre en soles**, incluso si la factura
está en dólares: por eso `monto` es en soles aunque el resto del comprobante esté en otra moneda.

---

## Las líneas del asiento, para quien escribe un driver

Desde la librería 0.7 el asiento **nace** en estas líneas y cada sistema contable es una traducción de
ellas (el Excel de CONCAR incluido). Por eso cada línea dice lo que un driver necesita para traducir sin
adivinar:

- **`rol`** — qué papel cumple: `principal` (el gasto en compras, el ingreso en ventas), `igv`,
  `retencion_4ta`, `tercero` (el proveedor o el cliente), `detraccion_tercero` y `detraccion`. Un ERP
  que pida el IGV en una columna aparte encuentra esa línea por su rol, no por su cuenta, que la elige
  cada empresa.
- **`documento.tipo_cp`** y **`referencia.tipo_cp`** — el código SUNAT (Tabla 10). Es el que manda
  (regla 4). `documento.tipo` sigue llevando la sigla del ERP por compatibilidad. La línea `detraccion`
  no lleva `tipo_cp`: su documento es la constancia pendiente, no un comprobante de SUNAT.
- **`detraccion.codigo`** — el código SUNAT del bien o servicio (Catálogo 54), al lado del interno.
- **`glosa`** va entera, con su prefijo (`IGV - `, `RET 4TA - `, `DETRACCION - `). Cortarla al largo
  que admite cada ERP es trabajo del driver.
- **`tasa_igv`** es la del comprobante como texto (`"18"`, `"10.5"`). Si un ERP solo admite enteros,
  redondea él.

Son campos **opcionales añadidos**, así que no cambian la versión del estándar (ver *Versionado*): un
consumidor de la 0.2 que no los conozca los ignora.

---

## Campos que conviene mirar dos veces

| Campo | Cuidado |
|---|---|
| `base_gravada`, `igv` | El importe **neto** de la operación, tras cualquier descuento. Así lo dan el `TaxableAmount` y el `TaxAmount` del XML, y así cuadra el total: base + IGV + no gravados + cargos. |
| `dscto_base`, `dscto_igv` | **No suman ni restan.** Dicen qué parte de la base y del IGV informa el registro en sus columnas de descuento (SIRE ventas, campos 16 y 18). Una nota de crédito de descuento global va **entera** ahí —así la registra SUNAT— y entonces valen lo mismo que `base_gravada` e `igv`. |
| `retencion` | Es la **retención de renta de 4ta** que muestra un recibo por honorarios. **No** es la retención del IGV del 3 %, que no entra en ningún asiento y que las IAs confunden constantemente con una detracción. |
| `destino_igv` | Solo compras. `DG` gravadas, `DGNG` mixtas, `DNG` no gravadas. Decide qué columnas usa el registro que se declara. |
| `condicion_pago` | `contado` o `credito`: lo que **declara** el documento. En la factura electrónica viene en `PaymentTerms FormaPago`, y una factura con cuotas es a crédito. Vacío no significa contado: significa que el documento no lo dice. |
| `cuenta_tercero` | Vacía en casi todos los registros: la cuenta del proveedor o del cliente sale de la configuración, por moneda. Solo se escribe cuando ESE documento va a otra (un gasto de representación a la `4699`), y entonces manda en todos los drivers. |
| `tipo_cambio` | El que **publica SUNAT para la fecha de emisión**, con 3 decimales. No el del día del pago. |
| `serie` | Vacía en los comprobantes que no la llevan (recibo de servicios públicos, tipo `14`). Que esté vacía no es un error. |
| `contraparte_doc` | Puede ir vacío en boletas a consumidor final. |
| `origen` | Trazabilidad, no lógica: `xml` es un dato leído de la fuente oficial; `vision` lo leyó una IA de una foto y merece revisión humana. |
| `confianza` | De 0 a 1. Solo tiene sentido por debajo de 1 en lo que leyó una IA. |

---

## Versionado

`pe_ledger` es la versión del estándar, no la de la librería. La regla:

- **Añadir un campo opcional** no sube la versión mayor. Un consumidor viejo lo ignora.
- **Quitar un campo, renombrarlo o cambiar su significado** sube la versión y se documenta aquí.
- Las claves que empiezan con `_` son anotaciones de quien produce el archivo. Se transportan y se ignoran;
  nunca llevan datos con significado contable.

`0.1` es la primera versión publicada y se deriva de un modelo que lleva un año generando el Excel de CONCAR
y el TXT del SIRE de empresas reales — no de un diseño en papel. Lo que falte, faltará porque nadie lo ha
necesitado todavía; se añade con un caso real detrás, no por si acaso.

**`0.2` (11-sep-2026) cambia el significado de dos campos**, y por eso sube: `base_gravada` e `igv` pasan a ser
siempre netos y `dscto_base`/`dscto_igv` dejan de restarse del total. En `0.1` el descuento se restaba de una
base bruta, pero el XML de SUNAT da la base ya neta, así que una nota de crédito de descuento global salía
contada dos veces. Un documento `0.1` sin descuentos significa exactamente lo mismo en `0.2`.

**Dentro de la `0.2`** (12-sep-2026) entran dos campos opcionales del comprobante, `condicion_pago` y
`cuenta_tercero`, para que un sistema que importa registros salga del documento sin datos de fuera. No
cambian el significado de nada: un documento sin ellos se exporta exactamente igual que antes.

---

## Anotaciones que produce el motor

Las claves que empiezan con `_` son anotaciones: se transportan, se ignoran y nunca llevan datos con
significado contable. Dos las escribe el propio motor (desde la 0.8.0 de la librería):

- **`_exportacion`** — en la respuesta de `exportar`: `{driver, archivo, huella, fecha}`. La **huella** es el
  sha256 del contenido del asiento que salió: las líneas neutrales, en su orden, **sin el correlativo**,
  serializadas con `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))`. Responde «¿este
  contenido ya salió?» —la misma tanda exportada otra vez tras un «deshacer» arranca en otro número y lleva la
  misma huella—, que es lo que hace falta para avisar de un lote repetido: el Excel de CONCAR se suma al
  importarlo dos veces. Un registro tributario (el TXT del SIRE) no la lleva: no hay asiento. La `fecha`
  (`AAAA-MM-DD`) la pone quien llama; el motor no mira el reloj. La fórmula es contrato: cambiarla se anuncia.
- **`_asiento.huella`** — en la respuesta de `generar_asiento`, la misma huella de esas líneas.

Un productor que guarde un documento puede copiar `_exportacion` en su raíz tal cual: el esquema admite ahí
cualquier clave `_`. Dentro de un comprobante o de una línea, no.

## Nombres reservados

Tres campos que `REFERENCIAS.md` propone y que **no** entran hasta que haya un caso real detrás (11-sep-2026).
El nombre está tomado —el día que entren, entran así— y mientras tanto un productor los lleva en `datos_raw`,
que el motor transporta sin interpretar:

| Dónde | Nombre | Qué será |
|---|---|---|
| comprobante, línea | `id_externo` | El id con el que el sistema de origen o de destino conoce ese comprobante o asiento (Merge `remote_id`, Rutter `platform_id`) |
| comprobante, línea | `dimensiones` | `[{tipo, codigo}]`: área, proyecto, obra… más allá del `centro_costo`, que sigue siendo la primera (Xero `Tracking[]`) |
| línea | `estado` | `propuesto \| exportado \| importado \| anulado`; el núcleo nunca escribiría `importado`. Ojo: `estado` ya existe en el comprobante (`ok \| observada \| duplicada`) y en la detracción (`PROVISIONADO \| PAGADO`) con otro sentido |

Lo que sí entró de esa propuesta: `_exportacion` (arriba), `EXIGE` en el contrato de driver y `pedir_a` en
`diagnosticar` (`ARQUITECTURA.md`).

Y cuatro que pide el registro de CONTASIS (12-sep-2026) y que esperan un caso real o una decisión:

| Dónde | Nombre | Qué será |
|---|---|---|
| comprobante | `medio_pago` | El código de medio de pago de SUNAT (`001` depósito en cuenta…), si resulta ser dato de cada documento y no un valor del contribuyente |
| comprobante | `retencion_igv` | `{porcentaje, monto}`: la retención del IGV del 3 %, que el XML trae en `PaymentTerms Retencion`. **No es `retencion`**, que es la renta de 4ta |
| comprobante | `percepcion` | El régimen de percepciones del IGV |
| comprobante | `no_domiciliado` | El número del comprobante que emite un sujeto no domiciliado |

El segundo centro de costo y el código de presupuesto de CONTASIS irían en `dimensiones`, el nombre ya
reservado de la tabla de arriba.

---

## Lo que este estándar **no** intenta ser

- **No es un plan de cuentas.** Las cuentas son las del contribuyente; el estándar solo las transporta.
- **No es un formato de factura electrónica.** Eso es UBL 2.1, y SUNAT ya lo define. `pe-ledger` empieza
  donde la factura termina.
- **No es un libro electrónico.** El TXT del SIRE y los archivos del PLE son salidas, no el estándar.
- **No lleva estado.** No hay identificadores de base de datos, ni usuarios, ni empresas: un documento
  `pe-ledger` se entiende solo, en cualquier máquina, sin consultar nada.
