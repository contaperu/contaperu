# API de registro: cómo se manda una compra o una venta, y el JSON que sirve para cualquier ERP

[REFERENCIAS.md](REFERENCIAS.md) miró el **asiento**: cómo modelan un `JournalEntry` QuickBooks, Xero y las APIs
unificadas. Este documento mira el escalón de antes, el **registro de un comprobante**: qué manda un sistema cuando
dice «anota esta compra» o «anota esta venta», y qué forma tiene que tener ese JSON para que le sirva a cualquier
ERP y no a uno solo. Termina con un borrador concreto para el motor.

**De dónde sale.** De la guía de uso de las API contables de STARSOFT Gold Edition, que registra por tipo de asiento
—compras, ventas, honorarios, cheques, estándar— y es hoy la forma más cercana a un «registro por API» que tiene un
ERP peruano instalado. Sirve de punto de partida, no de modelo a copiar.

**Estado: investigación y borrador.** Nada de lo que aquí se propone está en la librería 1.0.0 ni en
`open-accounting` 0.3. El proyecto crece con la misma regla de siempre: el estándar se mueve con casos reales
detrás, no por si acaso.

**Alcance.** Solo **compras y ventas**. Honorarios, cheques, asientos estándar y anexos quedan fuera: cada uno es
otro hecho contable y entra cuando tenga su caso.

**Convenciones.** Los RUC de los ejemplos son los seguros del proyecto (`20131312955` y `20601234567`); ninguna
empresa real aparece aquí. Los importes van en texto y las fechas en `AAAA-MM-DD`, como manda el estándar. Lo que no
se pudo confirmar en la documentación oficial va marcado *no verificado*. Investigación hecha el **15-sep-2026**;
las fuentes, al final.

---

## 0 · Tres cosas antes de empezar, porque el nombre engaña

1. **«Registrar» aquí no es guardar.** El motor no tiene estado, ni disco, ni red: recibe un documento y devuelve el
   diagnóstico y el asiento. Quien guarda es el sistema que llamó. Esto se llama registro porque es el momento del
   dominio —«anota esta compra»—, no porque el motor anote nada en ninguna parte.
2. **Quien tiene la librería no necesita esta API.** Un ERP en Python llama a `contaperu.api` dentro de su propio
   proceso, sin puerto y sin latencia. La puerta HTTP es para el que está en otro lenguaje o en otro servidor, y la
   levanta él: no hay una URL central del motor, ni la habrá mientras el motor no tenga estado.
3. **El formato es uno solo, y ya existe.** Es `open-accounting`. Este documento no propone un JSON nuevo al lado del
   estándar: propone que **el estándar sea también el cuerpo de la llamada**. La sección 6 cuenta por qué el primer
   borrador tenía dos formas y qué se ganó al juntarlas.

---

## 1 · El caso que lo motiva: la API de STARSOFT Gold Edition

