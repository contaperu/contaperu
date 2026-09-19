# API de registro: cómo se manda un comprobante, y el JSON que sirve para cualquier ERP

[REFERENCIAS.md](REFERENCIAS.md) miró el **asiento**: cómo modelan un `JournalEntry` QuickBooks, Xero y las APIs
unificadas. Este documento mira el escalón de antes, el **registro de un comprobante**: qué manda un sistema cuando
dice «anota esta compra», «anota esta venta» o «anota este recibo por honorarios», y qué forma tiene que tener ese
JSON para que le sirva a cualquier ERP y no a uno solo. Termina con un borrador concreto para el motor.

**De dónde sale.** De la guía de uso de las API contables de STARSOFT Gold Edition, que registra por tipo de asiento
—compras, ventas, honorarios, cheques, estándar— y es hoy la forma más cercana a un «registro por API» que tiene un
ERP peruano instalado. Sirve de punto de partida, no de modelo a copiar.

**Estado: investigación y borrador.** Nada de lo que aquí se propone está en la librería 1.0.0 ni en
`open-accounting` 0.3. El proyecto crece con la misma regla de siempre: el estándar se mueve con casos reales
detrás, no por si acaso.

**Y esto propone una `0.4`.** La mayor parte son campos opcionales que un consumidor de hoy ignora sin romperse,
pero dos piezas sí suben la versión, y a propósito: **`clase` en cada línea** y **el `rol` convertido en catálogo
publicado**, que son las que dejan el asiento listo para cualquier ERP y para los roles que todavía no existen («El
papel de cada línea»). El resumen de qué entra en cuál está al final, en «Qué va al estándar, qué va al motor».

**Alcance.** Compras y ventas, **con los recibos por honorarios dentro del libro de compras**, como están hoy
(decisión de John, 18-sep-2026; el porqué, en «Por qué no hay un libro de honorarios»). Cheques, asientos estándar y
anexos quedan fuera: cada uno es otro hecho contable y entra cuando tenga su caso.

**Cómo está ordenado.** Cuatro bloques, y cada uno se puede leer solo:

| | Secciones | Qué contesta |
|---|---|---|
| **De dónde sale** | 1 a 5 | Cómo lo resuelve el mundo, y qué es lo que el mundo no tiene |
| **La propuesta** | 6 a 11 | Qué hay hoy, cuál es el formato, cómo se ve en cuatro casos, por qué los libros son dos, qué dice cada línea del asiento y por qué el comprobante y el asiento son bloques distintos |
| **Cómo funciona** | 12 y 13 | Dónde corre el motor, en qué orden, y a dónde va cada salida |
| **Los límites y lo que queda** | 14 a 17 | Qué se deja fuera a propósito, qué toca a cada pieza, qué se decidió y qué no |
| **Cómo se construye** | 18 | Las partes en orden, sus tests y los documentos que hay que actualizar |

**Convenciones.** Los RUC de los ejemplos son los seguros del proyecto (`20131312955` y `20601234567`); ninguna
empresa real aparece aquí. Los importes van en texto y las fechas en `AAAA-MM-DD`, como manda el estándar. Lo que no
se pudo confirmar en la documentación oficial va marcado *no verificado*. Investigación hecha el **15 y el 16 de
septiembre de 2026**; las fuentes, consultadas el 15, al final.

---

## En una página

**El problema.** Cada ERP peruano recibe los asientos en su propio formato: STARSOFT pide una lista de líneas con la
cabecera repetida y vocabulario de CONCAR, el Excel de CONCAR pide sus 41 columnas, CONTASIS las suyas. Quien integra
tres sistemas escribe tres veces lo mismo.

**La propuesta.** Que el cuerpo de la llamada **sea el documento `open-accounting`**, el mismo archivo que se guarda,
se manda y se archiva, con cuatro bloques:

| Bloque | Qué lleva | Quién lo decide |
|---|---|---|
| `libro` | RUC, mes y qué registro es | El contribuyente |
| `comprobantes[]` | Los hechos: lo que dice cada factura, con las casillas de SUNAT y **sin cuentas** | SUNAT y el proveedor |
| `imputaciones{}` | La decisión contable de cada comprobante, por su `id_externo` | El usuario, en su ERP |
| `asiento[]` | El efecto: las líneas que cuadran, cada una con su `rol` y su `clase` | El motor, que lo **deriva** |

**Los cinco cambios que propone**, y su costo:

| Cambio | Por qué | Versión |
|---|---|---|
| `imputaciones` en la raíz | Sin ellas el archivo no explica su propio asiento | Aditivo |
| `documento.id_externo` en la línea | El enlace exacto entre línea, comprobante e imputación, como `SourceID` en Xero | Aditivo |
| `clase` en cada línea (`activo`, `pasivo`, `patrimonio`, `ingreso`, `gasto`) | Es lo único que un ERP de fuera entiende sin conocer el PCGE | **0.4** |
| `rol` y `libro.tipo` como catálogos publicados | Para que un rol o un libro nuevo no cueste una versión | **0.4** |
| El centro de costo en todas las líneas | El IGV y la detracción son de la misma obra que el gasto | Es decir la regla |

**Lo que no cambia:** el comprobante sigue siendo el de SUNAT y sin cuentas; los importes van en texto; `debe_haber`
explícito; la detracción en dos tiempos; y los recibos por honorarios se quedan en el libro de compras.

**Y la regla que lo hace escalable:** quien recibe tiene que poder contabilizar una línea con `clase`, `debe_haber` e
`importe` aunque no conozca su `rol`. Con eso, lo que venga después —la percepción, el anticipo, el banco— entra como
valor de catálogo o como bloque nuevo, sin volver a subir la versión.

---

## 0 · Tres cosas antes de empezar, porque el nombre engaña

1. **«Registrar» aquí no es guardar.** El motor no tiene estado, ni disco, ni red: recibe un documento y devuelve el
   diagnóstico y el asiento. Quien guarda es el sistema que llamó. Esto se llama registro porque es el momento del
   dominio —«anota esta compra»—, no porque el motor anote nada en ninguna parte.
2. **Quien tiene la librería no necesita esta API.** Un ERP en Python llama a `contaperu.api` dentro de su propio
   proceso, sin puerto y sin latencia. La puerta HTTP es para el que está en otro lenguaje o en otro servidor, y la
   levanta él. Existe además un MCP abierto en producción, pero **nadie está obligado a pasar por una URL ajena**:
   es una puerta que alguien corre, no un servicio del que dependa el cierre de mes de otro.
3. **El formato es uno solo, y ya existe.** Es `open-accounting`. Este documento no propone un JSON nuevo al lado del
   estándar: propone que **el estándar sea también el cuerpo de la llamada**. «El formato: uno solo, el del estándar» cuenta por qué el primer
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
6. **Su ruta de honorarios apunta a algo real.** `RegistrarAsientoHonorarios` existe aparte porque un recibo por
   honorarios no se parece a una compra: no lleva IGV, trae una retención y no entra al registro de compras de
   SUNAT. Pero eso no lo convierte en otro libro tributario: es una división **del destino**, y ahí es donde vive
   —el sub-diario `15` de CONCAR, la ruta propia de STARSOFT—. El porqué, en «Por qué no hay un libro de
   honorarios».

### Qué no se toma, y por qué

- **La cabecera repetida en cada línea.** Es la herencia del archivo plano: treinta campos duplicados por línea,
  donde una copia que se desincroniza es un asiento descuadrado. El documento va una vez y las líneas cuelgan de él.
- **El vocabulario de un sistema.** `subdiario`, `tipo_Anexo`, `tipo_Doc: "FT"`, `destino_Compra`, `conversion_Tc`
  son CONCAR y son STARSOFT, no SUNAT. Quien integre tres ERP tendría que aprender tres vocabularios; por eso el
  motor tiene desde la 1.1 un vocabulario neutral y el driver `asiento_neutral` (ver `ARQUITECTURA.md`).
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
a la cuenta de detracciones. Se ven generadas en «El recorrido, visto desde el ERP que ya tiene el dato».

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
| Dos recursos | `libro.tipo: compra \| venta`, los dos libros que define SUNAT. Los honorarios van en compras, y qué registro los lleva lo decide cada destino |
| Cuenta en la línea | La línea de diario la lleva; el comprobante nunca, y la decisión viaja en `imputaciones`, por `id_externo` |
| Impuesto explícito | `base_gravada` e `igv` siempre netos, `tasa_igv` leída del documento, y la línea con `rol: igv` |
| Moneda y T.C. | `moneda`, `tipo_cambio`. **Un comprobante en dólares sin tipo de cambio se observa con `TC_FALTA`, nivel error**: SUNAT lo exige, y el motor no lo inventa ni lo delega al destino |
| Cada casilla del registro | `base_gravada`, `igv`, `exonerado`, `inafecto`, `exportacion`, `isc`, `base_ivap`, `ivap`, `icbper`, `otros`, cada una con su importe. Son las columnas que SUNAT distingue, y el motor comprueba que sumen el total |
| Los dos números | `serie` + `numero` del emisor; `id_externo` del sistema que registra |
| Contraparte | `contraparte_tipo_doc`, `contraparte_doc`, `contraparte_nombre`: el modelo de los estándares abiertos |
| Estado inicial (borrador o contabilizado) | **No lo tiene, y es a propósito.** `estado` del comprobante es `ok`/`observada`/`duplicada` —validación, no ciclo de vida— y el de la línea es nombre reservado. Borrador o contabilizado es del sistema que guarda, y el motor no guarda («Qué queda fuera, a propósito») |
| Idempotencia | La identidad del comprobante y la huella de `_exportacion` |
| Dimensiones | `centro_costo` y `anexo_auxiliar`; `dimensiones` es nombre reservado |
| Nota de crédito | `tipo_cp: 07` con `ref_tipo_cp`, `ref_serie`, `ref_numero`, `ref_fecha` |
| Retenciones | `retencion` (renta de 4ta) y el bloque `detraccion` de dos tiempos: lo que no tiene nadie más |

**Por eso el JSON universal no es un modelo nuevo.** `REFERENCIAS.md` ya descartó inventar `Invoice`, `Bill` o
`Contact` propios, y el motivo sigue valiendo: en el Perú ese modelo lo define SUNAT, y el comprobante del estándar
son los campos de la Tabla 10 y del SIRE. Lo que falta no son campos: es que **la imputación quepa en el mismo
archivo**, y que la llamada no invente una segunda forma de decir lo que el documento ya dice.

**Casi todo lo que este documento propone cabe en la 0.3**, como campo opcional: el tag de la 0.3 avanza y nadie que
ya escriba documentos cambia nada. Las dos excepciones son `clase` y el `rol` como catálogo, que suben a la 0.4 («El
papel de cada línea»).

---

## 7 · El formato: uno solo, el del estándar

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
`type: ACCOUNTS_PAYABLE | ACCOUNTS_RECEIVABLE`, los dos dentro del cuerpo («Cómo registra un comprobante cada API de EE. UU.»).

### Campo por campo

**Dentro del documento** —lo que es contabilidad, y por tanto se guarda, se manda y se archiva:

| Nombre | De dónde sale | Oblig. | Por qué |
|---|---|---|---|
| `open_accounting` | 0.3 | sí | La versión del estándar con que se escribió |
| `libro.ruc` | 0.3 | sí | Sin RUC no hay libro |
| `libro.razon_social` | 0.3 | no | Informativo; algún driver la escribe |
| `libro.periodo` | 0.3 | sí | `AAAAMM`. Se exige siempre: derivarlo apagaría tres validaciones de plazo |
| `libro.tipo` | 0.3 | sí | `compra` o `venta`, los dos libros de SUNAT. Es el discriminador de Xero y Merge, y evita rutas por tipo. En la 0.4 se valida contra su catálogo, para que un registro nuevo no cueste una versión |
| `comprobantes[]` | 0.3 y SUNAT | sí | El modelo ya existe y lo define SUNAT: uno o los del mes |
| `contraparte_*` | 0.3, Tabla 1 | según el caso | Planos, con el RUC: el modelo de EN 16931, no un `Contact` propio |
| `detraccion` | 0.3 | no | Entra `PROVISIONADO`; la constancia llega después |
| `imputaciones{}` | **nuevo**, por `id_externo` | no | `cuenta_contable`, `centro_costo`, `cuenta_tercero` y `reparto[]`, lo que hoy es un argumento de la llamada |
| `asiento[]` | 0.3 | no | Para el ERP que ya lo armó. En la 0.4 cada línea lleva `clase` y enlaza con su comprobante por `documento.id_externo` («El papel de cada línea») |
| `emisor` | 0.3 | no | Qué software produjo el dato |

**Fuera del documento**, en la llamada: no describen la contabilidad sino qué hacer con ella, y el mismo archivo
tiene que servir para destinos distintos.

| Nombre | Qué decide |
|---|---|
| `driver` | El destino: `sire`, `concar`, `contasis`, `asiento_neutral`… Sin destino, la respuesta es el diagnóstico |
| `configuracion` | Lo del sistema de destino y lo general del contribuyente |
| `correlativos` | Desde qué número sigue cada sub-diario |
| `claves_previas` | Lo anotado en periodos anteriores, para reconocer el duplicado |
| `incluir_observados`, `fecha` | Qué entra al archivo y con qué fecha se escribe |

### Qué campos se usan y cuáles no: la ausencia es la respuesta

Un comprobante admite **46 campos y solo exige tres**: `tipo_cp`, `fecha_emision` y `total`. Todo lo demás es
opcional, y la regla es la misma para todos: **un campo está o no está, y si no está, ese hecho no ocurrió.** No hay
booleanos de presencia, ni ceros de relleno, ni cadenas vacías obligatorias.

Es la diferencia de fondo con la API de «El caso que lo motiva», donde cada línea manda `detraccion: false` más cinco campos
vacíos por si acaso. Probado contra el esquema:

| Lo que mandas | Resultado |
|---|---|
| Solo los tres obligatorios | **Valida** |
| Con el bloque `detraccion` | **Valida** |
| Sin `detraccion`, la clave omitida | **Valida** |
| `"detraccion": null` | **Valida** |
| `"detraccion": false` | **Rechazado**: `false` no es un objeto de detracción |
| `cod_Detraccion: ""`, `tasa_Detraccion: 0` de relleno | **Rechazado**: «Additional properties are not allowed» |
| `"subdiario": "10"` | **Rechazado**: es vocabulario de un sistema, no un hecho |

Lo sostiene `additionalProperties: false` en la raíz, en el comprobante y en la detracción: **una clave que el
estándar no conoce se rechaza en vez de ignorarse**, y quien se equivoca de nombre se entera en la primera llamada.
La válvula para lo que el motor no entiende es `datos_originales`, que se transporta sin interpretar.

Y ausencia no es lo mismo que silencio del validador: **los importes que sí están tienen que cuadrar.** El motor
comprueba que el total sea la suma de las casillas —por eso un recibo por honorarios con el importe en
`base_gravada` en vez de en `inafecto` sale observado con `TOTAL_NO_CUADRA`—, y que una factura en dólares traiga su
tipo de cambio, o la para con `TC_FALTA`.

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

---

## 8 · Cuatro ejemplos, uno por caso

Cada uno enseña algo distinto del formato, y los cuatro salen del motor: el JSON se valida contra el esquema —salvo
el bloque `imputaciones`, que es lo que este documento propone añadirle— y el asiento que se muestra es el que
devuelve de verdad, hoy, con la imputación entregada como la entrega la 1.0.

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
(`contasis`) o el documento neutral para otro ERP (`asiento_neutral`).

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

### Un recibo por honorarios: el que no lleva IGV y no va al SIRE

Vale la pena mirarlo porque rompe tres suposiciones a la vez: **no tiene IGV**, **trae una retención** y **no se
parece a una compra**, aunque viaje en el libro de compras. Van dos, uno con retención y otro sin ella:

> **El emisor de un recibo por honorarios es una persona natural**, con RUC que empieza en 10. Aquí va uno de los dos
> RUC seguros del proyecto, que empiezan en 20, porque en el repositorio no entra ningún documento de nadie: lo que
> el ejemplo enseña es la forma, no el identificador.

```json
{
  "open_accounting": "0.3",
  "libro": { "ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC",
             "periodo": "202601", "tipo": "compra" },
  "comprobantes": [
    {
      "tipo_cp": "02",
      "serie": "E001",
      "numero": "0000045",
      "fecha_emision": "2026-01-22",
      "contraparte_tipo_doc": "6",
      "contraparte_doc": "20131312955",
      "contraparte_nombre": "ASESORES DE PRUEBA SAC",
      "moneda": "PEN",
      "inafecto": "3000.00",
      "total": "3000.00",
      "retencion": "240.00",
      "concepto": "ASESORIA CONTABLE ENERO 2026",
      "origen": "xml",
      "id_externo": "rh-45"
    },
    {
      "tipo_cp": "02",
      "serie": "E001",
      "numero": "0000046",
      "fecha_emision": "2026-01-25",
      "contraparte_tipo_doc": "6",
      "contraparte_doc": "20131312955",
      "contraparte_nombre": "ASESORES DE PRUEBA SAC",
      "moneda": "PEN",
      "inafecto": "1200.00",
      "total": "1200.00",
      "concepto": "CAPACITACION",
      "origen": "xml",
      "id_externo": "rh-46"
    }
  ],
  "imputaciones": {
    "rh-45": { "cuenta_contable": "6321001", "centro_costo": "ADMIN" },
    "rh-46": { "cuenta_contable": "6321001", "centro_costo": "ADMIN" }
  }
}
```

**Cuatro cosas que enseña este ejemplo:**

1. **El importe va en `inafecto`, no en `base_gravada`.** Un recibo por honorarios no genera crédito fiscal: no hay
   base gravada ni IGV —esas claves ni siquiera aparecen, que es la misma regla de la ausencia— y el total es
   inafecto. No es un detalle de estilo: el motor comprueba que el total cuadre con base + IGV + no gravado + otros,
   y un recibo con el importe en la casilla equivocada sale observado con `TOTAL_NO_CUADRA` antes de llegar a ningún
   asiento.
2. **`retencion` aparece solo cuando el recibo la muestra.** En el segundo la clave sencillamente no está: no hay
   ningún `"retencion": 0` ni un booleano que diga que no hubo. Ausencia es respuesta.
3. **No va al SIRE, y lo sabe el destino, no el productor.** El registro de compras de SUNAT no admite recibos por
   honorarios, y eso está escrito una sola vez, en el driver: `FUERA_DEL_REGISTRO_SUNAT = {"02"}`
   (`contaperu/catalogos.py`). El ERP manda el mes de compras entero y cada destino toma lo suyo: el SIRE los deja
   fuera y CONCAR los lleva a su sub-diario `15`.
4. **La cuenta del tercero no es la de proveedores.** Un recibo por honorarios se debe por la cuenta de honorarios
   por pagar, no por la de facturas, y el motor lo sabe: el tipo `02` tiene tratamiento propio en el asiento.

El asiento que genera, real:

| `rol` | `cuenta` | | `importe` | |
|---|---|---|---|---|
| `principal` | 6321001 | D | 3000.00 | el gasto |
| `retencion_4ta` | 401721 | H | 240.00 | lo retenido, que se le paga a SUNAT |
| `tercero` | **424101** | H | 2760.00 | lo que se le debe al profesional: el neto |
| `principal` | 6321001 | D | 1200.00 | el segundo recibo, sin retención |
| `tercero` | **424101** | H | 1200.00 | aquí se le debe todo |

Tres líneas en el primero y dos en el segundo, sin que el documento haya tenido que decir en ninguna parte cuántas
líneas quería: salen de los hechos que trae.

Y queda la pregunta que este ejemplo levanta —si el libro correcto no debería ser «honorarios» en vez de «compra»—,
que resulta ser la mejor defensa de esta arquitectura. Está respondida en «Por qué no hay un libro de honorarios».

### Una factura en dólares, y una nota de crédito en soles

Los dos casos que más se equivocan, en un mismo documento. Son dos comprobantes independientes del mismo mes: la
factura en dólares, y una nota de crédito en soles que corrige **la compra del primer ejemplo** (`F001-123`), que se
anotó en ese mismo periodo. Una nota corrige el documento que dicen sus campos `ref_*`, esté o no en el mismo envío:

```json
{
  "open_accounting": "0.3",
  "libro": { "ruc": "20601234567", "periodo": "202601", "tipo": "compra" },
  "comprobantes": [
    {
      "tipo_cp": "01",
      "serie": "E001",
      "numero": "0000456",
      "fecha_emision": "2026-01-20",
      "contraparte_tipo_doc": "6",
      "contraparte_doc": "20131312955",
      "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC",
      "moneda": "USD",
      "tipo_cambio": "3.752",
      "base_gravada": "2000.00",
      "igv": "360.00",
      "total": "2360.00",
      "destino_igv": "DG",
      "concepto": "LICENCIAS DE SOFTWARE",
      "origen": "xml",
      "id_externo": "compra-456"
    },
    {
      "tipo_cp": "07",
      "serie": "FC01",
      "numero": "0000009",
      "fecha_emision": "2026-01-28",
      "contraparte_tipo_doc": "6",
      "contraparte_doc": "20131312955",
      "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC",
      "moneda": "PEN",
      "base_gravada": "1000.00",
      "igv": "180.00",
      "total": "1180.00",
      "destino_igv": "DG",
      "ref_tipo_cp": "01",
      "ref_serie": "F001",
      "ref_numero": "0000123",
      "ref_fecha": "2026-01-15",
      "concepto": "DESCUENTO POR SERVICIO NO PRESTADO",
      "origen": "xml",
      "id_externo": "nc-9"
    }
  ],
  "imputaciones": {
    "compra-456": { "cuenta_contable": "6591001", "centro_costo": "SISTEMAS" },
    "nc-9":       { "cuenta_contable": "6343001", "centro_costo": "OBRA01" }
  }
}
```

**La moneda extranjera.** Los importes van **en dólares, como los dice el comprobante**, y el `tipo_cambio` viaja
al lado: el motor lo arrastra a cada línea del asiento y deja la conversión a quien la necesite. **Si falta, no se
inventa ni se delega:** el comprobante se observa con `TC_FALTA`, nivel error, porque SUNAT lo exige. Un mes con una
factura en dólares sin tipo de cambio no exporta.

**La nota de crédito.** Es un comprobante más, con `tipo_cp: "07"` y los cuatro `ref_*` que dicen a qué factura
corrige — no un recurso aparte, como en QuickBooks o Xero. Va en la moneda en que se emitió, que no tiene por qué ser
la de la factura que corrige. Y **sus importes van en positivo**: el signo lo pone el driver. Se ve en el asiento que
sale, con los sentidos invertidos frente a una compra normal:

| `rol` | `cuenta` | | `importe` | |
|---|---|---|---|---|
| `principal` | 6591001 | D | 2000.00 | USD, con `tipo_cambio` 3.752 en cada línea |
| `igv` | 401111 | D | 360.00 | USD |
| `tercero` | 421202 | H | 2360.00 | USD — y la cuenta del tercero es la de moneda extranjera, no la de soles |
| `principal` | 6343001 | **H** | 1000.00 | la nota de crédito revierte el gasto |
| `igv` | 401111 | **H** | 180.00 | y el IGV |
| `tercero` | 421201 | **D** | 1180.00 | y baja lo que se le debe al proveedor |

Fíjate en la cuenta del tercero: `421202` para la factura en dólares y `421201` para la nota en soles. **El motor
separa la cuenta por moneda sin que el documento se lo pida** — sale de la configuración del entorno, no del hecho.

---

## 9 · Por qué no hay un libro de honorarios

El tercer ejemplo levanta la pregunta que el resto del documento no podía responder sin salirse del tema: si un
recibo por honorarios no es una compra, ¿por qué se registra en el libro de compras?

### El libro de honorarios existe, pero vive en el destino

La objeción es razonable: en la contabilidad peruana los honorarios son **su propio registro**, no una compra más.
STARSOFT tiene su ruta aparte (`RegistrarAsientoHonorarios`) y su sub-diario propio, distinto del de compras.

**Y es cierto: ese libro existe. Lo que pasa es que vive en el destino, que es donde esa división significa algo.**
En la configuración de CONCAR el tipo `02` trae `sub_diario: "15"` y la boleta el `13`; el resto de compras va al
sub-diario general. Cada sistema legacy los numera a su manera —el de STARSOFT no es el de CONCAR—, y por eso es
configuración de su driver y no un dato del hecho.

De ahí sale el reparto, que es lo que hace eficiente a esta arquitectura:

| | Quién lo decide | Dónde vive |
|---|---|---|
| **Qué ocurrió** | El hecho: se adquirió un servicio y hay un comprobante que lo respalda | El documento: `libro.tipo: compra` |
| **En qué registro entra** | Cada destino, declarando qué lleva y qué no | El driver: `FUERA_DEL_REGISTRO_SUNAT`, el `sub_diario` por tipo |

**El SIRE no lleva honorarios porque el registro de SUNAT no los admite**, y eso está escrito una vez, en el motor:
`FUERA_DEL_REGISTRO_SUNAT = {"02"}` (`contaperu/catalogos.py`), que el driver del SIRE lee. No hace falta que el ERP
lo sepa, ni que lo clasifique al capturar, ni que acierte: manda el mes de compras entero y **cada destino toma lo
suyo**.

### Lo que costaría el tercer libro (decisión de John, 18-sep-2026)

Se evaluó añadir `honorario` como tercer valor de `libro.tipo`, y se descartó. Esto es lo que costaba:

- **Una versión que rompe.** El enum de `libro.tipo` es cerrado y cada driver llavea sus formatos por ese valor: un
  tercero sería una **0.4** con su enmienda, no un campo opcional —y por un valor de enum, no por algo que el
  formato necesite: la 0.4 que este documento sí propone se la gana `clase`, que le sirve a todos los libros.
- **Trabajo en cada driver.** CONCAR y CONTASIS tendrían que declarar el libro nuevo con su sub-diario, o el mes de
  honorarios no saldría por ahí.
- **Mover la decisión del destino al productor.** Hoy la clasificación la declara un driver en una línea; repartida,
  la tendrían que acertar todos los ERP que integren, cada uno por su cuenta, y un error ahí parte mal el mes.
- **Partir el mes en dos documentos**, con la pregunta inmediata de a cuál pertenece una nota de crédito que corrige
  un honorario.

El nombre lo dice, además: `libro` es el **libro tributario**, y SUNAT define dos —el registro de compras y el de
ventas—. El de honorarios es un libro contable, no tributario, y por eso aparece donde aparece la contabilidad: en
el asiento y en el sub-diario de cada sistema.

**Lo que queda pendiente, si algún día llega su caso:** un sistema real que exija un envío de honorarios aparte,
como la ruta propia de STARSOFT. Ese día el tercer libro entra con su archivo aceptado detrás, que es la regla del
proyecto.

---

## 10 · El papel de cada línea: `rol` y `clase`

Una compra son tres líneas —el gasto, el IGV y lo que se le debe al proveedor— y una venta otras tres —el ingreso,
el IGV y lo que el cliente debe—. El `rol` de la línea dice cuál es cuál. El problema es que hoy los roles
`principal` y `tercero` **solo significan algo si además se mira `libro.tipo`**: en una compra `principal` es el
gasto y `tercero` un pasivo; en una venta, el ingreso y un activo. Una línea suelta no se explica sola, y la que
recibe un ERP de fuera es exactamente eso: una línea suelta.

### Cómo lo resuelve el mundo

| Sistema | Dónde vive el papel de la línea | Campo y valores |
|---|---|---|
| **QuickBooks Online** | En la cuenta, y en la cabecera | `Classification` (`Asset`, `Liability`, `Equity`, `Revenue`, `Expense`), `AccountType` (16 fijos) y `AccountSubType` (~250, con `SalesTaxPayable`, `WithholdingTaxPurchases`). La cuenta por pagar y la por cobrar van en la **cabecera** (`apAccountRef`, `arAccountRef`), nunca en la línea |
| **Xero** | En la cuenta | `Type` (18), `Class` (5) y **`SystemAccount`**: `DEBTORS`, `CREDITORS`, `GST`, `ROUNDING`… Un puntero que dice qué cuenta cumple qué función |
| **NetSuite** | En la cuenta, con enum **inmutable** | «no puedes crear ni modificar tipos de cuenta»; lo demás, con cuentas generadas por el sistema |
| **Sage Intacct** | Fuera de la cuenta | Solo `ACCOUNTTYPE` (`balancesheet` / `incomestatement`) y `NORMALBALANCE`; el papel lo pone la configuración del módulo |
| **Merge · Rutter · Apideck** | En la cuenta | `classification` o `category`, con los **mismos cinco valores** en las tres |
| **XBRL GL** | **En la línea** | El único: `accountPurposeCode` (`{tax}`, `{ifrs}`, `{primary}`…) y `accountType` (`{account}`, `{vendor}`, `{customer}`) |
| **SAF-T (OCDE)** | En una tabla de mapeo | El plan del contribuyente se mapea a uno estándar (`StandardAccountID`), y el impuesto va en la línea (`TaxInformation`) |

**El patrón es que la cuenta manda y la línea obedece.** Ningún sistema comercial escribe «esta línea es el IGV»: lo
deduce del tipo de la cuenta que la línea referencia. La única excepción, en todos, es el impuesto, que sí viaja en
la línea.

### Por qué aquí no se puede copiar tal cual

En QuickBooks o en Xero, la línea y el plan de cuentas **viven en el mismo sistema**: por eso basta con mirar la
cuenta. El asiento neutral de ContaPerú **viaja a otro sistema, que no tiene ese plan de cuentas**: quien recibe
`6343001` no sabe que es un gasto, y no lo va a saber mirando el número.

Por eso el `rol` en la línea es la decisión correcta, y es lo que ningún otro estándar tiene. Lo que falta es que la
línea se explique sola.

### La propuesta: dos ejes

| Eje | Qué dice | Valores | Estabilidad |
|---|---|---|---|
| **`clase`** | Qué es la cuenta. **Se deriva** del primer dígito, así que se rellena y se valida sola | `activo`, `pasivo`, `patrimonio`, `ingreso`, `gasto` | **Congelado.** Son los cinco valores idénticos en QuickBooks, Xero, Merge y Rutter: cualquier ERP del mundo ya sabe qué hacer con ellos |
| **`rol`** | Qué papel cumple en la operación peruana | `principal`, `igv`, `retencion_4ta`, `tercero`, `detraccion_tercero`, `detraccion`… | **Catálogo publicado y versionado**, no un enum cerrado dentro del esquema: crece sin cambiar la versión del documento |

Los dos ejes son independientes, y es lo que hace que la misma línea se lea igual en compras y en ventas:

| Caso | Cuenta | `rol` | `clase` | `debe_haber` | Qué dice la línea |
|---|---|---|---|---|---|
| Compra · el gasto | `6343001` | `principal` | `gasto` | D | un gasto |
| Compra · la mercadería | `201101` | `principal` | **`activo`** | D | existencias: **no es un gasto** |
| Compra · el IGV | `401111` | `igv` | `pasivo` | D | reduce el tributo por pagar: el crédito fiscal |
| Compra · el proveedor | `421201` | `tercero` | `pasivo` | H | se le debe |
| Venta · el ingreso | `701101` | `principal` | `ingreso` | H | un ingreso |
| Venta · el IGV | `401111` | `igv` | `pasivo` | H | aumenta el tributo por pagar: el débito fiscal |
| Venta · el cliente | `121201` | `tercero` | `activo` | D | nos deben |

Las dos líneas de IGV usan **la misma cuenta y la misma clase**, y lo que las distingue es el sentido: el crédito
fiscal reduce el tributo por pagar y el débito lo aumenta. Ninguna necesita llamarse `activo` para entenderse.

### La regla que lo sostiene

> **Quien recibe tiene que poder contabilizar una línea con `clase`, `debe_haber` e `importe`, aunque no conozca su
> `rol`.**

Es la regla de degradación, y es la que permite que el catálogo de roles crezca —la percepción, la retención del
IGV, el anticipo, el redondeo, la diferencia de cambio— **sin romper a ningún ERP ya integrado**: un rol desconocido
pierde detalle, no rompe el asiento. Es el mismo diseño de ISO 20022, que saca sus códigos a catálogos externos
«para añadir sin cambiar la versión del mensaje», y el camino que terminó tomando el SAF-T noruego, que sacó la
clasificación del esquema y la pasó a una tabla de mapeo.

### El asiento completo, con los dos ejes

Esta es la compra con detracción del primer ejemplo. Las cinco líneas, sus cuentas, sus sentidos y sus importes son
**los que el motor devuelve hoy**; lo que esta sección propone añadir es `clase`, el bloque `impuesto` y el
diccionario `plan_de_cuentas`:

```json
{
 "open_accounting": "0.4",
 "libro": { "ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC",
            "periodo": "202601", "tipo": "compra" },
 "asiento": [
  { "cuenta": "6343001", "clase": "gasto", "debe_haber": "D", "importe": "10000.00", "rol": "principal",
    "fecha": "2026-01-15", "moneda": "PEN", "centro_costo": "OBRA01", "tasa_igv": "18",
    "glosa": "SERVICIO DE MANTENIMIENTO ENERO 2026",
    "documento": { "tipo_cp": "01", "serie_numero": "F001-123",
                   "fecha_emision": "2026-01-15", "fecha_vencimiento": "2026-02-14" } },

  { "cuenta": "401111", "clase": "pasivo", "debe_haber": "D", "importe": "1800.00", "rol": "igv",
    "fecha": "2026-01-15", "moneda": "PEN", "tasa_igv": "18",
    "impuesto": { "codigo": "igv", "tasa": "18", "base": "10000.00" },
    "glosa": "IGV - SERVICIO DE MANTENIMIENTO ENERO 2026",
    "documento": { "…": "el mismo de arriba" } },

  { "cuenta": "421201", "clase": "pasivo", "debe_haber": "H", "importe": "11800.00", "rol": "tercero",
    "fecha": "2026-01-15", "moneda": "PEN",
    "contraparte_doc": "20131312955", "anexo_auxiliar": "OBRA01",
    "glosa": "SERVICIO DE MANTENIMIENTO ENERO 2026",
    "documento": { "…": "el mismo de arriba" } },

  { "cuenta": "421201", "clase": "pasivo", "debe_haber": "D", "importe": "1416.00", "rol": "detraccion_tercero",
    "fecha": "2026-01-15", "moneda": "PEN",
    "contraparte_doc": "20131312955", "anexo_auxiliar": "OBRA01",
    "glosa": "SERVICIO DE MANTENIMIENTO ENERO 2026",
    "documento": { "…": "el mismo de arriba" } },

  { "cuenta": "421203", "clase": "pasivo", "debe_haber": "H", "importe": "1416.00", "rol": "detraccion",
    "fecha": "2026-01-15", "moneda": "PEN", "contraparte_doc": "20131312955",
    "detraccion": { "codigo": "037", "tasa": "12", "base": "11800.00" },
    "glosa": "DETRACCION - SERVICIO DE MANTENIMIENTO ENERO 2026",
    "documento": { "…": "el mismo de arriba" } }
 ],
 "plan_de_cuentas": {
  "6343001": { "clase": "gasto",  "nombre": "Mantenimiento y reparaciones" },
  "401111":  { "clase": "pasivo", "nombre": "IGV - Cuenta propia", "elemento": "4" },
  "421201":  { "clase": "pasivo", "nombre": "Facturas por pagar" },
  "421203":  { "clase": "pasivo", "nombre": "Detracciones por pagar" }
 }
}
```

