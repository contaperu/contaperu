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
   estándar: propone que **el estándar sea también el cuerpo de la llamada**. La sección 7 cuenta por qué el primer
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

**Lo que hay que tener antes de llamar** (la guía lo pide en su primera página de configuración): una **IP pública**,
una **licencia activa** del ERP y **las cuentas contables ya configuradas** en su Configurador de cuentas. Es una
integración para los clientes de STARSOFT —pensada para el que tiene su contabilidad tercerizada en un estudio—, no
un formato que un tercero cualquiera pueda adoptar. En lo que la guía publica no aparece autenticación: el control
de acceso que describe es esa IP pública.

**Y el registro no termina en la llamada.** La API deja los datos en una tabla; el contador entra después al módulo
de contabilidad, a *Otros › Importación de datos externos*, elige el tipo y ejecuta la importación. **La API
alimenta una bandeja, no contabiliza** — y esto, que parece un defecto, es el acierto escondido de su diseño
(«Qué enseña», punto 4).

### Qué enseña

1. **Compras y ventas son dos hechos distintos, no dos formas del mismo.** Tienen campos propios —`destino_Compra` y
   la detracción de un lado; `exportacion` y el ISC del otro—, y por eso QuickBooks tiene `Bill` e `Invoice` y
   Business Central `purchaseInvoices` y `salesInvoices`. Lo que **no** se sigue de ahí es que hagan falta dos rutas:
   Xero y Merge lo dicen con un discriminador dentro del cuerpo, y aquí el documento ya lo trae en `libro.tipo`.
2. **El ERP quiere el asiento, no solo el documento.** Espera cuentas: `42102`, `60101`, `40111`. Un JSON que solo
   lleve el comprobante le obliga a inventarlas.
3. **La detracción y el centro de costo son de primera clase**, no un añadido. Cualquier estándar peruano tiene que
   llevarlos.
4. **La bandeja es lo mejor que tiene, y no lo dice.** Ningún sistema serio deja que una llamada de fuera escriba
   directamente en la contabilidad: la API deposita, y un contador aprueba. Es la razón de fondo de que el motor
   devuelva diagnóstico y asiento en vez de guardar nada —**quien llama decide**—, y de que la bandeja sea del ERP y
   no del motor.
5. **Su ruta de anexos existe porque su modelo usa ids internos.** `RegistrarAnexos` hace falta porque las líneas
   dicen `cod_Proveedor`, un código de su base: sin dar de alta la ficha antes, la compra no se puede colgar de
   nadie. Aquí no hace falta ninguna ruta equivalente, porque el RUC viaja en el propio comprobante
   (`contraparte_doc`), que es el modelo de EN 16931. Es la ventaja de la contraparte embebida, vista de cerca.
6. **Lo que ellos llaman «asiento de honorarios» aquí ya es una compra.** Su ejemplo es un recibo por honorarios con
   su cuenta de gasto y su retención; en el estándar es un comprobante de compra con `retencion`. No pide un bloque
   nuevo: pide que el caso exista.

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
- **La IP pública como control de acceso**, y una integración que exige licencia del propio ERP. Un estándar que
  pide una licencia para ser hablado no es un estándar.
- **Un ejemplo que hay que copiar a mano con cuarenta campos por línea.** En la guía, el ejemplo de ventas no cierra
  —reaparecen `ruc` y `listadoAsientos` dentro de un elemento del arreglo—. Puede ser cosa de cómo el PDF suelta el
  texto, pero un formato así es exactamente donde ese error deja de ser raro.

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
    peruanas no existen en ese mundo: son la parte que el estándar de aquí tiene que aportar. Es la tesis de todo
    esto, y por eso tiene la sección siguiente entera.

---

## 5 · Lo que ninguna API del mundo tiene: detracción, retención y percepción

El punto 12 de la sección anterior es el que justifica que este estándar exista, y merece su propia sección. De las
nueve fuentes revisadas —cinco ERP, tres API unificadas y los estándares abiertos europeos— **ninguna tiene un campo
para nada de esto**. No es un descuido suyo: es que en su mundo no existe.

Los tres son **movimientos de dinero paralelos a la operación**, no impuestos sobre ella. Por eso no caben en un
modelo que describe el impuesto como categoría, tasa y base: la plata se mueve entre partes que no son las dos de la
factura.

### La detracción, o por qué un asiento no se cierra de una vez

