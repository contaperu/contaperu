# Referencias: cómo modelan la contabilidad los sistemas de fuera, y qué tomar de ellos

Este documento recoge lo que hacen la API de QuickBooks Online, la de Xero, los ERP grandes de EE. UU. (Business
Central, NetSuite, Sage Intacct), las **APIs unificadas** (Merge, Codat, Rutter, Apideck) que ponen un modelo común
encima de decenas de sistemas contables, los **estándares abiertos de factura** (EN 16931, Peppol, UBL, UN/CEFACT) y
los **ERP abiertos** (Odoo, Apache OFBiz, iDempiere) — y lo compara, campo a campo, con `open-accounting`. Termina
con una propuesta concreta de qué añadir al estándar y qué no. Es la única casa de la investigación del repositorio:
lo que no esté aquí no se ha mirado.

**Mira tres escalones, y cada uno tiene su fecha**, que es lo que separa un documento de investigación de uno
desactualizado:

| Escalón | Qué compara | Investigación hecha el |
|---|---|---|
| **El asiento** | cómo modela cada uno un `JournalEntry` | 11-sep-2026 (librería 0.7.0) |
| **El registro del comprobante** | lo que un sistema manda cuando dice «anota esta compra»: `Bill` e `Invoice` | 15 y 16-sep-2026 (librería 1.0.0, estándar 0.3) |
| **La clasificación de la cuenta** | de dónde sale el papel de una línea y qué cuenta usa cada papel | 18-sep y 1-oct-2026 (librerías 1.0.0 y 4.1.0) |

Todo se escribió sobre la documentación pública de cada sistema; las fuentes, con su fecha de consulta, están al
final. Y se lee con una advertencia: **el repositorio avanzó desde entonces.** Donde la realidad adelantó al texto
hay una frase al final del párrafo que lo dice; lo que manda es `estandar/LEEME.md`, su esquema y sus enmiendas.

Su continuación —el ciclo contable de EE. UU. comparado con el peruano, los proyectos abiertos, los estándares del
otro lado (el PLE, SAF-T, XBRL GL, ISO 20022), la especificación MCP, el banco y las facturas de proveedores, y la
puerta a otra jurisdicción— está en el §8 de [HOJA-DE-RUTA.md](HOJA-DE-RUTA.md), que es el inventario de lo que
espera su caso real, con sus descartes en [ARQUITECTURA.md](ARQUITECTURA.md).

## Por qué mirar a EE. UU.

El problema que ContaPerú resuelve —cada sistema contable importa su propio archivo plano, con sus
columnas y sus siglas— no es peruano. En EE. UU. existe con otra forma: decenas de plataformas modernas
(QuickBooks, Xero, NetSuite, Sage, Dynamics) cada una con su API y su modelo de datos. La respuesta que
apareció allí son las *Unified APIs*: una capa que define **un solo modelo de asiento, factura y
proveedor** y lo traduce a cada plataforma, para que un desarrollador integre una vez. Es la posición
que ContaPerú quiere ocupar en Perú, con una diferencia: aquí los destinos son sistemas *legacy* que
importan archivos, no APIs. Ver la hoja de ruta en [ARQUITECTURA.md](ARQUITECTURA.md).

Y QuickBooks, que es a la vez el sistema contable más usado y el que más lejos ha llevado los agentes
de IA sobre el flujo diario, enseña algo sobre el orden de construcción: primero años de núcleo de
datos y reglas; los agentes, después.

## El asiento, comparado

| | QuickBooks Online | Xero | Merge | Rutter | Apideck | **open-accounting** |
|---|---|---|---|---|---|---|
| Objeto | `JournalEntry` | `ManualJournal` | `JournalEntry` | `JournalEntry` | `JournalEntry` | bloque `asiento` |
| Línea | `Line.JournalEntryLineDetail` | `JournalLines[]` | `JournalLine` | `line_items[]` | `line_items[]` | `linea` |
| Cuenta | `AccountRef` | `AccountCode` / `AccountID` | `account` | `account_id` | `ledger_account` | `cuenta` |
| Debe / Haber | `PostingType: Debit\|Credit` | signo de `LineAmount` (+ debe) | signo de `net_amount` (+ debe) | signo de `total_amount` | `type: debit\|credit` | `debe_haber: D\|H` |
| Importe | número | número | número | número | número | **texto exacto** |
| Cuadre | rechaza si no cuadra | rechaza | «las líneas suman 0» | — | mínimo 2 líneas, suman 0 | `partida_doble.exigir`, sin tolerancia |
| Impuesto por línea | `TaxCodeRef`, `TaxAmount`, `TaxApplicableOn` | `TaxType`, `TaxAmount` | `tax_rate` | `tax_rate_id` | `tax_rate`, `tax_type: sales\|purchase`, `tax_amount` | línea con `rol: impuesto`, `tasa_igv` |
| Con o sin impuesto | — | `LineAmountTypes: Exclusive\|Inclusive\|NoTax` | `inclusive_of_tax` | — | `tax_inclusive` | base siempre neta (regla del estándar) |
| Dimensiones | `ClassRef` (línea), `DepartmentRef` (transacción) | `Tracking[]` (hasta 2 por línea) | `tracking_categories[]` | `class_id`, `department_id`, `location_id` (vía `additional_fields`) | `tracking_categories[]`, `department_id`, `location_id` | `centro_costo`, `anexo_auxiliar` |
| Contraparte | `Entity{Type, EntityRef}` | — | `contact` | `customer_id`, `vendor_id` | `customer`, `supplier`, `employee` | `contraparte_doc` (RUC) |
| Documento origen | `DocNumber` | `/Journals`: `SourceType`, `SourceID` (solo lectura) | — | — | `source_type`, `source_id` | `documento{tipo_cp, serie_numero, fecha…}`, `referencia` |
| Rol de la línea | — | — | — | — | — | `rol: principal\|impuesto\|tercero\|…` |
| Estado | — | `Status: DRAFT\|POSTED\|VOIDED\|DELETED` | `posting_status: UNPOSTED\|POSTED` | — | `status: draft\|pending_approval\|approved\|posted\|voided…` | — |
| Id en el otro sistema | `Id` | `ManualJournalID` | `remote_id` | `platform_id` | `downstream_id` | — |
| Versión / concurrencia | `SyncToken` | `UpdatedDateUTC` | `modified_at` | `updated_at` | `row_version` | — |
| Lo no mapeado | — | — | `remote_data`, `remote_fields` | `platform_data`, `additional_fields` | `pass_through`, `custom_mappings` | `datos_originales` (comprobante) |
| Moneda y T.C. | `CurrencyRef`, `ExchangeRate`, `HomeTotalAmt` | — | `currency`, `exchange_rate` | `currency_code`, `currency_rate` | `currency`, `currency_rate` | `moneda`, `tipo_cambio` |