**Léelo desde el ERP que lo recibe.** Sin conocer el PCGE ni el plan del emisor sabe que la primera línea es un
gasto de 10 000, que la segunda reduce un tributo por pagar —un impuesto, lo dice su rol—, que se le deben 11 800 a un proveedor identificado por
su RUC, y que 1 416 de esa deuda se pagan al Banco de la Nación en vez de al proveedor. Y si mañana llega una línea
con `rol: "percepcion"`, que hoy no existe, la sigue contabilizando: es un `activo` al debe.

### Las tres piezas nuevas, y qué cuesta cada una

| Pieza | Qué es | Versión |
|---|---|---|
| **`clase` en cada línea** | Los cinco valores universales | **0.4**: pasa a ser obligatoria, para que ninguna línea quede sin explicarse |
| **`rol` como catálogo** | Sale del enum del esquema y pasa a un catálogo publicado, con su versión, junto a los catálogos de SUNAT. **Nace con los seis de hoy y ninguno más** | **0.4**: el esquema deja de rechazar un rol que todavía no existía |
| **`impuesto` y `plan_de_cuentas`** | El bloque de impuesto por línea —el único papel que todos los estándares ponen ahí— y el diccionario de cuentas del emisor | Opcionales: entran en la 0.4, o después con su caso |

### De dónde sale la `clase` (John, 18-sep-2026)

El primer borrador de esta sección decía que el motor la deduce **del rol y del libro**. No sirve, y se comprueba en
un caso diario: una **compra de mercadería** imputada a `201101` devuelve hoy `rol: principal`, y esa línea **no es
un gasto, es un activo**. Lo mismo una compra de activo fijo a `333101`. Deducirla del rol daría `gasto` en miles de
facturas al mes.

**La clase sale del primer dígito de la cuenta, sin excepciones** (John, 18-sep-2026). El PCGE clasifica por
elementos, y ese es el dato:

| Elemento del PCGE | `clase` |
|---|---|
| **1** disponible y exigible · **2** realizable · **3** inmovilizado | `activo` |
| **4** pasivo | `pasivo` |
| **5** patrimonio neto | `patrimonio` |
| **6** gastos por naturaleza · **9** costos por función | `gasto` |
| **7** ingresos | `ingreso` |
| **8** saldos intermediarios · **0** cuentas de orden | **ninguna** |

**El 9 mapea a `gasto`** porque muchas empresas imputan por destino y no por naturaleza, y esa línea es un gasto
igual. **El 8 y el 0 no encajan en ninguna clase, y no se fuerzan:** son de cierre y de control, el motor no las
emite desde compras ni ventas, y una imputación a ellas es casi seguro un error — así que **se observa con su
motivo**, como cualquier otra falta, en vez de inventarle una clase. Las cinco clases siguen siendo cinco, que es lo
que las hace universales.

**Y esto es todo lo que hace falta: ninguna línea necesita excepción.** Las cuentas que el motor pone por su cuenta
son de elemento 1, 4 o 7 —`1212` clientes, `4212` proveedores, `421203` detracción, `4241` honorarios, `401721`
retención, `701101` ventas—, y la única que elige el usuario es la del gasto, que es justo donde la regla vieja
fallaba.

**El IGV es el caso que lo prueba.** `401111` es elemento 4, así que su clase es `pasivo` — no `activo`, como decía
el primer borrador. Y es lo correcto: en el PCGE la 40 es una cuenta de pasivo y el crédito fiscal se anota **al
debe dentro de ella**; no existe una cuenta de activo. `clase: pasivo` con `debe_haber: D` dice exactamente «reduce
un pasivo», que es lo que pasa; `activo` al debe afirmaría «aumenta un activo», que es otra cosa. Lo que el ERP de
fuera necesita saber ya viaja igual: `rol: igv` dice que es impuesto y `debe_haber` dice el sentido.

Eso pide **una pieza que hoy no existe: el elemento de cada cuenta en el catálogo del PCGE**, que trae el código, el
nombre y su cuenta madre, pero no a qué elemento pertenece. Es un dato de la norma, no una opinión, así que entra
como los demás catálogos: con su fuente y su versión.

**Y aparece un control que antes no se podía hacer.** Al ser derivable, la clase no solo se rellena: **se valida**.
Un documento que llegue con `clase: gasto` en una cuenta `42` está mal, y el motor lo dice en vez de aceptarlo. Es
la misma idea que «el asiento es derivado»: lo que se puede recalcular se puede comprobar.

**Y por eso `clase` y `plan_de_cuentas` nunca se contradicen:** los dos leen el mismo plan. El diccionario dice qué
es cada cuenta y la línea repite la clase de la suya, para que quien reciba el asiento sin el diccionario siga
entendiéndolo.

**Y con eso el motor puede rellenar `clase` solo**: un documento 0.3 que llegue sin ella se completa al vuelo, así
que nadie tiene que reescribir lo que ya tiene guardado. El motor acepta las dos versiones durante toda la 1.x.

### Y lo mismo con `libro.tipo`: los tres niveles de cambio

`libro.tipo` tiene hoy el mismo problema que `rol`: es un enum cerrado de dos valores (`TIPOS_LIBRO`,
`contaperu/modelo.py`), así que **cualquier registro nuevo obligaría a subir la versión** — que es exactamente lo
que hizo caer el libro de honorarios. Conviene sacarlo al catálogo en la misma 0.4, porque después cada libro nuevo
sería otra versión.

Y hay que distinguir dos cosas que se confunden:

| Qué llega | Ejemplo | Cómo entra |
|---|---|---|
| **Otro registro del mismo hecho** | Un libro de honorarios, un registro simplificado | Un **valor nuevo en el catálogo** de tipos de libro. Cada driver declara en su `FORMATOS` qué libros lleva, y el que no lo declara nunca lo recibe |
| **Otro hecho** | Los movimientos del banco, los cheques | **Un bloque nuevo en la raíz**, como `movimientos[]`. Un movimiento bancario no tiene tipo de comprobante, ni serie, ni IGV: forzarlo como «tipo de libro» rompería a todo el que espera `comprobantes[]` |

Así lo hacen afuera: QuickBooks tiene un recurso por tipo de hecho —`Bill`, `Invoice`, `JournalEntry`, `Deposit`,
`Transfer`—, y Xero tiene `BankTransactions` aparte de `Invoices`. Un hecho nuevo es un recurso nuevo, no un valor
forzado en el enum de otro. Los códigos de tipo de documento de EN 16931 (`BT-3`: 380 factura, 381 nota de crédito)
viven en una **lista externa**, mantenida aparte de la norma, y los de ISO 20022 también, literalmente «para añadir
códigos sin impactar la versión de los mensajes».

De ahí sale la regla de versionado que este documento propone escribir en el estándar:

| Cambio | Ejemplo | ¿Sube la versión? |
|---|---|---|
| **Un valor nuevo en un catálogo** | Un rol `percepcion`; un libro `honorario` | **No.** Se publica el catálogo con su fecha, y quien no conoce el valor degrada con `clase` |
| **Un bloque opcional nuevo** | `movimientos[]` del banco; `plan_de_cuentas` | **No.** Quien no lo entiende lo ignora |
| **Cambiar lo que ya existe** | Volver obligatorio un campo, quitarlo, cambiar su significado | **Sí** |

Con esa regla, la 0.4 es la **última versión que hace falta por un buen tiempo**: después, los libros nuevos, los
roles nuevos y hasta el banco entran sin tocarla.

**Pero los dos catálogos no degradan igual, y conviene decirlo.** Un `rol` desconocido tiene red: la línea se
contabiliza con `clase`, `debe_haber` e `importe`. Un **`libro.tipo` desconocido no tiene ninguna**: quien recibe un
registro que no conoce no puede adivinar qué hacer con él. Su degradación es otra, y es la del destino: **el driver
que no declara ese libro en sus `FORMATOS` lo rechaza limpio**, diciendo qué libros lleva, en vez de intentar
escribirlo. Un valor de catálogo que nadie declara no es un error del documento: es un destino que no sirve para
ese libro.

### Lo que se descartó, y por qué

- **Renombrar los roles a `gasto`, `ingreso`, `por_pagar` y `por_cobrar`.** Se leería solo, pero rompe el enum para
  decir lo mismo con otro nombre, y cada caso nuevo volvería a romperlo. Xero resolvió los anticipos **añadiendo
  tipos de documento**, no renombrando tipos de cuenta.
- **Poner la cuenta por pagar en la cabecera**, como QuickBooks y Xero. Ellos pueden porque la cuenta vive en su
  mismo sistema; aquí el asiento viaja a otro.
- **Copiar los ~250 subtipos de QuickBooks.** Cada país fue añadiendo los suyos y el enum dejó de ser un estándar:
  es el camino del que no se vuelve.
- **Dejar la semántica solo en el plan de cuentas**, como hacen todos los ERP comerciales. Quien recibe el asiento no
  tiene ese plan; por eso `plan_de_cuentas` viaja como ayuda opcional y nunca como la única fuente.

---

## 11 · El comprobante y el asiento: por qué son dos bloques

Al leer un ejemplo parece que `comprobantes` y `asiento` dicen lo mismo dos veces: los dos traen el tipo de
comprobante, la serie y el número, las fechas y la moneda. No es así, y la diferencia es la que sostiene todo el
formato.

**El comprobante es el hecho; el asiento es su efecto sobre el plan de cuentas.** El asiento se regenera a partir
del comprobante, del plan de cuentas y de las reglas; el comprobante **no se puede reconstruir a partir del
asiento**. Por eso los dos se guardan, y por eso se enlazan.

### Cómo lo resuelve el mundo

| Quién | El documento | El asiento | El enlace |
|---|---|---|---|
| **Xero** | `/Invoices`: **se escribe** | `/Journals`: **solo lectura**, lo escribe su motor contable | `SourceID` + `SourceType` en cada asiento, con 24 valores (`ACCPAY`, `ACCREC`, `MANJOURNAL`…) |
| **QuickBooks Online** | `Bill` e `Invoice`, con vencimiento, términos de pago e ítems | `JournalEntry` guarda solo los asientos manuales y de ajuste; el efecto de una factura en el mayor se consulta por los reportes (`GeneralLedger`) | `LinkedTxn` entre documentos |
| **SAF-T (OCDE)** | `SourceDocuments`: facturas de venta, de compra y pagos | `GeneralLedgerEntries`: `Journal` → `Transaction` → `Line` | **Cruzado en los dos sentidos**: la línea lleva `SourceDocumentID` y la factura lleva `TransactionID` |
| **XBRL GL** | Los dos en el mismo árbol | `entryDetail`, con `documentType` y `entryType` | Del hecho al asiento, y del asiento al estado financiero |

