# pe-ledger 0.1 — el documento contable universal del Perú

Un solo JSON que sirve para las tres cosas que un contador peruano necesita mover de un sistema a otro:
**qué libro es**, **qué comprobantes lo componen** y **cómo queda el asiento**.

Existe porque hoy no hay ninguno. CONCAR, CONTASIS y SISCONT importan cada uno su propio archivo plano;
una IA que lee un PDF no tiene dónde depositar lo que extrajo; y quien cambia de sistema contable rehace la
integración desde cero. El estándar no reemplaza a ninguno: es el idioma intermedio.

**Esquema formal:** [`pe-ledger.schema.json`](pe-ledger.schema.json) (JSON Schema draft 2020-12).
Su identificador canónico —el `$id` con el que se cita este estándar desde fuera— es:

```
https://raw.githubusercontent.com/global-procesos-ai/contaperu/pe-ledger-0.1/estandar/pe-ledger.schema.json
```

Cuelga del tag **del estándar** (`pe-ledger-0.1`), no del de la librería: la versión del paquete sube
cada vez que se corrige un driver, y un identificador que se mueve bajo los pies de quien lo cita no
sirve como estándar. Mientras el estándar siga en 0.1, esa URL devuelve exactamente el mismo archivo.

```bash
python -m contaperu.cli validar mi-documento.json
```

---

## Los tres bloques

```json
{
  "pe_ledger": "0.1",
  "libro":        { "ruc": "20601234567", "razon_social": "EMPRESA SAC",
                    "periodo": "202601", "tipo": "compra" },
  "comprobantes": [ { "tipo_cp": "01", "serie": "F001", "numero": "00045680", "…": "…" } ],
  "asiento":      [ { "cuenta": "659999", "debe_haber": "D", "importe": "40000.00", "…": "…" } ]
}
```

**`libro`** — la cabecera tributaria. Un RUC, un mes (`AAAAMM`), y `venta` o `compra`. Es obligatoria: sin
saber de quién y de cuándo es, un comprobante suelto no es contabilidad.

**`comprobantes`** — los documentos soporte, con los campos tal como los define SUNAT. Es lo que sale de un
XML UBL, de la propuesta del SIRE o de leer un PDF. Un documento puede traer solo este bloque y pedir que
se le genere el asiento.

**`asiento`** — las líneas de diario, **sin nada de ningún ERP**: cuenta, debe o haber, importe, moneda,
glosa, centro de costo. Es el bloque que permite que un sistema contable consuma el resultado sin saber qué
lo generó. Es opcional: quien ya lo tiene armado lo manda, quien no, lo pide.

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

## Campos que conviene mirar dos veces

| Campo | Cuidado |
|---|---|
| `retencion` | Es la **retención de renta de 4ta** que muestra un recibo por honorarios. **No** es la retención del IGV del 3 %, que no entra en ningún asiento y que las IAs confunden constantemente con una detracción. |
| `destino_igv` | Solo compras. `DG` gravadas, `DGNG` mixtas, `DNG` no gravadas. Decide qué columnas usa el registro que se declara. |
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

---

## Lo que este estándar **no** intenta ser

- **No es un plan de cuentas.** Las cuentas son las del contribuyente; el estándar solo las transporta.
- **No es un formato de factura electrónica.** Eso es UBL 2.1, y SUNAT ya lo define. `pe-ledger` empieza
  donde la factura termina.
- **No es un libro electrónico.** El TXT del SIRE y los archivos del PLE son salidas, no el estándar.
- **No lleva estado.** No hay identificadores de base de datos, ni usuarios, ni empresas: un documento
  `pe-ledger` se entiende solo, en cualquier máquina, sin consultar nada.