Lo primero que se ve: **todos convergen en lo mismo** —cuenta, sentido, importe, impuesto, dimensión,
contraparte— y `open-accounting` ya lo tiene. Lo segundo: en dos decisiones el estándar peruano va **mejor**
que la mayoría para su caso. `debe_haber` explícito en vez de un signo evita el error más común al
integrar (restar dos veces una nota de crédito); y los importes como texto evitan que un `float` de
JSON pierda un céntimo. Lo tercero: el `rol` de la línea no lo tiene nadie, y es lo que permite que un
driver encuentre «la línea del IGV» sin saber qué cuenta usa cada empresa.

## El registro del comprobante, comparado

El escalón de antes del asiento: lo que un sistema manda cuando dice «anota esta compra». Nueve fuentes, con
`open-accounting` en la última fila. (Investigación del 15 y 16-sep-2026; *no verificado* marca lo que no se pudo
confirmar en la documentación oficial.)

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
| **`open-accounting`** | 1 documento, con `libro.tipo: compra \| venta` | Las cinco columnas del SIRE por comprobante (`base_gravada`, `igv`, `exonerado`, `inafecto`, `exportacion`); base siempre neta | `moneda` + `tipo_cambio`, que lo pone quien llama | `contraparte_doc` embebida, con su RUC y su tipo de documento | `serie` + `numero` del emisor; `id_externo` de quien registra | El mismo comprobante con `tipo_cp: 07` y `ref_tipo_cp` / `ref_serie` / `ref_numero` / `ref_fecha` | — | `id_externo` más la huella de `_exportacion` | **No**: la cuenta va al lado, en `imputaciones` |

**Lo que la tabla dice.** Las nueve fuentes coinciden en casi todo, y en lo único que `open-accounting` se aparta a
propósito es la última columna: **la cuenta no va dentro del comprobante**, va al lado. Es la decisión que el modelo
europeo confirma por su cuenta (abajo, `BT-19`) y la que permite que el mismo documento sirva para CONCAR, para
CONTASIS y para el SIRE sin reescribirlo.

**Y dos ausencias que son la respuesta.** Ninguna de las nueve tiene dónde poner una detracción, y ninguna tiene
estado de borrador que le sirva al caso peruano: aquí el estado de un comprobante lo pone SUNAT, no quien lo
registra.

## Los estándares abiertos de factura: el otro modelo

**EN 16931 y Peppol BIS Billing 3.0** no son una API sino un **modelo semántico de factura**, el que usa Europa para
facturar entre empresas. Es el artefacto con el que `open-accounting` se compara de verdad, porque los dos describen
un documento y no el estado de un sistema. Sus términos, con la nomenclatura `BT-` (término) y `BG-` (grupo):

| Grupo | Términos |
|---|---|
| Cabecera | `BT-1` número, `BT-2` fecha de emisión, `BT-9` vencimiento, `BT-3` tipo (380 factura, 381 nota de crédito), `BT-5` moneda |
| Referencias | `BT-10` referencia del comprador, `BT-13` orden de compra, `BT-19` **referencia contable del comprador** |
| Partes | `BG-4` vendedor (`BT-31` id fiscal), `BG-7` comprador (`BT-48` id fiscal) |
| Totales | `BG-22`: `BT-106` suma de líneas, `BT-109` sin IVA, `BT-112` con IVA, `BT-115` a pagar |
| Desglose de IVA | `BG-23`: `BT-116` base, `BT-117` importe, `BT-118` categoría, con su tasa |
| Líneas | `BG-25`: `BT-129` cantidad, `BT-131` importe neto, `BT-133` referencia contable, `BT-151`/`BT-152` categoría y tasa |

**Qué tomar.** Cuatro cosas, y las cuatro confirman decisiones que ya estaban tomadas:

1. **La contraparte va embebida, con su identificador fiscal**, no como un id interno: una factura es un documento
   entre dos empresas y tiene que significar lo mismo fuera del sistema que la emitió. Es lo que hace
   `contraparte_doc` con el RUC.
2. **El impuesto se declara por categoría y tasa en la línea, y su importe se agrega en un desglose de cabecera**,
   uno por cada combinación distinta de categoría y tasa. El equivalente aquí ya lo resolvió SUNAT con las columnas
   del SIRE.
3. **La cuenta contable no es parte de la factura**: solo aparece como «referencia contable del comprador»
   (`BT-19` en la cabecera, `BT-133` en la línea). **Es la razón por la que el estándar sacó `cuenta_contable` del
   comprobante en la 0.3**, y el respaldo externo de que la imputación viaja aparte.
4. **La nota de crédito es el mismo modelo con otro código de tipo** (381), no un documento distinto. Aquí es el
   `tipo_cp: 07` de la Tabla 10.

## El estándar de facto: los doce patrones

Lo que se repite en casi todas las fuentes de los dos escalones. Es la lista contra la que se midió el estándar, y
de la que salió que no había nada que corregirle en el centro:

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
12. **Ninguna de las fuentes revisadas tiene un campo de retención.** Es el patrón que falta, y tiene la sección
    siguiente entera.

## Lo que ninguna API del mundo tiene: detracción, retención y percepción

El patrón 12 es el que justifica que este estándar exista. De las **nueve fuentes revisadas** —cinco ERP, tres API
unificadas y los estándares abiertos europeos— **ninguna tiene un campo para nada de esto**. No es un descuido suyo:
es que en su mundo no existe.

