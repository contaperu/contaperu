# Referencias: cómo modelan la contabilidad las APIs de EE. UU., y qué tomar de ellas

Este documento recoge lo que hacen la API de QuickBooks Online, la de Xero y las **APIs unificadas**
(Merge, Codat, Rutter, Apideck) que ponen un modelo común encima de decenas de sistemas contables — y
lo compara, campo a campo, con `pe-ledger`. Termina con una propuesta concreta de qué añadir al
estándar y qué no. Investigación hecha el 11-sep-2026 sobre la documentación pública de cada uno; las
fuentes están al final.

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

| | QuickBooks Online | Xero | Merge | Rutter | Apideck | **pe-ledger** |
|---|---|---|---|---|---|---|
| Objeto | `JournalEntry` | `ManualJournal` | `JournalEntry` | `JournalEntry` | `JournalEntry` | bloque `asiento` |
| Línea | `Line.JournalEntryLineDetail` | `JournalLines[]` | `JournalLine` | `line_items[]` | `line_items[]` | `linea` |
| Cuenta | `AccountRef` | `AccountCode` / `AccountID` | `account` | `account_id` | `ledger_account` | `cuenta` |
| Debe / Haber | `PostingType: Debit\|Credit` | signo de `LineAmount` (+ debe) | signo de `net_amount` (+ debe) | signo de `total_amount` | `type: debit\|credit` | `debe_haber: D\|H` |
| Importe | número | número | número | número | número | **texto exacto** |
| Cuadre | rechaza si no cuadra | rechaza | «las líneas suman 0» | — | mínimo 2 líneas, suman 0 | `partida_doble.exigir`, sin tolerancia |
| Impuesto por línea | `TaxCodeRef`, `TaxAmount`, `TaxApplicableOn` | `TaxType`, `TaxAmount` | `tax_rate` | `tax_rate_id` | `tax_rate`, `tax_type: sales\|purchase`, `tax_amount` | línea con `rol: igv`, `tasa_igv` |
| Con o sin impuesto | — | `LineAmountTypes: Exclusive\|Inclusive\|NoTax` | `inclusive_of_tax` | — | `tax_inclusive` | base siempre neta (regla del estándar) |
| Dimensiones | `ClassRef` (línea), `DepartmentRef` (transacción) | `Tracking[]` (hasta 2 por línea) | `tracking_categories[]` | `class_id`, `department_id`, `location_id` (vía `additional_fields`) | `tracking_categories[]`, `department_id`, `location_id` | `centro_costo`, `anexo_auxiliar` |
| Contraparte | `Entity{Type, EntityRef}` | — | `contact` | `customer_id`, `vendor_id` | `customer`, `supplier`, `employee` | `contraparte_doc` (RUC) |
| Documento origen | `DocNumber` | `/Journals`: `SourceType`, `SourceID` (solo lectura) | — | — | `source_type`, `source_id` | `documento{tipo_cp, serie_numero, fecha…}`, `referencia` |
| Rol de la línea | — | — | — | — | — | `rol: principal\|igv\|tercero\|…` |
| Estado | — | `Status: DRAFT\|POSTED\|VOIDED\|DELETED` | `posting_status: UNPOSTED\|POSTED` | — | `status: draft\|pending_approval\|approved\|posted\|voided…` | — |
| Id en el otro sistema | `Id` | `ManualJournalID` | `remote_id` | `platform_id` | `downstream_id` | — |
| Versión / concurrencia | `SyncToken` | `UpdatedDateUTC` | `modified_at` | `updated_at` | `row_version` | — |
| Lo no mapeado | — | — | `remote_data`, `remote_fields` | `platform_data`, `additional_fields` | `pass_through`, `custom_mappings` | `datos_raw` (comprobante) |
| Moneda y T.C. | `CurrencyRef`, `ExchangeRate`, `HomeTotalAmt` | — | `currency`, `exchange_rate` | `currency_code`, `currency_rate` | `currency`, `currency_rate` | `moneda`, `tipo_cambio` |

Lo primero que se ve: **todos convergen en lo mismo** —cuenta, sentido, importe, impuesto, dimensión,
contraparte— y `pe-ledger` ya lo tiene. Lo segundo: en dos decisiones el estándar peruano va **mejor**
que la mayoría para su caso. `debe_haber` explícito en vez de un signo evita el error más común al
integrar (restar dos veces una nota de crédito); y los importes como texto evitan que un `float` de
JSON pierda un céntimo. Lo tercero: el `rol` de la línea no lo tiene nadie, y es lo que permite que un
driver encuentre «la línea del IGV» sin saber qué cuenta usa cada empresa.

## Siete hallazgos

### 1. Los impuestos son «el campo que rompe todo»