El comprador **no le paga todo al proveedor**: retiene un porcentaje del total y lo deposita en una cuenta que el
proveedor tiene en el Banco de la Nación, reservada para pagar sus impuestos. El proveedor cobra el resto.

Eso, por sí solo, ya rompe el modelo de EN 16931: hay un **tercero** —un banco del Estado— que cobra parte de una
factura entre dos empresas, y el importe que el proveedor recibe no es el total del documento.

Pero lo que de verdad no cabe en ningún modelo es que **ocurre en dos tiempos**. Cuando se registra la compra el
depósito todavía no se ha hecho: no hay número de constancia, y llega días después. Un documento de factura europeo
se considera cerrado al emitirse; aquí falta un dato que nadie tiene todavía.

El estándar lo resuelve con un bloque de estado dentro del comprobante:

```json
"detraccion": {
  "codigo": "027",           "porcentaje": 4,
  "monto": "198.00",         "cuenta": "00-123-456789",
  "estado": "PROVISIONADO",  "nro_constancia": "", "fecha_constancia": ""
}
```

- **`PROVISIONADO`** es el primer tiempo: la compra está registrada y la detracción se debe. El asiento se genera
  igual, y en el perfil neutral las dos líneas de la detracción cuelgan del propio comprobante.
- **`PAGADO`** es el segundo: se depositó, y entran `nro_constancia` y `fecha_constancia`. **El asiento ya importado
  no se regenera**, porque en un destino que suma lo que importa, como CONCAR, volver a importarlo duplicaría.
- El paso de uno a otro es una operación aparte y sin estado: entra el documento provisional y el archivo de
  constancias, sale el documento actualizado.

Y dos detalles que solo existen aquí:

- **El monto se deposita siempre en soles**, aunque la factura esté en dólares. Un modelo con una sola moneda por
  documento no puede decir eso; por eso `monto` es en soles aunque el resto del comprobante no lo sea.
- **La tabla de códigos vive en el motor** —código, nombre y tasa, con su fuente— y el ERP la sobreescribe desde su
  configuración. Un código que no está en la tabla queda en blanco en todas las operaciones, así que un `000`
  inventado nunca provisiona una detracción.

En el asiento son dos líneas con rol propio, `detraccion_tercero` y `detraccion`, que mueven del saldo del proveedor
a la cuenta de detracciones. Se ven generadas en la sección 9.

### La retención, que son dos cosas distintas con el mismo nombre

Confundirlas es un error contable, y por eso el estándar las separa por nombre:

| | Qué es | ¿Entra al asiento? | En el estándar |
|---|---|---|---|
| **Renta de 4ta categoría** | Lo que el contratante retiene de un recibo por honorarios y paga a SUNAT por cuenta del profesional | **Sí**, con rol propio `retencion_4ta` | `retencion`, hoy |
| **Retención del IGV** | El 3 % que aplica un agente de retención designado por SUNAT, y que el XML trae en `PaymentTerms` | **No, en ninguno** — tampoco en el asiento neutral | `retencion_igv`, nombre reservado |

**La del IGV no entra en ningún asiento, tampoco en el neutral**, y no es una omisión: es que **no es un hecho del
comprobante, sino del pago**. El agente de retención la aplica cuando paga la factura, días después, y lo que la
registra es el asiento de tesorería — que está fuera de compras y ventas, o sea fuera de lo que hace este motor. Es
el mismo motivo por el que el segundo tiempo de la detracción no regenera nada: lo que ocurre al pagar es otro hecho.
Por eso el campo está reservado con su forma tomada, para transportar el dato a quien sí lleve ese asiento, no para
que el motor lo contabilice.

**Y la de 4ta el motor no la calcula: lee la que el recibo muestra.** `retencion` es un importe, no una tasa —la
misma regla que con el IGV, cuya tasa se lee del comprobante y nunca de una configuración—, porque quien retuvo ya
decidió cuánto, y una tasa que cambia por norma no puede vivir en el código de nadie.

### La percepción, el espejo

Aquí el vendedor **cobra de más**: añade un porcentaje al comprador, que es un pago a cuenta del IGV de ese
comprador. Pasa con los combustibles, con ciertas importaciones y con una lista de bienes.

Es el reverso de la retención —uno cobra de más, el otro paga de menos—, y tiene el mismo problema para un modelo
extranjero: el total que cambia de manos no es el total de la operación. Hoy es un nombre reservado, `percepcion`, a
la espera de su caso real.