Los tres son **movimientos de dinero paralelos a la operación**, no impuestos sobre ella. Por eso no caben en un
modelo que describe el impuesto como categoría, tasa y base: la plata se mueve entre partes que no son las dos de la
factura. La detracción mete a un tercero —el Banco de la Nación— y se completa días después de emitir, con un dato
que al emitir no existe.

**Por qué EN 16931 y Peppol tampoco pueden.** No es que les falte un campo: es que el modelo no tiene dónde ponerlo.

1. **Describen el impuesto como categoría, tasa y base, agregado por cabecera.** Los tres mecanismos no son un
   impuesto sobre la operación, sino dinero que se mueve por fuera de ella.
2. **Suponen dos partes.** La detracción mete una tercera, que cobra parte de la factura.
3. **Suponen un documento cerrado.** La detracción se completa después, y el estándar la modela en dos tiempos.

Un ERP extranjero que quiera operar en el Perú tiene que resolver los tres con asientos manuales y campos libres,
que es exactamente lo que hoy hacen. **Recibirlos ya modelados es lo que este estándar aporta y ningún otro.**

| Mecanismo | Cómo está |
|---|---|
| Detracción | **Completa**, en dos tiempos, con su tabla de códigos en el motor y sus líneas propias en el asiento |
| Retención de renta de 4ta | **En el estándar**, con su rol en el asiento |
| Retención del IGV | Nombre reservado. **No entra en ningún asiento**: es un hecho del pago, no del comprobante |
| Percepción | Nombre reservado, `percepcion` |

Dos de los cuatro esperan un caso real, que es la regla del proyecto: el estándar se mueve con un archivo de verdad
detrás, no por si acaso. Mientras tanto, quien los tenga los transporta en `datos_originales`, que el motor pasa sin
interpretar. *(Los nombres de los roles cambiaron el 1-oct-2026: `igv` pasó a `impuesto`, `retencion_4ta` a
`retencion` y `detraccion_tercero` a `recorte`, con el tributo en su propio bloque — enmienda 0022.)*

## Siete hallazgos

### 1. Los impuestos son «el campo que rompe todo»

**Qué hacen.** Apideck lo dice con esas palabras: si no se distingue precio con impuesto incluido de
precio más impuesto, «los ingresos y la obligación tributaria salen mal los dos». Xero lo resuelve con
`LineAmountTypes` a nivel de documento; Merge con `inclusive_of_tax`. Y en QuickBooks US, el motor de
*Automated Sales Tax* **sobrescribe** el `TaxCode` que mandes con el que él calcula. La recomendación
transversal de las unificadas es mandar el impuesto **explícito** y no delegar en el motor del ERP.

**Qué hace open-accounting.** Exactamente eso, desde la 0.2: base e IGV siempre netos, la línea `igv` lleva
su importe, y `tasa_igv` se lee del comprobante (18, 10.5 o 0) y no de una configuración. Ningún
driver recalcula el IGV.

**Qué tomar.** Nada nuevo. El «tipo de impuesto por línea» (`TaxType` de Xero, `tax_type` de Apideck)
en Perú lo deciden `libro.tipo` y `rol`: el IGV de compras es crédito fiscal y el de ventas, débito, y
eso ya lo sabe cualquier driver por la cabecera.

### 2. Las dimensiones se abstraen como una lista

**Qué hacen.** Cada plataforma tiene dos o tres ejes de análisis con nombres distintos: `Class` y
`Department` («Location») en QuickBooks —la clase por línea, la ubicación por transacción—, dos
`Tracking categories` por línea en Xero, `subsidiary`/`department`/`location`/`class` en NetSuite e
Intacct. Las unificadas lo aplanan en `tracking_categories[]` por línea, y Apideck recomienda usar esa
misma lista para la **entidad** en escenarios multi-empresa, en vez de un parámetro por endpoint.

**Qué hace open-accounting.** Un `centro_costo` y un `anexo_auxiliar` por línea; la entidad es `libro.ruc`.
Basta para CONCAR (columna M y columna X) y para un estudio con treinta RUC.

**Qué tomar.** Una lista opcional `dimensiones: [{tipo, codigo}]` en comprobante y línea, para el ERP
que pida más de un eje (área + proyecto + obra). `centro_costo` no se toca: sigue siendo el primero y
el que CONCAR entiende.

### 3. Antes de escribir, el destino dice qué exige

**Qué hacen.** Codat expone `GET …/options/{dataType}`: el **modelo que ese ERP concreto exige** para
ese tipo de dato (campos obligatorios, largos máximos, enums, nombres para la pantalla). Merge tiene
`/meta` por integración con los campos requeridos. Y la escritura en Codat devuelve un `pushOperation`
con `status: Pending | Success | Failed | TimedOut`, `validation.errors[{itemId, message}]` y
`changes[{recordRef, type}]` — nunca una excepción a mitad de camino.

**Qué hace open-accounting.** `contaperu/drivers/contrato/examen.py::incumplimientos()` es el «options» del driver, y
`operaciones.diagnosticar` es el `validation.errors`: responde por serie-número qué falta, sin lanzar.

**Qué tomar.** Que **cada driver declare lo que exige** (`EXIGE = {"cuenta", "centro", "correlativo",
"moneda"}`) y `diagnosticar` lo lea de ahí, en vez de asumir que todo driver de asientos exige lo mismo
que CONCAR. Un driver de SISCONT que no use centros de costo no debería marcar «no listo» por ellos.
Así quedó (librería 0.8.0, hoy `contaperu/drivers/contrato/`): la cuenta y la equivalencia del tipo las exige el núcleo a todo
driver de asientos, que declara solo lo que añade (`centro_costo`, `moneda`); el correlativo no se exige, porque el
que falta arranca en 1. Desde la 0.10.0, a uno de registro el núcleo le exige la cuenta, y puede declarar
`centro_costo` y `cuenta_unica`.

### 4. Idempotencia: guardar el id externo y buscarlo antes de crear