**Qué hacen.** Apideck lo dice con esas palabras: si no se distingue precio con impuesto incluido de
precio más impuesto, «los ingresos y la obligación tributaria salen mal los dos». Xero lo resuelve con
`LineAmountTypes` a nivel de documento; Merge con `inclusive_of_tax`. Y en QuickBooks US, el motor de
*Automated Sales Tax* **sobrescribe** el `TaxCode` que mandes con el que él calcula. La recomendación
transversal de las unificadas es mandar el impuesto **explícito** y no delegar en el motor del ERP.

**Qué hace pe-ledger.** Exactamente eso, desde la 0.2: base e IGV siempre netos, la línea `igv` lleva
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

**Qué hace pe-ledger.** Un `centro_costo` y un `anexo_auxiliar` por línea; la entidad es `libro.ruc`.
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

**Qué hace pe-ledger.** `drivers/contrato.py::incumplimientos()` es el «options» del driver, y
`operaciones.diagnosticar` es el `validation.errors`: responde por serie-número qué falta, sin lanzar.

**Qué tomar.** Que **cada driver declare lo que exige** (`EXIGE = {"cuenta", "centro", "correlativo",
"moneda"}`) y `diagnosticar` lo lea de ahí, en vez de asumir que todo driver de asientos exige lo mismo
que CONCAR. Un driver de SISCONT que no use centros de costo no debería marcar «no listo» por ellos.

### 4. Idempotencia: guardar el id externo y buscarlo antes de crear

**Qué hacen.** QuickBooks lleva un `SyncToken` en cada objeto —un contador de versión: actualizar con
uno viejo falla—, usa `DocNumber` como clave de negocio, y desde ago-2025 obliga a `minorversion=75`.
Xero acepta `Idempotency-Key` en PUT/POST/PATCH desde 2023 y recomienda deduplicar webhooks por
`resourceId + eventDateUtc`. Apideck lleva `row_version`. Y la regla que repiten las tres unificadas:
**guardar el id externo de todo lo que se escribe y buscarlo antes de crear**, porque «los webhooks
pueden disparar dos veces el mismo evento».

**Qué hace pe-ledger.** El modelo tiene `clave` de duplicados (tipo, serie, número, documento de la
contraparte), que es la clave de negocio del comprobante. No tiene un id del sistema destino ni una
huella del asiento generado.

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

**Qué hace pe-ledger.** Cada línea lleva `documento` y `referencia` —de qué comprobante sale y, si es
una nota, a cuál corrige—, y el comprobante lleva `datos_raw` que el núcleo transporta y jamás lee.
Los importes van siempre en positivo y la nota de crédito invierte: nunca hay un asiento negativo que
«borre» otro.

**Qué tomar.** El **estado del asiento**. Hoy el bloque `asiento` de pe-ledger es siempre una
propuesta; no puede decir «esto ya se importó en CONCAR» ni «esto se anuló». Un `estado:
propuesto | exportado | importado | anulado` opcional por línea (o por documento) es lo que Merge
llama `posting_status` y Xero `Status`, y lo que un portal necesita para no re-exportar lo importado.

### 6. Las unificadas transportan lo que no entienden

**Qué hacen.** Merge devuelve `remote_data` (el JSON crudo del ERP) y acepta `remote_fields`; Rutter
`platform_data` y `additional_fields`; Apideck `pass_through` con rutas JSONPath y `custom_mappings`.
Es la válvula que evita que el modelo común crezca por cada campo raro de cada plataforma.

**Qué hace pe-ledger.** Regla 5 del estándar: «lo que no se entiende, se transporta», con `datos_raw`
en el comprobante y las claves `_` como anotaciones del productor.

**Qué tomar.** Nada: es el mismo diseño. Solo conviene documentar en `LEEME.md` que un driver puede
leer `datos_raw` para lo específico de su ERP —como Rutter con `additional_fields`— sin que el núcleo lo
interprete.

### 7. Los agentes llegaron después del núcleo, y piden en vez de adivinar

**Qué hacen.** Intuit lanzó en julio de 2025 un «equipo virtual» de agentes en QuickBooks Online
(Accounting, Payments, Finance, Customer, Payroll, Project Management) y en octubre *Intuit
Intelligence*, la capa que enruta una orden en lenguaje natural. El *Accounting agent* categoriza y
concilia, pero lo más interesante es que **«redacta las preguntas para pedir la información que falta»**
y gestiona la ida y vuelta con el contador antes de actualizar; el *Payments agent* predice retrasos y
redacta recordatorios; el *Finance agent* hace KPIs, escenarios y *benchmarking*. El humano revisa y
aprueba. Y QuickBooks no empezó por ahí: los agentes se apoyan en años de núcleo de datos y reglas.

**Qué hace pe-ledger.** `diagnosticar` responde «¿qué falta?» por serie-número, y las reglas del
servidor MCP del estudio dicen lo mismo que Intuit: enseñar qué sale antes de generar, y no ofrecerse a
corregir —un comprobante sin cuenta se arregla donde se revisa.

**Qué tomar.** Que cada faltante diga **a quién hay que pedírselo**: `faltantes[].pedir_a:
contador | proveedor | sistema`. La cuenta contable la pone el contador; la fecha del documento
referido que el XML no trae, el proveedor; el correlativo, el sistema. Es lo que le permite a un agente
redactar la pregunta correcta sin que el núcleo adivine nada.