### Por qué EN 16931 y Peppol no pueden con esto

No es que les falte un campo: es que el modelo no tiene dónde ponerlo.

1. **Describen el impuesto como categoría, tasa y base, agregado por cabecera.** Los tres mecanismos no son un
   impuesto sobre la operación, sino dinero que se mueve por fuera de ella.
2. **Suponen dos partes.** La detracción mete a un tercero —el Banco de la Nación— que cobra parte de la factura.
3. **Suponen un documento cerrado.** La detracción se completa días después, con un dato que al emitir no existe.

Un ERP extranjero que quiera operar en el Perú tiene que resolver los tres con asientos manuales y campos libres, que
es exactamente lo que hoy hacen. Recibirlos ya modelados es lo que este estándar aporta y ningún otro.

### El estado de los tres, sin adornos

| Mecanismo | Hoy |
|---|---|
| Detracción | **Completa**, en dos tiempos, con su tabla de códigos en el motor y dos líneas propias en el asiento |
| Retención de renta de 4ta | **En el estándar**, con su rol en el asiento |
| Retención del IGV | Nombre reservado, `retencion_igv`, con su forma ya tomada. **No entra en ningún asiento**: es un hecho del pago, no del comprobante |
| Percepción | Nombre reservado, `percepcion` |

Dos de los cuatro esperan un caso real, que es la regla del proyecto: el estándar se mueve con un archivo de verdad
detrás, no por si acaso. Y mientras tanto quien los tenga los transporta en `datos_originales`, que el motor pasa sin
interpretar.

---

## 6 · Qué de todo esto ya tiene `open-accounting` 0.3

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

## 7 · El borrador: un solo formato, el del estándar

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

### ¿Y el tipo de libro no lo dice la ruta?

Lo decía en el primer borrador, porque un `comprobante` suelto no tenía dónde decirlo. Con el documento como cuerpo
hay dos sitios para el mismo dato, y **el que sobra es la ruta**:

1. **Cinco operaciones reciben un documento** —`revisar`, `normalizar_detracciones`, `diagnosticar`,
   `generar_asiento` y `exportar`—, así que el tipo en la ruta las duplica a diez, y a doce cuando entre la
   siguiente. Decirlo en la ruta solo sale barato si hay una sola ruta, y no la hay.
2. **Tres de las cuatro puertas no tienen URL.** Python es `api.exportar(documento, driver=…)`; la CLI,
   `contaperu diagnosticar mi-mes.json`; MCP tampoco. Un dato que vive en la ruta obliga a la CLI a inventarse un
   `--tipo`, y entonces el mismo archivo significa cosas distintas según por dónde entre.
3. **El documento es un archivo.** Se guarda, se manda y se abre dentro de un año, cuando ya no hay petición
   alrededor. Una compra y una venta tienen casi los mismos campos —cambia si la contraparte es el proveedor o el
   cliente—, de modo que sin `tipo` un archivo suelto no sabe qué libro es.
4. **`libro` es la cabecera tributaria, y es RUC + mes + tipo.** Ya es obligatoria en la 0.3: sacarle el tipo sería
   una 0.4 que rompe a todos para ahorrar un campo.

No es una rareza de aquí: Xero lo dice con `Type: ACCPAY | ACCREC` y Merge con
`type: ACCOUNTS_PAYABLE | ACCOUNTS_RECEIVABLE`, los dos dentro del cuerpo (sección 2).

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

## 8 · El recorrido, visto desde el ERP que ya tiene el dato

Lo anterior mira el formato. Esta sección mira lo otro que pregunta quien va a integrar: **dónde corre esto, quién
hace qué y en qué orden.** Hace falta porque el resto del documento está escrito desde el que captura, y un ERP no
captura: la factura y el proveedor ya están en sus tablas.

### Dónde se procesa: dentro del ERP, siempre

**El motor es una librería que el ERP instala, no un servicio al que le pide permiso.** No hay un servidor de
ContaPerú en medio de nadie — justo lo contrario del modelo de la sección 1, donde `starsoftweb.com` está en medio y
por eso hacen falta IP pública y licencia. Los datos del contribuyente **no salen de la infraestructura de quien
integra**.