**Qué hacen.** QuickBooks lleva un `SyncToken` en cada objeto —un contador de versión: actualizar con
uno viejo falla—, usa `DocNumber` como clave de negocio, y desde ago-2025 obliga a `minorversion=75`.
Xero acepta `Idempotency-Key` en PUT/POST/PATCH desde 2023 y recomienda deduplicar webhooks por
`resourceId + eventDateUtc`. Apideck lleva `row_version`. Y la regla que repiten las tres unificadas:
**guardar el id externo de todo lo que se escribe y buscarlo antes de crear**, porque «los webhooks
pueden disparar dos veces el mismo evento».

**Qué hace open-accounting.** El modelo tiene `clave` de duplicados (tipo, serie, número, documento de la
contraparte), que es la clave de negocio del comprobante. Cuando se escribió esto no tenía un id externo ni una
huella del asiento generado; hoy tiene los dos: la huella en `_exportacion` (librería 0.8.0) e `id_externo` en el
comprobante (0.10.0), el id con el que la aplicación conoce el documento.

**Qué tomar.** `id_externo` opcional en comprobante y línea (el id con el que el sistema origen o
destino conoce ese registro), y una anotación `_exportacion: {driver, archivo, huella, fecha}` con la
**huella determinista de las líneas**: dos exportaciones iguales dan la misma huella, y quien importe
dos veces el mismo Excel en CONCAR puede saberlo antes de duplicar asientos. Esto último es hoy el
error más caro del flujo real —«el Excel de CONCAR va por tandas: su importación se SUMA»— y la
huella es lo que permite avisarlo.

### 5. Trazabilidad: nada se borra, todo sabe de dónde salió

**Qué hacen.** Xero tiene dos endpoints distintos a propósito: `/ManualJournals` (se escribe) y
`/Journals`, el **libro diario del sistema, de solo lectura**, donde cada línea lleva `SourceType` y
`SourceID` (la factura, el pago o el asiento manual del que nació). Apideck lleva `source_type` y
`source_id`; Merge, `remote_data` con el objeto crudo del ERP; Codat, `supplementalData`. La norma que
enseña Apideck a los desarrolladores: no se borra, se revierte.

**Qué hace open-accounting.** Cada línea lleva `documento` y `referencia` —de qué comprobante sale y, si es
una nota, a cuál corrige—, y el comprobante lleva `datos_originales`, que el núcleo transporta sin interpretar
(salvo las cuatro claves que escribe su propio lector de XML: `anticipo`, `emisor`, `adquirente` y `gratuitas`).
Los importes van siempre en positivo y la nota de crédito invierte: nunca hay un asiento negativo que
«borre» otro.

**Qué tomar.** El **estado del asiento**. Hoy el bloque `asiento` de open-accounting es siempre una
propuesta; no puede decir «esto ya se importó en CONCAR» ni «esto se anuló». Un `estado:
propuesto | exportado | importado | anulado` opcional por línea (o por documento) es lo que Merge
llama `posting_status` y Xero `Status`, y lo que un portal necesita para no re-exportar lo importado.

### 6. Las unificadas transportan lo que no entienden

**Qué hacen.** Merge devuelve `remote_data` (el JSON crudo del ERP) y acepta `remote_fields`; Rutter
`platform_data` y `additional_fields`; Apideck `pass_through` con rutas JSONPath y `custom_mappings`.
Es la válvula que evita que el modelo común crezca por cada campo raro de cada plataforma.

**Qué hace open-accounting.** Regla 5 del estándar: «lo que no se entiende, se transporta», con `datos_originales`
en el comprobante —que el núcleo no interpreta, salvo las cuatro claves de su lector de XML— y las claves `_` como
anotaciones del productor.

**Qué tomar.** Nada: es el mismo diseño. Solo conviene documentar en `LEEME.md` que un driver puede
leer `datos_originales` para lo específico de su ERP —como Rutter con `additional_fields`— sin que el núcleo lo
interprete.

### 7. Los agentes llegaron después del núcleo, y piden en vez de adivinar

**Qué hacen.** Intuit lanzó en julio de 2025 un «equipo virtual» de agentes en QuickBooks Online
(Accounting, Payments, Finance, Customer, Payroll, Project Management) y en octubre *Intuit
Intelligence*, la capa que enruta una orden en lenguaje natural. El *Accounting agent* categoriza y
concilia, pero lo más interesante es que **«redacta las preguntas para pedir la información que falta»**
y gestiona la ida y vuelta con el contador antes de actualizar; el *Payments agent* predice retrasos y
redacta recordatorios; el *Finance agent* hace KPIs, escenarios y *benchmarking*. El humano revisa y
aprueba. Y QuickBooks no empezó por ahí: los agentes se apoyan en años de núcleo de datos y reglas.

**Qué hace open-accounting.** `diagnosticar` responde «¿qué falta?» por serie-número, y las reglas del
servidor MCP del estudio dicen lo mismo que Intuit: enseñar qué sale antes de generar, y no ofrecerse a
corregir —un comprobante sin cuenta se arregla donde se revisa.

**Qué tomar.** Que cada faltante diga **a quién hay que pedírselo**: `faltantes[].pedir_a:
contador | proveedor | sistema`. La cuenta contable la pone el contador; la fecha del documento
referido que el XML no trae, el proveedor; el correlativo, el sistema. Es lo que le permite a un agente
redactar la pregunta correcta sin que el núcleo adivine nada.

## La clasificación de la cuenta, y qué cuenta usa cada papel

El escalón de abajo, y el que explica por qué la línea del estándar lleva `rol` y `clase`. (Investigación del
18-sep-2026 sobre los sistemas comerciales, y del 1-oct-2026 sobre los ERP abiertos.)

Una compra son tres líneas —el gasto, el IGV y lo que se le debe al proveedor— y una venta otras tres. El `rol` de
la línea dice cuál es cuál, y el problema que lo motiva es que `principal` y `tercero` **solo significan algo si
además se mira `libro.tipo`**: en una compra `principal` es el gasto y `tercero` un pasivo; en una venta, el ingreso
y un activo. Una línea suelta no se explica sola, y la que recibe un ERP de fuera es exactamente eso.

**Qué hacen.** Hay tres capas distintas, y el mundo las resuelve en sitios distintos. La primera es **clasificar la
cuenta**:

| Sistema | Dónde vive el papel de la línea | Campo y valores |
|---|---|---|
| **QuickBooks Online** | En la cuenta, y en la cabecera | `Classification` (`Asset`, `Liability`, `Equity`, `Revenue`, `Expense`), `AccountType` (16 fijos) y `AccountSubType` (~250, con `SalesTaxPayable`, `WithholdingTaxPurchases`). La cuenta por pagar y la por cobrar van en la **cabecera** (`apAccountRef`, `arAccountRef`), nunca en la línea |
| **Xero** | En la cuenta | `Type` (18), `Class` (5) y **`SystemAccount`**: `DEBTORS`, `CREDITORS`, `GST`, `ROUNDING`… Un puntero que dice qué cuenta cumple qué función |
| **NetSuite** | En la cuenta, con enum **inmutable** | «no puedes crear ni modificar tipos de cuenta»; lo demás, con cuentas generadas por el sistema |
| **Sage Intacct** | Fuera de la cuenta | Solo `ACCOUNTTYPE` (`balancesheet` / `incomestatement`) y `NORMALBALANCE`; el papel lo pone la configuración del módulo |
| **Merge · Rutter · Apideck** | En la cuenta | `classification` o `category`, con los **mismos cinco valores** en las tres |
| **Odoo** | En la cuenta, en dos niveles | 18 `account_type` (`asset_receivable`, `liability_payable`, `expense_depreciation`, `off_balance`…) agrupados en 6, que son las cinco `clases` de aquí más uno de fuera de balance |
| **XBRL GL** | **En la línea** | El único: `accountPurposeCode` (`{tax}`, `{ifrs}`, `{primary}`…) y `accountType` (`{account}`, `{vendor}`, `{customer}`) |
| **SAF-T (OCDE)** | En una tabla de mapeo | El plan del contribuyente se mapea a uno estándar (`StandardAccountID`), y el impuesto va en la línea (`TaxInformation`) |

**El patrón es que la cuenta manda y la línea obedece.** Ningún sistema comercial escribe «esta línea es el IGV»: lo
deduce del tipo de la cuenta que la línea referencia. La única excepción, en todos, es el impuesto, que sí viaja en
la línea.

La segunda capa es la **determinación**: qué cuenta usa cada papel. Y aquí los ERP abiertos van más lejos que los
comerciales, porque tienen que dejarlo configurar:

- **Apache OFBiz** separa `GlAccountClassId` (categorización y reportes) de `GlAccountTypeId` (el papel). Trae 57
  tipos, de los que su demo mapea 19, y el mapeo vive en una entidad aparte, `GlAccountTypeDefault`, resuelta **por
  organización**: `ACCOUNTS_PAYABLE` → `210000`, `SALES` → `400000`, `TAX` → `900000`… Su documentación dice para
  qué existe en una frase que describe exactamente lo que hace este motor: «The GL Account Type is used to translate
  **one side** of the journal entry.» Un lado lo pone quien imputa; el otro sale de la tabla.
- **iDempiere** lleva el patrón al extremo: `C_AcctSchema_Default` tiene unas 45 ranuras nombradas con prefijo según
  a qué se cuelgan (`C_` cliente, `V_` proveedor, `T_` impuesto, `P_` producto): `C_RECEIVABLE_ACCT`,
  `V_LIABILITY_ACCT`, `T_DUE_ACCT`… y las resuelve en **tres niveles, de lo más específico a lo más general**:
  esta entidad → su grupo → el defecto de la organización.
- **Business Central** da la respuesta más limpia a «¿a qué está amarrado el papel?». Sus *posting groups* combinan
  dos ejes, y su documentación los nombra así: «The VAT business posting group is about **who** I'm selling or
  buying from and the VAT product posting group is about **what** I'm selling or buying.» El papel no está amarrado
  a la cuenta: **el papel más las dimensiones determinan la cuenta.**

**Qué hace open-accounting.** La primera capa, con las **cinco `clases`** —tomadas del único vocabulario que
QuickBooks, Xero, Merge y Rutter comparten— derivadas del primer dígito del PCGE, y con el **`rol` en la línea**,
que es lo que ningún sistema comercial tiene y solo XBRL GL. La segunda capa existe en tres niveles —fábrica
(`contaperu/pipeline/preparacion/configuracion.py`) → driver (`CUENTAS_POR_DEFECTO`) → empresa— resueltos por
`contaperu/drivers/contrato/`, pero **sin dimensiones**: la cuenta de un papel no depende de quién ni de qué.

**Qué tomar.** El `rol` en la línea, y no en la cuenta, **no es copiable de los comerciales y es correcto que no lo
sea**: en QuickBooks la línea y el plan de cuentas viven en el mismo sistema, así que basta mirar la cuenta. Aquí el
asiento **viaja a otro sistema que no tiene ese plan de cuentas**, y una línea tiene que explicarse sola. Lo que sí
queda por tomar es la tabla de determinación con dimensiones de OFBiz, iDempiere y Business Central — la única de
las cinco capas que cubre un hueco real, y que espera su caso en el §8 de [HOJA-DE-RUTA.md](HOJA-DE-RUTA.md).

Y una nota sobre el suelo, que es lo que cierra la discusión del nivel fino: **aquí la fuente no es un ERP, es el
PLE.** El artículo 6 de la RS 234-2006 ya fija el nivel obligatorio de la cuenta, y su Formato 5.1 ya tiene la forma
de nuestra línea. De ahí salió que planilla, depreciación y asiento de destino —595 de 1 441 asientos en un mes
real— entren por su **libro** del PLE y no por un rol nuevo.

## El documento y su asiento, y el enlace entre los dos

Al leer un documento del estándar parece que `comprobantes` y `asiento` dicen lo mismo dos veces: los dos traen el
tipo, la serie y el número, las fechas y la moneda. No es así, y la diferencia es la que sostiene el formato: **el
comprobante es el hecho y el asiento es su efecto sobre el plan de cuentas.** El asiento se regenera a partir del
comprobante, del plan de cuentas y de las reglas; el comprobante **no se puede reconstruir a partir del asiento**.

**Qué hacen.** Todos los separan, y todos los enlazan:

| Quién | El documento | El asiento | El enlace |
|---|---|---|---|
| **Xero** | `/Invoices`: **se escribe** | `/Journals`: **solo lectura**, lo escribe su motor contable | `SourceID` + `SourceType` en cada asiento, con 24 valores (`ACCPAY`, `ACCREC`, `MANJOURNAL`…) |
| **QuickBooks Online** | `Bill` e `Invoice`, con vencimiento, términos de pago e ítems | `JournalEntry` guarda solo los asientos manuales y de ajuste; el efecto de una factura en el mayor se consulta por reportes (`GeneralLedger`) | `LinkedTxn` entre documentos |
| **SAF-T (OCDE)** | `SourceDocuments`: facturas de venta, de compra y pagos | `GeneralLedgerEntries`: `Journal` → `Transaction` → `Line` | **Cruzado en los dos sentidos**: la línea lleva `SourceDocumentID` y la factura lleva `TransactionID` |
| **XBRL GL** | Los dos en el mismo árbol | `entryDetail`, con `documentType` y `entryType` | Del hecho al asiento, y del asiento al estado financiero |
| **`open-accounting`** | bloque `comprobantes` | bloque `asiento`, derivado | `documento{tipo_cp, serie_numero, fecha…}` en la línea, más `id_externo` |

**Tres consecuencias que se repiten en todos:**

1. **El asiento siempre tiene más líneas que el documento**, porque añade lo que la factura no dice: la cuenta de
   control del proveedor o del cliente, y la del impuesto.
2. **El documento tiene lo que el asiento nunca tendrá**: los ítems con cantidad y precio, el vencimiento, los
   términos de pago, el saldo pendiente y el archivo original. La norma de auditoría de EE. UU. lo dice como regla
   de evidencia: **el documento original vale más que cualquier copia o conversión** (PCAOB AS 1105).
3. **SAF-T exige los dos a la vez**, porque con solo el diario no se puede probar el impuesto por línea ni cruzar
   contra la facturación electrónica. En el Perú pasa igual: SUNAT pide el Libro Diario **y** el Registro de
   Compras.

**Qué tomar.** El enlace explícito del asiento a su documento, que entró como `documento` en la línea y como
`documento.id_externo` el día que llegó su caso (enmienda 0009). Lo que **no** se toma es fusionar los dos bloques:
con solo asientos se pierde el impuesto por línea y la prueba ante SUNAT; con solo documentos se pierde lo que el
contador decidió.

## Lo que no se toma, y por qué

- **El signo en vez de Debe/Haber.** Merge, Rutter y Xero usan un importe con signo. Es más compacto y
  peor para el caso peruano: la nota de crédito ya invierte el asiento, y un signo encima de eso es la
  fuente del error de «restar dos veces». `debe_haber` explícito se queda.
- **Importes numéricos.** Todos mandan números. `open-accounting` manda texto y acepta número por
  compatibilidad; la contabilidad no perdona el `float`.
- **El motor de impuestos del destino.** QuickBooks sobrescribe el `TaxCode`; ContaPerú no delega
  jamás el IGV en el ERP. El impuesto va explícito, en su línea, con su tasa.
- **OAuth, webhooks, sincronización incremental, `SyncToken`.** Son el problema de una API con estado
  que habla con otra API con estado. ContaPerú no tiene estado ni sale a la red: entra un documento,
  sale un documento. Lo que sí se toma de ahí es la **idea** —id externo y huella— sin el mecanismo.
- **La entidad como parámetro.** Las unificadas necesitan `company_id` o `subsidiary_id` en cada
  llamada porque su cliente ve muchas empresas a la vez. En `open-accounting` la entidad es `libro.ruc` y un
  documento es de un RUC y un mes: no hace falta más.
- **Un modelo de factura y proveedor propio.** Codat, Merge y Apideck modelan `Invoice`, `Bill`,
  `Contact`, `Item`. En Perú ese modelo ya existe y lo define SUNAT: el comprobante de `open-accounting` son
  los campos de la Tabla 10 y del SIRE, no una abstracción nueva.
- **La representación JSON de UBL.** OASIS publicó una *committee note* con UBL 2.1, 2.2 y 2.3 en JSON: cada
  elemento dentro de un arreglo y el valor en la clave `"_"` —`"IssueDate": [{"_": "2026-01-15"}]`—, con prefijos
  `_D`, `_A`, `_B`. Está pensada para volver a XML sin pérdida, no para que una persona la escriba. **No es
  normativa**, y UN/CEFACT CII solo tiene sintaxis XML. De EN 16931 se toma el modelo, no la sintaxis.
- **Los ~250 `AccountSubType` de QuickBooks.** Es el nivel fino que al estándar le falta, y aun así no se copia:
  cada país fue añadiendo los suyos y el enum dejó de ser un estándar. **Es el camino del que no se vuelve**, porque
  un valor publicado no se puede quitar. Si algún día entra un nivel fino, serán los 18 de Odoo derivados de la
  divisionaria del PCGE, no 250 mantenidos a mano.
- **El modelo de un ERP como el estándar, Odoo incluido.** Cinco motivos, y el primero es dirimente. **La
  licencia**: Odoo es LGPL y `contaperu` es MIT — los valores de un enum son hechos y citarlos es referencia, pero
  **empaquetar el CSV de `l10n_pe`** aquí no se hace. Y los otros cuatro: Odoo **es** un destino, no el estándar;
  ningún destino del motor lee Odoo (CONCAR, CONTASIS, SISCONT y STARSOFT, no); su modelo **no es un contrato
  versionado** —el campo pasó por `user_type_id`, `account.account.type` y `account_type` en mayores sucesivas, y la
  promesa de «nada se quita hasta una 2.0» no se monta sobre eso—; y no compiten de capa: Odoo clasifica un plan de
  cuentas, `open-accounting` intercambia documentos. Los artefactos comparables son SAF-T, XBRL GL y EN 16931.
- **Una tabla cuenta → rol para el PCGE.** Sería lo que hacen los comerciales, y no funciona aquí: el `rol` no es un
  atributo de la cuenta —la misma cuenta puede ser el principal de un asiento y la contrapartida de otro—, la
  relación es de muchos a muchos, y así una cuenta nueva no obliga a tocar nada.