Tres consecuencias que se repiten en todos:

1. **El asiento siempre tiene más líneas que el documento**, porque añade lo que la factura no dice: la cuenta de
   control del proveedor o del cliente, y la del impuesto.
2. **El documento tiene lo que el asiento nunca tendrá**: los ítems con cantidad y precio, el vencimiento, los
   términos de pago, el saldo pendiente y el archivo original. La norma de auditoría de EE. UU. lo dice como regla
   de evidencia: el documento original vale más que cualquier copia o conversión (PCAOB AS 1105).
3. **SAF-T exige los dos a la vez**, porque con solo el diario no se puede probar el impuesto por línea ni cruzar
   contra la facturación electrónica. En el Perú pasa igual: SUNAT pide el Libro Diario **y** el Registro de
   Compras.

### Dónde está la frontera aquí

De los 55 campos de los dos bloques, **solo cuatro están en los dos**:

| | Comprobante | Línea del asiento |
|---|---|---|
| **Campos propios** | **42**: las casillas del registro (`base_gravada`, `igv`, `exonerado`, `inafecto`, `exportacion`, `isc`, `icbper`, `total`…), la identificación (`tipo_cp`, `serie`, `numero`, `fecha_emision`), la contraparte con su nombre y su tipo de documento, la referencia de la nota, la DUA y la trazabilidad (`origen`, `confianza`, `id_externo`, `observaciones`) | **13**: `cuenta`, `debe_haber`, `importe`, `rol`, `clase`, `centro_costo`, `anexo_auxiliar`, `sub_diario`, `correlativo`, `glosa`, `tasa_igv`, y los bloques `documento` y `referencia` |
| **Compartidos** | `contraparte_doc`, `moneda`, `tipo_cambio`, `detraccion` | los mismos cuatro |

Y cada coincidencia tiene su motivo:

- **La moneda y el tipo de cambio se congelan en la línea** para que el asiento se pueda valorar sin volver al
  documento. Es lo que hace ERPNext, que guarda en cada apunte el tipo de cambio de la transacción.
- **El bloque `detraccion` no es el mismo en los dos lados.** En el comprobante es el hecho —código, porcentaje,
  monto, constancia y estado—; en la línea es lo que el destino necesita escribir: `codigo`, `codigo_interno`,
  `tasa` y `base`.
- **`contraparte_doc` se repite** porque un sistema que importa asientos necesita el anexo en la línea, sin leer el
  comprobante.

### Lo que parece copia y es el enlace

El bloque `documento` dentro de cada línea —`tipo_cp`, `serie_numero`, `fecha_emision`, `fecha_vencimiento`— no
duplica el comprobante: **es el enlace**, el mismo papel que cumplen `SourceID` y `SourceType` en Xero y
`SourceDocumentID` en SAF-T. Está ahí para que la línea viaje sola a un ERP que recibió el asiento y no los
comprobantes.

**Y ahí hay una mejora pendiente:** el enlace es por serie y número (`F001-123`), que es la identidad tributaria,
no la del sistema que registró. Xero enlaza por id y SAF-T por número de documento en los dos sentidos. Añadir
**`documento.id_externo`** en la línea cierra el círculo: con `imputaciones` llaveadas por `id_externo` y el asiento
apuntando al mismo id, el archivo se explica entero sin adivinar nada. Ya figura como propuesta en
`INTEROPERABILIDAD.md`, esperando su caso.

### Qué pasa cuando se fusionan los dos

- **Solo asientos** —el Excel de un legacy— pierde serie y número, el RUC de la contraparte, la fecha de emisión
  frente a la de registro, el vencimiento y la base por tipo de impuesto. Con eso no se genera el registro de
  compras ni se cruza contra la facturación electrónica.
- **Solo documentos** pierde todo lo que no tiene comprobante detrás: provisiones, depreciación, diferencia de
  cambio, reclasificaciones y ajustes de cierre.

Por eso el documento del estándar lleva los dos bloques, y **cada uno es opcional**: quien solo declara el SIRE
manda comprobantes sin asiento, y quien solo alimenta a su sistema contable puede recibir el asiento sin los
comprobantes.

### El asiento es derivado, y por eso la cuenta aparece dos veces

En el documento completo de más abajo, la cuenta `6343001` está en `imputaciones` y otra vez en el `asiento`. No es
una copia: es **la decisión y su efecto**.

| Bloque | Qué es | Quién lo pone | Cuántas cuentas trae |
|---|---|---|---|
| `imputaciones` | La decisión: «esta factura va a la 6343001, obra OBRA01» | El usuario, una vez por comprobante | **Una** |
| `asiento` | El efecto: las líneas que cuadran | El motor | **Cinco**, en este caso |

Las otras cuatro cuentas —el IGV, el proveedor y las dos de la detracción— **no están en la imputación**: salen de
la configuración de la empresa. Los dos bloques no son equivalentes y ninguno se deduce del otro. Es lo mismo que
hace Xero: la línea de la factura lleva su `AccountCode`, y el asiento que genera vuelve a llevarlo, más las cuentas
de control que la factura nunca menciona.

**De ahí sale la regla que falta escribir: el asiento es derivado.** Se obtiene del comprobante, más la imputación,
más la configuración, y siempre da lo mismo. Si un documento llega con los tres bloques y el asiento **no
corresponde** a los otros dos, el motor lo dice en vez de elegir en silencio.

**Y comprobarlo no pide nada nuevo:** el motor ya calcula una **huella** del asiento, y la calcula a propósito
*excluyendo el correlativo*, que es lo único que cambia entre dos exportaciones del mismo mes. Rehacer el asiento y
comparar huellas es exactamente esa regla, con el mecanismo que ya está escrito y probado. Es la misma idea que Xero lleva al
extremo con un libro diario de solo lectura: lo que se escribe es el hecho y la decisión; el asiento se calcula.

### El centro de costo va en todas las líneas

Hoy el centro de costo se escribe en la línea del gasto y, en la del proveedor, como anexo auxiliar si la empresa lo
configuró así (`contaperu/asiento/motor.py`). Es lo que la práctica contable peruana espera, porque **los sistemas
legacy solo aceptan centro de costo donde la cuenta es de resultados**.

Pero eso es una limitación del destino, no del hecho: **el IGV de esa factura sí es de esa obra**, y también lo es
su detracción. Un ERP que quiera responder «cuánto IGV y cuánta detracción corresponden a OBRA01» hoy no puede, y es
justo lo que un sistema nuevo viene a buscar aquí.

Y así lo resuelve el resto del mundo: **las dimensiones van por línea, en todas**. Xero admite hasta dos `Tracking`
por línea, QuickBooks `ClassRef` por línea, NetSuite departamento, clase y ubicación por línea, y las API unificadas
`tracking_categories` por línea. Ninguna las restringe a las cuentas de resultados.

La propuesta, en tres reglas:

1. **El estándar permite `centro_costo` en cualquier línea**, sea de gasto, de impuesto o de balance.
2. **El asiento neutral lo propaga a todas las líneas del comprobante**, así que la del IGV queda así:

   ```json
   { "cuenta": "401111", "clase": "pasivo", "debe_haber": "D", "importe": "1800.00",
     "rol": "igv", "centro_costo": "OBRA01", "tasa_igv": "18",
     "documento": { "id_externo": "compra-123", "serie_numero": "F001-123" } }
   ```

3. **Cada driver decide dónde escribirlo.** CONCAR y CONTASIS siguen poniéndolo donde su sistema lo acepta, y su
   archivo no cambia ni una celda. El dato viaja completo y cada destino recorta lo que no sabe usar — el mismo
   principio que gobierna todo lo demás aquí.

**Lo que falta decidir es el reparto.** Cuando la imputación divide una factura entre dos obras, las líneas
comunes —el IGV, el proveedor, la detracción— no pertenecen a una sola. O se quedan sin centro, o se reparten en
proporción a la base y el asiento gana líneas que hoy no tiene. La propuesta es dejarlas sin centro y que el ERP
reparta si su análisis lo pide.

### El documento completo, en la 0.4

Una compra con detracción, con los tres bloques y el enlace cerrado. Las cinco líneas del asiento son las que el
motor devuelve hoy; lo que la 0.4 añade es `clase`, `documento.id_externo` y el bloque `imputaciones`:

```json
{
  "open_accounting": "0.4",

  "libro": { "ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC",
             "periodo": "202601", "tipo": "compra" },

  "comprobantes": [
    {
      "tipo_cp": "01", "serie": "F001", "numero": "0000123",
      "fecha_emision": "2026-01-15", "fecha_vencimiento": "2026-02-14",
      "condicion_pago": "credito",
      "contraparte_tipo_doc": "6", "contraparte_doc": "20131312955",
      "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC",
      "moneda": "PEN",
      "base_gravada": "10000.00", "igv": "1800.00", "total": "11800.00",
      "destino_igv": "DG",
      "detraccion": { "codigo": "037", "porcentaje": "12", "monto": "1416.00",
                      "estado": "PROVISIONADO" },
      "concepto": "SERVICIO DE MANTENIMIENTO ENERO 2026",
      "origen": "xml", "id_externo": "compra-123"
    }
  ],

  "imputaciones": {
    "compra-123": { "cuenta_contable": "6343001", "centro_costo": "OBRA01" }
  },

  "asiento": [
    { "cuenta": "6343001", "clase": "gasto", "debe_haber": "D", "importe": "10000.00",
      "rol": "principal", "fecha": "2026-01-15", "moneda": "PEN",
      "centro_costo": "OBRA01", "tasa_igv": "18",
      "glosa": "SERVICIO DE MANTENIMIENTO ENERO 2026",
      "documento": { "id_externo": "compra-123", "tipo_cp": "01", "serie_numero": "F001-123",
                     "fecha_emision": "2026-01-15", "fecha_vencimiento": "2026-02-14" } },

    { "cuenta": "401111", "clase": "pasivo", "debe_haber": "D", "importe": "1800.00",
      "rol": "igv", "fecha": "2026-01-15", "moneda": "PEN", "tasa_igv": "18",
      "glosa": "IGV - SERVICIO DE MANTENIMIENTO ENERO 2026",
      "documento": { "id_externo": "compra-123", "…": "el mismo de arriba" } },

    { "cuenta": "421201", "clase": "pasivo", "debe_haber": "H", "importe": "11800.00",
      "rol": "tercero", "fecha": "2026-01-15", "moneda": "PEN",
      "contraparte_doc": "20131312955", "anexo_auxiliar": "OBRA01",
      "documento": { "id_externo": "compra-123", "…": "el mismo de arriba" } },

    { "cuenta": "421201", "clase": "pasivo", "debe_haber": "D", "importe": "1416.00",
      "rol": "detraccion_tercero", "fecha": "2026-01-15", "moneda": "PEN",
      "contraparte_doc": "20131312955", "anexo_auxiliar": "OBRA01",
      "documento": { "id_externo": "compra-123", "…": "el mismo de arriba" } },

    { "cuenta": "421203", "clase": "pasivo", "debe_haber": "H", "importe": "1416.00",
      "rol": "detraccion", "fecha": "2026-01-15", "moneda": "PEN",
      "contraparte_doc": "20131312955",
      "detraccion": { "codigo": "037", "tasa": "12", "base": "11800.00" },
      "glosa": "DETRACCION - SERVICIO DE MANTENIMIENTO ENERO 2026",
      "documento": { "id_externo": "compra-123", "…": "el mismo de arriba" } }
  ]
}
```