| El ERP… | Cómo llama | Dónde corre el motor |
|---|---|---|
| Está en Python (Odoo, Frappe, un servicio propio) | `api.exportar(documento, driver="concar")` | Dentro de su propio proceso: sin red y sin puerto |
| Está en otro lenguaje (.NET, Java, PHP) | `POST http://localhost:8080/v1/exportar` | `contaperu-http`, que levanta él en su servidor o su contenedor |
| Procesa lotes sin programar | `contaperu desde-json mes.json --driver concar` | Su máquina |
| Es un agente de IA | El servidor MCP | Su cliente |

Sí hay una ruta HTTP, entonces, pero es **suya**. Las cuatro puertas dan lo mismo, y un test lo comprueba: el mismo
XML da el mismo documento y el mismo diagnóstico por cualquiera de ellas.

### Quién vuelve estándar cada entrada

| Entra | Quién lo estandariza |
|---|---|
| XML de SUNAT, o el TXT de la propuesta del SIRE | **El motor**: `leer_xml`, `leer_propuesta_sire` |
| PDF, fotos, o las tablas propias del ERP | **El ERP**: su IA o su mapeo entrega los campos. El motor no sale a la red ni lee imágenes |

En los dos casos, **validar lo armado es siempre del motor** (`revisar`, `diagnosticar`).

### Las dos piezas que no son el documento

| Pieza | Qué lleva | Cada cuánto |
|---|---|---|
| **Configuración** | Lo que vale para todo el entorno: cuentas por defecto, si usa centros de costo, y una sección por sistema contable —siglas, sub-diarios, en qué columna va cada dato— | Una vez por empresa |
| **Imputación** | Lo que se decide para **un** comprobante: su cuenta, su centro de costo, la cuenta del total o un reparto entre varias | Solo donde haga falta |

**El usuario no teclea la cuenta en cada factura.** Deja los valores por defecto una vez e imputa lo que se sale de
la norma; lo que la imputación no traiga sale de la configuración.

### Los cuatro pasos

1. **Armar el documento** desde sus tablas —o dejar que el motor lo arme, si lo que tiene son los XML o el TXT.
2. **Diagnosticar antes de exportar**, siempre. La respuesta dice si el mes está listo para ese destino y, si no,
   qué falta y **a quién pedírselo**: `pedir_a` distingue al contador del sistema.
3. **Mostrar, corregir y volver al paso 2.** Ahí está su bandeja —su pantalla, sus usuarios, su base—, que es suya:
   el motor no guardó nada entre una llamada y la siguiente.
4. **Exportar.** Devuelve el archivo del destino y la huella con la que después reconocerá lo que ya exportó.

### Lo que sale, según el destino

- **SIRE:** el TXT del registro. **No lleva cuentas**, así que quien solo quiere el SIRE no configura plan contable.
- **CONCAR y CONTASIS:** los asientos o el registro, cada uno con el vocabulario de su sistema.
- **Otro ERP:** el asiento neutral, que es lo que un sistema nuevo viene a buscar aquí.

### El asiento, que ya existe

No está por implementar: **el Excel de CONCAR son asientos**, y `generar_asiento` es una operación pública desde la
1.0. Lo que añade el driver `open_accounting` es el **perfil neutral** —las mismas cuentas, sentidos e importes, sin
el vocabulario de un legacy—. Este es el asiento real de la compra del ejemplo de arriba, generado por el motor:

| `rol` | `cuenta` | | `importe` |
|---|---|---|---|
| `principal` | 6343001 | D | 10000.00 |
| `igv` | 401111 | D | 1800.00 |
| `tercero` | 421201 | H | 11800.00 |
| `detraccion_tercero` | 421201 | D | 1416.00 |
| `detraccion` | 421203 | H | 1416.00 |

Y así viene cada línea:

```json
{
  "cuenta": "6343001", "debe_haber": "D", "importe": "10000.00", "rol": "principal",
  "fecha": "2026-01-15", "moneda": "PEN", "centro_costo": "OBRA01",
  "glosa": "SERVICIO DE MANTENIMIENTO ENERO 2026", "tasa_igv": "18",
  "documento": { "tipo_cp": "01", "serie_numero": "F001-123",
                 "fecha_emision": "2026-01-15", "fecha_vencimiento": "2026-02-14" }
}
```

