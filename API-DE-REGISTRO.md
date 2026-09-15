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

1. **La llamada por tipo de registro es la forma natural del dominio.** Compras y ventas son dos hechos distintos,
   con campos distintos (`destino_Compra` y la detracción de un lado; `exportacion` y el ISC del otro). Dos rutas se
   explican solas, y es lo mismo que hacen QuickBooks con `Bill` e `Invoice` y Business Central con
   `purchaseInvoices` y `salesInvoices`.
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
son los campos de la Tabla 10 y del SIRE. Lo que falta no son campos: es **la forma de la llamada**.

---

## 6 · El borrador: `POST /v1/compras` y `POST /v1/ventas`

Un comprobante por llamada. El cuerpo es un **envoltorio de la API**, no un documento `open-accounting`: el motor lo
convierte en un documento de un solo comprobante y sigue el mismo pipeline de siempre.

### La forma del cuerpo

| Clave | Oblig. | Qué es |
|---|---|---|
| `ruc` | sí | El contribuyente dueño del libro (`libro.ruc`). No es un `company_id` inventado |
| `razon_social` | no | `libro.razon_social` |
| `periodo` | no | `AAAAMM`. Si falta, se deriva de `fecha_emision` y **la respuesta lo dice** |
| `comprobante` | sí | El objeto del estándar 0.3, **tal cual**, sin un solo campo nuevo |
| `imputacion` | no | Las cuentas de este comprobante, sin llave: `cuenta_contable`, `centro_costo`, `cuenta_tercero`, `reparto[]` |
| `asiento` | no | Las líneas de diario, si el ERP ya las armó |
| `configuracion` | no | La de siempre |
| `driver` | no | Sin destino, la respuesta es el registro y su diagnóstico; con destino, además el asiento |
| `con_archivo` | no | `false` por defecto: no devuelve el archivo a quien solo registra |
| `claves_previas` | no | Lo anotado en periodos anteriores, para detectar el duplicado |
| `emisor` | no | Qué software produjo el dato |

**El tipo de libro lo dice la ruta**, no el cuerpo: `/v1/compras` es `compra`. Son dos hechos distintos, como
`Bill` e `Invoice`.

### Una compra con detracción

```json
{
  "ruc": "20601234567",
  "razon_social": "EMPRESA DE PRUEBA SAC",
  "periodo": "202601",
  "driver": "concar",
  "comprobante": {
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
  },
  "imputacion": { "cuenta_contable": "6343001", "centro_costo": "OBRA01" }
}
```

### Una venta

```json
{
  "ruc": "20601234567",
  "driver": "concar",
  "comprobante": {
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
  },
  "imputacion": { "cuenta_contable": "7041001", "cuenta_tercero": "1212" }
}
```

Esta venta no manda `periodo`: se deriva `202601` de la fecha de emisión, y la respuesta lo declara.

### La respuesta

Reusa lo que ya existe —`diagnosticar` entero, con su esquema publicado— en vez de inventar otro:

```json
{
  "identidad": { "ruc": "20601234567", "libro": "compra", "tipo_cp": "01",
                 "serie": "F001", "numero": "123", "contraparte_doc": "20131312955" },
  "libro": { "ruc": "20601234567", "periodo": "202601", "tipo": "compra", "periodo_derivado": false },
  "comprobante": { "…": "el mismo, con su estado y sus observaciones" },
  "listo": true,
  "diagnostico": { "…": "qué falta, con su motivo y a quién pedírselo" },
  "asiento": [ { "…": "las líneas" } ],
  "_asiento": { "lineas": 4, "cuadre": "ok", "huella": "…", "motor": "1.1.0" }
}
```

Con un solo comprobante, la lista de lo que falta es corta y accionable, y cada faltante ya dice **a quién hay que
pedírselo**: al contador, al proveedor o al sistema.

### Campo por campo

| Nombre | De dónde sale | Oblig. | Por qué |
|---|---|---|---|
| `ruc` | `libro.ruc` (0.3) | sí | Sin RUC no hay libro; sube al envoltorio para no mandar un `libro` a medias |
| `razon_social` | `libro.razon_social` | no | Informativo; algún driver la escribe |
| `periodo` | `libro.periodo` | no | El lote lo exige; un comprobante suelto lo deriva de su fecha |
| el tipo de libro | `libro.tipo` | — | Lo dice la ruta, como `Bill` e `Invoice` |
| `comprobante.*` | 0.3 y SUNAT | sí | El modelo ya existe y lo define SUNAT |
| `contraparte_*` | 0.3, Tabla 1 | según el caso | Planos, con el RUC: es el modelo de EN 16931, no un `Contact` propio |
| `detraccion` | 0.3 | no | Entra `PROVISIONADO`; la constancia llega después |
| `imputacion.cuenta_contable` | patrón de EE. UU. (`AccountRef`, `AccountCode`) | no | Va en la misma llamada; si falta, manda la configuración |
| `imputacion.centro_costo` | patrón de EE. UU. (`Tracking`) | no | Lo mismo; que bloquee o no lo decide lo que el driver exige |
| `imputacion.cuenta_tercero` | la imputación de hoy | no | La cuenta del total: 42 en compras, 12 en ventas |
| `imputacion.reparto[]` | la imputación de hoy | no | Es lo más cerca del detalle por ítem que hay hoy |
| `asiento[]` | 0.3 | no | Para el ERP que ya lo armó |
| `driver` | la tabla de operaciones | no | Sin destino no hay nada que exigir |
| `claves_previas` | la fachada | no | Idempotencia sin cabecera |