STARSOFT publica seis rutas contables, todas `POST`, y una séptima para exportar
([ayuda de las APIs de integración](https://starsoftweb.com/apisintegracion/Help)):

| Ruta | Qué registra |
|---|---|
| `Api/RegistrarAsientoCompras` | Asientos de compras |
| `Api/RegistrarAsientoVentas` | Asientos de ventas |
| `Api/RegistrarAsientoHonorarios` | Recibos por honorarios |
| `Api/RegistrarAsientoCheques` | Cheques y pagos |
| `Api/RegistrarAsientoStandar` | Asientos varios |
| `Api/RegistrarAnexos` | La ficha del cliente o proveedor |
| `Api/ExportarMovimientos` | Devuelve lo registrado, por `Tipo_Asiento`: COM, VTA, CHE, HON, STD |

**La forma del cuerpo.** Un objeto con el RUC de la empresa y una lista, `listadoAsientos`, donde **cada elemento es
una línea de diario** que repite la cabecera del comprobante. Reescrito con los RUC seguros, una compra de 200 más
38 de IGV se manda como tres elementos que solo se distinguen en tres campos:

| Campo | Línea 1 | Línea 2 | Línea 3 |
|---|---|---|---|
| `cuenta` | `42102` | `60101` | `40111` |
| `debe_Haber` | `H` | `D` | `D` |
| `importe_Doc` | `238` | `200` | `38` |
| El resto (`annomes`, `subdiario`, `comprobante`, `fecha_Documento`, `tipo_Anexo`, `cod_Proveedor`, `tipo_Doc`, `nro_Doc`, `igv`, `tasa_Igv`, `tc`, `glosa`, `destino_Compra`…) | igual | igual | igual |

Los campos que lleva cada línea de compras: `cuenta`, `annomes`, `subdiario`, `comprobante`, `fecha_Documento`,
`fecha_Registro`, `fecha_Vencimiento`, `tipo_Anexo`, `cod_Proveedor`, `tipo_Doc`, `nro_Doc`, `igv`, `tasa_Igv`,
`importe_Doc`, `conversion_Tc`, `tc`, `glosa`, `glosa_Mov`, `destino_Compra`, `centro_Costos`, `p_Mixto`,
`valor_CIF`, `tipo_Doc_Ref`, `nro_Doc_Ref`, `fecha_Doc_Ref`, `detraccion`, `cod_Detraccion`, `tasa_Detraccion`,
`importe_Detraccion`, `nro_Detraccion`, `fecha_Detraccion`, `importacion`, `igv_Aplicar`, `anulado`, `otro_Imp`,
`impBolsa`, `nro_File`, `cinterface`, `codemp`, `usuario`. Ventas cambia `cod_Proveedor` por `cod_Cliente` y suma
`ruc_Cliente`, `razon_Social`, `valor_ISC`, `exportacion`, `exonerado`, `otros_Cargos` y `nro_Doc_Hasta`.

**Y el registro no termina en la llamada.** La API deja los datos en una tabla; el contador entra después al módulo
de contabilidad, a *Otros › Importación de datos externos*, elige el tipo y ejecuta la importación. La API alimenta
una bandeja, no contabiliza.

### Qué enseña

1. **Compras y ventas son dos hechos distintos, no dos formas del mismo.** Tienen campos propios —`destino_Compra` y
   la detracción de un lado; `exportacion` y el ISC del otro—, y por eso QuickBooks tiene `Bill` e `Invoice` y
   Business Central `purchaseInvoices` y `salesInvoices`. Lo que **no** se sigue de ahí es que hagan falta dos rutas:
   Xero y Merge lo dicen con un discriminador dentro del cuerpo, y aquí el documento ya lo trae en `libro.tipo`.
2. **El ERP quiere el asiento, no solo el documento.** Espera cuentas: `42102`, `60101`, `40111`. Un JSON que solo
   lleve el comprobante le obliga a inventarlas.
3. **La detracción y el centro de costo son de primera clase**, no un añadido. Cualquier estándar peruano tiene que
   llevarlos.

### Qué no se toma, y por qué

- **La cabecera repetida en cada línea.** Es la herencia del archivo plano: treinta campos duplicados por línea,
  donde una copia que se desincroniza es un asiento descuadrado. El documento va una vez y las líneas cuelgan de él.
- **El vocabulario de un sistema.** `subdiario`, `tipo_Anexo`, `tipo_Doc: "FT"`, `destino_Compra`, `conversion_Tc`
  son CONCAR y son STARSOFT, no SUNAT. Quien integre tres ERP tendría que aprender tres vocabularios; por eso el
  motor tiene desde la 1.1 un vocabulario neutral y el driver `open_accounting` (ver `ARQUITECTURA.md`).
- **Los números en coma flotante.** `importe_Doc: 238` y `tc: 3.026` son `float` de JSON. La contabilidad no perdona
  el céntimo que se pierde: el estándar manda importes en texto.
- **La serie y el número pegados con un espacio** (`"nro_Doc": "100 1"`). El estándar los separa, porque el motor
  normaliza los ceros a la izquierda para reconocer duplicados.
- **La tasa del ejemplo.** La guía publica `tasa_Igv: 19`, que hoy no rige. Es el recordatorio de por qué el motor
  lee la tasa del comprobante y nunca de una configuración ni de un ejemplo.
- **El mes en `annomes` dentro de cada línea.** El periodo es del libro, no de la línea.

---

## 2 · Cómo registra un comprobante cada API de EE. UU.

| | Compras y ventas | Impuesto | Moneda y T.C. | Contraparte | Los dos números | Nota de crédito | Borrador | Idempotencia | Cuenta en la línea |
|---|---|---|---|---|---|---|---|---|---|
| **QuickBooks Online** | 2 recursos: `Bill`, `Invoice` | `TaxCodeRef` por línea + `TxnTaxDetail` en cabecera; `GlobalTaxCalculation` incluido o excluido | `CurrencyRef` + `ExchangeRate` (*no verificado*) | Solo id interno (`VendorRef`, `CustomerRef`) | `DocNumber`, autogenerado si falta | Recursos aparte: `CreditMemo`, `VendorCredit` | No (*no verificado*) | `?requestid=`: repetir devuelve la respuesta original | Sí, `AccountRef` en la línea por cuenta |
| **Xero** | 1 recurso con `Type: ACCPAY \| ACCREC` | `TaxType` y `TaxAmount` por línea; `LineAmountTypes` | `CurrencyCode` + `CurrencyRate`; si falta, la del día | `Contact` por id o nombre | `InvoiceNumber` / `Reference` | Endpoint aparte, `CreditNotes` | `DRAFT`, `SUBMITTED`, `AUTHORISED` | Cabecera `Idempotency-Key` | Sí, `AccountCode` |
| **Business Central** | 2 recursos, cabecera y líneas en una llamada (*deep insert*) | `taxCode` por línea; `taxPercent` de solo lectura; `pricesIncludeTax` | `currencyCode`; el T.C. sale de su tabla | Id o número, con dirección opcional | `vendorInvoiceNumber` / `number` | Recursos aparte | `Draft` y luego la acción `post` | No documentada | Sí, `lineType: Account` |
| **NetSuite** | 2 registros: `vendorBill`, `invoice` | SuiteTax con `taxDetails` (la documentación se contradice sobre si el REST lo acepta) | `currency` + `exchangeRate` | Id interno (`entity`) | `tranId` | Registros aparte | `approvalStatus` | `externalId` con *upsert*, y cabecera en modo asíncrono | Sí, en la sublista `expense` |
| **Sage Intacct** (XML) | 2 objetos: APBILL, ARINVOICE | `TAXENTRIES` por línea; `INCLUSIVETAX` | `CURRENCY` + `EXCHRATE` | Id | `RECORDID` / `DOCNUMBER` | Objetos aparte | *no verificado* | *no verificado* | Sí |
| **Merge** (unificada) | 1 modelo con `type: ACCOUNTS_PAYABLE \| ACCOUNTS_RECEIVABLE` | `tax_rate` por línea; `inclusive_of_tax` | `currency` + `exchange_rate` | Id | `number` | Modelos aparte, que se aplican a la factura | `DRAFT` | `remote_id` de solo lectura; idempotencia en beta | Sí, `account` |
| **Codat** (unificada) | 2 modelos: `bills`, `invoices` | `taxRateRef` y `taxAmount` por línea | `currency` (+ `currencyRate`, *no verificado*) | `supplierRef` / `customerRef` | `reference` / `invoiceNumber` | Modelos aparte | `status` | *no verificado* | Sí, `accountRef` |
| **Apideck** (unificada) | 2 recursos | `tax_rate {id, code, rate}` por línea; `tax_inclusive` | `currency` + `currency_rate` | Id | `bill_number` / `reference` | El `type` admite `credit` | `draft` | Sin cabecera; tiene `pass_through` | Sí, `ledger_account` |
| **Rutter** (unificada) | 2 recursos, con el cuerpo envuelto | `tax_rate_id` por línea | `currency_code` | `vendor_id` / `customer_id` | `document_number` | Recursos aparte | No escribible | Cabecera, solo en modo asíncrono | Sí, `account_id` |

---

## 3 · Los estándares abiertos: el otro modelo

**EN 16931 y Peppol BIS Billing 3.0** no son una API sino un **modelo semántico de factura**, el que usa Europa para
facturar entre empresas. Sus términos, con la nomenclatura `BT-` (término) y `BG-` (grupo):

| Grupo | Términos |
|---|---|
| Cabecera | `BT-1` número, `BT-2` fecha de emisión, `BT-9` vencimiento, `BT-3` tipo (380 factura, 381 nota de crédito), `BT-5` moneda |
| Referencias | `BT-10` referencia del comprador, `BT-13` orden de compra, `BT-19` **referencia contable del comprador** |
| Partes | `BG-4` vendedor (`BT-31` id fiscal), `BG-7` comprador (`BT-48` id fiscal) |
| Totales | `BG-22`: `BT-106` suma de líneas, `BT-109` sin IVA, `BT-112` con IVA, `BT-115` a pagar |
| Desglose de IVA | `BG-23`: `BT-116` base, `BT-117` importe, `BT-118` categoría, con su tasa |
| Líneas | `BG-25`: `BT-129` cantidad, `BT-131` importe neto, `BT-133` referencia contable, `BT-151`/`BT-152` categoría y tasa |

Cuatro cosas que enseña, y que confirman decisiones ya tomadas aquí:

1. **La contraparte va embebida, con su identificador fiscal**, no como un id interno: una factura es un documento
   entre dos empresas y tiene que significar lo mismo fuera del sistema que la emitió. Es lo que hace
   `contraparte_doc` con el RUC.
2. **El impuesto se declara por categoría y tasa en la línea, y su importe se agrega en un desglose de cabecera**,
   uno por cada combinación distinta de categoría y tasa. El estándar peruano tiene el equivalente ya resuelto por
   las columnas del SIRE: `base_gravada`, `igv`, `exonerado`, `inafecto`, `exportacion`.
3. **La cuenta contable no es parte de la factura**: solo aparece como «referencia contable del comprador»
   (`BT-19`, `BT-133`). Es exactamente la razón por la que la 0.3 sacó `cuenta_contable` del comprobante.
4. **La nota de crédito es el mismo modelo con otro código de tipo** (381), no un documento distinto. Aquí es el
   `tipo_cp: 07` de la Tabla 10.

**UBL en JSON existe, pero no es normativa.** OASIS publicó una *committee note* con la representación JSON de UBL
2.1, 2.2 y 2.3: cada elemento va dentro de un arreglo y el valor en la clave `"_"`
(`"IssueDate": [{"_": "2026-01-15"}]`), con prefijos `_D`, `_A`, `_B`. Está pensada para volver a XML sin pérdida,
no para que una persona la escriba. **UN/CEFACT CII** solo tiene sintaxis XML.

---

## 4 · El estándar de facto

Lo que se repite en casi todas las fuentes de arriba:

1. **Cabecera y líneas en un solo `POST`.** Incluso Business Central, que separa los recursos, admite mandarlo todo
   junto.
2. **Dos recursos, o uno con discriminador.** La mayoría separa compras de ventas; Xero y Merge usan un modelo con
   `type`. La estructura es casi la misma en los dos casos.
3. **La cuenta contable va en la línea**, y siempre distinguiendo la línea por cuenta de la línea por ítem
   (`AccountBased` frente a `ItemBased`, `expense` frente a `item`, `lineType`).
4. **El impuesto se manda explícito**, con un código o una tasa por línea, más un indicador de si los precios lo
   incluyen. Nadie recomienda delegarlo en el motor del destino.
5. **Moneda ISO 4217 y tipo de cambio opcional**; si falta, el sistema usa su propia tabla.
6. **Dos números distintos**: el que puso quien emitió el documento y la referencia interna de quien lo registra.
7. **La contraparte por id interno en los ERP, embebida en los estándares abiertos.** Lo razonable es aceptar las
   dos: el id si existe, y si no el identificador fiscal con el nombre.
8. **Estado inicial declarado**: borrador o contabilizado.
9. **Idempotencia por clave de petición** (`requestid`, `Idempotency-Key`) más un id externo para reconocer lo ya
   escrito.
10. **Dimensiones analíticas por línea**, con dos o tres ejes según el sistema.
11. **Las notas de crédito casi siempre son un recurso aparte**, con la misma forma y un enlace al documento que
    corrigen.
12. **Ninguna de las fuentes revisadas tiene un campo de retención.** Las retenciones, detracciones y percepciones
    peruanas no existen en ese mundo: son la parte que el estándar de aquí tiene que aportar.

---

## 5 · Qué de todo esto ya tiene `open-accounting` 0.3

| Patrón de facto | Qué tiene el estándar hoy |
|---|---|
| Cabecera y líneas en una llamada | El documento lleva `comprobantes[]` y `asiento[]` a la vez |
| Dos recursos | `libro.tipo: compra \| venta` |
| Cuenta en la línea | La línea de diario la lleva; en el comprobante viaja aparte, en la imputación por `id_externo` |
| Impuesto explícito | `base_gravada` e `igv` siempre netos, `tasa_igv` leída del documento, y la línea con `rol: igv` |
| Moneda y T.C. | `moneda`, `tipo_cambio` |
| Los dos números | `serie` + `numero` del emisor; `id_externo` del sistema que registra |
| Contraparte | `contraparte_tipo_doc`, `contraparte_doc`, `contraparte_nombre`: el modelo de los estándares abiertos |
| Estado | `estado` del comprobante (`ok`, `observada`, `duplicada`); el de la línea es nombre reservado |
| Idempotencia | La identidad del comprobante y la huella de `_exportacion` |
| Dimensiones | `centro_costo` y `anexo_auxiliar`; `dimensiones` es nombre reservado |
| Nota de crédito | `tipo_cp: 07` con `ref_tipo_cp`, `ref_serie`, `ref_numero`, `ref_fecha` |
| Retenciones | `retencion` (renta de 4ta) y el bloque `detraccion` de dos tiempos: lo que no tiene nadie más |

**Por eso el JSON universal no es un modelo nuevo.** `REFERENCIAS.md` ya descartó inventar `Invoice`, `Bill` o
`Contact` propios, y el motivo sigue valiendo: en el Perú ese modelo lo define SUNAT, y el comprobante del estándar
son los campos de la Tabla 10 y del SIRE. Lo que falta no son campos: es que **la imputación quepa en el mismo
archivo**, y que la llamada no invente una segunda forma de decir lo que el documento ya dice.

---

## 6 · El borrador: un solo formato, el del estándar

El primer borrador de esta sección proponía `POST /v1/compras` y `POST /v1/ventas` con un cuerpo propio: `ruc`,
`razon_social` y `periodo` sueltos en la raíz, un `comprobante` en singular y la `imputacion` sin llave. Era la forma
de STARSOFT traducida al vocabulario de aquí. John lo leyó y preguntó lo que había que preguntar: si el estándar ya
existe, **¿por qué el cuerpo de la llamada es otra cosa?** No hay respuesta buena, y por eso el borrador es ahora uno
solo: **el cuerpo de la llamada es el documento `open-accounting`**, con la imputación dentro (decisión de John del
15-sep-2026).

### Las dos formas, y por qué sobraba una

| El envoltorio que se proponía | El estándar 0.3 | ¿Hacía falta la diferencia? |
|---|---|---|
| `ruc`, `razon_social`, `periodo` sueltos | dentro de `libro` | **No.** El mismo dato en otro sitio |
| el tipo de libro, dicho por la ruta | `libro.tipo`: `compra` o `venta` | **No.** El documento ya lo dice; la ruta lo repetía |
| `comprobante`, uno | `comprobantes[]` | **No.** Una lista de uno |
| `imputacion` sin llave | hoy, un argumento aparte de la llamada | **No.** Cabe dentro, con llave por `id_externo` |
| `driver`, `configuracion`, `con_archivo` | no están | **Sí.** Eso no es contabilidad: es qué hacer con ella |

**Lo que se gana al juntarlas:**

- **Una sola forma para uno o para cinco mil comprobantes.** Quien integra escribe un camino, no dos.
- **Es un archivo, no el cuerpo de una petición.** Se guarda, se versiona, se manda por correo y se comprueba sin
  API ni servidor: `python -m contaperu.cli diagnosticar mi-mes.json`.
- **Sobran las rutas por tipo**, y con ellas la última herencia de STARSOFT que quedaba en el borrador.
- **Sobra derivar el periodo**, que era la primera decisión pendiente: el libro lo trae siempre, así que las tres
  validaciones de plazo —periodo anterior, fecha posterior y crédito fiscal fuera de plazo— siguen vivas.
- **Sobra el riesgo de que las dos puertas se separen.** No hay dos caminos que puedan dar asientos distintos: un
  comprobante suelto es un documento de un comprobante, y pasa por donde pasan todos los demás.
- **Se mantiene lo que la 0.3 decidió a propósito:** la cuenta **no** vuelve dentro del comprobante. El comprobante
  es el hecho que define SUNAT; la imputación es la decisión de quien lo contabiliza. Mismo sobre, bloques distintos.

### Una compra con detracción

```json
{
  "open_accounting": "0.3",
  "libro": {
    "ruc": "20601234567",
    "razon_social": "EMPRESA DE PRUEBA SAC",
    "periodo": "202601",
    "tipo": "compra"
  },
  "comprobantes": [
    {
      "tipo_cp": "01",
      "serie": "F001",
      "numero": "0000123",
      "fecha_emision": "2026-01-15",
      "fecha_vencimiento": "2026-02-14",
      "condicion_pago": "credito",
      "contraparte_tipo_doc": "6",
      "contraparte_doc": "20131312955",
      "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC",
      "moneda": "PEN",
      "base_gravada": "10000.00",
      "igv": "1800.00",
      "total": "11800.00",
      "destino_igv": "DG",
      "detraccion": {
        "codigo": "037",
        "porcentaje": "12",
        "monto": "1416.00",
        "estado": "PROVISIONADO"
      },
      "concepto": "SERVICIO DE MANTENIMIENTO ENERO 2026",
      "origen": "manual",
      "id_externo": "compra-123"
    }
  ],
  "imputaciones": {
    "compra-123": { "cuenta_contable": "6343001", "centro_costo": "OBRA01" }
  }
}
```

**El destino no está dentro, y es a propósito.** Lo dice la llamada —`POST /v1/exportar` con `driver: "concar"`—
porque este mismo archivo, sin cambiar una coma, tiene que dar el TXT del SIRE (`sire`), el Excel de CONTASIS
(`contasis`) o el documento neutral para otro ERP (`open_accounting`).

### Una venta, y el mes entero

```json
{
  "open_accounting": "0.3",
  "libro": { "ruc": "20601234567", "periodo": "202601", "tipo": "venta" },
  "comprobantes": [
    {
      "tipo_cp": "01",
      "serie": "F001",
      "numero": "0000987",
      "fecha_emision": "2026-01-20",
      "contraparte_tipo_doc": "6",
      "contraparte_doc": "20131312955",
      "contraparte_nombre": "CLIENTE DE PRUEBA SAC",
      "moneda": "PEN",
      "base_gravada": "5000.00",
      "igv": "900.00",
      "total": "5900.00",
      "concepto": "VENTA DE SERVICIOS ENERO 2026",
      "origen": "manual",
      "id_externo": "venta-987"
    }
  ],
  "imputaciones": {
    "venta-987": { "cuenta_contable": "7041001", "cuenta_tercero": "1212" }
  }
}
```

**Uno o quinientos, la forma no cambia:** `comprobantes[]` crece y `imputaciones` lleva una entrada por `id_externo`,
que es lo que ya hace hoy la imputación como argumento. El tope de comprobantes del lote, que ya existe, vale
también para quien manda uno: no hace falta un freno aparte.

### La respuesta

No hay nada que inventar: es la de `diagnosticar`, con su esquema ya publicado
(`GET /v1/esquemas/diagnostico.schema.json`). Con un comprobante, la lista de lo que falta es corta y accionable, y
cada faltante ya dice **a quién hay que pedírselo**: al contador, al proveedor o al sistema.

```json
{
  "identidad": { "ruc": "20601234567", "libro": "compra", "tipo_cp": "01",
                 "serie": "F001", "numero": "123", "contraparte_doc": "20131312955" },
  "listo": true,
  "diagnostico": { "…": "qué falta, con su motivo y a quién pedírselo" },
  "asiento": [ { "…": "las líneas" } ],
  "_asiento": { "lineas": 4, "cuadre": "ok", "huella": "…", "motor": "1.1.0" }
}
```

### Campo por campo

**Dentro del documento** —lo que es contabilidad, y por tanto se guarda, se manda y se archiva:

| Nombre | De dónde sale | Oblig. | Por qué |
|---|---|---|---|
| `open_accounting` | 0.3 | sí | La versión del estándar con que se escribió |
| `libro.ruc` | 0.3 | sí | Sin RUC no hay libro |
| `libro.razon_social` | 0.3 | no | Informativo; algún driver la escribe |
| `libro.periodo` | 0.3 | sí | `AAAAMM`. Se exige siempre: derivarlo apagaría tres validaciones de plazo |
| `libro.tipo` | 0.3 | sí | `compra` o `venta`. Es el discriminador de Xero y Merge, y evita rutas por tipo |
| `comprobantes[]` | 0.3 y SUNAT | sí | El modelo ya existe y lo define SUNAT: uno o los del mes |
| `contraparte_*` | 0.3, Tabla 1 | según el caso | Planos, con el RUC: el modelo de EN 16931, no un `Contact` propio |
| `detraccion` | 0.3 | no | Entra `PROVISIONADO`; la constancia llega después |
| `imputaciones{}` | **nuevo**, por `id_externo` | no | `cuenta_contable`, `centro_costo`, `cuenta_tercero` y `reparto[]`, lo que hoy es un argumento de la llamada |
| `asiento[]` | 0.3 | no | Para el ERP que ya lo armó |
| `emisor` | 0.3 | no | Qué software produjo el dato |

**Fuera del documento**, en la llamada: no describen la contabilidad sino qué hacer con ella, y el mismo archivo
tiene que servir para destinos distintos.

| Nombre | Qué decide |
|---|---|
| `driver` | El destino: `sire`, `concar`, `contasis`, `open_accounting`… Sin destino, la respuesta es el diagnóstico |
| `configuracion` | Lo del sistema de destino y lo general del contribuyente |
| `correlativos` | Desde qué número sigue cada sub-diario |
| `claves_previas` | Lo anotado en periodos anteriores, para reconocer el duplicado |
| `incluir_observados`, `fecha` | Qué entra al archivo y con qué fecha se escribe |

### Tres reglas del borrador

1. **Las cuentas viajan en el mismo archivo, al lado del comprobante y nunca dentro de él.** `cuenta_contable` y
   `centro_costo` salieron del comprobante en la 0.3 a propósito —el comprobante es el hecho de SUNAT, y el hecho no
   cambia según quién lo contabilice—, y el modelo los rechaza ahí. `imputaciones` respeta esa frontera: hechos y
   decisiones en el mismo sobre, en bloques distintos, como ya convive `asiento[]`.
2. **Una clave desconocida se rechaza.** El esquema del estándar no admite campos de más, y en una API pública eso es
   una virtud: quien se equivoca de nombre se entera en la primera llamada y no al cerrar el mes. El mensaje nombra
   la clave y sugiere `datos_originales`, que es la válvula para lo que el motor no entiende.
3. **La nota de crédito va en el mismo documento**, con `tipo_cp: 07` y los campos `ref_*`. No es un recurso aparte:
   el signo lo pone el driver, y los importes siguen siendo positivos.

---

## 7 · Qué queda fuera, a propósito

- **Las líneas de detalle por ítem.** Un `Item` o un `InvoiceLine` sería un modelo propio, ya descartado, y el
  registro de compras y ventas de SUNAT no lo pide. Quien reparte el gasto entre cuentas usa `reparto`; quien quiera
  el detalle lo transporta en `datos_originales`.
- **El impuesto por línea de detalle y el indicador de precios con impuesto** (`LineAmountTypes`,
  `pricesIncludeTax`). Sin ítems no tienen dónde ir, y el IGV nunca se delega al destino: va explícito, con su tasa.
- **Un cuerpo propio de la API.** Fue el primer borrador y duró lo que tardó la primera lectura: un formato que solo
  existe dentro de una petición no se puede guardar, ni mandar, ni comprobar sin servidor. La sección 6 lo cuenta.
- **Las rutas por tipo, `/v1/compras` y `/v1/ventas`.** El documento dice `libro.tipo`; una ruta que repite un campo
  del cuerpo solo añade un sitio donde los dos pueden contradecirse.
- **La cabecera `Idempotency-Key`.** La clave natural aquí es la identidad del comprobante más la huella del
  asiento, y las dos ya existen.
- **El estado de borrador o contabilizado.** `estado` de la línea es un nombre reservado que espera su caso, y
  `comprobante.estado` ya significa otra cosa.
- **La contraparte con dirección, correo o id interno del ERP.** Eso es la ficha del proveedor, no el hecho que se
  registra.
- **Los lotes.** Ya existen: son las operaciones de hoy, con su tope de comprobantes.
- **Importes numéricos y el signo en vez de `debe_haber`.** Siguen descartados, por las mismas dos razones: el
  céntimo que pierde un `float` y la nota de crédito restada dos veces.
- **OAuth, webhooks, sincronización incremental.** El motor no tiene estado ni sale a la red.

---

## 8 · Qué pide esto del estándar

**Pide una sola cosa, y es aditiva.** El esquema tiene hoy cinco claves en la raíz —`open_accounting`, `libro`,
`comprobantes`, `asiento` y `emisor`— y rechaza cualquier otra, así que `imputaciones` hay que añadirlo ahí. Un campo
opcional nuevo **no sube la versión**: avanza el tag `open-accounting-0.3` y quien ya escribe 0.3 sigue valiendo.

| Cambio | Clasificación |
|---|---|
| `imputaciones` en la raíz del documento, con llave por `id_externo` | **Aditivo.** Avanza el tag `open-accounting-0.3`, no sube a 0.4 |
| Aceptar el documento con un solo comprobante | Ya vale: `comprobantes[]` nunca exigió más de uno |
| La respuesta que reusa el esquema del diagnóstico | Ya vale: está publicado |
| Rechazar una clave desconocida | Ya vale: el esquema no admite campos de más |
| `dimensiones`, `medio_pago`, `retencion_igv`, `percepcion`, `no_domiciliado`, `estado` de línea | Aditivos, pero **piden su enmienda (E1) y un caso real**. Fuera de esta tanda |
| Hacer `libro.periodo` opcional | **Rompe**, y ya no hace falta: el documento lo trae siempre |
| Devolver `cuenta_contable` al comprobante | **Rompe**: revierte la 0.3. Por eso es un bloque hermano y no un campo del comprobante |
| Un bloque de ítems en el comprobante | Cambia qué es un comprobante. Fuera |

---

## 9 · Lo que falta decidir

**Resueltas por el formato único** —las cuatro se caían solas en cuanto el cuerpo dejó de ser un envoltorio:

| Antes era una decisión | Cómo queda |
|---|---|
| Si el periodo se deriva de la fecha | No se deriva: el libro lo trae. Las tres validaciones de plazo siguen vivas |
| Quién numera cuando llega un comprobante suelto | Lo mismo que hoy: un documento de uno se numera como uno de mil |
| Que las dos puertas no se separen | No hay dos puertas: hay un documento y un pipeline |
| El freno de la ruta por comprobante | El tope de comprobantes del lote ya lo cubre |

**Abiertas:**

1. **El correlativo, en el fondo.** Hoy el motor numera por lote y por sub-diario. Quien mande un comprobante por
   semana va a pedir que la numeración siga la del mes anterior, y el motor no tiene estado: o el ERP manda
   `correlativos`, como hoy, o se acepta que el destino numere. Es la única decisión que el formato no resolvió.
2. **El nombre de `imputaciones`.** Es preciso en el vocabulario del motor y ajeno al de un ERP, que diría «cuentas»
   o «asignación». Entra en el estándar, así que el nombre se elige una vez.
3. **Rechazar la clave desconocida** endurece la API para quien hoy, desde Python, manda campos de más.
4. **Si `imputaciones` viaja también de vuelta**, en la respuesta y en la salida del driver `open_accounting`: quien
   recibe el documento neutral podría querer saber con qué cuentas se armó el asiento que lleva al lado.

---

## 10 · Fuentes

Consultadas el 15-sep-2026.

**El caso peruano**
- STARSOFT Gold Edition, ayuda de las APIs de integración: https://starsoftweb.com/apisintegracion/Help
- «Guía de Uso – API'S CONTABLES» de STARSOFT (documento del proveedor). No entra al repositorio: es de un tercero y
  sus ejemplos traen datos de empresas reales.

**QuickBooks Online**
- `Bill`: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/bill
- `Invoice`: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/invoice
- `CreditMemo`: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/creditmemo
- `requestid` y buenas prácticas: https://help.developer.intuit.com/s/article/QuickBooks-Online-API-Best-Practices

**Xero**
- `Invoices` (ACCPAY y ACCREC): https://developer.xero.com/documentation/api/accounting/invoices
- Idempotencia: https://developer.xero.com/documentation/guides/idempotent-requests/idempotency/

**Dynamics 365 Business Central**
- Crear factura de compra: https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/api/dynamics_purchaseinvoice_create
- Crear factura de venta: https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/api/dynamics_salesinvoice_create
- Línea de factura de compra: https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/resources/dynamics_purchaseinvoiceline

**Oracle NetSuite**
- `vendorBill` en el REST: https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/article_164484956387.html
- Peticiones asíncronas e idempotencia: https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/subsect_164494900632.html

**Sage Intacct**
- Facturas de proveedor (APBILL): https://developer.intacct.com/api/accounts-payable/bills/
- Facturas de venta: https://developer.intacct.com/api/accounts-receivable/invoices/

**APIs unificadas**
- Merge: https://docs.merge.dev/accounting/invoices/
- Codat: https://docs.codat.io/payables/async/bills/
- Apideck: https://developers.apideck.com/apis/accounting/reference/bills y …/invoices
- Rutter: https://docs.rutter.com/rest/2023-03-14/bills y …/invoices

**Estándares abiertos**
- Peppol BIS Billing 3.0: https://docs.peppol.eu/poacc/billing/3.0/bis/
- Su sintaxis UBL: https://docs.peppol.eu/poacc/billing/3.0/syntax/ubl-invoice/tree/
- UBL 2.3 en JSON (OASIS, *committee note*, no normativa):
  https://docs.oasis-open.org/ubl/UBL-2.3-JSON/v1.0/UBL-2.3-JSON-v1.0.html