**Lo que hace ese asiento portable entre ERPs es `rol`, no la cuenta.** Un sistema que quiera el IGV en una columna
aparte busca la línea por su rol, porque la cuenta `401111` la elige cada empresa pero «esta línea es el IGV» vale
para todas. Los roles son `principal`, `igv`, `retencion_4ta`, `tercero`, `detraccion_tercero` y `detraccion`.

---

## 9 · La arquitectura de los destinos: al SIRE llegan todos

Los destinos no son tres opciones en fila. **El SIRE está al final de todos los caminos**, porque es el trámite con
SUNAT y la liquidación del impuesto; un sistema legacy se alimenta a diario con los comprobantes y al cierre saca su
TXT. Lo que cambia es por dónde se llega:

```
        Comprobantes (los hechos)
                 │
                 ├──────────────► SIRE ──► SUNAT
                 │                 ▲
                 ▼                 │
        Registro contable ─────────┘
    CONCAR · CONTASIS · STARSOFT · asiento neutral
```

**Y por eso el driver `sire` no exige nada.** Se llega al SIRE con la contabilidad hecha o sin ella: un contribuyente
puede presentar su registro a SUNAT aunque el mes no esté contabilizado todavía, que es justo lo que un sistema
legacy solo no permite, porque antes hay que digitarlo.

**Dónde termina el motor.** Dentro de compras y ventas, el SIRE es el final. Lo que sigue —el libro diario, el mayor
y los estados financieros— se queda en el sistema contable, y el motor no entra ahí.

### Lo que exige cada destino

| Destino | Grupo | Qué exige |
|---|---|---|
| `sire` | sire | **nada** |
| `open_accounting` | erp | cuenta contable |
| `contasis` | legacy | cuenta contable, cuenta única |
| `concar` | legacy | centro de costo, cuenta contable, moneda, tipo |

El camino de los asientos sin software contable es **el más barato de los tres que llevan cuentas**, porque un driver
neutral no declara claves de un sistema legacy y el núcleo solo le pide la cuenta.

### Lo que el entorno declara

Dos campos, y el segundo no es «¿presenta el SIRE?» —todos lo presentan— sino quién lo produce:

| Campo | Valores |
|---|---|
| **¿Dónde lleva su contabilidad?** | CONCAR · CONTASIS · STARSOFT · **«ninguno: generar asientos»** · ninguno |
| **¿Quién saca el TXT del SIRE?** | Su sistema contable, que ya lo alimenta a diario · **el motor, directo desde los comprobantes** |

Lo que el mes tiene que cumplir es **la suma de lo que exigen los destinos declarados**. Si el entorno eligió generar
asientos, la cuenta contable pasa a ser obligatoria y el diagnóstico la pide; si solo presenta el SIRE, no se le pide
ninguna cuenta. La cuenta sale de donde ya sale: manda la imputación del comprobante, lo que no traiga sale de las
cuentas por defecto del entorno, y si tampoco hay, el diagnóstico se la pide al contador.

**Legacy y neutral son excluyentes** (decisión de John, 15-sep-2026): si hay sistema contable, el asiento sale en su
estructura y no hace falta el neutral.

### El botón «Generar asientos»

Para quien eligió **sin software contable**, donde otros descargan el Excel que alimenta a su legacy va un botón que
dice **Generar asientos**. No exporta a nadie: arma el asiento y lo entrega. Es el mismo asiento de CONCAR, más
limpio. Este es el archivo que produce, generado por el motor para la compra del ejemplo de la sección 7:

```json
{
 "open_accounting": "0.3",
 "libro": { "ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC",
            "periodo": "202601", "tipo": "compra" },
 "asiento": [
  { "cuenta": "6343001", "debe_haber": "D", "importe": "10000.00", "rol": "principal",
    "fecha": "2026-01-15", "moneda": "PEN", "centro_costo": "OBRA01", "tasa_igv": "18",
    "glosa": "SERVICIO DE MANTENIMIENTO ENERO 2026",
    "documento": { "tipo_cp": "01", "serie_numero": "F001-123",
                   "fecha_emision": "2026-01-15", "fecha_vencimiento": "2026-02-14" } },

  { "cuenta": "401111", "debe_haber": "D", "importe": "1800.00", "rol": "igv",
    "glosa": "IGV - SERVICIO DE MANTENIMIENTO ENERO 2026", "documento": "el mismo" },

  { "cuenta": "421201", "debe_haber": "H", "importe": "11800.00", "rol": "tercero",
    "contraparte_doc": "20131312955", "anexo_auxiliar": "OBRA01", "documento": "el mismo" },

  { "cuenta": "421201", "debe_haber": "D", "importe": "1416.00", "rol": "detraccion_tercero",
    "contraparte_doc": "20131312955", "anexo_auxiliar": "OBRA01", "documento": "el mismo" },

  { "cuenta": "421203", "debe_haber": "H", "importe": "1416.00", "rol": "detraccion",
    "glosa": "DETRACCION - SERVICIO DE MANTENIMIENTO ENERO 2026",
    "contraparte_doc": "20131312955",
    "detraccion": { "codigo": "037", "tasa": "12", "base": "11800.00" },
    "documento": { "tipo_cp": "01", "serie_numero": "F001-123",
                   "fecha_emision": "2026-01-15", "fecha_vencimiento": "2026-02-14" } }
 ]
}
```