**Léelo por bloques.** `libro` dice de qué registro y de qué mes es. `comprobantes` trae el hecho, con las casillas
que SUNAT distingue y sin una sola cuenta. `imputaciones` trae la decisión del contador, llaveada por el mismo
`id_externo`. Y `asiento` trae el efecto: cinco líneas que cuadran, cada una diciendo qué es (`clase`), qué papel
cumple (`rol`) y de qué comprobante nace (`documento.id_externo`).

Ese último enlace es el que cierra el círculo: **desde cualquier línea se llega a su comprobante y a la imputación
con la que se armó**, sin adivinar por serie y número.


---

## 12 · El recorrido, visto desde el ERP que ya tiene el dato

Lo anterior mira el formato. Esta sección mira lo otro que pregunta quien va a integrar: **dónde corre esto, quién
hace qué y en qué orden.** Hace falta porque el resto del documento está escrito desde el que captura, y un ERP no
captura: la factura y el proveedor ya están en sus tablas.

### Dónde se procesa: dentro del ERP, siempre

**El motor es una librería que el ERP instala, no un servicio al que le pide permiso.** No hay un servidor de
ContaPerú en medio de nadie — justo lo contrario del modelo de «El caso que lo motiva», donde `starsoftweb.com` está en medio y
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

### La configuración y la imputación

| Pieza | Qué lleva | Cada cuánto | Dónde viaja |
|---|---|---|---|
| **Configuración** | Lo que vale para todo el entorno: cuentas por defecto, si usa centros de costo, y una sección por sistema contable —siglas, sub-diarios, en qué columna va cada dato— | Una vez por empresa | **Fuera del documento**: no es contabilidad de un mes, es cómo escribe esta empresa |
| **Imputación** | Lo que se decide para **un** comprobante: su cuenta, su centro de costo, la cuenta del total o un reparto entre varias | Solo donde haga falta | **Dentro**, en `imputaciones`, con llave por `id_externo` |

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
1.0. Lo que añade el driver `asiento_neutral` es el **perfil neutral** —las mismas cuentas, sentidos e importes, sin
el vocabulario de un legacy—. Este es el asiento real de la compra del ejemplo de arriba, generado por el motor
**hoy**: con la 0.4, cada línea suma su `clase` y el centro de costo se propaga a todas («El papel de cada línea»):

| `rol` | `cuenta` | | `importe` |
|---|---|---|---|
| `principal` | 6343001 | D | 10000.00 |
| `igv` | 401111 | D | 1800.00 |
| `tercero` | 421201 | H | 11800.00 |
| `detraccion_tercero` | 421201 | D | 1416.00 |
| `detraccion` | 421203 | H | 1416.00 |

Cada línea entera, y el archivo que se descarga, están en «El botón «Generar asientos»».

**Lo que hace ese asiento portable entre ERPs es `rol`, no la cuenta.** Un sistema que quiera el IGV en una columna
aparte busca la línea por su rol, porque la cuenta `401111` la elige cada empresa pero «esta línea es el IGV» vale
para todas. Los roles son `principal`, `igv`, `retencion_4ta`, `tercero`, `detraccion_tercero` y `detraccion`.

---