### Cuatro reglas del borrador

1. **El periodo derivado se declara.** Derivarlo de la propia fecha del comprobante vuelve tautológicas tres
   validaciones de plazo —el periodo anterior, la fecha posterior y el crédito fiscal fuera de plazo—, que entonces
   nunca saltan. Por eso la respuesta marca `periodo_derivado` y avisa; quien quiera esa comprobación manda el
   periodo.
2. **Las cuentas viajan en la misma llamada, al lado del comprobante y no dentro de él.** `cuenta_contable` y
   `centro_costo` salieron del comprobante en la 0.3 a propósito, y el modelo los rechaza: devolverlos ahí
   revertiría esa decisión y rompería a quien ya migró.
3. **Una clave desconocida se rechaza.** El esquema del estándar no admite campos de más, y en una API pública eso
   es una virtud: quien se equivoca de nombre se entera en la primera llamada y no al cerrar el mes. El mensaje
   nombra la clave y sugiere `datos_originales`, que es la válvula para lo que el motor no entiende.
4. **La nota de crédito va por la misma ruta**, con `tipo_cp: 07` y los campos `ref_*`. No es un recurso aparte: el
   signo lo pone el driver, y los importes siguen siendo positivos.

---

## 7 · Qué queda fuera, a propósito

- **Las líneas de detalle por ítem.** Un `Item` o un `InvoiceLine` sería un modelo propio, ya descartado, y el
  registro de compras y ventas de SUNAT no lo pide. Quien reparte el gasto entre cuentas usa `reparto`; quien quiera
  el detalle lo transporta en `datos_originales`.
- **El impuesto por línea de detalle y el indicador de precios con impuesto** (`LineAmountTypes`,
  `pricesIncludeTax`). Sin ítems no tienen dónde ir, y el IGV nunca se delega al destino: va explícito, con su tasa.
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

**Cabe entero en `open-accounting` 0.3.** El cuerpo de la llamada es un envoltorio de la API, así que nada de lo
anterior toca el esquema del estándar ni pide la enmienda del hito E1.

| Cambio | Clasificación |
|---|---|
| Las rutas `/v1/compras` y `/v1/ventas` | Aditivo, en la API y no en el estándar |
| `ruc`, `razon_social` y `periodo` sueltos en el cuerpo | Aditivo (envoltorio) |
| `imputacion` sin llave, la de este comprobante | Aditivo (envoltorio) |
| Derivar el periodo de la fecha de emisión | Aditivo: es una regla de la puerta, y el núcleo no inventa datos |
| Rechazar una clave desconocida en la puerta | Aditivo: endurece la API, no el estándar |
| La respuesta que reusa el esquema del diagnóstico | Aditivo |
| `dimensiones`, `medio_pago`, `retencion_igv`, `percepcion`, `no_domiciliado`, `estado` de línea | Aditivos al esquema, pero **piden su enmienda (E1) y un caso real**. Fuera de esta tanda |
| Hacer `libro.periodo` opcional en el esquema | **Rompe**: sería una 0.4. Por eso el periodo se deriva en la puerta |
| Devolver `cuenta_contable` al comprobante | **Rompe**: revierte la 0.3. Por eso va en `imputacion` |
| Un bloque de ítems en el comprobante | Cambia qué es un comprobante. Fuera |

---

## 9 · Lo que falta decidir

1. **El periodo derivado**: ¿se acepta con aviso, o se exige siempre? Derivarlo apaga tres validaciones de plazo.
2. **El correlativo**: hoy se numera por lote y por sub-diario. Registrando de a uno, ¿quién lleva la cuenta: el ERP
   en su llamada, o el motor no numera y lo hace el destino?
3. **Que las dos puertas no se separen**: un comprobante por la ruta nueva tiene que dar exactamente el mismo
   asiento que dentro de un lote, y eso pide su test.
4. **El nombre de `imputacion`**: es preciso en el vocabulario del motor y ajeno al de un ERP.
5. **El freno**: el lote tiene su tope de comprobantes; una ruta por comprobante necesita el suyo.
6. **Rechazar la clave desconocida** endurece la API para quien hoy, desde Python, manda campos de más.

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