El archivo se llama `open_accounting_20601234567_202601_compra.json`, y lleva **el libro y el asiento, no los
comprobantes**: quien pulsa el botón ya los tiene.

### En qué es «más limpio» que CONCAR

Las dos salidas dan **las mismas cinco líneas, los mismos roles, las mismas cuentas y los mismos importes**. La
diferencia es lo que el perfil de CONCAR añade porque su sistema lo pide:

| | CONCAR | Neutral |
|---|---|---|
| `sub_diario` | `"10"` | — |
| `correlativo` | `"010001"` | — |
| La sigla del documento | `documento.tipo: "FT"` | — (solo `tipo_cp: "01"`, el código de SUNAT) |
| La línea de la detracción | Cuelga de un documento comodín: `tipo "DR"`, `serie_numero "9999999999"` | Cuelga **del propio comprobante**: `F001-123` |
| El código de la detracción | `037` más `codigo_interno: "03701"` | Solo `037`, el de SUNAT |

Tres campos menos y dos invenciones menos —el documento comodín y el código interno—, y con ellos se va todo el
vocabulario que solo significa algo dentro de un sistema. Lo que queda es lo que cualquier contabilidad entiende.

---

## 10 · Qué queda fuera, a propósito

- **Las líneas de detalle por ítem.** Un `Item` o un `InvoiceLine` sería un modelo propio, ya descartado, y el
  registro de compras y ventas de SUNAT no lo pide. Quien reparte el gasto entre cuentas usa `reparto`; quien quiera
  el detalle lo transporta en `datos_originales`.
- **El impuesto por línea de detalle y el indicador de precios con impuesto** (`LineAmountTypes`,
  `pricesIncludeTax`). Sin ítems no tienen dónde ir, y el IGV nunca se delega al destino: va explícito, con su tasa.
- **Un cuerpo propio de la API.** Fue el primer borrador y duró lo que tardó la primera lectura: un formato que solo
  existe dentro de una petición no se puede guardar, ni mandar, ni comprobar sin servidor. La sección 7 lo cuenta.
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

## 11 · Qué va al estándar, qué va al motor, y qué no va a ninguno de los dos

**El criterio.** Al **estándar** va lo que dos sistemas necesitan para entenderse sin haber hablado nunca entre
ellos. Al **motor** va lo que se calcula a partir de eso. Un dato que se puede derivar no entra al estándar, y una
regla que cambia según el sistema de destino no entra al núcleo: vive en la configuración de su driver.

### Al estándar, `open-accounting`

| Qué | Por qué | Cuándo |
|---|---|---|
| **`imputaciones` en la raíz**, con llave por `id_externo` | Sin ellas el archivo no explica su propio asiento, y el estándar promete que un documento «se entiende solo, en cualquier máquina, sin consultar nada» | Ahora. Aditivo |
| **La regla de hasta dónde viaja cada bloque** | `libro` y `comprobantes` son hechos y valen en todas partes; `imputaciones` y `asiento` están en el plan de cuentas de quien los escribió y son **informativos fuera de él**. Sin esa regla, un ERP copia cuentas ajenas en silencio. `emisor` ya dice de quién son | Ahora. Es texto, no esquema |
| `dimensiones`, `medio_pago`, `retencion_igv`, `percepcion`, `no_domiciliado` | Son hechos, y les falta el caso real que manda la regla del proyecto | Con su caso (E1) |
| Honorarios y cheques | **Honorarios no pide nada**: su «asiento de honorarios» aquí es una compra con `retencion`. Cheques sí es otro hecho —un pago, no un comprobante— y sería otro libro | Cheques, cuando haya caso |
| Una ficha de proveedor o cliente | **Nunca.** Es un maestro, no un hecho. El RUC viaja embebido en el comprobante, que es justo lo que le ahorra a este estándar la ruta de anexos que STARSOFT necesita | — |