## 13 · Los destinos: al SIRE llegan todos

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
| `asiento_neutral` | erp | cuenta contable |
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
limpio. Este es el archivo que produce, generado por el motor para la compra del primero de los «Cuatro ejemplos»:

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
    "glosa": "IGV - SERVICIO DE MANTENIMIENTO ENERO 2026", "documento": { "…": "el mismo de arriba" } },

  { "cuenta": "421201", "debe_haber": "H", "importe": "11800.00", "rol": "tercero",
    "contraparte_doc": "20131312955", "anexo_auxiliar": "OBRA01", "documento": { "…": "el mismo de arriba" } },

  { "cuenta": "421201", "debe_haber": "D", "importe": "1416.00", "rol": "detraccion_tercero",
    "contraparte_doc": "20131312955", "anexo_auxiliar": "OBRA01", "documento": { "…": "el mismo de arriba" } },

  { "cuenta": "421203", "debe_haber": "H", "importe": "1416.00", "rol": "detraccion",
    "glosa": "DETRACCION - SERVICIO DE MANTENIMIENTO ENERO 2026",
    "contraparte_doc": "20131312955",
    "detraccion": { "codigo": "037", "tasa": "12", "base": "11800.00" },
    "documento": { "tipo_cp": "01", "serie_numero": "F001-123",
                   "fecha_emision": "2026-01-15", "fecha_vencimiento": "2026-02-14" } }
 ]
}
```

El archivo se llama `asiento_neutral_20601234567_202601_compra.json`, y lleva **el libro y el asiento, no los
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

## 14 · Qué queda fuera, a propósito

- **Las líneas de detalle por ítem.** Un `Item` o un `InvoiceLine` sería un modelo propio, ya descartado, y el
  registro de compras y ventas de SUNAT no lo pide. Quien reparte el gasto entre cuentas usa `reparto`; quien quiera
  el detalle lo transporta en `datos_originales`.
- **El impuesto por línea de detalle y el indicador de precios con impuesto** (`LineAmountTypes`,
  `pricesIncludeTax`). Sin ítems no tienen dónde ir, y el IGV nunca se delega al destino: va explícito, con su tasa.
- **Un cuerpo propio de la API.** Fue el primer borrador y duró lo que tardó la primera lectura: un formato que solo
  existe dentro de una petición no se puede guardar, ni mandar, ni comprobar sin servidor. «El formato: uno solo, el del estándar» lo cuenta.
- **Las rutas por tipo, `/v1/compras` y `/v1/ventas`.** El documento dice `libro.tipo`; una ruta que repite un campo
  del cuerpo solo añade un sitio donde los dos pueden contradecirse.
- **La cabecera `Idempotency-Key`.** La clave natural aquí es la identidad del comprobante más la huella del
  asiento, y las dos ya existen.
- **El estado de borrador o contabilizado.** `estado` de la línea es un nombre reservado que espera su caso, y
  `comprobante.estado` ya significa otra cosa.
- **La contraparte con dirección, correo o id interno del ERP.** Eso es la ficha del proveedor, no el hecho que se
  registra.
- **Los lotes.** Ya existen: son las operaciones de hoy, con su tope de comprobantes.
- **El signo en vez de `debe_haber`**, y los importes numéricos **como recomendación**: el céntimo que pierde un
  `float` y la nota de crédito restada dos veces. Con una salvedad que hay que resolver: el esquema todavía **admite**
  números, así que hoy es consejo y no regla («Lo que falta decidir»).
- **OAuth, webhooks, sincronización incremental.** El motor no tiene estado ni sale a la red.

---

## 15 · Qué va al estándar, qué va al motor, y qué no va a ninguno de los dos

**El criterio.** Al **estándar** va lo que dos sistemas necesitan para entenderse sin haber hablado nunca entre
ellos. Al **motor** va lo que se calcula a partir de eso. Un dato que se puede derivar no entra al estándar, y una
regla que cambia según el sistema de destino no entra al núcleo: vive en la configuración de su driver.

### Al estándar, `open-accounting`

| Qué | Por qué | Cuándo |
|---|---|---|
| **`imputaciones` en la raíz**, con llave por `id_externo` | Sin ellas el archivo no explica su propio asiento, y el estándar promete que un documento «se entiende solo, en cualquier máquina, sin consultar nada» | Ahora. Aditivo |
| **La regla de hasta dónde viaja cada bloque** | `libro` y `comprobantes` son hechos y valen en todas partes; `imputaciones` y `asiento` están en el plan de cuentas de quien los escribió y son **informativos fuera de él**. Sin esa regla, un ERP copia cuentas ajenas en silencio. `emisor` ya dice de quién son | Ahora. Es texto, no esquema |
| **`clase` en cada línea**: `activo`, `pasivo`, `patrimonio`, `ingreso`, `gasto` | Es lo único que un ERP de fuera entiende sin conocer el PCGE, y son los cinco valores que QuickBooks, Xero, Merge y Rutter comparten. Sin ella, `principal` y `tercero` solo significan algo mirando `libro.tipo` («El papel de cada línea») | **0.4** |
| **`libro.tipo` como catálogo publicado** | Un registro nuevo no puede costar una versión del documento, y un hecho nuevo —el banco— entra como bloque propio, no como valor forzado aquí. Es lo que hacen QuickBooks con un recurso por hecho y EN 16931 con su lista externa de tipos de documento | **0.4** |
| **`centro_costo` en cualquier línea**, no solo en las de resultados | El IGV y la detracción de una factura son de la misma obra que el gasto; que el legacy no tenga dónde ponerlos es un límite del destino, no del hecho. Xero, QuickBooks, NetSuite y las unificadas llevan sus dimensiones por línea, sin restringirlas | Ya cabe: es decir la regla |
| **El asiento es derivado** del comprobante, la imputación y la configuración | Si los tres bloques viajan juntos y el asiento no corresponde, hay dos verdades en un archivo. Xero lo lleva al extremo con un libro diario de solo lectura | Ahora. Es texto, no esquema |
| **`documento.id_externo` en la línea** | Hoy la línea enlaza con su comprobante por serie y número; Xero enlaza por `SourceID` y SAF-T por `SourceDocumentID`. Con el id, el asiento, la imputación y el comprobante quedan atados sin adivinar | Aditivo |
| **`rol` como catálogo publicado**, fuera del enum del esquema | Un rol nuevo —percepción, anticipo, redondeo— no puede obligar a una versión del documento. Es el diseño de ISO 20022 y el que terminó adoptando SAF-T | **0.4** |
| **La regla de degradación**: se puede contabilizar con `clase`, `debe_haber` e `importe` aunque el `rol` sea desconocido | Es lo que permite que el catálogo crezca sin romper a quien ya integró | **0.4**. Es texto, no esquema |
| `impuesto {codigo, tasa, base}` en la línea, y `plan_de_cuentas` en la raíz | El impuesto es el único papel que todos los estándares sí ponen en la línea; el diccionario de cuentas es el `SystemAccount` de Xero y el `StandardAccountID` de SAF-T, como ayuda opcional | 0.4 u después, con su caso |
| `dimensiones`, `medio_pago`, `retencion_igv`, `percepcion`, `no_domiciliado` | Son hechos, y les falta el caso real que manda la regla del proyecto | Con su caso (E1) |
| Cheques | Es otro hecho —un pago, no un comprobante— y sería otro libro más | Cuando haya caso |
| Una ficha de proveedor o cliente | **Nunca.** Es un maestro, no un hecho. El RUC viaja embebido en el comprobante, que es justo lo que le ahorra a este estándar la ruta de anexos que STARSOFT necesita | — |

### Al motor, `contaperu`

| Qué | Por qué |
|---|---|
| **Aceptar `imputaciones` dentro del documento**, sin dejar de aceptar el argumento de hoy | Es la pieza que hace real el formato único, y nadie que ya integre tiene que cambiar |
| **Una batería de conformidad**: casos de entrada con su documento esperado | Es lo que le permite a un ERP de fuera comprobar que emite bien sin escribirle a nadie. Hoy hay `diagnosticar` y `verificar-driver`; falta el juego de casos |
| **Renombrar el driver a `asiento_neutral`** | Hoy se llama igual que el estándar. Es gratis mientras siga sin publicar, y rompe a quien lo integre si se hace después de la 1.1.0 («Los dos nombres, decididos») |
| **Propagar el centro de costo a todas las líneas** en el vocabulario neutral, y dejar que cada driver legacy escriba donde su sistema acepta | Es lo que permite preguntar cuánto IGV y cuánta detracción son de una obra. El Excel de CONCAR no cambia: su driver sigue con sus reglas |
| **Avisar cuando el asiento que llega no corresponde** al comprobante y su imputación | Un archivo con dos verdades es peor que uno incompleto |
| **Rellenar `clase` él mismo**, desde el rol y el libro | Así un documento 0.3 que llega sin ella se completa al vuelo, y nadie tiene que reescribir lo que ya guardó |
| **Publicar el catálogo de roles**, con su versión, al lado de los catálogos de SUNAT | Un ERP consulta qué roles puede recibir en vez de descubrirlos cuando le llega uno que no conoce |
| **Nada para el correlativo** | Ya está todo: numera en el orden recibido, devuelve los rangos, los anuncia en `diagnosticar`, lo excluye de la huella y lo omite en el asiento neutral. Lo que faltaba era decir que la unidad es el mes («El correlativo») |
| **No tener bandeja.** El motor recibe, responde y olvida | Depositar y esperar aprobación es del ERP, que es quien tiene usuarios y base de datos. Copiar la bandeja aquí le daría estado al motor, que es lo único que no puede tener |
| **Diagnosticar contra los destinos que el entorno declaró**, no contra el driver de esa llamada | Es lo que hace que «generar asientos» vuelva obligatoria la cuenta contable, y que quien tiene SIRE y CONCAR reciba una sola respuesta en vez de dos («Los destinos») |
| **No salir a la red.** Ni descargar del SIRE, ni llamar a otro sistema | Misma razón, y ya está escrito en la hoja de ruta |

### A ninguno de los dos

- **El vocabulario legacy** —`subdiario`, la sigla del documento, `destino_Compra`—: vive en la configuración del
  driver que lo necesita, que es donde ya está. Ni el estándar ni el núcleo lo conocen.
- **Autenticación, permisos, IP pública, licencias.** Eso es de quien publique una puerta, no del formato.
- **La ficha del anexo, el detalle por ítem y los ids internos de nadie.**

### Los cambios al esquema: uno aditivo y dos que suben a la 0.4

**`imputaciones` es aditivo y se queda en la 0.3.** Hoy la raíz admite cinco claves —`open_accounting`, `libro`,
`comprobantes`, `asiento` y `emisor`— y rechaza cualquier otra, así que hay que añadirla ahí. Un campo opcional nuevo
no sube la versión: **avanza el tag `open-accounting-0.3`** y quien ya escribe 0.3 sigue valiendo.

**`clase` y el `rol` como catálogo suben a la 0.4** (John, 18-sep-2026): son las dos piezas que dejan la línea del
asiento lista para cualquier ERP y para los roles que todavía no existen («El papel de cada línea»). Suben la
versión porque `clase` pasa a ser obligatoria y porque la clave `open_accounting` es una constante en el esquema.

| Qué cambia en el esquema | Hoy | En la 0.4 |
|---|---|---|
| `linea.clase` | no existe | `enum: ["activo", "pasivo", "patrimonio", "ingreso", "gasto"]`, obligatoria |
| `linea.rol` | `enum` cerrado de seis valores | Texto validado contra el catálogo publicado, que se versiona aparte |
| `libro.tipo` | `enum: ["venta", "compra"]` | Texto validado contra su catálogo, que crece sin subir la versión |
| `open_accounting` | `const: "0.3"` | `const: "0.4"` |
| El `$id` canónico, que cuelga del tag del estándar | `.../open-accounting-0.3/...` | `.../open-accounting-0.4/...`, con su propio tag |

**Lo que no cambia de significado para nadie:** un documento 0.3 dice exactamente lo mismo en la 0.4, y **el motor
rellena `clase` solo** —del primer dígito de la cuenta, según «De dónde sale la `clase`»—. Acepta las dos versiones durante toda la 1.x.

**Y el tercer libro, el de honorarios, sigue descartado** (John, 18-sep-2026): se quedan en el libro de compras y
qué registro los lleva lo decide cada destino, como hoy. El porqué y lo que costaba, en «Por qué no hay un libro de
honorarios».

| Cambio | Clasificación |
|---|---|
| `imputaciones` en la raíz del documento, con llave por `id_externo` | **Aditivo.** Avanza el tag `open-accounting-0.3`, no sube a 0.4 |
| `clase` obligatoria en cada línea | **0.4.** Es lo que deja la línea explicándose sola fuera del Perú |
| `rol` fuera del enum, contra un catálogo publicado | **0.4.** A cambio, los roles que vengan después ya no piden versión |
| Aceptar el documento con un solo comprobante | Ya vale: `comprobantes[]` nunca exigió más de uno |
| La respuesta que reusa el esquema del diagnóstico | Ya vale: está publicado |
| Rechazar una clave desconocida | Ya vale: el esquema no admite campos de más |
| `dimensiones`, `medio_pago`, `retencion_igv`, `percepcion`, `no_domiciliado`, `estado` de línea | Aditivos, pero **piden su enmienda (E1) y un caso real**. Fuera de esta tanda |
| Hacer `libro.periodo` opcional | **Rompe**, y ya no hace falta: el documento lo trae siempre |
| Devolver `cuenta_contable` al comprobante | **Rompe**: revierte la 0.3. Por eso es un bloque hermano y no un campo del comprobante |
| Un bloque de ítems en el comprobante | Cambia qué es un comprobante. Fuera |

---

## 16 · Gobernanza y conformidad: cómo vive el estándar fuera de aquí

Mientras `rol` y `libro.tipo` eran enums cerrados, quien quisiera un valor nuevo tenía que abrir un PR y discutirlo.
**Al sacarlos a catálogos abiertos, esa conversación desaparece — y hay que reponerla a propósito**, o cada ERP
inventará sus propios roles y el estándar dejará de serlo en un año. Son las dos preguntas que hace cualquiera antes
de apostar años de integración, y hoy no tienen respuesta escrita.

### Cómo comprueba un tercero que emite bien

Hoy hay dos piezas y falta la tercera:

| Pieza | Qué comprueba | Estado |
|---|---|---|
| `diagnosticar` | Un documento concreto: qué bloquea, qué falta y a quién pedírselo | **Existe** |
| `contaperu verificar-driver` | Un driver propio contra el contrato, antes de registrarlo | **Existe** |
| **La batería de conformidad** | Que lo que un sistema **produce** es un documento correcto | **Falta** |

La batería es un juego de casos con su documento esperado: para cada uno, los datos de entrada y el
`open-accounting` que debe salir. Un ERP la corre contra su propio código y sabe si cumple, **sin escribirle a
nadie**. Es lo que separa «integrar en una tarde» de «abrir un hilo de correos».

Qué tendría que cubrir, por lo que este documento ya descubrió que se equivoca:

- Los cuatro ejemplos de «Cuatro ejemplos», que ya están y ya se validan.
- **El recibo por honorarios con el importe en `inafecto`**, que puesto en `base_gravada` sale observado.
- **La factura en dólares sin tipo de cambio**, que bloquea.
- **La nota de crédito con sus importes en positivo**, y en su propia moneda.
- **La ausencia como respuesta**: sin `detraccion: false`, sin ceros de relleno, sin claves de otro sistema.
- **Cada rol con su clase**, recorriendo el catálogo entero.

Vive en el repositorio, con los documentos y sus salidas esperadas, y se publica con el tag del estándar: **la
batería de la 0.4 se cita como se cita el esquema**.

### Quién decide qué entra al catálogo

Un catálogo abierto necesita tres cosas escritas, y ninguna es burocracia:

| Qué | Propuesta |
|---|---|
| **Quién aprueba** | John, mientras el repositorio sea suyo. Dicho, no sobreentendido: quien integra necesita saber a quién le pregunta |
| **Cómo se propone** | Un issue con el caso real detrás —un archivo de verdad de un sistema de verdad—, que es la regla que ya gobierna el estándar |
| **Qué se responde** | Si entra, entra como valor de catálogo con su fecha; si no, se dice por qué. Un catálogo que crece sin criterio es un enum con más pasos |

Y una regla que protege al que ya integró: **un valor publicado no se quita ni cambia de significado**. Si resulta
equivocado, se marca como obsoleto y entra otro al lado — que es lo que hacen las listas de códigos de ISO 20022 y
de EN 16931, y la razón de que sus mensajes sobrevivan décadas.

### Lo que no se gobierna

Los catálogos de **SUNAT** —tipos de comprobante, documentos de identidad, monedas, detracciones, el PCGE— no se
proponen ni se discuten: se copian de la norma, con su fuente y su fecha. Cuando SUNAT cambia una tasa o añade un
código, el catálogo lo refleja y ya. Lo que se gobierna es solo lo que este estándar inventa: los **roles**, las
**clases** y los **tipos de libro**.

---

## 17 · Lo que ya quedó decidido

**Cuatro se cayeron solas** en cuanto el cuerpo de la llamada dejó de ser un envoltorio y pasó a ser el documento:

| Antes era una decisión | Cómo queda |
|---|---|
| Si el periodo se deriva de la fecha | No se deriva: el libro lo trae. Las tres validaciones de plazo siguen vivas |
| Quién numera cuando llega un comprobante suelto | Lo mismo que hoy: un documento de uno se numera como uno de mil |
| Que las dos puertas no se separen | No hay dos puertas: hay un documento y un pipeline |
| El freno de la ruta por comprobante | El tope de comprobantes del lote ya lo cubre |

### El catálogo de roles se abre, pero no crece (John, 18-sep-2026)

**Los seis roles se quedan como están, y son solo de compras y ventas.** `principal`, `igv`, `tercero`,
`retencion_4ta`, `detraccion_tercero` y `detraccion` cubren completos los dos libros que el motor genera: una venta
usa tres, una compra hasta seis, y la nota de crédito no añade ninguno porque reusa los mismos con los sentidos
invertidos.

**Y aun así el catálogo se abre.** No para añadir valores ahora —no hace falta ninguno— sino porque **abrirlo es
gratis hoy y caro después**: con el enum cerrado, el día que entre el bloque del banco o el de las letras de cambio
sus roles costarían otra versión del estándar; con el catálogo, ninguno. Es la misma razón por la que `libro.tipo`
también sale del enum.

Lo que eso deja claro para quien lea «un catálogo abierto»: **no es una invitación a que los roles proliferen.** Un
rol nuevo solo aparece cuando aparece el hecho que lo necesita, y un hecho nuevo entra como bloque propio en la
raíz, nunca como valor forzado en el enum de otro.

### El libro de honorarios: no se hace (John, 18-sep-2026)

Los recibos por honorarios se quedan **dentro del libro de compras**, como hoy, y qué registro los lleva lo sigue
declarando cada destino. Con eso los drivers se quedan como están y el estándar se ahorra **esa** versión —la 0.4
que sí se propone es la de `clase` y los catálogos, por otro motivo—. El porqué entero, en «Por qué no hay un libro
de honorarios».

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

De ahí los dos modos, que son exactamente los dos flujos de «Los destinos: al SIRE llegan todos»:

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
| El driver, que se llamaba `open_accounting` | **`asiento_neutral`** ✅ hecho el 18-sep-2026 | Dice qué produce y con qué vocabulario, y no reproduce la confusión de llamarse igual que el estándar. Hay precedente de nombrar un driver por su salida y no por un sistema: `csv` tampoco nombra un destino |

**El renombrado se hizo el 18-sep-2026**, y se hizo primero justamente porque era gratis: el driver estaba en «Sin
publicar», así que nadie lo usaba; después de la 1.1.0 habría roto a quien lo hubiera integrado. Cambiaron el módulo
`contaperu/drivers/open_accounting/` → `.../asiento_neutral/`, el valor de `driver`, el formato
`asiento_neutral_json`, el nombre del archivo que se descarga y la superficie pública congelada. **No tocó el
estándar:** la clave `open_accounting` del documento y el nombre con guion siguen igual, y separarlas de las del
driver fue el único riesgo real del cambio.

---

## 18 · Lo que falta decidir

Nueve, y ninguna es de arquitectura: son de alcance, salvo una que es un agujero que apareció al probar el esquema.

1. **Si `clase` es obligatoria también para quien la manda, o solo para quien la escribe.** Que el motor la rellene
   es el motor siendo generoso, no el estándar: un tercero que emita `asiento[]` sin `clase` sería rechazado por el
   esquema. La salida clásica es **estricto al emitir y permisivo al aceptar** —obligatoria en lo que el motor
   escribe, opcional en lo que lee—, que es lo que hace que un estándar sobreviva a sus propios productores.
2. **Si `id_externo` pasa a ser obligatorio cuando el documento trae `imputaciones`.** Hoy es opcional, pero con las
   imputaciones llaveadas por él y `documento.id_externo` en la línea se vuelve estructural: **un comprobante sin
   `id_externo` no se puede imputar** —el motor ya lo rechaza—, así que el esquema debería exigirlo en ese caso en
   vez de dejar que falle más tarde.

3. **Rechazar la clave desconocida** endurece la API para quien hoy, desde Python, manda campos de más.
4. **Si `imputaciones` viaja también de vuelta**, en la respuesta y en la salida del driver neutral: quien recibe el
   documento podría querer saber con qué cuentas se armó el asiento que lleva al lado.
5. **Si el archivo del botón lleva también los comprobantes.** Hoy sale con `libro` y `asiento`, porque quien lo pide
   ya tiene los hechos. Un ERP de fuera que reciba ese archivo sí querría los dos, y entonces el archivo pasa a ser
   un documento completo del estándar en vez de solo el asiento.
6. **Los importes en texto son recomendación, no validación.** El estándar dice que van en texto exacto, «porque la
   contabilidad no perdona el céntimo que se pierde», pero el esquema también admite números sin límite de
   decimales: probado, deja pasar `118.005`. O el esquema exige texto, o acepta números pero de dos decimales. Hoy
   la regla que más se repite en este documento es la única que nadie comprueba.
7. **Si `impuesto` y `plan_de_cuentas` entran con la 0.4 o esperan su caso.** Los dos son opcionales y ninguno hace
   falta para que `clase` funcione; entrar juntos ahorra una versión, y esperar respeta la regla de que el estándar
   crece con un archivo real detrás.
8. **El centro de costo de las líneas comunes cuando hay reparto.** Si una factura se divide entre dos obras,
   el IGV, el proveedor y la detracción no son de una sola: o van sin centro, o se reparten en proporción a la
   base y el asiento gana líneas que hoy no tiene. La propuesta es dejarlas sin centro.
9. **Cuándo se publica la 0.4.** Con `clase` y el catálogo de roles hay que decidir si sale junto con la 1.1.0 del
   motor —que ya arrastra el renombrado del driver— o después, con su pre-release y su guía de migración.

---

## 19 · Cómo se implementa

Este documento es investigación y borrador, pero lo que propone se ejecuta por partes, con la batería verde en cada
una y el OK de John entre ellas. El orden importa: **la parte 2 tiene fecha límite** y la 3 arrastra una versión del
estándar.

### Parte 1 · `imputaciones` dentro del documento (aditivo, tag `open-accounting-0.3`)

| Qué | Dónde |
|---|---|
| La raíz admite `imputaciones`, con llave por `id_externo` | `estandar/open-accounting.schema.json` |
| El pipeline la lee del documento sin dejar de aceptar el argumento de hoy, y rechaza que lleguen los dos | `contaperu/pipeline/preparacion.py`, `contaperu/api/` |
| `documento.id_externo` en la línea del asiento | el esquema y `contaperu/asiento/motor.py` |

**Los tests que la fijan:** un documento con `imputaciones` da exactamente el mismo asiento que hoy da con la
imputación como argumento; una llave que no es de ningún comprobante se rechaza; mandar las dos formas a la vez se
rechaza; el snapshot de CONCAR y las huellas no se mueven.

### Parte 2 · Renombrar el driver a `asiento_neutral` (antes de la 1.1.0)

Es gratis mientras siga sin publicar y rompe a quien lo integre si se hace después. Son 89 apariciones en 31
archivos, la mayoría tests y fixtures, y hay que distinguirlas de las 36 del estándar, que se quedan.

**Los tests que la fijan:** la superficie pública regenerada solo con el nombre nuevo; la caracterización, el MCP y
`openconta.json` al día; el documento que produce, byte a byte igual salvo el nombre del archivo.

### Parte 3 · La 0.4: `clase` y los catálogos

| Qué | Dónde |
|---|---|
| `clase` obligatoria en cada línea, derivada del primer dígito de la cuenta | el esquema y `contaperu/asiento/motor.py` |
| **Validar** la clase que llega, y observar una imputación a una cuenta de elemento 8 o 0 | `contaperu/pipeline/preparacion.py`, `contaperu/asiento/faltas.py` |
| **La clase de cada cuenta en el catálogo del PCGE**, que hoy solo trae código, nombre y cuenta madre | `contaperu/datos/`, servido por `api.buscar_cuenta_pcge` |
| `rol` y `libro.tipo` validados contra un catálogo publicado, no contra un enum | el esquema, `contaperu/modelo.py`, `contaperu/drivers/contrato.py` |
| Los catálogos `roles`, `clases` y `tipos_de_libro`, con su versión | `contaperu/datos/`, servidos por `api.catalogos_*` |
| La regla de degradación y la de versionado en tres niveles | `estandar/LEEME.md` |
| La enmienda que acompaña el salto de versión | `estandar/enmiendas/` (hito E1, que todavía no existe) |

**Los tests que la fijan:** cada rol tiene su clase y un test las recorre todas; un documento 0.3 entra y sale
completado, con el mismo asiento; un rol que no está en el catálogo no rompe el documento; el snapshot de CONCAR
idéntico.

**Y antes del tag:** `contaperu/_version.py`, la sección del CHANGELOG, una pre-release `rc` y la guía de migración,
como manda el proyecto para una versión mayor del estándar.

### Parte 4 · La batería de conformidad y la gobernanza

Con `rol` y `libro.tipo` en catálogos abiertos, las dos dejan de ser opcionales: sin batería nadie puede comprobar
que emite bien, y sin gobernanza cada ERP inventa sus roles. Lo que hay que escribir está en «Gobernanza y
conformidad»; lo que hay que construir son los casos con su documento esperado, publicados con el tag del estándar,
y las tres líneas de quién aprueba, cómo se propone y qué se responde.

**Los tests que la fijan:** la batería corre en CI contra el propio motor —si el motor no pasa su propia
conformidad, no la pasa nadie— y cada caso nuevo del documento entra en ella.

### Parte 5 · Lo opcional, cuando tenga su caso

El bloque `impuesto` en la línea, el diccionario `plan_de_cuentas`, y propagar el centro de costo a todas las líneas
del asiento neutral. Esto último **cambia una salida** —la del driver neutral, no la de CONCAR— y por tanto se
anuncia en el CHANGELOG como cambio de comportamiento.

### Los documentos que hay que actualizar cuando se aplique

Cinco dicen hoy que la imputación llega aparte del documento, y tres describen el asiento sin `clase`:

| Documento | Qué cambia |
|---|---|
| `README.md` | «El motor por dentro»: la imputación pasa a ser un bloque del documento |
| `diagramas/arquitectura-del-motor.svg` | Dibuja «la imputación aparte» |
| `ARQUITECTURA.md` | La línea neutral, con `clase` y el enlace por `id_externo` |
| `INTEGRAR.md` | Su ejemplo `curl`, que manda `imputacion` como argumento |
| `estandar/LEEME.md` | La imputación, las reglas nuevas y el versionado en tres niveles |
| `CHANGELOG.md` · `HOJA-DE-RUTA.md` | La versión con su porqué, y los hitos de cada parte |

### Lo que bloquea cada parte

| Decisión pendiente | Bloquea |
|---|---|
| Si se rechaza la clave desconocida | Parte 1 |
| Si `imputaciones` vuelve en la respuesta | Parte 1 |
| Los importes en texto como regla del esquema | Parte 3, que ya toca el esquema |
| El centro de las líneas comunes cuando hay reparto | Parte 5 |
| Si `impuesto` y `plan_de_cuentas` entran con la 0.4 | Partes 3 y 5 |
| Cuándo se publica la 0.4 | Parte 3 |
| Si `clase` es obligatoria al emitir y opcional al aceptar | Parte 3 |
| Si `id_externo` se exige cuando hay `imputaciones` | Parte 1 |

---

## 20 · Fuentes

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

**El papel de la línea, y la frontera entre documento y asiento** (consultadas el 18-sep-2026)

- Xero, el libro diario de solo lectura con `SourceID` y `SourceType`:
  https://developer.xero.com/documentation/api/accounting/journals
- Xero, cuentas con `Type`, `Class` y `SystemAccount`: https://developer.xero.com/documentation/api/accounting/accounts
  y su especificación: https://github.com/XeroAPI/Xero-OpenAPI/blob/master/xero_accounting.yaml
- QuickBooks, la cuenta con `Classification`, `AccountType` y `AccountSubType`:
  https://developer.intuit.com/app/developer/qbo/docs/api/accounting/most-commonly-used/account ; el asiento manual:
  …/journalentry ; el mayor, por reportes: …/all-entities/generalledger
- NetSuite, tipos de cuenta que no se pueden crear ni modificar:
  https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_3947502870.html ; cuentas generadas por el
  sistema: …/bridgehead_4078513386.html
- Sage Intacct, la cuenta con `ACCOUNTTYPE` y `NORMALBALANCE`: https://developer.intacct.com/api/general-ledger/accounts/
- Merge (`classification`): https://docs.merge.dev/accounting/accounts/ ·
  Rutter (`category`): https://docs.rutter.com/rest/2023-02-07/accounts · Apideck: https://specs.apideck.com/accounting.yml
- SAF-T de la OCDE, con `SourceDocuments` y `GeneralLedgerEntries` enlazados en los dos sentidos: guía 2.0 y su
  apéndice B, en el archivo público de la OCDE
- XBRL GL, `accountPurposeCode` y `accountType`:
  https://www.xbrl.org/GLWGNotes/XBRL-GL-WGN-Amazing_Account-2007-07-08.htm y
  http://www.xbrl.org/wgn/templates/wgn-2009-02-17/templates-wgn-wgn-2009-02-17.html
- ISO 20022, catálogos de códigos externos «para añadir sin cambiar la versión de los mensajes»:
  https://www.iso20022.org/catalogue-messages/additional-content-messages/external-code-sets
- PCAOB AS 1105, la evidencia del documento original:
  https://pcaobus.org/oversight/standards/auditing-standards/details/AS1105