## Lo que no se toma, y por qué

- **El signo en vez de Debe/Haber.** Merge, Rutter y Xero usan un importe con signo. Es más compacto y
  peor para el caso peruano: la nota de crédito ya invierte el asiento, y un signo encima de eso es la
  fuente del error de «restar dos veces». `debe_haber` explícito se queda.
- **Importes numéricos.** Todos mandan números. `pe-ledger` manda texto y acepta número por
  compatibilidad; la contabilidad no perdona el `float`.
- **El motor de impuestos del destino.** QuickBooks sobrescribe el `TaxCode`; ContaPerú no delega
  jamás el IGV en el ERP. El impuesto va explícito, en su línea, con su tasa.
- **OAuth, webhooks, sincronización incremental, `SyncToken`.** Son el problema de una API con estado
  que habla con otra API con estado. ContaPerú no tiene estado ni sale a la red: entra un documento,
  sale un documento. Lo que sí se toma de ahí es la **idea** —id externo y huella— sin el mecanismo.
- **La entidad como parámetro.** Las unificadas necesitan `company_id` o `subsidiary_id` en cada
  llamada porque su cliente ve muchas empresas a la vez. En `pe-ledger` la entidad es `libro.ruc` y un
  documento es de un RUC y un mes: no hace falta más.
- **Un modelo de factura y proveedor propio.** Codat, Merge y Apideck modelan `Invoice`, `Bill`,
  `Contact`, `Item`. En Perú ese modelo ya existe y lo define SUNAT: el comprobante de `pe-ledger` son
  los campos de la Tabla 10 y del SIRE, no una abstracción nueva.

## Propuesta para `pe-ledger`: campos opcionales

Todo lo de abajo es **aditivo**: campos opcionales que un consumidor de la 0.2 ignora sin romperse, así
que la versión del estándar no sube (ver `estandar/LEEME.md` §Versionado). Y ninguno es una regla
contable: son transporte y trazabilidad. Están aquí como propuesta, pendiente de decidir; no están
implementados.

| Dónde | Campo | Lo inspira | Qué caso peruano lo necesita | Qué test lo fijaría |
|---|---|---|---|---|
| comprobante, línea | `id_externo: string` | Merge `remote_id`, Rutter `platform_id`, Apideck `downstream_id` | Un portal que guarda el comprobante con su propio id y quiere reconocerlo cuando vuelve del MCP; un driver que escribe el id del asiento en el ERP | El id entra y sale intacto por `leer_xml`, `revisar`, `generar_asiento` y `exportar` (transporte puro) |
| comprobante, línea | `dimensiones: [{tipo, codigo}]` | Xero `Tracking[]`, Merge/Apideck `tracking_categories[]` | STARSOFT/SISCONT con área + proyecto + obra; `centro_costo` sigue siendo la primera | CONCAR ignora `dimensiones` y su Excel no cambia (snapshot); el CSV las escribe aplanadas |
| línea | `estado: propuesto \| exportado \| importado \| anulado` | Merge `posting_status`, Xero `Status`, Apideck `status` | Que el portal no re-exporte lo ya importado en CONCAR; que una anulación quede dicha y no borrada | `generar_asiento` produce `propuesto`; `exportar` deja `exportado`; el núcleo nunca escribe `importado` (lo pone quien importó) |
| documento | `_exportacion: {driver, archivo, huella, fecha}` | QBO `DocNumber` + `SyncToken`, Xero `Idempotency-Key`, la regla «busca el id externo antes de crear» | Avisar de que ese mismo lote ya se exportó: el Excel de CONCAR se **suma** al importarlo dos veces | La huella es determinista (dos llamadas iguales, misma huella) y cambia si cambia un céntimo o una cuenta; la `fecha` la pone quien llama, nunca el núcleo (`test_frontera`: sin reloj) |
| fachada | `diagnosticar.faltantes[].pedir_a: contador \| proveedor \| sistema` | El *Accounting agent* de Intuit, que «redacta las preguntas para pedir la información que falta» | Que un agente sepa a quién preguntar sin adivinar | Cada código de observación y cada faltante tiene un `pedir_a` asignado en una tabla, y un test lo recorre entero |
| contrato de driver | `EXIGE: set[str]` declarativo | Codat `GET …/options/{dataType}`, Merge `/meta` | Un driver de asientos que no usa centros de costo no debe bloquear por ellos | `diagnosticar` marca «no listo» solo por lo que el driver elegido exige; el test de conformidad comprueba que `EXIGE` sea un subconjunto conocido |

Lo que **no** cambia con esto: `debe_haber`, importes en texto, base neta, `rol`, `documento`,
`referencia`, `datos_raw`. La propuesta añade en los bordes; el centro del estándar se queda como está
porque, comparado con lo de fuera, no hay nada que corregir.

## Fuentes

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