### Al motor, `contaperu`

| Qué | Por qué |
|---|---|
| **Aceptar `imputaciones` dentro del documento**, sin dejar de aceptar el argumento de hoy | Es la pieza que hace real el formato único, y nadie que ya integre tiene que cambiar |
| **Una batería de conformidad**: casos de entrada con su documento esperado | Es lo que le permite a un ERP de fuera comprobar que emite bien sin escribirle a nadie. Hoy hay `diagnosticar` y `verificar-driver`; falta el juego de casos |
| **Renombrar el driver a `asiento_neutral`** | Hoy se llama igual que el estándar. Es gratis mientras siga sin publicar, y rompe a quien lo integre si se hace después de la 1.1.0 (sección 12) |
| **Nada para el correlativo** | Ya está todo: numera en el orden recibido, devuelve los rangos, los anuncia en `diagnosticar`, lo excluye de la huella y lo omite en el asiento neutral. Lo que faltaba era decir que la unidad es el mes (sección 12) |
| **No tener bandeja.** El motor recibe, responde y olvida | Depositar y esperar aprobación es del ERP, que es quien tiene usuarios y base de datos. Copiar la bandeja aquí le daría estado al motor, que es lo único que no puede tener |
| **Diagnosticar contra los destinos que el entorno declaró**, no contra el driver de esa llamada | Es lo que hace que «generar asientos» vuelva obligatoria la cuenta contable, y que quien tiene SIRE y CONCAR reciba una sola respuesta en vez de dos (sección 9) |
| **No salir a la red.** Ni descargar del SIRE, ni llamar a otro sistema | Misma razón, y ya está escrito en la hoja de ruta |

### A ninguno de los dos

- **El vocabulario legacy** —`subdiario`, la sigla del documento, `destino_Compra`—: vive en la configuración del
  driver que lo necesita, que es donde ya está. Ni el estándar ni el núcleo lo conocen.
- **Autenticación, permisos, IP pública, licencias.** Eso es de quien publique una puerta, no del formato.
- **La ficha del anexo, el detalle por ítem y los ids internos de nadie.**

**Y lo que pide del esquema es una sola cosa, aditiva.** Hoy la raíz admite cinco claves —`open_accounting`,
`libro`, `comprobantes`, `asiento` y `emisor`— y rechaza cualquier otra, así que `imputaciones` hay que añadirla ahí.
Un campo opcional nuevo **no sube la versión**: avanza el tag `open-accounting-0.3` y quien ya escribe 0.3 sigue
valiendo.

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

## 12 · Lo que falta decidir

**Resueltas por el formato único** —las cuatro se caían solas en cuanto el cuerpo dejó de ser un envoltorio:

| Antes era una decisión | Cómo queda |
|---|---|
| Si el periodo se deriva de la fecha | No se deriva: el libro lo trae. Las tres validaciones de plazo siguen vivas |
| Quién numera cuando llega un comprobante suelto | Lo mismo que hoy: un documento de uno se numera como uno de mil |
| Que las dos puertas no se separen | No hay dos puertas: hay un documento y un pipeline |
| El freno de la ruta por comprobante | El tope de comprobantes del lote ya lo cubre |

### El correlativo: la unidad de numeración es el mes, no el lote

Era la que quedaba, y resulta ser doctrina y no funcionalidad. **El correlativo es el número de voucher dentro del
sub-diario de un sistema legacy** (`MMNNNN`: mes y cuatro dígitos). Tres hechos lo acotan:

- **Solo existe para destinos legacy.** El asiento neutral no lleva correlativo ni sub-diario, así que para quien no
  tiene software contable la pregunta ni se plantea.
- **No es identidad.** Un comprobante es su RUC, libro, tipo, serie, número y contraparte. El correlativo no entra.
- **Y el motor ya decidió que no cuenta:** la huella de una exportación se calcula **excluyéndolo**, con este
  comentario en el código —«la misma exportación, repetida tras un *deshacer*, arranca en otro correlativo»—. El
  correlativo es una etiqueta del destino, no un dato del hecho.