- **Un rol nuevo por cada hecho nuevo** (planilla, depreciación, asiento de destino). Son 595 de 1 441 asientos en
  un mes real, así que el hueco es grande y la tentación también. Pero cada uno de esos hechos **ya tiene su libro
  en el PLE**, que es fuente normativa: entran por `libro.tipo`, no por un rol que habría que inventar y después
  mantener.

## Lo que falta mirar

Dos huecos declarados, para que nadie los dé por investigados:

- **El `ReportCode` de Xero**: el único campo de clasificación de cuenta que no está investigado en ningún documento
  del repositorio. Está en su API de cuentas.
- **La licencia exacta del módulo `l10n_pe` de Odoo**, y qué `account_type` asigna a cada elemento del PCGE, en
  especial al 9. Está en su `__manifest__.py` y su CSV. Hace falta solo para *comparar*: empaquetarlo está
  descartado arriba.

## Propuesta para `open-accounting`: campos opcionales

Todo lo de abajo es **aditivo**: campos opcionales que un consumidor de la 0.3 ignora sin romperse, así
que la versión del estándar no sube (ver `estandar/LEEME.md` §Versionado). Y ninguno es una regla
contable: son transporte y trazabilidad.

**Decidido el 11-sep-2026 (librería 0.8.0), con la regla del estándar —crece con casos reales detrás, no por
si acaso—:** entraron los tres que tenían caso real hoy: **`_exportacion`** con la huella (el Excel de CONCAR
se suma al importarlo dos veces), **`EXIGE`** en el contrato de driver (el portal se negaba sin centro de
costo y el motor solo avisaba: una regla viviendo fuera del motor) y **`pedir_a`** (como
`diagnosticar.que_falta[].pedir_a`; `proveedor` reservado). De los otros tres, `id_externo`
entró en el comprobante con la librería 0.10.0 (el caso llegó: la imputación de cada documento viaja por él), y
`dimensiones` y `estado` de la línea quedan como **nombres reservados** en `estandar/LEEME.md` hasta que haya un caso.

| Dónde | Campo | Lo inspira | Qué caso peruano lo necesita | Qué test lo fijaría |
|---|---|---|---|---|
| comprobante, línea | `id_externo: string` | Merge `remote_id`, Rutter `platform_id`, Apideck `downstream_id` | Un portal que guarda el comprobante con su propio id y quiere reconocerlo cuando vuelve del MCP; un driver que escribe el id del asiento en el ERP | El id entra y sale intacto por `leer_xml`, `revisar`, `generar_asiento` y `exportar` (transporte puro) |
| comprobante, línea | `dimensiones: [{tipo, codigo}]` | Xero `Tracking[]`, Merge/Apideck `tracking_categories[]` | STARSOFT/SISCONT con área + proyecto + obra; `centro_costo` sigue siendo la primera | CONCAR ignora `dimensiones` y su Excel no cambia (snapshot); el CSV las escribe aplanadas |
| línea | `estado: propuesto \| exportado \| importado \| anulado` | Merge `posting_status`, Xero `Status`, Apideck `status` | Que el portal no re-exporte lo ya importado en CONCAR; que una anulación quede dicha y no borrada | `generar_asiento` produce `propuesto`; `exportar` deja `exportado`; el núcleo nunca escribe `importado` (lo pone quien importó) |
| documento | `_exportacion: {driver, archivo, huella, fecha}` | QBO `DocNumber` + `SyncToken`, Xero `Idempotency-Key`, la regla «busca el id externo antes de crear» | Avisar de que ese mismo lote ya se exportó: el Excel de CONCAR se **suma** al importarlo dos veces | La huella es determinista (dos llamadas iguales, misma huella) y cambia si cambia un céntimo o una cuenta; la `fecha` la pone quien llama, nunca el núcleo (`test_frontera`: sin reloj) |
| fachada | `diagnosticar.faltantes[].pedir_a: contador \| proveedor \| sistema` | El *Accounting agent* de Intuit, que «redacta las preguntas para pedir la información que falta» | Que un agente sepa a quién preguntar sin adivinar | Cada código de observación y cada faltante tiene un `pedir_a` asignado en una tabla, y un test lo recorre entero |
| contrato de driver | `EXIGE: set[str]` declarativo | Codat `GET …/options/{dataType}`, Merge `/meta` | Un driver de asientos que no usa centros de costo no debe bloquear por ellos | `diagnosticar` marca «no listo» solo por lo que el driver elegido exige; el test de conformidad comprueba que `EXIGE` sea un subconjunto conocido |

Lo que **no** cambia con esto: `debe_haber`, importes en texto, base neta, `rol`, `documento`,
`referencia`, `datos_originales`. La propuesta añade en los bordes; el centro del estándar se queda como está
porque, comparado con lo de fuera, no hay nada que corregir.

## Fuentes

### Del asiento

Consultadas el 11-sep-2026.

**QuickBooks Online (Intuit)**
- Referencia de `JournalEntry`: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/journalentry
- Referencia de `Bill`: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/bill
- Modelo `JournalEntry` / `JournalEntryLineDetail` tal como lo implementa el SDK comunitario: https://github.com/ej2/python-quickbooks/blob/master/quickbooks/objects/journalentry.py
- Automated Sales Tax y cómo sobrescribe el `TaxCode`: https://help.developer.intuit.com/s/article/QBO-online-automated-sales-tax y https://blogs.intuit.com/2017/12/11/using-quickbooks-online-api-automated-sales-tax/
- `SyncToken`, CDC, lote de 30, `minorversion=75`, límites y formato de error: https://dev.to/zuplo/quickbooks-api-complete-developers-guide-2026-3l77 y https://medium.com/intuitdev/changes-to-our-accounting-api-that-may-impact-your-application-c330bd1a06f5
- Clases y ubicaciones como centros de costo: https://developers.apideck.com/connectors/quickbooks/docs/application_owner+departments_and_classes
- Agentes de IA (jul-2025): https://investors.intuit.com/news-events/press-releases/detail/1258/intuit-introduces-ground-breaking-virtual-team-of-ai-agents-to-fuel-growth-for-businesses
- Qué hace cada agente en QuickBooks Online: https://quickbooks.intuit.com/learn-support/en-us/help-article/accounting-bookkeeping/overview-agents-quickbooks-online/L9irCAtK4_US_en_US

**Xero**
- Manual Journals: https://developer.xero.com/documentation/api/accounting/manualjournals
- Journals (solo lectura, `SourceType`): https://developer.xero.com/documentation/api/accounting/journals y https://devblog.xero.com/navigating-the-shift-understanding-journals-vs-manual-journals-in-the-new-xero-app-tiers-dd8cc09a8418
- Impuestos en la API: https://developer.xero.com/documentation/guides/how-to-guides/tax-in-xero
- Tipos y enums (`LineAmountTypes`, `TaxRate`): https://xeroapi.github.io/xero-node/accounting/index.html
- `Idempotency-Key` (dic-2023): https://github.com/XeroAPI/xero-python/pull/124
- Webhooks y deduplicación: https://hookdeck.com/webhooks/platforms/guide-to-xero-webhooks-features-and-best-practices

**APIs unificadas**
- Merge — `JournalEntry` y `JournalLine`: https://docs.merge.dev/accounting/journal-entries/ ; modelos y convenciones (`remote_id`, `remote_data`, `/meta`): https://docs.merge.dev/accounting/overview/ ; retos de integración: https://www.merge.dev/blog/integration-challenges-for-payroll-software-vendors
- Codat — modelo de datos contable: https://docs.codat.io/data-model/accounting/ ; escritura (`options`, `pushOperation`, `validation.errors`): https://docs.codat.io/using-the-api/push
- Rutter — `JournalEntry`: https://docs.rutter.com/rest/2023-03-14/journal-entries ; propuesta: https://www.rutter.com/blog/erp-integration-unified-api
- Apideck — `JournalEntry`: https://developers.apideck.com/apis/accounting/reference/journal-entries ; «Accounting for developers» (impuestos, idempotencia, inmutabilidad): https://www.apideck.com/blog/accounting-for-developers ; multi-entidad: https://www.apideck.com/blog/multi-entity-general-ledger-integration

### Del registro del comprobante

Consultadas el 15-sep-2026.

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
- Crear factura de venta: …/api/dynamics_salesinvoice_create ; línea de factura de compra:
  …/resources/dynamics_purchaseinvoiceline

**Oracle NetSuite**
- `vendorBill` en el REST: https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/article_164484956387.html
- Peticiones asíncronas e idempotencia: …/subsect_164494900632.html

**Sage Intacct**
- Facturas de proveedor (APBILL): https://developer.intacct.com/api/accounts-payable/bills/
- Facturas de venta: https://developer.intacct.com/api/accounts-receivable/invoices/

**APIs unificadas**
- Merge: https://docs.merge.dev/accounting/invoices/ · Codat: https://docs.codat.io/payables/async/bills/
- Apideck: https://developers.apideck.com/apis/accounting/reference/bills y …/invoices
- Rutter: https://docs.rutter.com/rest/2023-03-14/bills y …/invoices

**Estándares abiertos de factura**
- Peppol BIS Billing 3.0: https://docs.peppol.eu/poacc/billing/3.0/bis/ ; su sintaxis UBL:
  https://docs.peppol.eu/poacc/billing/3.0/syntax/ubl-invoice/tree/
- UBL 2.3 en JSON (OASIS, *committee note*, no normativa):
  https://docs.oasis-open.org/ubl/UBL-2.3-JSON/v1.0/UBL-2.3-JSON-v1.0.html

### De la clasificación de la cuenta

Consultadas el 18-sep-2026 (los sistemas comerciales) y el 1-oct-2026 (los ERP abiertos).

**Dónde vive el papel de la línea**
- Xero, el libro diario de solo lectura con `SourceID` y `SourceType`:
  https://developer.xero.com/documentation/api/accounting/journals
- Xero, cuentas con `Type`, `Class` y `SystemAccount`: https://developer.xero.com/documentation/api/accounting/accounts
  y su especificación: https://github.com/XeroAPI/Xero-OpenAPI/blob/master/xero_accounting.yaml
- QuickBooks, la cuenta con `Classification`, `AccountType` y `AccountSubType`:
  https://developer.intuit.com/app/developer/qbo/docs/api/accounting/most-commonly-used/account ; el mayor, por
  reportes: …/all-entities/generalledger
- NetSuite, tipos de cuenta que no se pueden crear ni modificar:
  https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_3947502870.html
- Sage Intacct, la cuenta con `ACCOUNTTYPE` y `NORMALBALANCE`: https://developer.intacct.com/api/general-ledger/accounts/
- Merge (`classification`): https://docs.merge.dev/accounting/accounts/ ·
  Rutter (`category`): https://docs.rutter.com/rest/2023-02-07/accounts · Apideck: https://specs.apideck.com/accounting.yml
- XBRL GL, `accountPurposeCode` y `accountType`:
  https://www.xbrl.org/GLWGNotes/XBRL-GL-WGN-Amazing_Account-2007-07-08.htm
- SAF-T de la OCDE, con `SourceDocuments` y `GeneralLedgerEntries` enlazados en los dos sentidos: guía 2.0 y su
  apéndice B, en el archivo público de la OCDE
- ISO 20022, catálogos de códigos externos «para añadir sin cambiar la versión de los mensajes»:
  https://www.iso20022.org/catalogue-messages/additional-content-messages/external-code-sets
- PCAOB AS 1105, la evidencia del documento original:
  https://pcaobus.org/oversight/standards/auditing-standards/details/AS1105

**La determinación de cuentas, en los ERP abiertos**
- Apache OFBiz, `GlAccountTypeDefault` y «translate one side of the journal entry»: su guía de contabilidad general
- iDempiere, `C_AcctSchema_Default` y sus ranuras con prefijo: su wiki de esquema contable
- Business Central, *VAT posting groups* («about **who**» y «about **what**»):
  https://learn.microsoft.com/en-us/dynamics365/business-central/finance-setup-vat
- Odoo, los 18 `account_type` y sus grupos derivados: el modelo `account.account` de su documentación de desarrollo