**El choque que se temía no es del motor: es de mandarle un lote donde va un mes.** Si se exportan 20 facturas salen
0001–0020; si la semana siguiente se exportan solo 5, vuelven a salir 0001–0005 y chocan. Pero en contabilidad el
número de voucher pertenece **al libro del mes**, no a la tanda en que alguien subió los archivos — y el documento
del estándar ya *es* un mes: `libro` es RUC, periodo y tipo.

De ahí los dos modos, que son exactamente los dos flujos de la sección 9:

| | **Mes completo** (por defecto) | **Por tandas** |
|---|---|---|
| Cuándo | El contador cierra el mes y exporta | El ERP alimenta a su legacy a diario o semanal |
| Qué manda | **Todos los comprobantes del mes** | Solo los nuevos |
| Desde qué número | Desde 1 | Desde donde el ERP le diga, en `correlativos` |
| Quién lleva la cuenta | **Nadie** | El ERP: guarda el rango que el motor devuelve y lo manda en la siguiente |

**En el modo del mes completo nadie guarda estado.** Mandando siempre el mes entero y en un orden fijo —fecha, serie,
número—, el mismo mes da siempre los mismos números, aunque el usuario haya cargado las facturas en cualquier orden:
el número no depende de cómo se subieron, sino de qué mes es.

**Y cada comprobante tiene su propio número**, no hay uno por lote; lo único que dependía del lote era desde dónde se
empezaba a contar.

Nada de esto pide código: el motor ya numera en el orden recibido, ya devuelve los rangos usados, ya los anuncia en
`diagnosticar` antes de generar nada, ya excluye el correlativo de la huella y ya lo omite en el asiento neutral. Lo
que faltaba era decir **cuál es la unidad**, y que el ancla para casar lo exportado con la base del ERP es el
`id_externo` y la huella — nunca el número de voucher.

### Los dos nombres, decididos (John, 15-sep-2026)

Se eligieron con cuatro criterios: que no sean vocabulario de ningún sistema —ni CONCAR, ni SAP, ni SUNAT—, que
estén en español como el resto de claves del estándar, que no choquen con algo que ya se llame así, y que un ERP no
peruano los entienda sin glosario. Los dos candidatos más obvios se caían por choque: **`cuentas`** a secas, porque
la configuración ya tiene una sección `cuentas` con las cuentas por defecto del entorno, y **`asiento`** a secas para
el driver, porque es una clave raíz del estándar.

| | Decisión | Por qué |
|---|---|---|
| El bloque de las cuentas por comprobante | **`imputaciones`**, se queda | Es la palabra que el motor ya usa y no es invento local: SAP en español llama «imputación» exactamente a esto. Un contador la entiende sin explicación |
| El driver, hoy `open_accounting` | **`asiento_neutral`** | Dice qué produce y con qué vocabulario, y no reproduce la confusión de llamarse igual que el estándar. Hay precedente de nombrar un driver por su salida y no por un sistema: `csv` tampoco nombra un destino |

**El renombrado es gratis ahora y caro después.** El driver está en «Sin publicar»: nadie lo usa todavía. Cuando salga
la 1.1.0, cambiarlo rompe a quien lo haya integrado. Y no toca el estándar: `open-accounting.schema.json` solo usa
`open_accounting` como clave del documento, que no cambia.

Lo que cambia cuando se aplique: el módulo `contaperu/drivers/open_accounting/` → `.../asiento_neutral/`, el valor
`driver="asiento_neutral"`, el formato `asiento_neutral_json`, el nombre del archivo que se descarga y la superficie
pública congelada. Son 89 apariciones del driver en 31 archivos —la mayoría tests y fixtures—, que hay que distinguir
de las 36 del estándar, que se quedan.

**Abiertas:**

1. **Rechazar la clave desconocida** endurece la API para quien hoy, desde Python, manda campos de más.
2. **Si `imputaciones` viaja también de vuelta**, en la respuesta y en la salida del driver neutral: quien recibe el
   documento podría querer saber con qué cuentas se armó el asiento que lleva al lado.
3. **Si el archivo del botón lleva también los comprobantes.** Hoy sale con `libro` y `asiento`, porque quien lo pide
   ya tiene los hechos. Un ERP de fuera que reciba ese archivo sí querría los dos, y entonces el archivo pasa a ser
   un documento completo del estándar en vez de solo el asiento.

---

## 13 · Fuentes

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
