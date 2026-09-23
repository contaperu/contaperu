# Interoperabilidad: el ciclo contable, lo que enseñan EE. UU. y lo abierto, y cómo entraría cada pieza en el motor

# Parte I · Marco

## 0 · Cómo se lee

[REFERENCIAS.md](REFERENCIAS.md) (11-sep-2026) miró **lo cerrado**: la API de QuickBooks Online, la de Xero y las
APIs unificadas de EE. UU. (Merge, Codat, Rutter, Apideck). De ahí salieron `EXIGE` en el contrato de driver,
`pedir_a` en `diagnosticar`, la huella de `_exportacion` y los nombres reservados del estándar. Este documento es su
continuación y reúne **toda la investigación** que ordena la [HOJA-DE-RUTA.md](HOJA-DE-RUTA.md): el ciclo contable de
EE. UU. comparado con el peruano, los proyectos de código abierto, los estándares que ya definen cómo se traza un
asiento, las reglas de SUNAT como datos, las facturas de proveedores y el banco, la especificación MCP y la puerta
escrita a otra jurisdicción.

**Estado: investigación, escrita sobre la librería 0.10.0 y `open-accounting` 0.3**, cuando nada de lo que aquí se
propone estaba implementado. Parte entró después —las enmiendas `0008` a `0011` del estándar y la cabecera del asiento
que creció en la 1.4.0, entre otras—, así que lo que sigue abierto se lee contra la librería y el estándar de hoy. El
proyecto crece con una regla —se afina lo que existe y el estándar crece con casos reales, no por si acaso—, así que
este documento es una **hoja de ruta condicionada**: cada propuesta dice qué caso real la destraba y qué test la
fijaría. La tabla del §12 las inventaría con el hito que le toca a cada una, junto con lo que se descartó; la
[HOJA-DE-RUTA.md](HOJA-DE-RUTA.md) las ordena.

**Índice.**

| Parte | Sección | Qué responde |
|---|---|---|
| **I · Marco** | §0 · Cómo se lee | Alcance, índice, molde, convenciones y lo que sigue sin verificar |
| | §1 · El ciclo contable, comparado | Dónde controla cada país; lo que el Perú tiene y EE. UU. no |
| **II · Las etapas del ciclo** | §2 · Recibir la factura | Canales y cuentas por pagar en EE. UU.; la bandeja y la propuesta del RCE en el Perú |
| | §3 · Validar antes de asentar | Las reglas de SUNAT como datos; el plan de cuentas del destino; la identidad del tercero |
| | §4 · Asentar: identidad y trazabilidad | La identidad del comprobante; el índice por comprobante; la tabla de asignación |
| | §5 · Exportar al destino | Inmutabilidad y concurrencia; los sistemas legacy; la puerta para cualquier ERP |
| | §6 · Pagar y conciliar: el banco | Formatos, *push* y *pull*, conciliación, pasarelas, rieles de pago y fraude |
| | §7 · Declarar: SIRE, sales tax y 1099 | Cómo declara EE. UU. y sus analogías peruanas verificadas |
| **III · Lo transversal** | §8 · Modelos de referencia | Los ERPs abiertos, los *ledgers* y los estándares del libro mayor |
| | §9 · El estándar y su gobierno | Enmiendas, conformidad y retiro |
| | §10 · Arquitectura y puertas | La frontera del núcleo; la puerta MCP |
| | §11 · Otra jurisdicción | Qué es universal y qué peruano; cómo entraría otro país |
| **IV · Inventario** | §12 · Tabla de propuestas y descartes | Cada propuesta con su hito; cada descarte con la sección de su motivo |
| | §13 · Fuentes | Agrupadas por tema, con su fecha de consulta |

**El molde de cada etapa.** Las secciones de la Parte II siguen el mismo orden interno:
1. **Qué hacen** EE. UU. y los proyectos abiertos.
2. **Perú**, cuando la etapa tiene algo propio del país.
3. **Qué hace ContaPerú hoy**, con `ruta:línea`.
4. **Qué tomar**: cada propuesta con su caso real y los tests que la fijarían.
5. **Qué no se toma**, con su motivo.

**Cómo se cita.** Entre este documento y la hoja de ruta se cita por identificador estable: desde aquí, el id del hito
(C9, D3); desde la hoja de ruta, el número de la propuesta o el título de la etapa. Nunca por número de sección, para
que cualquiera de los dos se pueda reordenar sin romper una remisión. Dentro de este documento, «§N» remite a una
sección.

**Lo que no cambia**, y ordena todas las propuestas: el motor no lee PDFs ni fotos, no se conecta a SUNAT ni a ningún
banco, y no guarda nada ([README.md](README.md), «Qué no hace»). Conectarse, recibir correos, leer con IA, aprender
del historial y guardar el estado de una conciliación es trabajo **de la aplicación que consume el motor**. El motor
lee formatos, propone con motivo y arma asientos, siempre como funciones puras.

**Convenciones del documento.**

| Marca | Significado |
|---|---|
| **N** · **D** · **F** · **A** | Nivel donde vive una pieza: **N**úcleo, **D**river, **F**achada o puerta MCP, **A**plicación que consume el motor |
| `nombre*` | Nombre provisional, a decidir por el mantenedor antes de entrar en el código |
| *no verificado* | No se confirmó en una fuente primaria |
| *según terceros* / *según el proveedor* | La fuente es secundaria o es el propio fabricante |
| *práctica contable* | Uso extendido sin una norma primaria encontrada |
| *ilustrativo* | Ejemplo de diseño; no es una propuesta ni una regla |
| `ruta:línea` | Código de este repositorio en la 0.10.0 |

**Lo que sigue sin verificar**, y se revisa al abrir el hito que lo usa:
- Qué hace CONCAR al importar una cuenta, un anexo o un centro de costo que no existen (C10).
- La composición exacta del CAR del SIRE (0.0).
- La descarga del XML de los comprobantes recibidos desde SOL o el SIRE (C9): el manual de la API del SIRE de compras no
  la menciona.
- Un formato de máquina para la constancia de detracción, y el TXT de detracciones campo por campo (D1).
- Que algún banco peruano entregue MT940 o camt (D2).
- La primera versión del SDK de MCP que acepta anotaciones (0.2).
- Los nombres y la estructura de los archivos de importación del PLAME (propuesta 27).
- El tratamiento del IGV de la comisión de las pasarelas (D5).

Fuentes consultadas el 13 y el 14-sep-2026. Las URL van junto a cada hallazgo y agrupadas en el §13.

---

## 1 · El ciclo contable, comparado: EE. UU. frente al Perú

### Qué hacen

La pregunta (14-sep-2026) fue cómo es en EE. UU. el ciclo que en el Perú resuelven el XML de SUNAT y el SIRE: cómo
llega una factura emitida al sistema del comprador y cómo se declaran compras y ventas. La respuesta corta es que **los
dos países controlan en lugares distintos**. El Perú controla por comprobante y con el Estado en medio, antes de que la
factura exista. EE. UU. controla por agregado y con auditoría posterior, sin que ningún fisco vea una factura.

```
ETAPA          EE. UU.                                    PERÚ                                      CONTAPERÚ (hoy · hito)
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
EMISIÓN        Invoice de QuickBooks · EDI X12 810        XML UBL 2.1 firmado ─► OSE o SUNAT        no emite
               sin validación previa ni formato legal     validación previa ─► CDR del emisor       (README, «Qué no hace»)
ENTREGA  §2    PDF por correo · papel · EDI 810           correo con XML y PDF                      bandeja de la aplicación;
               portal del comprador (PO flip) · red AP    web del emisor durante un año             el motor lee bytes
               DBNAlliance (voluntaria)                   ── ninguna red reparte ──                 (lectores/archivos.py)
CUENTAS  §2-4  alta: W-9 + TIN Matching                   RUC en el XML · padrón                    validar · C8 padron*
POR PAGAR      buzón ─► borrador ─► tres vías             bandeja ─► leer_xml ─► revisar            diagnosticar · C9
               aprobación ─► Bill (pasivo)                propuesta del RCE = lista de control      imputación ─► exportar
PAGO     §6    ACH · cheque · tarjeta virtual             transferencia · detracción al BN          D1 aplicar_constancias*
               Same Day ACH · FedNow · RTP                retención del IGV (3 %)                   D3 conciliar*
               remesa 820 o remt.001 · riesgo: BEC        factura negociable (conformidad)
DECLARACIÓN    renta anual (1120 · 1065 · Schedule C)     SIRE: RCE y RVIE, mensual, por comprobante driver sire
         §7    sales tax agregado por jurisdicción        PDT 621 agregado · PLAME 4ta mensual      leer_propuesta_sire
               use tax autoliquidado · 1099 anual (IRIS)  DAOT residual                             (PLAME y 621: fuera)
```

**La diferencia que ordena el resto.**

| Etapa | EE. UU. | Perú | Consecuencia para el motor |
|---|---|---|---|
| Validación del comprobante | Nadie la valida: no hay formato legal de factura B2B ni red obligatoria (§2) | Validación previa del OSE o de SUNAT, con CDR | El motor nunca emite ni valida en línea; lee el resultado (C3) |
| Entrega al comprador | Muchos canales, ninguno obligatorio salvo con el gobierno federal (§2) | Ningún canal obligatorio: correo, o la web del emisor durante un año | La bandeja es de la aplicación; el motor lee bytes |
| Identidad del tercero | Documento aparte: el W-9, verificado con TIN Matching (§3) | El RUC viaja dentro del comprobante, con dígito verificador | `ruc_valido` y el padrón como dato (C8) |
| Lista de lo que facturaron los proveedores | No existe: el comprador la reconstruye con órdenes, recepciones y estados de cuenta (§2) | La propuesta del RCE en el SIRE | `cruzar_con_propuesta*` (C9) |
| Declaración | Agregada por jurisdicción (sales tax) y anual por tercero (1099) (§7) | Por comprobante y mensual (SIRE), más agregada (PDT 621) | El driver `sire` ya escribe el reemplazo |

### Lo que el Perú ya tiene y EE. UU. no

En EE. UU. el comprador no tiene una lista de lo que sus proveedores le facturaron. Por eso existen el alta del
proveedor con W-9, el emparejamiento a tres vías y la conciliación contra el estado de cuenta del proveedor. En el Perú,
SUNAT entrega esa lista: la propuesta del RCE.

| Pregunta del contador | EE. UU. responde con | Perú responde con | En el motor |
|---|---|---|---|
| ¿Me llegaron todas las facturas? | El estado de cuenta del proveedor y las tres vías | La propuesta del RCE | C9: `solo_en_propuesta`, con `pedir_a: proveedor` (§2) |
| ¿Este proveedor existe? | W-9 y TIN Matching | RUC con módulo 11 y el padrón reducido | `ruc_valido` (`contaperu/catalogos.py:94`) y C8 (§3) |
| ¿La factura es válida? | Nadie la validó | OSE y CDR | C3, `leer_cdr*` (§3) |
| ¿Ya la anoté? | El aviso de duplicado del ERP | El error 452 de SUNAT | `DUPLICADO_PERIODO_ANTERIOR` (`contaperu/validar.py:211-227`) y el hito 0.1 |
| ¿Qué declaro? | La suma propia por jurisdicción | El reemplazo de la propuesta | El driver `sire` (§7) |

### Qué tomar

Ninguna pieza nueva sale sola de esta comparación. Sale un orden de prioridad: **C9 es la ventaja que EE. UU. no
tiene, y conviene no aplazarla**. Cada etapa del diagrama tiene su sección, con lo que se toma y lo que no.

---

# Parte II · Las etapas del ciclo

## 2 · Recibir la factura

### Qué hacen: EE. UU., de la factura emitida al pasivo

**No hay validación previa ni formato legal.** Ningún fisco ve una factura B2B antes ni después de emitirla. La
obligación es llevar registros: toda persona sujeta a un impuesto llevará los registros que el Secretario del Tesoro
prescriba ([IRC §6001](https://www.law.cornell.edu/uscode/text/26/6001)), suficientes para acreditar ingresos,
deducciones y créditos ([26 CFR 1.6001-1](https://www.law.cornell.edu/cfr/text/26/1.6001-1)). La Pub 583 dice qué sirve
de sustento —facturas pagadas, recibos, cheques cobrados, estados de cuenta— ([Pub 583](https://www.irs.gov/publications/p583)),
y la Pub 463 fija la prueba documental de un gasto: monto, fecha, lugar y carácter del gasto
([Pub 463](https://www.irs.gov/publications/p463)). Los registros electrónicos deben conservarse legibles y
recuperables ([Rev. Proc. 98-25](https://www.irs.gov/pub/irs-drop/rp-98-25.pdf)). No hay un SAF-T ni un libro que se
entregue: se muestran en auditoría (*no verificado* como norma expresa: se deduce de que ninguna de esas fuentes prevé
su envío).

| Supuesto | Conservación | Fuente |
|---|---|---|
| Regla general | 3 años | [Pub 583](https://www.irs.gov/publications/p583) |
| Se omitió más del 25 % de los ingresos brutos | 6 años | [Pub 583](https://www.irs.gov/publications/p583) |
| Deducción por deuda incobrable o por valores sin valor | 7 años | [IRS](https://irs.gov/businesses/small-businesses-self-employed/how-long-should-i-keep-records) (extracto de búsqueda) |
| Registros de impuestos laborales | 4 años | [Pub 583](https://www.irs.gov/publications/p583) |

**El número fiscal del proveedor no va en la factura.** Se pide aparte con el formulario **W-9**, y quien emite
formularios 1099 lo verifica con **TIN Matching**, que solo confirma si el par nombre y número coincide
([W-9](https://www.irs.gov/instructions/iw9), [TIN Matching](https://www.irs.gov/tax-professionals/taxpayer-identification-number-tin-matching)).
Sin un número válido, el pagador retiene el 24 % (*backup withholding*). Ni la definición de factura válida para el
gobierno federal lo exige, salvo que el contrato lo pida ([FAR 52.232-25](https://www.acquisition.gov/far/52.232-25)).

**Los canales de entrega.** Ninguna fuente abierta publica el reparto por canal: ni AFP, ni Billentis, ni la Reserva
Federal lo dan.

| Canal | Qué es | ¿Obligatorio? | Calidad de la fuente |
|---|---|---|---|
| PDF por correo | El canal más común en pymes | No | Sin cifra fiable |
| Papel | Correo postal; el 26 % de los pagos B2B de EE. UU. y Canadá aún se hace con cheque ([AFP 2025](https://www.financialprofessionals.org/training-resources/resources/survey-research-economic-data/Details/digitalpayments)) | No | Encuesta de AFP, de pagos y no de facturas |
| EDI X12 810 | La factura que responde a una orden de compra 850, con el 856 de aviso de despacho y el 820 de remesa; pasa por un proveedor EDI ([X12](https://x12.org/products/transaction-sets), [Cleo](https://www.cleo.com/edi-transactions/edi-810), [SPS Commerce](https://www.spscommerce.com/edi-document/edi-810-electronic-invoice/)) | Lo exige el socio comercial: retail, manufactura, logística | *según terceros* y *según el proveedor* |
| Portal del comprador | SAP Business Network y Coupa: el proveedor «voltea» la orden de compra (*PO flip*); Coupa acepta además cXML, correo y redes ([SAP](https://www.sap.com/products/spend-management/ariba-network.html), [Coupa](https://docs.coupa.com/en/supplier-documentation/coupa-for-suppliers/the-coupa-supplier-portal-or-csp/features-and-processes-in-the-coupa-supplier-portal/invoices)) | Lo exige el comprador | Documentación del fabricante |
| Red de cuentas por pagar | AvidXchange, con más de 1,5 millones de proveedores en su red, y BILL ([AvidXchange](https://www.avidxchange.com/suppliers/), [BILL](https://www.bill.com/about-us)) | No | *según el proveedor*; BILL da cifras contradictorias en la misma página |
| DBNAlliance | Red de cuatro esquinas con UBL, nacida del piloto de la Reserva Federal y la Business Payments Coalition; lanzó una *Mass Adoption API* en nov-2025 y su primera conferencia en Nueva York el 22-abr-2026 ([DBNAlliance](https://dbnalliance.org/), [conferencia](https://www.prnewswire.com/news-releases/dbnalliance-to-host-united-states-e-invoicing-conference-in-new-york-city-on-april-22-302744325.html)) | No | No publica cifras de adopción |
| Gobierno federal, agencias civiles | Invoice Processing Platform (IPP), gratuita: más de 220 agencias y más de 200 000 proveedores ([IPP](https://www.ipp.gov/)) | Sí, por el memorando OMB M-15-19 ([OMB](https://www.whitehouse.gov/wp-content/uploads/legacy_drupal_files/omb/memoranda/2015/m-15-19.pdf), [FedWeek](https://www.fedweek.com/federal-managers-daily-report/transition-to-electronic-invoicing-omb-tells-agencies/)) | Primaria |
| Departamento de Defensa | WAWF dentro de PIEE, «la única forma electrónica aceptable» de solicitud de pago ([DFARS 252.232-7006](https://www.acquisition.gov/dfars/252.232-7006-wide-area-workflow-payment-instructions.)) | Sí | Primaria |

Billentis estima para 2026 que el 29 % de las facturas B2B del mundo son electrónicas, con Norteamérica «menor», sin
cifra propia (*según terceros*, [Qvalia](https://qvalia.com/billentis-2026-key-report-findings/)). No se encontró ningún
mandato de factura electrónica B2B, federal ni estatal, a 2026 (*según terceros*: una búsqueda no prueba una ausencia).

**Las cuentas por pagar: de la factura al pasivo.**

```
alta del proveedor ── W-9 ─► TIN Matching (sin número válido: retención del 24 %)
      │
captura ── QuickBooks: buzón @assist.intuit.com ─► extrae fecha, monto y proveedor ─► «For review»
      │    Xero: correo de la organización ─► BORRADOR con la cabecera, sin líneas
      │    NetSuite Bill Capture ─► Scanned Vendor Bills
      ▼
emparejamiento a tres vías (NetSuite, «3 Way Match Vendor Bill Approval Workflow»)
  Bill Validation ─► Quantity Tolerance ─► Quantity Difference (contra la recepción)
                  ─► Amount Validation (contra la orden de compra)
  fuera de tolerancia (en % y en diferencia absoluta, por artículo, proveedor y subsidiaria)
                  ─► Pending Approval, con «Bill Exception»
      ▼
Approved | Rejected ─► Bill o Vendor Bill (el pasivo) ─► pago ─► remesa (§6)
```

En QuickBooks Online la factura de proveedor entra por la red de QuickBooks, por carga de archivo o a mano, queda «For
review» o «Unpaid», y al guardarse crea el pasivo
([QuickBooks](https://quickbooks.intuit.com/learn-support/en-us/help-article/pay-bills/enter-bills-record-bill-payments-quickbooks-online/L1e9Ce5J7_US_en_US)).
NetSuite extrae los datos con IA a *Scanned Vendor Bills*, donde se revisan y se emparejan con proveedor, artículo y
orden de compra ([Bill Capture](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/article_164726334180.html)),
y su flujo de tres vías declara la tolerancia en porcentaje y la diferencia en importe absoluto
([flujo](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_4096454192.html),
[tolerancias](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_4168980481.html)).

**El emisor.** QuickBooks envía la factura por correo con un botón «Pay Now» si el vendedor cobra con QuickBooks
Payments ([QuickBooks](https://quickbooks.intuit.com/learn-support/en-us/help-article/invoicing/create-invoices-quickbooks-online/L7gSzvCld_US_en_US));
en retail sale un 810 por un proveedor EDI. Nada de eso pasa por un fisco.

### Qué hacen: lo abierto, las redes y las unificadas

- **Redes de factura electrónica.** Peppol usa el modelo de cuatro esquinas —emisor, su *access point*, el *access point*
  del receptor, receptor—, descubre al destinatario con SML y SMP y transporta BIS Billing 3.0, que es UBL 2.1 sobre
  EN 16931 ([e-rechnung-bund](https://e-rechnung-bund.de/en/faq/peppols-technical-solution-the-four-corner-model/),
  [BIS 3.0](https://docs.peppol.eu/poacc/billing/3.0/bis/)). **La red reparte la factura**: el receptor la recibe
  estructurada.
- **Correo.** Odoo crea facturas de proveedor desde un alias del diario de compras, avisa de duplicados y autocompleta
  desde la factura anterior del mismo proveedor ([vendor bills 17](https://www.odoo.com/documentation/17.0/applications/finance/accounting/vendor_bills.html));
  Xero da una dirección que crea **borradores** y solo acepta adjuntos
  ([Xero Central](https://central.xero.com/s/question/0D53m00009ditslCAA/where-do-i-find-my-xero-bills-email-address));
  QuickBooks lee lo reenviado y lo deja para revisar y emparejar con el banco
  ([Intuit](https://quickbooks.intuit.com/learn-support/en-us/help-article/accounts-payable/email-receipts-bills-quickbooks-online/L7r2LAQ7C_US_en_US));
  Midday tiene una bandeja con estados «emparejado», «sugerido» y «pendiente» ([documentación](https://midday.ai/docs/receipt-matching/)).
- **Extracción.** `invoice2data` usa plantillas YAML por emisor con campos obligatorios de fecha, importe y número
  ([repositorio](https://github.com/invoice-x/invoice2data)). El framework OCA `account_invoice_import` prefiere el XML
  estructurado (UBL, Factur-X), busca al proveedor por su identificador fiscal, guarda una configuración de importación
  por proveedor y, si ya hay un borrador, ofrece actualizarlo ([OCA/edi](https://github.com/OCA/edi),
  [README](https://github.com/OCA/edi/tree/12.0/account_invoice_import)).
- **APIs unificadas.** Codat exige que el proveedor exista antes de crear la factura y ofrece opciones de mapeo por
  conexión ([bills](https://docs.codat.io/payables/sync/bills)); Merge escribe la factura de proveedor como `Invoice` con
  `type=ACCOUNTS_PAYABLE` ([invoices](https://docs.merge.dev/accounting/invoices/)).
- **El flujo común**, con sus estados reales: ingesta → formato (el XML estructurado gana al PDF) → duplicado → proveedor
  por identificador fiscal → cuenta sugerida → **borrador** → contabilizado → emparejado con el pago. En Odoo,
  `account.move.state` va de `draft` a `posted` o `cancel`; en ERPNext, `docstatus` 0/1/2
  ([`purchase_invoice.py`](https://github.com/frappe/erpnext/blob/develop/erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py)).

### Perú: SUNAT liquida, pero no reparte

- El Perú tiene un modelo de **validación previa**: el OSE hace la comprobación, emite la constancia de recepción (CDR) y
  la envía a SUNAT ([OSE](https://cpe.sunat.gob.pe/informacion_general/operador_servicios_electronicos)); en SEE-Del
  Contribuyente el envío tiene su propio plazo ([SEE-Del Contribuyente](https://cpe.sunat.gob.pe/sistema_emision/see_contribuyente)).
  Los plazos se citan vigentes a la fecha de consulta. **Pero no hay una red que entregue el XML al receptor**: el CDR
  es la constancia del emisor, no del adquiriente.
- El emisor está obligado a **poner el comprobante a disposición del adquiriente en una página web durante un año**, y a
  conservar los que emite y los que recibe ([SEE-Del Contribuyente](https://cpe.sunat.gob.pe/sistema_emision/see_contribuyente)).
  En la práctica el XML llega por correo. La norma es el art. 25 de la RS 097-2012/SUNAT, en el texto de la
  RS 206-2019/SUNAT ([El Peruano](https://elperuano.pe/NormasElperuano/2019/10/22/1819173-1/1819173-1.htm)), y
  el medio lo elige el emisor.
- La **propuesta del Registro de Compras en el SIRE** trae los **hechos** de lo que los proveedores informaron, no el XML.
- Hay OSE que ofrecen recepción por correo con portal de descarga; no encontramos una API pública documentada para esos
  servicios. La descarga en SOL del XML de los comprobantes recibidos se describe en fuentes de terceros, pero *no está
  verificada* en una fuente oficial (ni la norma, ni desde cuándo, ni para qué sistemas de emisión). Se volvió a
  buscar el 14-sep-2026: el [manual de la API del SIRE de compras v24](https://cpe.sunat.gob.pe/sites/default/files/inline-files/Manual%20de%20servicios%20Web%20Api%20-%20SIRE_Compras%20v24.pdf)
  no menciona el XML, y SUNAT Virtual solo permite consultar la validez y los datos del comprobante.
- **Lo más parecido a una red con conformidad del comprador es la factura negociable.** Para las facturas y los
  recibos por honorarios electrónicos al crédito, SUNAT pone el comprobante a disposición del adquirente en su
  Plataforma de Confirmación. El adquirente tiene ocho días calendario para dar conformidad o disconformidad, y si no
  responde, la conformidad se presume (DS 239-2021-EF, arts. 6 a 8; RS 165-2021/SUNAT). Con la factura confirmada, el
  proveedor la anota en cuenta en CAVALI
  ([Plataforma de Confirmación](https://cpe.sunat.gob.pe/plataforma-de-confirmacion-del-rhe-y-de-la-fe),
  [RS 165-2021](https://busquedas.elperuano.pe/dispositivo/NL/2012062-1),
  [DS 239-2021-EF](https://busquedas.elperuano.pe/normaslegales/aprueban-el-reglamento-del-titulo-i-del-decreto-de-urgencia-decreto-supremo-no-239-2021-ef-1992708-3/)).
  No reparte todas las facturas: solo las que se venden al crédito y quieren negociarse.

La consecuencia de diseño: **el canal práctico es una bandeja** —una dirección de correo por RUC, la subida manual o la
mensajería— y **la propuesta del RCE es la lista de control** de lo que debería haber llegado.

### Qué hace ContaPerú hoy

- **Identifica por bytes y extensión.** `expandir` desarma los ZIP y `convertir_xml` convierte los XML UBL 2.1 y la
  propuesta del SIRE; los PDF y las imágenes quedan en `pendientes_ia` para que los lea la aplicación
  (`contaperu/lectores/archivos.py:78-144`). Si el mismo comprobante llega como XML y como lectura de IA, **el XML gana**
  (`clave_orden`, `contaperu/lectores/archivos.py:147`).
- **La propuesta ya se lee como comprobantes** (`sire_txt.parsear`, `contaperu/lectores/sire_txt.py:171`), con la fila
  cruda en `datos_originales`.
- **`comparar_sire` compara TXT contra TXT, campo a campo**: el reemplazo generado contra la exportación del detalle de
  SUNAT (`contaperu/comparar_sire.py`). Nació de un contraste real.
- **Los duplicados entre periodos no llegan a la fachada.** `validar.revisar(…, claves_previas)` existe y produce
  `DUPLICADO_PERIODO_ANTERIOR` (`contaperu/validar.py:211-251`), y ese código tiene hasta su `pedir_a`
  (`contaperu/operaciones.py:57`). Pero la fachada llama siempre sin `claves_previas`, así que desde la CLI o el MCP ese
  error nunca se dispara.
- **`pedir_a: proveedor` está reservado** y nadie lo usa (`contaperu/asiento/faltas.py:19`, `contaperu/operaciones.py:22`).
- **Los ítems del UBL no se modelan**: del XML se toma solo la descripción de la primera línea como `concepto`
  (`contaperu/lectores/xml_ubl.py:240-242`).

### Qué tomar

**1. `claves_previas` en la fachada** (**F**): en `revisar`, `diagnosticar`, `exportar` y el MCP. La aplicación, que
recuerda lo que ya anotó, pasa sus claves; el motor ya sabe qué hacer con ellas.

**2. `cruzar_con_propuesta*`** (**N**, y **F** para exponerla). Compara un nivel más arriba que `comparar_sire`: entre
comprobantes y por su `clave`, porque los dos lados ya son comprobantes.

```python
def cruzar_con_propuesta(cargados: list[Comprobante], propuesta: list[Comprobante]) -> dict:
    """Pura. La propuesta del RCE es la lista de control; no corrige nada."""
    p = {c.clave: c for c in propuesta}
    q = {c.clave: c for c in cargados if not c.excluida}
    return {
        "en_los_dos": [{"clave": k, "diferencias": diferencias(q[k], p[k], ("total", "base_gravada", "igv"))}
                       for k in sorted(p.keys() & q.keys())],
        "solo_en_propuesta": [{"clave": k, "motivo": "falta el XML", "pedir_a": PROVEEDOR}      # primer caso real
                              for k in sorted(p.keys() - q.keys())],
        "solo_cargados": [{"clave": k, "motivo": "no está en la propuesta: validez o anulación", "pedir_a": CONTADOR}
                          for k in sorted(q.keys() - p.keys())],
    }
```

`solo_en_propuesta` es **el primer caso real de `pedir_a: proveedor`**: SUNAT dice que la factura existe, y quien tiene
el XML es el proveedor. En `solo_cargados`, la consulta de validez la hace la aplicación y el motor recibe el resultado
como dato. Qué observación dispararía ese dato entra con la documentación del servicio de validez como fuente.

**3. `sugerir_imputacion*`** (**N**). Es el análogo determinista de la configuración por proveedor de OCA y del
autocompletado de Odoo:

```python
def sugerir_imputacion(c: Comprobante, historial: list[dict], minimo: int = 2) -> dict:
    """historial ◄ APP: [{proveedor, cuenta_contable, centro_costo}] de lo ya revisado.
    Pura y determinista (conteo). Devuelve propuestas con motivo y NUNCA escribe la imputación:
    la decide el contador en la pantalla de revisión."""
    previas = [h for h in historial if h["proveedor"] == solo_digitos(c.contraparte_doc)]
    conteo = Counter((h["cuenta_contable"], h.get("centro_costo", "")) for h in previas)
    return {"id_externo": c.id_externo, "propuestas": [
        {"cuenta_contable": cuenta, "centro_costo": centro, "motivo": f"{n} de {len(previas)} de este proveedor"}
        for (cuenta, centro), n in sorted(conteo.items(), key=lambda x: (-x[1], x[0]))[:3] if n >= minimo]}
```

```
CANALES (APLICACIÓN): correo · subida · bandeja de un OSE · web del emisor          SIRE: propuesta del RCE
      │ bytes + nombre                                                                   │
MOTOR  expandir ─► convertir_xml ─► comprobantes (origen xml)          sire_txt.parsear ─► propuesta (origen sire)
      │               └─► pendientes_ia ─► APP: IA ─► comprobante (origen vision, confianza < 1)
      ▼
validar.revisar(…, claves_previas* ◄ APP)          el XML gana a la lectura por IA (clave_orden)
      ▼
cruzar_con_propuesta* ─┬─ en_los_dos: diferencias ─────────► contador
                       ├─ solo_en_propuesta ───────────────► pedir_a: proveedor
                       └─ solo_cargados ───────────────────► contador (validez: la consulta la APP)
      ▼
sugerir_imputacion*(c, historial ◄ APP) ─► propuestas con motivo
      ▼
APP · revisión: el contador decide ─► imputacion { id_externo: … }
      ▼
diagnosticar(…, plan_de_cuentas*) ─► exportar ─► CONCAR · CONTASIS · SIRE ─► §6: emparejar con el pago
```

**Caso real que lo destraba:** la propuesta del RCE, que el motor ya lee, y el contraste que dio origen a `comparar_sire`.

**Tests que lo fijarían:**
- Los tres cajones, con un caso en cada uno.
- Una clave con ceros a la izquierda casa con la misma sin ceros.
- Un RUC de proveedor mal escrito sale como uno solo en la propuesta más uno solo cargado, que es lo correcto en compras.
- `sugerir_imputacion` desempata de forma estable, respeta el mínimo y no toca la imputación.

### Qué no se toma

- Leer `cbc:AccountingCost` (BT-19/BT-133). No hay evidencia de que los XML peruanos lo traigan, y el lector no lo lee.
  Queda como pista para cuando un XML real lo muestre. La orden de compra (`cac:OrderReference`) sí está en la guía
  de SUNAT —opcional, «Número de la orden de compra»— ([guía UBL 2.1](https://cpe.sunat.gob.pe/sites/default/files/inline-files/guia%2Bxml%2Bfactura%2Bversion%202-1%2B1%2B0%20%282%29_0%20%282%29.pdf)),
  pero leerla solo sirve con el emparejamiento a tres vías, que no se toma (§12).
- Imputar por ítem de la factura: es un hueco declarado. Hoy lo cubre el reparto de la imputación.
- **Emparejar órdenes de compra y recepciones** (las tres vías de EE. UU.). Necesita estado y las guías de remisión,
  que están fuera por decisión; de ahí solo se toma la tolerancia en dos medidas (§6).
- **Un buzón, estados de borrador o la aprobación de facturas** (QuickBooks, Xero, NetSuite). Son de la aplicación; el
  motor ya dice lo que falta (§2).
- **Redes EDI, portales, DBNAlliance o Peppol dentro del motor.** El Perú valida antes de emitir, y un canal de entrega
  es transporte.
- **La factura negociable como canal del motor.** Queda en vigilancia en la hoja de ruta: la conformidad la registra
  SUNAT y la anotación en cuenta es de CAVALI (§2).

---

## 3 · Validar antes de asentar

### Qué hacen

`REFERENCIAS.md` §3 ya recoge la idea base: Codat `GET …/options/{dataType}` y Merge `/meta` dicen qué exige el destino
antes de escribir. Lo nuevo está en **dónde se evalúa** la exigencia:

- **ERPNext** declara por empresa qué dimensiones son obligatorias según el tipo de cuenta
  ([`Accounting Dimension Detail`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/accounting_dimension_detail/accounting_dimension_detail.json):
  `mandatory_for_pl`, `mandatory_for_bs`, `default_dimension`), y qué valores permite o restringe cada cuenta
  ([`Accounting Dimension Filter`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/accounting_dimension_filter/accounting_dimension_filter.json):
  `allow_or_restrict`, `accounts`, `dimensions`). El rechazo es por línea: «Cost Center is required for 'Profit and
  Loss' account» ([`gl_entry.py`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/gl_entry/gl_entry.py)).
- **Odoo 18** lo hace por prefijo de cuenta, con puntuación: `account.analytic.applicability` marca un plan analítico
  como `optional|mandatory|unavailable` según `account_prefix` y `business_domain` (factura, compra), y
  `account.analytic.distribution.model` pone valores por defecto por socio, prefijo de cuenta o producto
  ([analytic_plan.py](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/analytic/models/analytic_plan.py),
  [account_analytic_plan.py](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_analytic_plan.py),
  [analytic_distribution_model.py](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/analytic/models/analytic_distribution_model.py)).
- **Codat** devuelve un esquema recursivo `{type, displayName, required, properties, validation{warnings, information},
  options[]}` y, al escribir, `validation.errors[{itemId, message, validatorName}]` ([push](https://docs.codat.io/using-the-api/push)).
- **Merge** tiene esquemas que dependen de una elección previa: con `has_conditional_fields`, `/meta` se llama dos
  veces, primero para elegir la plantilla y después para saber sus campos
  ([plantillas y campos condicionales](https://docs.merge.dev/merge-unified/writing-data/programmatic-writes-with-meta/templates-and-conditional-fields)).

El patrón: **la exigencia se evalúa por línea contra su cuenta**, no por destino entero. Cuando falta el dato, el orden
habitual es: valor por defecto configurado → mapeo → aviso → pedirlo.

### Qué hacen: SUNAT y los proyectos que leen su UBL

- **SUNAT publica sus reglas como una hoja de cálculo.** «Reglas de validación», actualizada al 26.08.2026
  ([guías y manuales](https://cpe.sunat.gob.pe/guias-y-manuales)), trae una fila por regla con el tag UBL, la condición,
  si es `ERROR` u `OBSERV`, su código y su mensaje, además de hojas de códigos de retorno, catálogos (Anexo 8), listados
  y un control de cambios con fecha de vigencia. El número exacto de hojas, códigos y filas es *no verificado*. Las XSL
  oficiales publicadas en la misma página son de 2022.
- **Greenter** ([monorepo](https://github.com/thegreenter/greenter), MIT) separa lo puro de lo que toca red o firma:
  `xml-parser` convierte en modelo facturas, notas, recibos, retenciones, percepciones, guías, resúmenes y bajas
  ([xml-parser](https://greenter.dev/packages/xml-parser/)); `DomCdrReader` lee del CDR `ResponseCode`, `Description`,
  `ReferenceID` y sus `Note` ([código](https://raw.githubusercontent.com/thegreenter/ws/master/src/Ws/Reader/DomCdrReader.php));
  `xcodes` y `cpe-validator` son intentos previos de llevar los códigos y las XSL oficiales a datos.
- **KoSIT y Peppol** enseñan a separar el motor de sus reglas y a probar **una regla con un caso**
  ([peppol-bis-invoice-3](https://github.com/OpenPEPPOL/peppol-bis-invoice-3)).
- **Datos públicos que un motor puede recibir sin salir a la red**: el padrón reducido del RUC
  ([SUNAT](https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html)) y el tipo de cambio publicado por SUNAT, la
  SBS o el BCRP ([API del BCRP](https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/api)).
- **Licencias.** De MIT, BSD y Apache-2.0 (Greenter, Lycet, OpenUBL) se puede portar código con su aviso; de LGPL (Odoo
  `l10n_pe`), AGPL (OCA) u OEEL (`l10n_pe_edi`) solo se toman ideas y datos oficiales.

### Qué hacen: la identidad del tercero en EE. UU.

En EE. UU. el número fiscal no viaja en la factura (§2): el pagador lo pide con el W-9 y lo contrasta con TIN Matching,
que confirma el **par** nombre y número, en red y solo para quien emite formularios 1099. Sin número válido, retiene el
24 %. En el Perú el RUC viaja en el comprobante y su dígito verificador se comprueba sin red (`contaperu/catalogos.py:94`).
Lo que TIN Matching aporta además —el nombre registrado— es lo que daría el padrón reducido del RUC recibido como dato
(C8).

**Qué tomar:** que la forma del padrón admita `razon_social*` junto a `activo*` y `habido*`, para que el aviso de no
habido muestre el nombre del padrón. **Qué no:** un aviso por diferencia de nombre, que en el Perú no tiene consecuencia
legal documentada, ni una retención calculada por el motor (§12). **Test que lo fijaría:** sin padrón no cambia nada;
con padrón, un nombre distinto no produce observación (mutación).

### Perú: el hallazgo que ordena esta sección

La plantilla oficial de importación de CONCAR, transcrita en este repositorio y verificada contra el archivo, dice lo
mismo que ERPNext y Odoo, **y lo dice por cuenta** (`contaperu/drivers/concar/datos.py:77-103`):

| Columna | Nota literal de la plantilla |
|---|---|
| K · Cuenta Contable | «Debe existir en el Plan de Cuentas» |
| L · Código de Anexo | «Si Cuenta Contable tiene seleccionado Tipo de Anexo, debe existir en la tabla de Anexos» |
| M · Centro de Costo | «Si Cuenta Contable tiene habilitado C. Costo, Ver T.G. 05» |
| R-T · Documento | «Si Cuenta Contable tiene habilitado el Documento Referencia» |
| U · Vencimiento | «Si Cuenta Contable tiene habilitada la Fecha de Vencimiento» |
| V · Área | «Si Cuenta Contable tiene habilitada el Area» |
| Y · Medio de Pago | «Si Cuenta Contable tiene habilitado Tipo Medio Pago» |
| AI-AL · Tasa | «Si la Cuenta Contable tiene configurada la Tasa» |

Y el motor ya lo reconoce: `lleva_centro` explica que «en CONCAR la marca "C. Costo habilitado" vive en cada cuenta del
plan; aquí se declara por prefijo en `cuentas_con_centro`» (`contaperu/asiento/resolucion.py:190-202`). **El prefijo es
un sustituto de un dato que existe en el destino.**

### Qué hace ContaPerú hoy

- Cada driver declara `EXIGE`: CONCAR `{"centro_costo", "moneda"}` (`contaperu/drivers/concar/datos.py:21`), CONTASIS
  `{"cuenta_unica"}` (`contaperu/drivers/contasis/datos.py:24`) y el CSV nada (`contaperu/drivers/csv/__init__.py:33`).
  `contrato.exige()` le suma lo que el núcleo exige a su familia (`contaperu/drivers/contrato.py:155`).
- Una sola tabla de faltas (`FALTAS`, `contaperu/asiento/faltas.py:121`) alimenta las dos caras: `faltantes_para`
  describe sin lanzar y `exigir_requisitos` lanza antes de llamar al driver (`contaperu/asiento/resolucion.py:271`,
  `:293`).
- `centro_costo` falta solo si la cuenta lo lleva, y eso se decide por prefijo (`cuentas_con_centro`, de fábrica
  `["62", "63", "65", "70"]`, `contaperu/configuracion.py:289`). La lista `centros_costo` se declara
  (`contaperu/configuracion.py:280`) pero el motor no comprueba contra ella.
- **La cadena de resolución de una cuenta es de un solo eslabón** (3.0): la imputación del documento, y si no la
  falta `sin_cuenta`. No hay cuenta general que la supla —`cuentas.gasto` y `cuentas.ventas` existieron hasta la
  2.7 y se retiraron: con una puesta, el motor dejaba de contar como `sin_cuenta` lo que nadie había imputado y el
  mes salía «listo» a un comodín—. Tampoco hay valor por defecto por prefijo ni por proveedor. Lo que una aplicación
  sepa de un proveedor lo mete ella en la imputación; con qué cuentas empieza una empresa lo declara su driver
  (`CUENTAS_POR_DEFECTO.compras` y `.ventas`), y eso siembra su plan, no imputa.
- El PCGE 2026 se consulta, pero no valida (`contaperu/pcge/catalogo.py`), y **nada comprueba que una cuenta exista en
  el plan del destino**. Hoy ese error aparece recién al importar el Excel en CONCAR.
- `generar_asiento` no llama a `exigir_requisitos` (`contaperu/operaciones.py:323-345`): sus líneas pueden salir sin
  centro de costo aunque el destino sea CONCAR. Es coherente con que sean «líneas de diario del estándar, sin formato de
  ningún ERP», pero conviene decidirlo explícitamente (pregunta abierta del §12).

### Qué tomar

**1. El plan de cuentas del destino como dato** (`plan_de_cuentas*`, nivel **N** para comprobar y **D** para leerlo).
Una forma neutral, `{codigo: {centro_costo: bool}}`, que la aplicación obtiene del plan exportado de su CONCAR y el
driver traduce. Solo `centro_costo` tiene hoy un caso: el que ya resuelve `lleva_centro`. Las demás marcas de la
plantilla (anexo, documento, vencimiento, área, medio de pago, tasa) entran cada una con el suyo.

**2. Una falta nueva, `cuenta_fuera_del_plan*`, bajo el requisito de núcleo `cuenta_contable`.** Así bloquea en todo
destino que lleva cuentas sin tocar el `EXIGE` de nadie. Se comprueban **todas las cuentas que el destino escribiría**,
no solo la de la imputación: una cuenta de IGV o de proveedores que no existe rechaza igual. `pedir_a` es `contador`
si la cuenta sale de la imputación y `sistema` si sale de la configuración, con el mismo criterio que ya usa
`PEDIR_A` (`contaperu/operaciones.py:50-69`).

**3. `lleva_centro` lee la marca cuando hay plan y el prefijo cuando no.**

**4. El mismo circuito que la imputación.** El plan no cabe dentro de `configuracion`: `errores_de_configuracion`
rechaza con razón las claves que no conoce (`contaperu/operaciones.py:151-153`). Llega como argumento de la fachada
—en `diagnosticar`, `exportar` y `generar_asiento`, los tres a la vez, para que «listo» signifique lo mismo que «se
exporta»— y viaja al núcleo bajo una clave reservada, igual que `imputaciones` (`contaperu/operaciones.py:203`).

```
documento ──► comprobantes ──► detracciones.normalizar ──► validar.revisar(…, claves_previas*)
configuracion ──► errores_de_configuracion ──► config_aplicada(driver)
imputacion ────► con_imputacion ──┐
plan_de_cuentas* ► con_plan* ─────┴──► config { imputaciones, plan_de_cuentas* }
                                             │
                     faltantes_para(comprobantes, config, exige(driver))
                       sin_sigla · sin_codigo_de_moneda · reparto_no_admitido · sin_cuenta ·
                       cuenta_fuera_del_plan* · reparto_que_no_cuadra · sin_centro (marca* | prefijo)
                             ┌───────────────┴────────────────┐
                    describe (no lanza)                 hace cumplir (lanza)
             diagnosticar → que_falta[].pedir_a    exigir_requisitos → NoExportable → driver
```

```python
# núcleo · asiento/resolucion.py — pseudocódigo, nombres provisionales
def lleva_centro(cuenta: str, config: dict) -> bool:
    if not config.get("usa_centros_costo", True):
        return False
    plan = config.get("plan_de_cuentas")                 # clave reservada, como "imputaciones"
    if plan is not None:                                 # la marca del destino manda
        return bool((plan.get(cuenta.strip()) or {}).get("centro_costo"))
    ...                                                  # lo de hoy: cuentas_con_centro por prefijo

def cuentas_fuera_del_plan(comprobantes, config, es_venta=False) -> list[Comprobante]:
    plan = config.get("plan_de_cuentas")
    if plan is None:                                     # sin plan no se comprueba, y diagnosticar lo dice
        return []
    def escribiria(c):                                   # las mismas cuentas que resuelve el asiento
        return [cuenta for cuenta, _centro, _importe in partes_de(c, config, es_venta)] + \
               [cuenta_tercero(c, config, es_venta)]     # + IGV, detracción… según el libro
    return [c for c in comprobantes if any(cta and cta not in plan for cta in escribiria(c))]
```

**5. En la puerta MCP**, `diagnosticar` publica su forma con `outputSchema`. Tiene que cubrir también la respuesta
temprana cuando la configuración es inválida (`_sin_configuracion`, `contaperu/operaciones.py:455`). Ver §10.

**Caso real que lo destraba:** la nota K de la plantilla, más un error de importación de CONCAR por una cuenta
inexistente. *No verificado:* qué hace exactamente CONCAR al importar una cuenta, un anexo o un centro que no existen
(la plantilla dice «debe existir», no si rechaza la fila o el archivo).

**Tests que lo fijarían:**
- Con un plan que no tiene la cuenta: `listo_para_exportar` es falso, `pedir_a` es `contador` y `exportar` lanza la
  excepción nueva.
- Sin plan: el snapshot de CONCAR sale idéntico.
- Una 63 con `centro_costo: false` en el plan no bloquea. Si `lleva_centro` ignora el plan, el test cae (mutación).

### Qué no se toma

- **Un lenguaje de requisitos declarativos** (`aplica_si{familia, libro, prefijo, rol}` con niveles). ERPNext y
Odoo lo necesitan porque ellos *son* el destino; ContaPerú escribe hacia un destino que ya guarda esa exigencia en su
plan. Tomar el dato es más corto y no inventa reglas (§12).
- **Los estados de intercambio de OCA y el `blocking_level` de Odoo** dentro del motor. Son estado de la aplicación, y la
  gradación error/aviso ya existe (`Observacion.nivel` y `FALTAS`).
- **TIN Matching o el padrón consultados en línea, y retenciones calculadas por el motor.** Lo primero es red; lo
  segundo, una regla sin un comprobante que la muestre.

---

## 4 · Asentar: identidad y trazabilidad

### Qué hacen

- **Hacia atrás**, del asiento al documento: ERPNext guarda hasta la fila (`voucher_detail_no`), SAF-T el documento
  por línea (`SourceDocumentID`) y el PLE 5.1 el registro de origen en el campo 20. En los registros, el CUO «debe ser
  el mismo consignado en el Libro Diario» ([Anexo 2](https://spij.minjus.gob.pe/Graficos/Peru/2015/Junio/30/RS-169-2015-SUNAT-ANX-2.pdf)):
  **el enlace va en los dos sentidos**.
- **Hacia delante**, de la factura a lo que la liquida: ERPNext `against_voucher` y su subledger
  [`Payment Ledger Entry`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/payment_ledger_entry/payment_ledger_entry.json)
  (con `delinked`); Odoo `account.partial.reconcile`, una tabla muchos-a-muchos con importe parcial entre líneas;
  XBRL GL `documentApplyToNumber`; el `Assignment` de [python-accounting](https://github.com/ekmungai/python-accounting).
- **Agrupar sin pisar:** el PLE prohíbe consolidar en el Libro Diario («No se permite la consolidación de
  operaciones») y, donde la admite —el Registro de Inventario Permanente Valorizado—, exige añadir al CUO «un número
  secuencial separado de un guión» y conservar el detalle ([RS 042-2018/SUNAT, anexo](https://www.sunat.gob.pe/legislacion/superin/2018/anexo-042-2018.pdf)).
- **Borrados como lápidas:** Codat `metadata.isDeleted` y la distinción entre `modifiedDate` (en Codat) y
  `sourceModifiedDate` (en el sistema de origen) ([modified dates](https://docs.codat.io/using-the-api/modified-dates));
  Merge `remote_was_deleted` ([journal entries](https://docs.merge.dev/accounting/journal-entries/)).

### Qué hace ContaPerú hoy

- Cada línea lleva `documento` —sigla, `tipo_cp`, serie-número, fechas— y, en notas, `referencia` al documento que
  corrige (`contaperu/asiento/motor.py:126-134`). La línea de la detracción apunta a su factura por `referencia`.
- **La unión línea → comprobante no es directa.** `contraparte_doc` va solo en las líneas de tercero y de detracción;
  el `serie_numero` de la línea sale formateado según el driver, mientras que `Comprobante.clave` quita los ceros; y
  `generar_asiento` devuelve el libro y las líneas, no los comprobantes (`contaperu/operaciones.py:342`). Hoy las
  líneas de un comprobante se reconocen por `(sub_diario, correlativo)`, que cambia al re-exportar.
- **La huella es por tanda** (`contaperu/asiento/huella.py:34-41`): el sha256 de todas las líneas, sin el correlativo.
  Responde bien a «¿esta tanda ya salió?», pero no a la pregunta que de verdad cuesta. Si una tanda lleva los
  comprobantes A y B y la siguiente lleva B y C, las huellas son distintas, B se importa dos veces y CONCAR la suma.
- El CSV se ofrece como la salida «más honesta», buena «para escribir un driver nuevo teniendo delante lo que hay que
  traducir» (`contaperu/drivers/csv/__init__.py:3-6`), pero sus columnas no llevan `rol` ni los `tipo_cp`
  (`contaperu/drivers/csv/__init__.py:41-65`): justo lo que un driver necesita para no adivinar.
- Ningún driver consolida: CONCAR escribe una fila por línea neutral y un asiento por comprobante.

### Qué tomar

**1. Un índice por comprobante como anotación** (`_asiento.comprobantes*`, y lo mismo en `_exportacion`; nivel **F**).
Las claves `_` solo valen en la raíz del documento (`estandar/LEEME.md`, «Anotaciones que produce el motor»), así que el
índice va ahí y **no toca la línea, ni el esquema de línea, ni el snapshot**:

```python
# fachada · generar_asiento / exportar — las líneas no cambian; solo se anota dónde empieza y acaba cada comprobante
# (lineas_del_libro ya arma las líneas comprobante por comprobante, contaperu/asiento/motor.py:208)
indice, lineas = [], []
for c in comprobantes:                                    # en el orden del libro
    propias = lineas_del_comprobante(c, …)                # las mismas de hoy
    indice.append({
        "id_externo": c.id_externo or None,               # la llave de la aplicación
        "clave": [libro.ruc, libro.tipo, *c.clave],       # la identidad estable (punto 2)
        "lineas": [len(lineas), len(lineas) + len(propias) - 1],
        "huella": huella(propias),                        # la MISMA fórmula, por comprobante
    })
    lineas += propias
salida["_asiento"]["comprobantes"] = indice               # huella(lineas) de la tanda: intacta
```

**2. La identidad estable** = `libro.ruc` + `libro.tipo` + `Comprobante.clave`, **sin el periodo**: un comprobante se
anota una sola vez por RUC (`DUPLICADO_PERIODO_ANTERIOR`, el error 452 de SUNAT, `contaperu/validar.py:211-227`), así que
la misma clave sirve también para detectar duplicados entre periodos. Es legible y no necesita un hash nuevo.

- **Cumple el papel que el PLE le da al CUO, pero no es el CUO.** El CUO lo pone el software contable que genera el
  libro; en el flujo de hoy ese software es el destino (CONCAR), no ContaPerú. El análogo del lado del SIRE es el CAR
  (*no verificado*: su composición exacta).
- **En ventas la contraparte sobra.** La serie-número del emisor ya es única, y un RUC de cliente mal escrito partiría
  la identidad en dos. `comparar_sire.py` toma la misma decisión por la misma razón (`contaperu/comparar_sire.py:70-73`).
  Decidirlo es parte de la propuesta.
- Para un destino que importa archivos, el id en el destino es (mes, sub-diario, número), que el motor ya devuelve en
  `_asiento.sub_diarios` (`contaperu/operaciones.py:343`). Por eso el `id_externo` reservado para la **línea** no tiene
  todavía caso con CONCAR: lo tendrá el primer destino con API.

**3. Hacia delante: una tabla de asignación** (`aplicaciones*`: `[{movimiento, clave, importe}]`, con parciales). Es la
salida de la conciliación del §6, y sigue a `account.partial.reconcile` y a `Payment Ledger Entry`.

**4. Cómo sigue un agente una línea hasta su papel.** Sin base de datos, con lo que ya viaja:

```
_asiento.comprobantes[k] ── lineas[i..j] ──► asiento[i..j]
        │ id_externo · clave
        ▼
comprobantes[] del documento de ENTRADA (generar_asiento no lo devuelve: el agente o la aplicación lo conserva)
        │ origen · archivo_nombre · datos_originales (el UBL leído, o la fila cruda del SIRE)
        ▼
el XML o la fila de la propuesta, que guarda la aplicación
```

**Caso real que lo destraba:** tandas de CONCAR que se solapan, que la huella por tanda no detecta, y el comprobante
que cambió después de exportarse (§5).

**Tests que lo fijarían:**
- Los rangos del índice cubren `0..n-1` sin huecos ni solapes.
- Las líneas de cada rango cuadran solas.
- El literal de `tests/test_huella.py:24` no cambia.
- Otro punto de partida del correlativo da la misma huella por comprobante; un céntimo da la misma clave con otra huella.

**Esperan un caso:** `trazas*`, la tabla fila-de-destino → líneas neutrales para el primer driver que consolide
(test: partición exacta e importes que suman); y `documento.id_externo` dentro de la línea, para el primer driver
`desde_lineas` que necesite el id del origen, que es lo único que ve (`contaperu/drivers/contrato.py`).

### Qué no se toma

- **Llamar CUO a la identidad del §4, o hacerla un hash opaco.** El CUO es del software que genera el PLE, y una clave
  legible se puede leer en un error.
- **Una huella de la configuración aplicada.** Metería las imputaciones en la huella y no tiene caso.

---

## 5 · Exportar al destino: inmutabilidad, sistemas legacy y cualquier ERP

### Qué hacen: inmutabilidad y concurrencia

- **Nunca se edita lo contabilizado; se revierte.** `REFERENCIAS.md` §5 ya lo recoge. Lo nuevo es que revertir obliga a
  elegir **la fecha**. ERPNext, con `enable_immutable_ledger`, asienta la cancelación en su propia fecha
  ([documentación](https://docs.frappe.io/erpnext/user/manual/en/immutable-ledger-in-erpnext)); Formance permite
  revertir en la fecha del original (`atEffectiveDate`) y separa la fecha del hecho (`timestamp`) de la de inserción
  (`insertedAt`); el PLE usa el estado 9 con el CUO original en vez de tocar el periodo cerrado.
- **La excepción controlada existe**, y tiene nombre: ERPNext
  [`Repost Accounting Ledger`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/repost_accounting_ledger/repost_accounting_ledger.json),
  sometible y limitado por `repost_allowed_types`.
- **Bloqueos en capas.** Odoo 18 tiene fechas de bloqueo por impuesto, venta, compra y ejercicio, y una `hard_lock_date`
  «irreversible and does not allow any exception»; las excepciones a las demás se registran con usuario, motivo y
  caducidad en `account.lock_exception` ([company.py](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/company.py),
  [account_lock_exception.py](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_lock_exception.py)).
- **Integridad demostrable:** hash encadenado y secuencia sin huecos en Odoo
  ([inalterabilidad](https://www.odoo.com/documentation/18.0/applications/finance/accounting/reporting/data_inalterability.html))
  y en el log de Formance («SHA256 hash of the log entry, chained from the previous log»).
- **Concurrencia sin duplicados:** TigerBeetle usa el `id` del cliente como clave de idempotencia y encadena
  transferencias atómicas con el flag `linked` ([linked events](https://docs.tigerbeetle.com/coding/linked-events/)). El
  patrón *transactional outbox* garantiza que un mensaje sale solo si la transacción se confirma, y exige consumidores
  idempotentes ([microservices.io](https://microservices.io/patterns/data/transactional-outbox.html)). django-hordak
  llega a hacer cumplir el cuadre con un *trigger* en la base
  ([documentación](https://django-hordak.readthedocs.io/en/latest/hordak-database-triggers.html)).
- **Lo que se usó, congelado en el asiento:** ERPNext guarda en cada `GL Entry` el tipo de cambio de la transacción
  (`transaction_exchange_rate`) junto a los importes en cada moneda.

### Qué hacen: los sistemas de escritorio sin API

En EE. UU., los sistemas de escritorio sin API se integran en tres escalones, y cada uno tiene su
análogo peruano:

| Escalón | EE. UU. | Aquí |
|---|---|---|
| **1 · Archivo** | QuickBooks Desktop importa **IIF**, texto tabulado con `!TRNS`/`!SPL`/`!ENDTRNS`, con «only limited error checking» ([Intuit](https://quickbooks.intuit.com/learn-support/en-us/help-article/list-management/iif-overview-import-kit-sample-files-headers/L5CZIpJne_US_en_US)) | El Excel de CONCAR y el de CONTASIS |
| **2 · SDK o API local** | **qbXML** (`JournalEntryAddRq` con líneas de débito y crédito) | La API web de STARSOFT Contabilidad Gold Edition (`POST Api/RegistrarAsientoCompras`, `…Ventas`, `…Standar`…; [ayuda](https://starsoftweb.com/apisintegracion/Help)). Su forma campo a campo, comparada con las API de EE. UU. y con EN 16931, en [API-DE-REGISTRO.md](API-DE-REGISTRO.md) |
| **3 · Agente en la PC del cliente** | **QuickBooks Web Connector**: un `.QWC` y un servicio SOAP al que «QuickBooks llama» (`authenticate`, `sendRequestXML`, `receiveResponseXML`; [guía](https://static.developer.intuit.com/qbSDK-current/doc/pdf/QBWC_proguide.pdf)). Codat y Rutter lo usan con **escrituras en cola** y restricciones declaradas: la PC encendida, un usuario, horario de sincronización ([Codat](https://docs.codat.io/integrations/accounting/quickbooksdesktop/accounting-quickbooksdesktop/), [Rutter](https://docs.rutter.com/platforms/accounting/qbd)) | Un conector local, **de la aplicación y nunca del motor** |

### Qué hacen: la puerta abierta para cualquier ERP

- **Un contrato publicado es la fuente de todo lo demás.** Codat genera sus SDKs de TypeScript, Python, Go y C# desde su
  OpenAPI con Speakeasy ([caso](https://www.speakeasy.com/customers/codat)); Apideck publica sus especificaciones con
  licencia MIT ([openapi-specs](https://github.com/apideck-libraries/openapi-specs)); Merge usa Fern y Xero OpenAPI
  Generator ([Xero-OpenAPI](https://github.com/XeroAPI/Xero-OpenAPI)); Stainless genera SDKs y también servidores MCP
  desde OpenAPI ([stainless](https://www.stainless.com/)). OpenAPI 3.1 es compatible con JSON Schema 2020-12, la versión
  del esquema del estándar.
- **Motor y reglas se versionan aparte.** El validador de XRechnung de KoSIT es un solo motor con tres modos —CLI,
  librería y demonio HTTP— y sus reglas viven en otro repositorio con su propia versión
  ([validator](https://github.com/itplr-kosit/validator), [configuración](https://github.com/itplr-kosit/validator-configuration-xrechnung)).
- **Entrar tiene reglas escritas.** Airbyte distingue conectores *Certified* y *Community* y pide para contribuir una
  discusión previa, tests, documentación y un sandbox ([guía](https://docs.airbyte.com/platform/contributing-to-airbyte/submit-new-connector));
  Xero certifica a sus socios con puntos de control ([checkpoints](https://developer.xero.com/documentation/xero-app-store/app-partner-guides/certification-checkpoints))
  e Intuit evalúa toda app antes de producción ([requisitos](https://developer.intuit.com/app/developer/qbo/docs/go-live/publish-app/technical-requirements)).
- **Embeberse en un ERP abierto es un patrón conocido.** Un módulo de Odoo declara `external_dependencies` y no se instala
  si faltan ([manifiesto](https://www.odoo.com/documentation/18.0/developer/reference/backend/module.html)); una app de
  Frappe engancha `doc_events` (`validate`, `on_submit`) y ERPNext localiza con `regional_overrides`
  ([hooks](https://docs.frappe.io/framework/user/en/python-api/hooks)).

### Qué hace ContaPerú hoy

- **El núcleo no tiene problema de concurrencia, porque no tiene estado.** No sale a la red, no lee el entorno ni mira el
  reloj, y los tests lo hacen cumplir (`tests/test_frontera.py:75-106`). Dos matices:
  - **El disco no tiene test.** Leer datos empaquetados es aceptable (el catálogo del PCGE con `lru_cache`,
    `contaperu/pcge/catalogo.py:27`), pero `comparar_sire.leer` abre una ruta del usuario (`contaperu/comparar_sire.py:77-80`),
    que es trabajo de la puerta.
  - `validar.revisar` y `detracciones.normalizar` escriben sobre los comprobantes que reciben. En la fachada es seguro,
    porque cada llamada construye los suyos; no lo sería si una aplicación compartiera objetos entre hilos.
- **Las tres fechas ya existen.** La del hecho es `documento.fecha_emision`; la contable, `linea.fecha`, acotada al periodo
  (`contaperu/asiento/motor.py:114-119`); la de registro, `_exportacion.fecha`, que pone quien llama. SAF-T
  (`TransactionDate`, `GLPostingDate`, `SystemEntryDate`) y Formance son una tabla de equivalencias, no una propuesta.
- **El tipo de cambio ya va congelado en cada línea**, pero como `float` (`contaperu/asiento/motor.py:111`, y la tasa de
  la detracción en `:71`), contra la regla de `Decimal` de punta a punta.
- **El único contador compartido es el correlativo** por sub-diario y mes. El motor numera desde el punto de partida que
  le dan (`contaperu/asiento/resolucion.py:205`) y devuelve los rangos que usó, pero el contador vive en la aplicación:
  dos exportaciones simultáneas con el mismo punto de partida chocan en el destino.
- **Una tensión declarada.** `estandar/LEEME.md` («La detracción, que ocurre en dos tiempos») dice que, al pasar a
  `PAGADO`, «el asiento puede regenerarse con el número real». Si ese asiento ya se importó en un destino que suma,
  regenerarlo lo duplica, y la huella distinta impide reconocerlo. Hoy es una frase del documento, no código: el motor
  escribe siempre el número comodín (`NUMERO_DETRACCION_PENDIENTE`, `contaperu/asiento/configuracion.py:22`).

### Qué tomar

**1. Una tabla de decisión por comprobante**, con la identidad y la huella del §4. La consulta la aplicación, que es la
que recuerda qué exportó:

| ¿La identidad ya se exportó a ese destino? | ¿La huella es la misma? | Qué es | Qué se hace |
|---|---|---|---|
| no | — | nuevo | sale en la tanda |
| sí | sí | ya salió | no se repite |
| sí | no | cambió después de exportarse | **no se regenera**: lo resuelve el contador en el destino, con fuente (el análogo del estado 9 del PLE) |

**2. Corregir la frase del LEEME** sobre la detracción regenerada: cómo se resuelve el segundo tiempo (un asiento
complementario, un asiento del pago o la corrección en el destino) es una decisión contable con fuente y archivo real, y
el estándar no debe adelantarla.

**3. El tipo de cambio y la tasa de la detracción como texto en la línea**, con el `float` solo al escribir la columna.
Tiene costo, y hay que decirlo: la huella de toda tanda en dólares o con detracción cambia, y la fórmula es contrato
(`contaperu/asiento/huella.py:20-23`). Es un cambio de comportamiento que se anuncia en el `CHANGELOG`.

**4. La versión del motor en `_asiento` y `_exportacion`**, fuera de la huella: cuando un cambio de comportamiento se
anuncia, quien guardó una tanda necesita saber con qué versión salió.

**5. Para la aplicación, como orientación de ingeniería** (no hay fuente contable detrás):
- La fuente de verdad es una base relacional; lo exportado no se edita.
- La exportación y el rango de correlativos que consumió se registran **en la misma transacción, antes de entregar el
  archivo** (el outbox aplicado a un Excel).
- Solo se cachean **hechos inmutables**: el tipo de cambio publicado para una fecha, el plan de cuentas de una versión.
  Un diccionario en memoria basta a la escala de un estudio contable; un caché compartido (Redis) solo se justifica con
  varios procesos, y sigue siendo seguro solo porque lo cacheado no cambia. **Nunca** se cachean imputaciones ni
  configuración.

```
APLICACIÓN (con estado)                                   MOTOR (sin estado)
documentos · imputaciones · configuración ─────────────►  diagnosticar / exportar
claves ya anotadas ───────── claves_previas* ──────────►
plan del destino ──────────── plan_de_cuentas* ────────►
                              ◄──── bytes + _exportacion { huella, comprobantes*[clave, huella],
                                                           sub_diarios, motor* }
registra la exportación + el rango de correlativos (una transacción) ─► entrega ─► destino (SUMA)
```

**6. Hacia un sistema legacy.** La escritura hacia un legacy es asíncrona y se confirma después —el nombre reservado `estado` de la
línea, `exportado → importado`, lo pondrá quien importó—, y las limitaciones del destino se declaran antes de escribir
(`EXIGE`, `no_caben`).

### Qué no se toma

- **Log con hash encadenado, secuencia sin huecos, fechas de bloqueo.** Son estado: de la aplicación o del ERP de
  destino, nunca del motor.
- **Guardar aparte el tipo de cambio usado, o tres fechas nuevas.** Ya van en la línea y en `_exportacion` (§5).
- **`Idempotency-Key`, webhooks y sincronización incremental.** Descartados en `REFERENCIAS.md` por la misma razón: el
  motor no habla con otra API con estado.
- **Redis como recomendación contable.** No hay una fuente contable que la respalde; queda como nota de ingeniería para
  la aplicación (§5).

---

## 6 · Pagar y conciliar: el banco

### Qué hacen: los formatos

| Formato | Qué es | Lo que sirve para conciliar |
|---|---|---|
| **ISO 20022 camt.052 / camt.053 / camt.054** | Mismo esqueleto: reporte intradía, extracto (con saldo obligatorio) y **aviso de cargo o abono**, que es el *push* | `Ntry/Amt`, `CdtDbtInd`, `Sts` (BOOK/PDNG/INFO), `BookgDt`, `ValDt`, `AcctSvcrRef`, `BkTxCd`, `TxDtls/Refs/EndToEndId`, `RltdPties`, `RmtInf/Ustrd` y `RmtInf/Strd` ([guía de mensajes camt.054 de Standard Chartered](https://www.sc.com/en/uploads/sites/66/content/docs/Standard-Chartered-ISO-20022-message-formatting-guideline-for-camt.054.pdf)) |
| **SWIFT MT940 / MT942** | Extracto diario / reporte intradía | `:61:` (fecha valor, D/C, importe, tipo, referencia del cliente, `//` referencia del banco) y `:86:` con subcampos en las variantes estructuradas ([Danske Bank](https://danskeci.com/-/media/pdf/danskeci-com/swift-mt/reconciliation/mt940_structured.pdf), [MT942](https://developer.huntington.com/enterprisepayments/docs/swift-mt942-intra-day)) |
| **BAI2** | Estándar de EE. UU. | Registro `16` de transacción con código de tipo ([Huntington](https://developer.huntington.com/enterprisepayments/docs/bai2)) |
| **OFX** | Descarga para pymes y particulares | `FITID`, el id único de la transacción y la llave antiduplicado ([especificación de FNB](https://www.online.fnb.co.za/rhelp_0_15/Downloads/Statement_File_Specifications/Statement_Type_-_OFX.pdf)) |

### Qué hacen: el push y el pull

- **Plaid Transactions Sync** ([API](https://plaid.com/docs/api/products/transactions/)): llega el webhook
  `SYNC_UPDATES_AVAILABLE`, se llama a `/transactions/sync` con el cursor guardado mientras `has_more`, se aplican
  `added`, `modified` y `removed`, y se guarda `next_cursor`. La lección que importa: **una transacción pendiente no se
  confirma, se reemplaza**. Sale en `removed` y la definitiva entra en `added` con otro `transaction_id` y
  `pending_transaction_id` apuntando a la anterior; el nombre y el importe pueden cambiar
  ([datos de transacciones](https://plaid.com/docs/transactions/transactions-data/)).
- **GoCardless Bank Account Data** cubre el EEE bajo PSD2, con bancos que limitan las consultas por día
  ([documentación](https://docs.gocardless.com/bank-account-data/overview)), y según su propia página tiene cerradas las
  altas nuevas ([aviso](https://bankaccountdata.gocardless.com/new-signups-disabled)).
- **Codat Bank Feeds** empuja transacciones bancarias **hacia** el software contable: una cuenta origen que el cliente
  mapea (`pending` → `linked`) y lotes de hasta 1000 transacciones con `pushOperation` asíncrono; en QuickBooks, «Success»
  no significa visible todavía ([crear la cuenta](https://docs.codat.io/bank-feeds/create-account),
  [enviar transacciones](https://docs.codat.io/bank-feeds/pushing-transactions)).
- **Xero Bank Feeds** (solo para entidades socias) recibe extractos con saldo inicial y final que deben cuadrar, y usa el
  `transactionId` de cada línea para detectar duplicados ([OpenAPI](https://github.com/XeroAPI/Xero-OpenAPI/blob/master/xero_bankfeeds.yaml)).
- **Open Banking UK** notifica con un único evento, `resource-update`, que no trae la transacción: solo dice «vuelve a
  leer» ([perfil de notificación de eventos](https://openbankinguk.github.io/read-write-api-site3/v3.1.10/profiles/event-notification-api-profile.html)).
  El *push* bancario, en la práctica, es un aviso más un *pull*.

### Qué hacen: los proyectos abiertos

- **Odoo**: cada línea de extracto crea al instante un asiento contra la **cuenta transitoria** del diario, y conciliar
  reemplaza esa línea por la contrapartida real
  ([documentación 17](https://www.odoo.com/documentation/17.0/applications/finance/accounting/bank/reconciliation.html),
  [`account_bank_statement_line.py`](https://raw.githubusercontent.com/odoo/odoo/17.0/addons/account/models/account_bank_statement_line.py)).
  Las reglas (`account.reconcile.model`) combinan etiqueta con `contains`/`match_regex`, rango de importe, socio,
  tolerancia de pago y un mapeo regex → socio ([código 17](https://raw.githubusercontent.com/odoo/odoo/17.0/addons/account/models/account_reconcile_model.py)).
  La edición 19 las simplificó; el detalle de qué se retiró es *según terceros*.
- **OCA** importa camt, camt.054, OFX y hojas de cálculo, y pone una restricción `unique(unique_import_id)`: «una
  transacción bancaria solo puede importarse una vez» ([bank-statement-import](https://github.com/OCA/bank-statement-import),
  [código](https://raw.githubusercontent.com/OCA/bank-statement-import/18.0/account_statement_import_base/models/account_bank_statement_line.py)).
  En la rama 18.0 no hay módulo MT940.
- **ERPNext** **no** asienta al importar: crea un `Bank Transaction` (Pending, Unreconciled, Reconciled, Settled) con
  `transaction_id` para duplicados y una tabla hija de pagos con el importe asignado
  ([documentación](https://docs.frappe.io/erpnext/user/manual/en/bank-transaction)). Su herramienta de conciliación
  puntúa de forma **aditiva y explicable**: uno más por referencia que coincide, por importe igual y por socio igual
  ([`bank_reconciliation_tool.py`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/bank_reconciliation_tool/bank_reconciliation_tool.py)).
- **Midday** empareja movimientos con los recibos de su bandeja con pesos (50 % *embedding*, 35 % importe, 10 % moneda,
  5 % fecha) y umbrales, y solo automatiza un patrón de comercio tras confirmaciones repetidas, *según su artículo*
  ([motor de conciliación](https://midday.ai/updates/automatic-reconciliation-engine/)).
- **Blnk** declara reglas `{field, operator, allowable_drift}` —la tolerancia en % para importes y en segundos para
  fechas— y estrategias `one_to_one`, `one_to_many` y `many_to_one`
  ([reglas](https://docs.blnkfinance.com/reconciliations/matching-rules),
  [estrategias](https://docs.blnkfinance.com/reconciliations/strategies.md)).
- **Deduplicación en el resto:** Actual Budget no admite dos veces el mismo `imported_id` y, sin id, busca importe, fecha
  cercana y beneficiario parecido ([importar](https://actualbudget.org/docs/transactions/importing/)); Firefly III
  combina un identificador externo con un hash
  ([detección de duplicados](https://docs.firefly-iii.org/references/data-importer/duplicate-detection/)).
- **Aprender sin estado en el motor:** `smart_importer` entrena un clasificador con las entradas ya existentes del libro
  y lo aplica al importar ([repositorio](https://github.com/beancount/smart_importer)); hledger usa reglas CSV con `if`
  por regex ([manual](https://hledger.org/1.40/hledger.html#csv)).

### Qué hacen: EE. UU., de verdad

- **El banco no empuja: un tercero agrega.** QuickBooks Online recibe las transacciones por agregación, las descarga cada
  noche y **solo las contabilizadas**. Las muestra en una bandeja *Pending / Posted / Excluded* (nombres de 2026,
  [Intuit](https://quickbooks.intuit.com/learn-support/en-us/help-article/matching-rules/learn-updates-new-ai-powered-banking-page/L0hR7A9Zf_US_en_US)).
  Sugiere *Match* con el mismo importe en una ventana de 90 días antes a 20 después, y no sugiere cuando una comisión
  alteró el importe o varios cobros se depositaron juntos ([Intuit](https://quickbooks.intuit.com/learn-support/en-us/help-article/bank-feeds/match-online-bank-transactions-quickbooks-online/L6qyw0PvP_US_en_US)).
  Sus **reglas** tienen hasta 5 condiciones (*contiene*, *no contiene*, *es exactamente*) y **una regla gana a la
  sugerencia de la IA** ([reglas](https://quickbooks.intuit.com/learn-support/en-us/help-article/banking/set-bank-rules-categorize-online-banking-online/L0mjJl0nD_US_en_US)).
  Lo de alta confianza se confirma en lote (*Ready to post*) y las transferencias entre cuentas propias se emparejan
  solas (*Pair*). *Según el proveedor.*
- **Xero** suma *Find & Match* (varias facturas contra una línea) y *cash coding*; su `BankTransaction.Type` distingue
  `RECEIVE`, `SPEND` y sus variantes de transferencia, anticipo y sobrepago ([OpenAPI](https://raw.githubusercontent.com/XeroAPI/Xero-OpenAPI/master/xero_accounting.yaml)).
- **FDX es el modelo de la transacción**: `transactionId`, `status` `PENDING|POSTED|AUTHORIZATION|MEMO`, `debitCreditMemo`,
  fechas de transacción y de contabilización, `referenceTransactionId` para la reversión e importe siempre positivo
  (*según Plaid Core Exchange 6.4*, [referencia](https://plaid.com/core-exchange/docs/reference/6.4/)).
- **El push llega por el agregador y es un aviso.** Yodlee avisa cada 15 minutos con un enlace para releer
  ([Yodlee](https://developer.yodlee.com/resources/yodlee/data-extracts/docs/event_notification)); MX no garantiza orden
  y repite ([MX](https://docs.mx.com/resources/webhooks/)). Un webhook es una orden de releer la fuente, nunca un hecho.
- **Los procesadores de pago pasan por una cuenta de compensación.** Stripe lista cada liquidación con bruto, comisión y
  neto (`balance_transactions?payout=`) y avisa cuando está lista para conciliar
  ([Stripe](https://docs.stripe.com/payouts/reconciliation)); la cuenta *clearing* recibe la venta en bruto, paga la
  comisión, entrega el neto al banco y queda en cero.
- **La regulación no es lo que lo hizo posible.** La regla 1033 de la CFPB está suspendida por un juez desde el
  29-oct-2025 y en reconsideración ([ABA](https://bankingjournal.aba.com/2025/11/kentucky-federal-court-enjoins-cfpb-from-enforcing-current-1033-final-rule/)):
  lo que funciona se apoya en acuerdos, agregación y un estándar.

### Qué hacen: el pago, la remesa y el fraude en EE. UU.

| Riel | Límite por operación | Remesa | Fuente |
|---|---|---|---|
| Same Day ACH | US$1 millón; US$10 millones desde el 17-sep-2027 | En CTX, un 820 en los registros adicionales (*según terceros*) | [Nacha](https://www.nacha.org/news/same-day-ach-payment-limit-increase-10-million) |
| FedNow | US$10 millones desde nov-2025 | ISO 20022 | [FRB Services](https://www.frbservices.org/news/press-releases/090525-fednow-transaction-limit-increase) |
| RTP (The Clearing House) | US$10 millones (*según terceros*) | ISO 20022 | — |
| Tarjeta virtual | — | La del emisor de la red | [AvidXchange](https://www.avidxchange.com/suppliers/) (*según el proveedor*) |
| Cheque | — | En papel | 26 % de los pagos B2B ([AFP 2025](https://www.financialprofessionals.org/training-resources/resources/survey-research-economic-data/Details/digitalpayments)) |

La remesa puede viajar separada del pago con el mensaje `remt.001` de ISO 20022, según la guía de prácticas de ASC X9
([X9](https://x9.org/iso-20022-remittance-market-practices-guide/)).

**El riesgo dominante no es tributario: es el fraude.** En la encuesta de AFP de 2026, el 76 % de las empresas sufrió
fraude intentado o consumado en 2025, y el 74 % fue afectado por suplantación del correo corporativo (BEC), cuyo
objetivo típico es cambiar la cuenta bancaria de un proveedor
([AFP 2026](https://www.financialprofessionals.org/about/learn-more/press-releases/Details/over-75-percent-of-us-firms-experienced-payments-fraud-in-2025-while-ai-adoption-for-fraud-mitigation-lags)).
El FBI recomienda confirmar todo cambio de cuenta por un segundo canal, llamando a un número ya conocido y no al que
viene en el correo, y exigir doble aprobación ([IC3, 2017](https://www.ic3.gov/PSA/2017/PSA170504),
[IC3, 2024](https://www.ic3.gov/PSA/2024/PSA240911)). Nacha hizo obligatorio el monitoreo de fraude en ACH: fase 1 el
20-mar-2026 y fase 2 el 19-jun-2026
([Nacha](https://www.nacha.org/rules/risk-management-topics-fraud-monitoring-phase-1)).

**La tolerancia al emparejar.** El flujo de tres vías de NetSuite declara la tolerancia en dos medidas —porcentaje y
diferencia absoluta— y lo que queda fuera no se aprueba solo: pasa a excepción con motivo (§2).

### Perú: lo confirmado y lo que no

**Confirmado:**
- **No hay *open finance* vigente.** La SBS está en su hoja de ruta y, según terceros, la regulación se espera hacia 2027
  ([IUPANA](https://iupana.com/2025/11/25/es-el-proyecto-mas-importante-que-tiene-la-sbs-dice-el-regulador-financiero-sobre-el-open-finance-en-peru/)).
  La interoperabilidad que impulsa el BCRP es **de pagos, no de datos de cuenta**
  ([BCRP](https://www.bcrp.gob.pe/sistema-de-pagos/interoperabilidad/estrategia-de-interoperabilidad-de-los-pagos-minoristas.html)).
- **Los movimientos llegan hoy por archivo.** El BCP ofrece Host to Host por SFTP con archivos de recaudación
  ([viabcp](https://www.viabcp.com/empresas/cobranzas-y-pagos/telecredito/host-to-host)) y anunció APIs de empresa con
  consulta de movimientos, *según terceros* ([ecommercenews](https://www.ecommercenews.pe/pagos-online/2026/bcp-optimiza-la-gestion-de-pagos-y-transferencias-de-empresas-con-apis-y-host-to-host.html/)).
  Hay agregadores que listan la banca de empresas peruana con un endpoint de movimientos, *según el proveedor*
  ([Prometeo](https://docs.prometeoapi.com/docs/per%C3%BA)).
- **Los sistemas contables peruanos concilian importando Excel** ([CONCAR CB](https://realsystems.com.pe/concar/concar-cb/),
  [Starsoft](https://www.starsoft.com.pe/prod_contabilidad.html)).
- **ITF:** 0,005 % (TUO de la Ley del ITF, DS 150-2007-EF, art. 10, con la tasa de la Ley 29667), retenido por las
  empresas del sistema financiero (art. 16) y deducible para el Impuesto a la Renta (art. 19)
  ([TUO](https://www.sunat.gob.pe/legislacion/itf/ds150_07.htm)).
- **Detracciones:** el depósito masivo se hace con un TXT por SOL
  ([orientación SUNAT](https://orientacion.sunat.gob.pe/02-deposito-de-detracciones-aspecto-generales)), y la constancia
  la genera SOL cuando el Banco de la Nación comunica el pago
  ([orientación SUNAT](https://orientacion.sunat.gob.pe/3145-03-constancia-de-deposito-de-detraccion-empresas)): **no
  hay un formato de máquina documentado para la constancia**.

**No confirmado:** que algún banco peruano entregue MT940 o camt; APIs públicas de movimientos de BBVA Perú, Interbank o
Scotiabank Perú; la cobertura de otros agregadores; el formato posicional del TXT de detracciones campo por campo.

**Canales, a la fecha de consulta** (13-sep-2026; la tabla venía de la hoja de ruta):

| Canal | Qué hay | Calidad |
|---|---|---|
| Pasarelas | Culqi con webhooks ([docs](https://docs.culqi.com/es/documentacion/pagos-online/webhooks/)); Niubiz con callback firmado `NBZ-Signature` ([docs](https://desarrolladores.niubiz.com.pe/docs/api-callback-de-pago-link.md)); Izipay con IPN y `kr-hash`; Mercado Pago con webhooks `x-signature` y un **reporte de liquidaciones por API** con columnas documentadas ([MP](https://www.mercadopago.com.pe/developers/es/docs/checkout-pro-preferences/additional-content/reports/released-money/report-use)) | Según el proveedor |
| Yape y Plin | Yape Empresa descarga reportes de 90 días, sin API; Yape en línea entra por las pasarelas; Plin no publica API y solo se ve como abono en el extracto | Según el proveedor |
| APIs de bancos | BBVA Perú anuncia API Pay con saldos y movimientos en tiempo real ([BBVA](https://www.bbva.com/es/pe/innovacion/bbva-impulsa-la-transformacion-digital-empresarial-a-traves-de-sus-apis/)); APIs de empresa del BCP | BBVA según el banco; BCP según terceros |
| Extractos | Excel o TXT de la banca por internet; MT940 en los bancos grandes | MT940 según terceros; columnas sin fuente |
| Agregadores | Prometeo consulta movimientos por sondeo con las credenciales del usuario | Según el proveedor |
| Regulación | SBS: lineamientos de finanzas abiertas del 20-jul-2026 que priorizan ahorro y tarjetas de crédito, sin cuentas corrientes ni empresas; regulación hacia 2027. BCRP: pagos inmediatos con alias, interoperabilidad de pagos y no de datos | Según terceros |

Las dos listas no se contradicen, pero conviene leerlas juntas: el MT940 de los bancos grandes solo consta *según
terceros*, y los lineamientos de finanzas abiertas de la SBS del 20-jul-2026 no cambian que no haya regulación vigente.

### Qué hace ContaPerú hoy

- **Nada de banco.** Existen solo `condicion_pago` en el comprobante, `medio_pago` como configuración de CONTASIS (y
  reservado en el estándar) y la columna Y de CONCAR, que el motor no llena y que la plantilla exige cuando la cuenta
  tiene habilitado el medio de pago (§3).
- **La conciliación de constancias de detracción está pendiente de un archivo real** (`contaperu/detracciones.py:109-112`,
  [ARQUITECTURA.md](ARQUITECTURA.md) «Hoja de ruta»). Pero la mitad ya está: `diagnosticar` lista las detracciones que
  esperan constancia (`_detraccion_pendiente`, `contaperu/operaciones.py:405`), y el monto en soles enteros ya tiene su
  regla con fuente (`monto_detraccion`, `contaperu/detracciones.py:57`).
- **Dos trampas verificadas para un lector de extractos.** Un `.xlsx` empieza por `PK\x03\x04` y el lector lo toma por
  ZIP y lo desarma (`contaperu/lectores/archivos.py:56-58`, `:78-110`). Y un `.txt` es un archivo «auxiliar» que se ignora
  en silencio salvo que sea la propuesta del SIRE (`contaperu/lectores/archivos.py:26`, `:39-43`).

### Qué tomar

**1. El movimiento, con el vocabulario de camt** (`Movimiento*`, **N**). Es el formato más completo y el que otros
traducen; un Excel peruano se proyecta hacia él, no al revés:

```python
Movimiento* = {
    "cuenta_banco": "…", "moneda": "PEN", "importe": "1500.00",      # texto exacto, siempre positivo
    "sentido": "cargo|abono",
    "contabilizado": True,                  # BOOK/PDNG de camt — NO se llama `estado`: ya tiene tres sentidos
    "fecha_contable": "AAAA-MM-DD", "fecha_valor": "AAAA-MM-DD",
    "referencia_banco": "…",                # AcctSvcrRef / número de operación
    "referencia_extremo": "…",              # EndToEndId, si viene
    "contraparte": {"nombre": "…", "documento": "…", "cuenta": "…"},
    "descripcion": "…", "codigo_banco": "…",  # BkTxCd o el código propio del banco
    "datos_originales": {},                 # la fila cruda, que el motor transporta y no lee
}
```

**2. El primer lector es el archivo real de un banco peruano**, con la misma regla que un driver: un formato que nadie ha
entregado no se lee. Lo que haya que corregir en la clasificación de entradas (un libro de Excel antes que un ZIP, un TXT
de banco que no es auxiliar) entra con él.

**3. Primero se empareja y después se asienta** —como ERPNext, no como la cuenta transitoria inmediata de Odoo—, porque
el destino suma: con transitoria, cada movimiento produciría un asiento transitorio y otro de reclasificación, dos
importaciones por hecho. La cuenta transitoria queda como opción del contador para lo que siga sin pareja al cierre, y la
cuenta sale de la configuración, nunca del motor.

**4. Deduplicar** por la referencia del banco o, si falta, por una huella determinista (cuenta, fecha contable, importe,
descripción y ordinal dentro del día), como `FITID`, `unique_import_id` o `imported_id`. **Solo lo contabilizado se
propone**; lo pendiente informa y nada más (la lección de Plaid).

**5. `conciliar*`, una función pura** (**N**):

```python
def conciliar(movimientos: list[dict], pendientes: list[dict], reglas: dict) -> dict:
    """Propone parejas; no asienta ni guarda. Puntaje aditivo y explicable (como ERPNext): cada
    motivo suma y se dice. Los pesos y la tolerancia son provisionales y se calibran con el archivo real.
    `pendientes` y lo aprendido del historial llegan como datos desde la aplicación."""
    propuestas, sin_pareja, informativos = [], [], []
    for m in movimientos:
        if not m["contabilizado"]:
            informativos.append(m)
            continue
        candidatos = [evaluar(m, d, reglas) for d in pendientes]      # → {clave, puntaje, motivos[]}
        candidatos = [c for c in candidatos if c["puntaje"] >= reglas["umbral"]]
        (propuestas if candidatos else sin_pareja).append(
            {"movimiento": m["referencia_banco"], "candidatos": ordenar(candidatos)})
    return {"propuestas": propuestas, "sin_pareja": sin_pareja, "informativos": informativos}

# motivos legibles, por ejemplo:
#   "importe igual" · "importe dentro de la tolerancia" · "serie-número en la descripción"
#   "RUC de la contraparte en la descripción" · "número de operación citado en la factura"
#   "cuenta del Banco de la Nación y monto de detracción en soles enteros" (detracciones.monto_detraccion)
```

La cardinalidad no es teórica en el Perú: **una factura con detracción se paga con dos movimientos**, el neto al
proveedor y el depósito en el Banco de la Nación. Es el primer caso natural de aplicación parcial, y sale en la tabla
`aplicaciones*` del §4.

**6. El primer caso es `aplicar_constancias*`**, la operación sin estado que el estándar ya describe (`estandar/LEEME.md`,
«La detracción»): entra el documento con detracciones `PROVISIONADO` y el archivo de constancias, y sale el documento con
`PAGADO`, `nro_constancia` y `fecha_constancia`. Antes de diseñar su lector hay que ver **qué archivo real existe**, dado
que la constancia no tiene un formato de máquina documentado: una exportación de la consulta en SOL, el TXT del depósito
masivo u otro.

**7. El asiento de tesorería espera.** Es una regla contable nueva y necesita su fuente (las cuentas del PCGE y el ITF con
su norma) y un archivo aceptado del sub-diario de bancos de CONCAR, que probablemente pida el medio de pago.

**8. En la puerta MCP:** `leer_extracto*` y `proponer_parejas*`, cuando exista su lector.

```
BANCO · AGREGADOR · PORTAL ── Excel · TXT · H2H · API ──► APLICACIÓN: credenciales, cursor, reintentos, guarda lo crudo
                                                                │ bytes + nombre
┌───────────────────────────── MOTOR (puro) ────────────────────▼──────────────────────────────┐
│ identificar(nombre, datos) ──► lector del banco X [archivo real]   (un libro Excel no es un ZIP) │
│ movimientos ──► deduplicar(movimientos, referencias_previas ◄ APP) ──► nuevos                  │
│ conciliar(nuevos, pendientes ◄ APP, reglas) ──► propuestas · sin_pareja · informativos         │
└────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                     APLICACIÓN: el contador confirma ──► guarda parejas y aplicaciones*
                                             │
MOTOR: aplicar_constancias*(documento, constancias)  ◄── PRIMER CASO [archivo real]
       asiento de tesorería                           ◄── ESPERA: fuente + archivo aceptado del destino
                                             │
DRIVER concar: sub-diario de bancos, columna Y (medio de pago) ──► Excel que el destino SUMA
```

**9. Cinco precisiones del diseño**, que salieron al ordenar el frente «Entradas · El banco inicia el proceso contable» de la hoja de ruta:

1. **Hechos y avisos.** Hechos son la línea del extracto y la liquidación de la pasarela. Un webhook o un correo son un
   `Aviso*` (`tipo`: cobro, devolución, contracargo): se empareja, y **nunca produce asiento**.
2. **Liquidación de pasarela en dos niveles.** `LiquidacionPasarela*` lleva sus líneas (venta, devolución, comisión,
   impuesto de la comisión, contracargo, reserva, ajuste) con el invariante `suma(neto de las líneas) == neto`. Primero
   se empareja la línea del banco con la liquidación, uno a uno; después, las líneas de la liquidación con los
   comprobantes de venta. La cuenta puente es el saldo en poder de la pasarela.
3. **Reglas como dato.** `ReglaBanco*` sintetiza QuickBooks y Xero: prioridad, sentido, cuentas, condiciones
   `contiene | no_contiene | igual | empieza_por | entre` y una acción con la forma de una imputación. **Sin expresiones
   regulares** —una expresión maliciosa por una puerta pública puede colgar el proceso— y con tope.
4. **Cada candidato dice cómo y cuánto.** `conciliar*` devuelve `metodo*` (`regla | pareja | memoria | prediccion`) y
   `certeza*` (`alta | media | baja`); solo lo de certeza alta va a confirmar en lote, y la regla va antes que la
   predicción. Los pesos de puntuación son `parametros*`.
5. **Deduplicación con espacio de nombres**: `(fuente, id_en_fuente, tipo_registro)`, y una relectura con solape no
   duplica.

**10. La tolerancia en dos medidas** (precisión de diseño para `conciliar*`, sin función nueva). Como en NetSuite, la
tolerancia de importe se declara en porcentaje **y** en diferencia absoluta dentro de `parametros*`. Un candidato fuera
de cualquiera de las dos no llega a certeza alta, y lleva su motivo. **Test que lo fijaría** (con D3): un importe
dentro del porcentaje pero fuera del absoluto no da `certeza: alta`.

**11. Una cuenta del proveedor que no es la conocida** (`cuentas_conocidas*`, **N** · **F**). La lección del fraude por
suplantación, sin estado en el motor. La aplicación pasa `{ruc: [cuenta]}` con las cuentas que ya confirmó; en
`conciliar*`, una cuenta de contraparte que no está entre ellas **impide la certeza alta** y lleva el motivo «cuenta
del proveedor distinta de la conocida: confirmar por otro canal», con `pedir_a: proveedor`. Nunca bloquea y nunca
recuerda nada entre llamadas.
- **Caso real que lo destraba:** D2, el primer extracto que traiga la cuenta de la contraparte, y un caso real de
  cambio de cuenta.
- **Tests que lo fijarían:** sin `cuentas_conocidas` no cambia nada; con una cuenta nueva, la pareja baja de `alta` y
  lleva su motivo.
- **Qué no:** la doble aprobación ni un registro de cuentas dentro del motor (§12).

### Qué no se toma

- **La cuenta transitoria inmediata** (Odoo). El destino suma; primero se empareja (§6).
- ***Embeddings* y aprendizaje estadístico dentro del motor** (Midday, `smart_importer`). No son deterministas: son de la
  aplicación, y el motor recibe lo aprendido como datos.
- **Doble aprobación o un registro de cuentas bancarias de proveedores.** Son estado (§6).

---

## 7 · Declarar: SIRE, sales tax y 1099

### Qué hacen

**No hay IVA nacional ni registro de compras o de ventas ante ningún fisco.** EE. UU. es el único país de la OCDE sin
un impuesto amplio al consumo a nivel nacional (cita del CRS tomada del resumen del buscador,
[CRS](https://www.congress.gov/crs-product/IF13037)). Las compras y las ventas llegan al IRS solo dentro de la renta
anual, y a los estados dentro de una declaración de sales tax agregada. El único cruce por tercero es el 1099.

| Aspecto | EE. UU. | Perú | Qué significa para el motor |
|---|---|---|---|
| Impuesto al consumo | Sin IVA nacional; sales tax en 45 estados y DC | IGV nacional del 18 % | Un impuesto con tasa nacional cabe en campos fijos; uno por jurisdicción, no (§11) |
| Dónde se liquida | En el estado y la localidad, con código de jurisdicción | SUNAT | — |
| Granularidad ante el fisco | Agregada por jurisdicción | Por comprobante (SIRE) y agregada (PDT 621) | El SIRE ya es un driver de registro |
| Periodicidad | Según el volumen, distinta en cada estado | Mensual | El periodo de declaración puede no ser el contable (§11) |
| Nexo | Económico desde *Wayfair*; *marketplace facilitators* | Domicilio | — |
| Compras sin impuesto cobrado | *Use tax* autoliquidado por el comprador | IGV por utilización de servicios de no domiciliados, autoliquidado | Qué tomar, punto 2 |
| Impuesto pagado en compras | Costo (*práctica contable*: sin norma primaria encontrada) | Crédito fiscal, con requisitos | `rol: igv` en compras |
| Lista de terceros | 1099 anual por proveedor | Propuesta del SIRE, mensual; PLAME, mensual; DAOT, anual y residual | C9; Qué tomar, punto 3 |
| Retención del pagador | *Backup withholding* del 24 % sin número válido | Renta de 4ta del 8 %; retención del IGV del 3 % | `RETENCION_TASA`; C4 |
| Canal electrónico | IRIS para el 1099; el portal de cada estado | SOL y SIRE | Un driver solo escribe el archivo |
| Libros | Se conservan y se muestran en auditoría (IRC §6001, Rev. Proc. 98-25) | Registros electrónicos (SIRE, PLE) | — |
| Plan de cuentas | Libre ([Pub 583](https://www.irs.gov/publications/p583)) | PCGE, que el motor consulta (`contaperu/pcge/`) | La cuenta la pone la imputación en los dos |
| Renta | Anual, con pagos estimados | Anual, con pagos a cuenta | Fuera del motor |

**El sales tax: tres estados de ejemplo.**

| Estado | Formulario y periodicidad | Dónde va el *use tax* | Fuente |
|---|---|---|---|
| California | CDTFA-401. El CDTFA asigna la periodicidad según las ventas gravadas: trimestral con prepagos (desde US$17,000 al mes), trimestral, mensual o anual. Se presenta aunque no haya ventas | Línea 2, «Purchases subject to use tax» | [CDTFA](https://cdtfa.ca.gov/taxes-and-fees/sales-use-tax-returns-filing-dates.htm), [use tax](https://cdtfa.ca.gov/taxes-and-fees/applying-tax-sales-purchases-faq.htm) |
| Texas | 01-114. Mensual, trimestral o anual; vence el día 20. Los montos que definen cada periodicidad, *no verificados* | Item 3, «Taxable Purchases»; sin permiso, Form 01-156 | [Comptroller](https://comptroller.texas.gov/taxes/sales/filing-requirements.php), [use tax](https://comptroller.texas.gov/taxes/sales/use-tax.php) |
| Nueva York | ST-100 trimestral, con periodos de marzo a mayo, de junio a agosto…; ST-101 anual si el impuesto es de US$3,000 o menos; ST-809 mensual desde US$300,000 por trimestre. Vence 20 días después del periodo | Columna D: compras usadas en NY sin impuesto de NY | [ST-100](https://www.tax.ny.gov/forms/current-forms/st/st100i.htm), [periodicidad](https://www.tax.ny.gov/pubs_and_bulls/tg_bulletins/st/filing_requirements_for_sales_and_use_tax_returns.htm) |

En Nueva York cada venta y cada compra gravada se informa con el **código de la jurisdicción** donde se entregó o se
usó: la unidad de agregación es la jurisdicción, no la factura.

**Streamlined Sales Tax, *Wayfair* y Puerto Rico.** 24 estados aprobaron legislación conforme al acuerdo SSUTA: 23
miembros plenos y Tennessee como asociado. Cada estado miembro publica gratis archivos de tasas por jurisdicción y de
límites por código postal; el certificado de exención multiestado (F0003) lo guarda el vendedor, no el estado; y los
*Certified Service Providers* calculan, declaran y pagan por el vendedor
([SST](https://www.streamlinedsalestax.org/Shared-Pages/faqs/faqs---about-streamlined),
[archivos](https://www.streamlinedsalestax.org/Shared-Pages/rate-and-boundary-files),
[CSP](https://www.streamlinedsalestax.org/certified-service-providers/what-is-a-csp),
[F0003](https://www.streamlinedsalestax.org/docs/default-source/forms/exemption-certificate-instructions.pdf)). El nexo
sin presencia física lo abrió *South Dakota v. Wayfair* (21-jun-2018): US$100,000 de ventas o 200 transacciones al año
en el estado ([sentencia](https://www.supremecourt.gov/opinions/17pdf/17-494_j4el.pdf)). Lo más transaccional del país
es Puerto Rico: IVU del 11,5 %, planilla mensual agregada por SURI y, desde 2015, terminales fiscales que transmiten las
transacciones a Hacienda en los comercios con ventas de más de US$125,000
([planilla](https://hacienda.pr.gov/ivu/planilla-mensual-de-ivu),
[terminales](https://hacienda.pr.gov/publicaciones/determinacion-administrativa-num-15-20)). Si es en tiempo real y con
qué detalle, *no verificado*.

**Los terceros: el 1099.**
- El umbral del 1099-NEC y del 1099-MISC, y el del *backup withholding*, sube de US$600 a **US$2,000 para pagos desde el
  1-ene-2026**, con ajuste por inflación desde 2027 (P.L. 119-21, §70433)
  ([ley](https://www.congress.gov/119/plaws/publ21/PLAW-119publ21.pdf), [Pub 1099](https://www.irs.gov/publications/p1099),
  [backup withholding](https://www.irs.gov/businesses/small-businesses-self-employed/backup-withholding)).
- El 1099-K de los procesadores de pago vuelve a US$20,000 y 200 transacciones
  ([IR-2025-107](https://www.irs.gov/newsroom/irs-issues-faqs-on-form-1099-k-threshold-under-the-one-big-beautiful-bill-dollar-limit-reverts-to-20000)).
- El 1099-NEC se entrega al proveedor y al IRS hasta el 31 de enero; con 10 o más declaraciones la presentación
  electrónica es obligatoria ([instrucciones](https://www.irs.gov/instructions/i1099mec),
  [TD 9972](https://www.federalregister.gov/documents/2023/02/23/2023-03710/electronic-filing-requirements-for-specified-returns-and-other-documents)).
- **FIRE se retira**: el último día es el 19-nov-2026 y, desde el 1-ene-2027, **IRIS** es el único canal
  ([IRS](https://www.irs.gov/e-file-providers/filing-information-returns-electronically-fire)). FIRE usaba registros
  posicionales de 750 caracteres; IRIS acepta un CSV por plantilla en su portal, hasta 100 declaraciones, o XML de
  sistema a sistema con esquemas anuales ([Pub 1220](https://www.irs.gov/pub/irs-pdf/p1220.pdf),
  [Pub 5717](https://www.irs.gov/pub/irs-pdf/p5717.pdf), [Pub 5718](https://www.irs.gov/pub/irs-pdf/p5718.pdf)).

**La renta.** Formularios 1120, 1120-S, 1065 o Schedule C, con el costo de ventas en el 1125-A y la conciliación entre
libros y declaración en el Schedule M-3 si los activos llegan a US$10 millones; las corporaciones pagan a cuenta en los
meses 4, 6, 9 y 12 del ejercicio ([1125-A](https://www.irs.gov/forms-pubs/about-form-1125-a),
[M-3](https://www.irs.gov/instructions/i1120sm3), [1120](https://www.irs.gov/instructions/i1120)). No hay plan de
cuentas obligatorio: salvo pocos casos, la ley no exige ningún tipo específico de registros (Pub 583).

### Perú: las analogías, verificadas

| EE. UU. | Perú | En qué se parece | Fuente peruana |
|---|---|---|---|
| *Use tax*: el comprador autoliquida lo que el proveedor no cobró | **IGV por utilización de servicios prestados por no domiciliados.** El contribuyente es el usuario (TUO de la Ley del IGV, art. 1 inc. b y art. 9.1 inc. c). La obligación nace al anotar el comprobante o al pagar, lo que ocurra primero (art. 4 inc. d). Se paga con el Formulario Virtual 1662, tributo 1041 (RS 000047-2026/SUNAT, vigente desde el 1-jul-2026). El crédito se usa desde el periodo del pago (Reglamento, art. 6 num. 11). Los tipos 91, 97 y 98 van al archivo de no domiciliados del RCE | En quién paga y cómo. No en el fondo: el *use tax* es costo; el IGV, crédito | [Ley, cap. I](https://www.sunat.gob.pe/legislacion/tributaria/igv/ley/capitul1.htm), [cap. III](https://www.sunat.gob.pe/legislacion/igv/ley/capitul3.pdf), [RS 047-2026](https://www.sunat.gob.pe/legislacion/superin/2026/000047-2026.pdf), [anexo RS 040-2022](https://www.sunat.gob.pe/legislacion/superin/2022/anexo-040-2022.pdf) |
| 1099-NEC: por proveedor de servicios, anual, con umbral | **PLAME, Formulario Virtual 601**: mensual, con todos los prestadores de renta de 4ta pagados en el periodo y la retención del 8 % | Una lista por tercero, con retención | [SUNAT](https://www2.sunat.gob.pe/pdt/pdtModulos/independientes/p601/faq/regPrestadores.html) |
| El 1099 como lista de terceros | **DAOT** (RS 024-2002/SUNAT): anual, con los terceros de más de 2 UIT. **No cuenta lo anotado en registros electrónicos**, así que quien lleva el SIRE suele quedar sin nada que declarar | Anual y por tercero | [DAOT](https://orientacion.sunat.gob.pe/declaracion-anual-de-operaciones-con-terceros-daot), [exclusión](https://orientacion.sunat.gob.pe/03-operaciones-que-no-deben-considerarse-para-el-calculo-de-las-operaciones-con-terceros-daot) |
| *Backup withholding* del 24 % | **Régimen de retenciones del IGV**: 3 % desde el 1-mar-2014 (RS 037-2002/SUNAT, con la tasa de la RS 033-2014), PDT 626 y comprobante de retención tipo 20. El HTML de la RS 037-2002 en sunat.gob.pe aún muestra el 6 %: no citarlo | Solo en la forma: retiene el pagador. En el fondo es un anticipo del IGV del proveedor | [orientación](https://orientacion.sunat.gob.pe/73-importe-de-la-operacion-y-tasa-de-retencion), [comprobante 20](https://cpe.sunat.gob.pe/tipos_de_comprobantes/comprobante_de_retencion) |
| — | **SIRE**: RVIE y RCE para todos los obligados a llevar esos registros desde el periodo octubre 2026 (RS 000125-2026/SUNAT) | Sin análogo en EE. UU. | [RS 125-2026](https://www.sunat.gob.pe/legislacion/superin/2026/000125-2026.pdf) |

**El asiento que se parece, y la diferencia que importa** (*ilustrativo*: ni los roles ni las cuentas están decididos):

```
EE. UU. · compra a otro estado sin sales tax (use tax, tasa t)   PERÚ · servicio de un no domiciliado (tipo 91)
D gasto                     B     principal                      D gasto                           B       principal
D gasto (use tax: costo)    B·t   impuesto_uso*                  D IGV no domiciliados, crédito    B·18 %  igv_no_domiciliado*
H use tax por pagar         B·t   impuesto_uso_por_pagar*        H IGV no domiciliados, por pagar  B·18 %  igv_no_domiciliado_por_pagar*
H proveedor                 B     tercero                        H proveedor del exterior          B       tercero
```

La diferencia está en la segunda línea: en EE. UU. es costo; en el Perú, crédito fiscal.

### Qué hace ContaPerú hoy

- El driver `sire` escribe el RVIE (Anexo 3) y el RCE (Anexo 11) de reemplazo desde el comprobante
  (`contaperu/drivers/sire/txt.py:39`, `:118-155`); `leer_propuesta_sire` lee la propuesta, y `comparar_sire` la
  contrasta campo a campo.
- **El no domiciliado está a medias.** Los tipos 91, 97 y 98 están en el catálogo (`contaperu/catalogos.py:37-39`) y
  `no_domiciliado` es un nombre reservado del estándar (`estandar/LEEME.md:283`). Pero el driver `sire` solo escribe el
  archivo principal del RCE, no el de no domiciliados, y el asiento no tiene `rol` para ese IGV
  (`contaperu/asiento/motor.py:40`).
- **La renta de 4ta** entra como tipo 02 con `retencion` y su comprobación del 8 % (`contaperu/validar.py:82-96`); nada
  del motor escribe el PLAME.
- **El resumen por contraparte de `diagnosticar` mezcla monedas**: toma la moneda del primer comprobante y suma los
  totales de todos (`contaperu/operaciones.py:549-557`). Es justo lo que una declaración por jurisdicción nunca hace:
  sumar en una casilla lo que no tiene la misma llave.

### Qué tomar

**1. El resumen por contraparte agrupa por moneda** (**F**). Agrupar por contraparte y moneda, o dar un total por moneda
dentro de cada contraparte. Es aritmética, no una regla contable.
- **Caso real que lo destraba:** un proveedor que factura en soles y en dólares el mismo mes.
- **Tests que lo fijarían:** dos comprobantes del mismo RUC, uno en PEN y otro en USD, no dan un único total; con una
  sola moneda la salida no cambia.

**2. El IGV por utilización de servicios de no domiciliados** (**N** · estándar · **D**). El par de líneas
autoliquidado con su `rol` propio, y el archivo de no domiciliados del RCE. La fuente ya está (arriba); falta el caso.
- **Caso real que lo destraba:** un comprobante 91 real con su pago por el Formulario 1662 y un asiento aceptado por
  CONCAR.
- **Tests que lo fijarían:** el 91 da cuatro líneas que cuadran; una factura 01 sale idéntica (snapshot de CONCAR); el
  `rol` nuevo entra por su enmienda. Ampliar el enum cerrado de `rol` rompe a un validador estricto de la 0.3, y es la
  enmienda la que decide si el cambio es aditivo.

**3. El archivo de 4ta del PLAME, análogo del 1099-NEC** (**D**). Con la misma separación que EE. UU.: el umbral y la
tasa son regla, del núcleo; el archivo es formato, del driver.
- **Caso real que lo destraba:** un archivo que PLAME haya importado, y el recibo por honorarios electrónico real de C7.
  Los nombres y la estructura de los archivos de importación, *no verificados*.
- **Tests que lo fijarían:** las cuatro capas de prueba de un driver; sin recibos por honorarios no hay filas.

**4. Los padrones que deciden una retención llegan como dato** (**N**), igual que el padrón de C8, cuando exista el caso
de C4. El motor nunca calcula una retención que no muestre el comprobante.

### Qué no se toma

- Un resumen anual por tercero, o la DAOT: el libro es mensual (`contaperu/modelo.py:113-128`) y la exclusión de lo
  anotado en registros electrónicos la vacía.
- Sales tax, nexo o certificados de exención: no hay caso peruano; solo ilustran la puerta del §11.
- Calendarios de vencimientos, pagos a cuenta y plazos de conservación: el núcleo no tiene reloj
  (`tests/test_frontera.py:94`) ni disco.
- Asentar el 91 como costo, a imitación del *use tax*: en el Perú es crédito con requisitos.
- Convertir monedas dentro de un resumen: sería una cifra nueva sin caso.

---

# Parte III · Lo transversal

## 8 · Modelos de referencia: ERPs abiertos, ledgers y estándares

### Qué hacen

Todos resuelven lo mismo: representar una partida doble sin atarse a un plan de cuentas ni a un ERP concreto. Y la
mayoría separa **tres identidades** que un modelo ingenuo mezcla: el **id técnico** del asiento, el **número de
negocio** del documento que lo soporta y el **puntero a la línea de origen**. Además, la mayoría guarda el
**motivo** de la línea aparte de la cuenta.

| Proyecto | Id técnico del asiento | Número de negocio | Puntero al origen | Motivo aparte de la cuenta | Cómo corrige |
|---|---|---|---|---|---|
| **PLE 5.1, Libro Diario** ([RS 169-2015/SUNAT, Anexo 2](https://spij.minjus.gob.pe/Graficos/Peru/2015/Junio/30/RS-169-2015-SUNAT-ANX-2.pdf)) | Campo 2, **CUO**: «llave única o clave única o clave primaria del software contable que identifica de manera unívoca el asiento contable» | Campos 10-12: tipo, serie y número del comprobante | Campo 20, **dato estructurado**: código del libro & periodo & CUO & correlativo del Registro de Ventas o de Compras | Campo 3: prefijo del correlativo A (apertura), M (movimiento), C (cierre) | Campo 21, estado: 1 del periodo, 8 de un periodo anterior no anotado, 9 corrige uno ya anotado con su CUO original |
| **SAF-T** ([XSD noruego 1.10, derivado del de la OCDE](https://raw.githubusercontent.com/Skatteetaten/saf-t/master/Norwegian_SAF-T_Financial_Schema_v_1.10.xsd)) | `SystemID` | `TransactionID` | `SourceDocumentID` y `RecordID` por línea | — | `CrossReference`: documentos conciliados |
| **XBRL GL** ([anexo del estándar estonio basado en XBRL GL 2015](https://wp.itl.ee/wp-content/uploads/2021/02/ANNEX-I-XBRL-GL-accounting-entry-data-standard.pdf)) | `entryHeader@id` | `documentNumber`, `documentType` | `documentReference`; hacia delante, `documentApplyToNumber` | `sourceJournalID` = el **diario**, equivalente a nuestro sub-diario (no al rol); `amountMemo` marca una línea informativa | — |
| **ERPNext** ([`GL Entry`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/gl_entry/gl_entry.json)) | `name` | `voucher_type` + `voucher_no` | `voucher_detail_no` (la fila del documento); hacia delante, `against_voucher` | — | `is_cancelled`; con [libro inmutable](https://docs.frappe.io/erpnext/user/manual/en/immutable-ledger-in-erpnext), la cancelación se asienta en su propia fecha |
| **Odoo 18** ([`account.move.line`](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_move_line.py)) | `id`, más `inalterable_hash` y secuencia sin huecos | `name` del `account.move` | `move_id`; `matched_debit_ids` hacia la conciliación | `display_type` (product, tax, payment_term…) ≈ nuestro `rol` | `reversed_entry_id` ([`account.move`](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_move.py)) |
| **TigerBeetle** ([Transfer](https://docs.tigerbeetle.com/reference/transfer/)) | `id` (u128; es la clave de idempotencia) | `user_data_128` (quién/qué) | `user_data_64`, `user_data_32` | `code`: «why» | Inmutable: se corrige con transferencias nuevas |
| **Formance Ledger** ([API v2](https://raw.githubusercontent.com/formancehq/ledger/main/openapi/v2.yaml)) | `id` y `reference` («unique within the ledger») | `metadata` | `metadata` | Numscript | `revert`, con `atEffectiveDate` opcional |
| **Beancount / beangulp** ([sintaxis](https://beancount.github.io/docs/beancount_language_syntax/)) | — (texto plano, con `filename` y `lineno`) | metadatos libres | links `^` para unir factura y pago | — | Otra transacción |
| **Panora** ([modelo unificado](https://raw.githubusercontent.com/panoratech/Panora/main/packages/api/src/accounting/journalentry/types/model.unified.ts)) · **Nango** ([records](https://nango.dev/docs/reference/api/sync/records-list)) | `id` propio | `remote_id` | `remote_data` | — | Nango: `_nango_metadata.last_action` ADDED\|UPDATED\|DELETED y `deleted_at` |
| **OCA `edi_oca`** ([`edi.exchange.record`](https://raw.githubusercontent.com/OCA/edi-framework/17.0/edi_oca/models/edi_exchange_record.py)) | `identifier` | `external_identifier` | `model` + `res_id`, `parent_id` | Tipo de intercambio | Estados del intercambio y `ack_exchange_id` |
| **Apache Fineract** ([documentación](https://fineract.apache.org/docs/legacy/)) | `transactionId` | `referenceNumber` | `entityType` | Reglas contables y *financial activity mappings* por producto | `command=reverse` |
| **EN 16931 / UBL** ([BT-19 y BT-133](https://github.com/ConnectingEurope/eInvoicing-EN16931/issues/270)) | — | BT-1, número de factura | — | BT-19 / BT-133 «Buyer accounting reference» (`cbc:AccountingCost`): el vendedor envía la referencia contable **del comprador** | Nota de crédito |

Tres patrones se generalizan:

- **La identidad es una tupla, no un número.** Hacia atrás, (documento, número, fila); hacia delante, (documento que
  se liquida). Nadie usa el correlativo del diario como identidad, porque se reasigna.
- **El motivo va aparte de la cuenta.** La cuenta la elige cada empresa; el motivo (el IGV, el tercero, la comisión)
  es lo que otro sistema necesita para traducir sin adivinar.
- **Las importaciones tienen un protocolo.** El `Importer` de [beangulp](https://raw.githubusercontent.com/beancount/beangulp/master/beangulp/importer.py)
  separa `identify(filepath)`, `extract(filepath, existing)` y `deduplicate(entries, existing)`, y marca los repetidos
  con `__duplicate__` usando una ventana de fechas ([extract.py](https://raw.githubusercontent.com/beancount/beangulp/master/beangulp/extract.py)).
  Es la simetría, del lado de la entrada, de lo que en ContaPerú es el contrato de driver.

### Qué hace ContaPerú hoy

| Identidad | Hoy | Dónde |
|---|---|---|
| Número de negocio | `documento.serie_numero` en cada línea; `Comprobante.clave` = (tipo, serie, número sin ceros, documento de la contraparte) | `contaperu/asiento/motor.py:126-127`, `contaperu/modelo.py:300` |
| Id técnico en el destino | (mes, sub-diario, correlativo): lo numera el motor desde el punto de partida que da quien llama, y **cambia al re-exportar** | `contaperu/asiento/resolucion.py:306`, `contaperu/asiento/huella.py:13-15` |
| Puntero al origen | No existe: la línea no dice de qué comprobante salió más allá de su serie-número | `contaperu/asiento/lineas.py` |
| Motivo | `rol`: `principal`, `igv`, `retencion_4ta`, `tercero`, `detraccion_tercero`, `detraccion` | `contaperu/asiento/motor.py` |

### Qué tomar

Ningún modelo nuevo. `open-accounting` ya separa el motivo de la cuenta —el `rol` no lo tiene ninguna de las APIs
comparadas en `REFERENCIAS.md`— y ya transporta lo que no entiende (`datos_originales`). Las dos identidades que
faltan se resuelven **sin tocar la línea**, con el índice por comprobante del §4. El protocolo de beangulp se usa en
el §6, cuando exista el primer lector de un extracto bancario.

### Qué no se toma

- **Numscript o cualquier lenguaje de reglas contables** (Formance). Las reglas viven en código, con su fuente al lado
  ([CONTRIBUTING.md](CONTRIBUTING.md)).
- **Importes en enteros de la unidad mínima** (TigerBeetle). El texto exacto con `Decimal` ya lo resuelve y no pierde la
  moneda de vista.
- **Modelos definidos por el usuario y *field mappings* por conexión** (Nango, Merge). El modelo lo define SUNAT
  (`REFERENCIAS.md`, «Lo que no se toma»), y dónde va cada dato ya lo resuelven `COLUMNAS_ELEGIBLES` y la configuración
  por sistema.

---

## 9 · El estándar y su gobierno

Cómo cambia un estándar sin romper a quien lo usa. Qué hay hoy y los hitos: `HOJA-DE-RUTA.md`, frente «El estándar abierto y la comunidad».

### Qué hacen

- **Una propuesta por cambio, con estados.** Las SEP de MCP piden un *sponsor* y, para quedar en final, una
  implementación de referencia y un escenario de conformidad ([guía](https://modelcontextprotocol.io/community/sep-guidelines));
  las PEP de Python fijan secciones y estados ([PEP 1](https://peps.python.org/pep-0001/)); FDX publica dos versiones al
  año a partir de RFC de sus miembros ([FDX](https://financialdataexchange.org/fdx-feed/fdx-announces-spring-2025-api-release-fdx-api-version-6-4/)).
- **Un calendario y una prueba por regla.** Peppol BIS publica versiones en mayo y noviembre, obligatorias unos tres
  meses después ([notas](https://docs.peppol.eu/poacc/billing/3.0/release-notes/)), con pruebas unitarias por regla.
- **Una suite de conformidad ejecutable.** JSON Schema Test Suite guarda cada caso como `{description, schema, tests:
  [{description, data, valid}]}` y Bowtie corre implementaciones ajenas contra ella
  ([suite](https://github.com/json-schema-org/JSON-Schema-Test-Suite), [Bowtie](https://github.com/bowtie-json-schema/bowtie)).
- **Retirar sin romper.** Codat cambia con *expand and contract* y aviso previo ([política](https://docs.codat.io/using-the-api/change-policy));
  SUNAT lleva su propio control de cambios con fecha de vigencia y lista las observaciones que pasan a error.

### Qué tomar: la enmienda

**Plantilla de enmienda:** `# NNNN · título` · **Estado** · **Compatibilidad** (aditivo o cambio de significado) ·
**Nivel** · **Motivación** (el caso real) · **Fuente** · **Especificación** · **Test** · **Versión**.

**Estados:** `borrador → con caso real → aceptada → final`, y además `reservada`, `rechazada` y `reemplazada`.

---

## 10 · Arquitectura y puertas: fachada y MCP

```
APLICACIÓN · red · credenciales · IA · estado · pantalla de revisión
  correo y bandejas · IA de PDF y fotos · descarga del SIRE · servicio de validez · banco, agregador o H2H
  guarda: documentos · imputaciones · configuración · plan del destino · claves anotadas ·
          exportaciones (clave + huella + rangos de correlativo) · movimientos · parejas · historial por proveedor
      │ bytes        │ documento + configuracion + imputacion + claves_previas* + plan_de_cuentas*       │ bytes
══════▼══════════════▼═════════════════════════════════════════════════════════════════════════════════▼══════
3 · FACHADA Y PUERTAS · operaciones · servidor_mcp · cli
    hoy: leer_xml · leer_propuesta_sire · revisar · diagnosticar · generar_asiento · exportar · cuadrar · …
    *:   cruzar_con_propuesta · sugerir_imputacion · leer_extracto · proponer_parejas ·
         anotaciones MCP · outputSchema(diagnosticar) · [pedir lo que falta, cuando el SDK lo traiga]
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
2 · DRIVERS · concar (construir) · contasis (desde_comprobantes) · sire (linea) · csv (desde_lineas) · terceros
    *:        el plan exportado de CONCAR → forma neutral · el sub-diario de bancos          [archivo real]
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
1 · NÚCLEO · sin red, disco, estado ni reloj
    lectores: xml_ubl · sire_txt · *extracto del banco X [archivo real]
    validar(claves_previas) · detracciones · *aplicar_constancias [archivo real]
    asiento: partes_de → faltantes_para(*plan) → FALTAS → motor → huella · *índice por comprobante
    *cruzar · *conciliar · *sugerir   (proponen con motivo; nunca deciden)
```

La regla que ordena el diagrama es la de siempre, extendida a las dos entradas nuevas: **cada flecha que cruza la línea
doble lleva datos, nunca una conexión**. Lo que el motor necesita saber del mundo —qué se anotó antes, qué plan tiene
el destino, qué movimientos llegaron, qué decidió el contador otras veces— se lo da la aplicación como argumento.

### La puerta MCP

**Qué dice la especificación.**

| Revisión | Lo que importa aquí | Fuente |
|---|---|---|
| **2025-06-18** | Salida estructurada (`outputSchema` + `structuredContent`), *elicitation*, enlaces a recursos en los resultados | [changelog](https://modelcontextprotocol.io/specification/2025-06-18/changelog) |
| **2025-11-25** | Tareas experimentales; *elicitation* por URL; los errores de validación de entrada son errores de herramienta, «to enable model self-correction» (SEP-1303); JSON Schema 2020-12 | [changelog](https://modelcontextprotocol.io/specification/2025-11-25/changelog) |
| **2026-07-28** | Sin estado (sin `initialize`); pedir datos al usuario pasa a viajar en la respuesta (`resultType: "input_required"` con un `requestState` que el servidor debe firmar y tratar «as attacker-controlled»); las tareas pasan a ser una extensión; *sampling*, *roots* y *logging* quedan obsoletos | [changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog), [MRTR](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr), [SEP-2663](https://modelcontextprotocol.io/seps/2663-tasks-extension) |

Las anotaciones de herramienta son pistas, no seguridad: `readOnlyHint` vale falso por defecto, `destructiveHint`
verdadero, `idempotentHint` falso y `openWorldHint` verdadero, y «clients should never make tool use decisions based on
ToolAnnotations received from untrusted servers» ([schema.ts 2025-11-25](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2025-11-25/schema.ts)).
En modo formulario, un servidor no debe pedir contraseñas ni credenciales
([elicitation](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation)).

**Cómo diseñan sus herramientas los servidores contables.** Xero (oficial) usa verbos `list-*`, `create-*` y `update-*`
([xero-mcp-server](https://github.com/XeroAPI/xero-mcp-server)). Intuit usa `{verbo}_{entidad}` y variables para apagar
escritura, actualización y borrado ([quickbooks-online-mcp-server](https://github.com/intuit/quickbooks-online-mcp-server)).
Apideck ofrece un modo dinámico de tres herramientas para catálogos grandes y un `--scope read|write|destructive`
([mcp](https://github.com/apideck-libraries/mcp)). Merge agrupa herramientas en paquetes y revisa datos personales antes
de devolverlos ([Agent Handler](https://docs.merge.dev/merge-agent-handler/overview)).

**Qué hace ContaPerú hoy** (`contaperu/servidor_mcp.py`): FastMCP, 11 herramientas y 5 recursos, transporte HTTP sin
estado (`stateless_http`, `:443`); ninguna herramienta escribe nada fuera de su respuesta. Comprobado en el SDK instalado
(`mcp` 1.30.0): `FastMCP.tool` acepta `annotations` y `structured_output`; las 11 herramientas tienen hoy ambas vacías;
las excepciones de una herramienta ya llegan al cliente como `isError`; y el protocolo más reciente que conoce es el
2025-11-25, sin `requestState`: **ese SDK no habla todavía 2026-07-28**.

| Herramienta | Anotaciones | `outputSchema` | Pedir lo que falta | Cuándo |
|---|---|---|---|---|
| Las 11 de hoy | `readOnlyHint: true`, `openWorldHint: false` (con `readOnlyHint` verdadero, `destructiveHint` e `idempotentHint` no significan nada) | — | — | Ya; subiendo el mínimo del pin `mcp>=1.2`, que no garantiza `annotations` (*no verificado*: en qué versión entró) |
| `diagnosticar` | las mismas | Sí, cubriendo también la forma `_sin_configuracion` | Con MRTR | Espera un SDK con 2026-07-28 |
| `exportar` | las mismas | No: devuelve el archivo como recurso embebido | — | Ya |
| Las nuevas (§3, §6, §2) | las mismas | Sí | — | Cada una cuando exista su función |

No se proponen tareas (todo es síncrono y hay un tope de 5.000 comprobantes, `contaperu/operaciones.py:33`), ni prompts, ni
*sampling*. *No verificado*: si la *elicitation* del SDK actual funciona con el transporte sin estado.

### Qué no se toma

- **Del MCP: tareas, *sampling*, *roots*, prompts, el modo dinámico de Apideck y los interruptores de escritura de QBO.**
  Once herramientas puras no los necesitan.

---

## 11 · Otra jurisdicción

**Estado: diseño escrito, sin código.** Decisión de John (14-sep-2026): se deja pensado cómo entraría otro país para
que el núcleo no se cierre la puerta, y nada se mueve hasta que haya **un cliente real fuera del Perú**, con su sistema
de destino y un archivo que ese sistema haya aceptado. Hasta entonces `ARQUITECTURA.md:25` sigue siendo cierto: el
núcleo sabe contabilidad peruana y nada más. Los hitos J0-J6 están en la hoja de ruta, frente «El motor · Otra jurisdicción».

### Qué hace ContaPerú hoy: lo universal y lo peruano

| Pieza | Universal ya | Peruano | Dónde |
|---|---|---|---|
| Libro | La entidad, un periodo, un tipo de libro | RUC de 11 dígitos, periodo AAAAMM, `venta` o `compra` | `contaperu/modelo.py:25`, `:113-128` |
| Comprobante | Número, fecha, total, contraparte, moneda, `id_externo`, `datos_originales` | Los impuestos en campos fijos (`base_gravada`, `igv`, `isc`, `ivap`, `icbper`, `retencion`, `detraccion`) | `contaperu/modelo.py:170-202`, `:311-314` |
| Esquema | `cuenta`, `debe_haber` e `importe` de la línea; la moneda ISO 4217 | «Documento contable universal del Perú»; `libro.ruc`; comprobante y línea cerrados; `rol` como enum cerrado | `estandar/open-accounting.schema.json:7`, `:58`, `:68`, `:188`, `:196-197` |
| Validación | Número, fecha, total que cuadra, nota sin referencia, duplicados | Dígito del RUC, IGV del 18 %, plazo de anotación, 4ta del 8 %, boleta desde S/ 700, error 452; importa `catalogos` | `contaperu/validar.py:16`, `:40-208`; `contaperu/catalogos.py:94` |
| Asiento | Partida doble, línea neutral, huella, imputación, faltas, resolución de cuentas | Roles cerrados, impuestos dentro de una función, detracción en cinco líneas, tipo de cambio solo para USD, fecha acotada al mes, correlativo MMNNNN | `contaperu/partida_doble.py:72-99`; `contaperu/asiento/motor.py:40`, `:89`, `:111`, `:178-197`; `contaperu/asiento/resolucion.py:306-344` |
| Configuración | La maquinaria de campos y su validación | La configuración general con cuentas del PCGE; cuentas por moneda solo PEN y USD | `contaperu/configuracion.py:32-232`, `:240-243`, `:246-315` |
| Lectores | Expandir ZIP; la parte genérica del UBL | Catálogos 01 y 05, `schemeID` a la Tabla 1, detracción en `PaymentTerms`, la propuesta del SIRE; el reparto entre lectores escrito a mano | `contaperu/lectores/xml_ubl.py`, `contaperu/lectores/sire_txt.py`, `contaperu/lectores/archivos.py:121-144` |
| Drivers | Las cuatro formas y los entry points | `FORMATOS` solo `venta` y `compra`; firmas con el `Libro` peruano; claves de detracción obligatorias; golden de compras peruano | `contaperu/drivers/contrato.py:71-72`, `:227-230`, `:280-286`; `contaperu/drivers/__init__.py:37`; `tests/test_contrato_drivers.py:33` |
| Dependencias ocultas | — | `formato` → `igv` → `validar` → `catalogos`; `generar` importa el registro de drivers | `contaperu/formato.py:16`, `contaperu/igv.py:28`, `contaperu/generar.py:20`, `:25` |
| Frontera | Red, reloj, entorno y puertas | No separa lo universal de lo peruano | `tests/test_frontera.py:29-32`, `:75`, `:94` |

Hay dos clases de acoplamiento, y hay que medir las dos: **por import** (los módulos que importan `catalogos`, `igv`,
`detracciones`, `sire_txt` o `pcge`) y **por contenido** (`Libro`, la configuración general y `asiento/configuracion`
no importan nada peruano, pero lo son).

### Qué tomar: el diseño

**1. El principio.** El núcleo universal no importa nada de una jurisdicción; cada jurisdicción es un perfil que se
enchufa como un driver.

**2. La partición.**

```
contaperu/                                (universal: no importa jurisdicciones/)
  modelo (Libro genérico*) · partida_doble · configuracion (la maquinaria) · formato (sin igv)
  asiento/ lineas · huella · imputacion · faltas · resolucion · motor (principal y tercero)
  lectores/archivos (expandir) · drivers/contrato · drivers/__init__ · drivers/csv
  jurisdicciones/__init__*  (registro por entry points; "pe" de serie y por defecto)
  operaciones · cli · servidor_mcp  (eligen la jurisdicción por libro.jurisdiccion*)
          ▲ entry points contaperu.jurisdicciones*
contaperu/jurisdicciones/pe*/             (lo peruano, movido sin reescribir)
  catalogos · igv · detracciones · pcge/ · reglas* · impuestos* (IGV, 4ta, detracción ─► líneas)
  configuracion_general* · periodos* (AAAAMM, límites, MMNNNN)
  lectores: xml_ubl (perfil SUNAT) · sire_txt · comparar_sire
  drivers por defecto: sire · concar · contasis · golden de conformidad
paquete aparte de un tercero: contaperu-<país>*   (ilustrativo)
```

**3. El contrato de una jurisdicción** (pseudocódigo, nombres provisionales), espejo del contrato de driver:

```python
CODIGO = "pe"                                           # ISO 3166-1 alfa-2
IDENTIFICADOR = {"nombre": "RUC", "validar": ruc_valido, "normalizar": solo_digitos}
LIBROS = ("venta", "compra")
PERIODO = {"patron": "AAAAMM", "limites": limites_del_periodo, "prefijo_correlativo": mes}
TIPOS_DOCUMENTO = {"01": {"nombre": "Factura", "invierte": False, "da_credito": True}, ...}
REGLAS = (Regla(codigo, nivel, pedir_a, funcion, fuente), ...)       # sin fuente no se registra
ROLES = ("igv", "retencion_4ta", "detraccion_tercero", "detraccion")  # se suman a principal y tercero
def impuestos(comprobante, config, sentido) -> list[LineaDiario]: ... # emite las líneas con su rol
CONFIGURACION_GENERAL, CONFIGURACION_DEL_ASIENTO, MONEDA_FUNCIONAL = ..., ..., "PEN"
LECTORES, DRIVERS_POR_DEFECTO, GOLDEN = ..., ("sire", "concar", "contasis"), "compras_202601.json"
```

Se registra por el grupo `contaperu.jurisdicciones*`, como los drivers por `contaperu.drivers`
(`contaperu/drivers/__init__.py:37`): los de serie ganan ante un nombre repetido, y uno que no cumple el contrato se
ignora con aviso. Un test de conformidad, análogo a `tests/test_contrato_drivers.py`, exige que cada jurisdicción
exporte su golden con el asiento cuadrado.

**4. El cambio en el estándar.** `libro.jurisdiccion*`, opcional y `"pe"` por defecto, con perfiles del esquema
(`if`/`then` sobre `libro.jurisdiccion`):
- `pe` conserva `ruc`, `periodo` y los campos fijos de impuesto **exactamente como en la 0.3**;
- las demás usan `libro.identificador*` y `comprobante.impuestos[]*`: `[{codigo*, jurisdiccion_fiscal*, base, tasa,
  importe, tratamiento*}]`, con `tratamiento*` = `credito | costo | autoliquidado | retencion`;
- **un dato, un dueño**: en `pe` la lista está prohibida, y en las demás los campos fijos; nunca los dos.

Sube a **0.4**, aunque un documento peruano sin `jurisdiccion` siga significando lo mismo: el esquema se define como
«documento contable universal del Perú», y aceptar otro país cambia el significado del documento entero
(`estandar/LEEME.md`, «Versionado»). Entra por una enmienda con su caso real (§9); ningún nombre se reserva antes.

**5. EE. UU. como ejemplo** (*ilustrativo*: no es una propuesta ni una regla).

| Pieza del contrato | Perú | EE. UU. |
|---|---|---|
| Identificador | RUC, con dígito verificador | EIN o SSN de 9 dígitos, **sin** dígito verificador: solo formato; la comprobación real es TIN Matching, en red, de la aplicación (§3) |
| Periodo | Mensual, el mismo para el libro y la declaración | Contable mensual; declaración de sales tax mensual, trimestral o anual según el estado y el volumen (§7) |
| Impuestos | IGV nacional, crédito en compras | Sales tax por jurisdicción, costo en compras; *use tax* autoliquidado (§7) |
| Roles | `igv`, `retencion_4ta`, detracción | `impuesto_venta*`, `impuesto_uso*`, `impuesto_uso_por_pagar*` |
| Declaración por tercero | — (el SIRE es por comprobante) | 1099-NEC hacia IRIS: el umbral de US$2,000 es regla de la jurisdicción; el CSV de la Pub 5717 es formato de un driver |
| Destinos | CONCAR, CONTASIS, SIRE | QuickBooks, Xero, NetSuite ([REFERENCIAS.md](REFERENCIAS.md)) |

El asiento de *use tax* al lado del IGV de no domiciliados está en el §7: la diferencia está en la segunda línea, costo
en EE. UU. y crédito en el Perú.

**Lo que choca con el contrato de hoy**, y queda nombrado sin resolver: `FORMATOS` solo acepta `venta` y `compra`
(`contaperu/drivers/contrato.py:227-230`); un 1099 junta doce periodos y una declaración trimestral junta tres libros. La
forma nueva de driver que haga falta la decide el caso real.

**6. Por qué el orden J0-J6.** Primero se hace visible el acoplamiento sin mover nada (J0): medir es gratis y protege
desde ese día. Después se cortan las dependencias ocultas (J1), que harían fallar cualquier paso posterior. La
validación (J2) y los impuestos (J3) se separan en paralelo, porque no se tocan entre sí; J2 conviene después de C1 y C2
para no mover las reglas dos veces. Solo con los dos se puede empaquetar el perfil peruano (J4), y solo con el perfil
tiene sentido cambiar el estándar (J5). La segunda jurisdicción (J6) llega al final, con su archivo aceptado. En cada
paso, el snapshot de CONCAR y la huella quedan idénticos.

**7. Riesgos, y cómo se contienen.**
- **La aplicación en producción** importa `contaperu.api`, `contaperu.asiento` y el modelo (`CLAUDE.md`, «Quién lo
  consume»): antes de mover nada se leen los símbolos que usa. Cuando se escribió esto entraba por
  `contaperu.operaciones`, la ruta de la 0.x que la 2.0 retiró.
- **El MCP abierto en producción**: ninguna herramienta cambia de firma.
- **La huella**: su fórmula es contrato (`contaperu/asiento/huella.py`); ningún paso la toca.
- **Un refactor mueve reglas; no las escribe** (`ARQUITECTURA.md`, «Lo que no se negocia»).

### Qué no se toma

- La jurisdicción en la configuración: es del libro.
- Un motor de impuestos genérico, con tasas como datos sin fuente.
- Adelantar J1-J6 sin el cliente.
- Traducir al inglés el vocabulario del estándar.

---

# Parte IV · Inventario

## 12 · Tabla de propuestas y descartes

### Propuestas

El orden en que se ejecutan, con sus hitos, dependencias y criterios de salida, está en
[HOJA-DE-RUTA.md](HOJA-DE-RUTA.md); esta tabla queda como el inventario de lo que la investigación propuso, con el hito que le toca a cada
propuesta («—» si todavía no tiene uno). Debajo, lo que se descartó o queda en vigilancia.

Prioridad **A**: afina lo que existe, tiene un caso visto y no necesita datos de fuera. **B**: tiene caso, pero cambia
una salida (y se anuncia) o es una función nueva que decide el mantenedor. **C**: espera un archivo real. **D**: espera un
segundo caso o una versión del SDK.

| # | Propuesta | Nivel | Caso real que la destraba | Test que la fijaría | Nombre | Prio | Hito |
|---|---|---|---|---|---|---|---|
| 1 | `claves_previas` en `revisar`, `diagnosticar`, `exportar` y el MCP | F | `DUPLICADO_PERIODO_ANTERIOR` nunca se dispara desde la fachada (error 452) | Con una clave previa, el comprobante sale en `bloqueantes` con `pedir_a: contador`; sin ella, todo igual | ya existe en `validar` | A | 0.1 |
| 2 | Anotaciones en las 11 herramientas | F | Sin anotación, un cliente asume `destructiveHint` y `openWorldHint` verdaderos | `test_servidor_mcp` recorre las 11 | — | A | 0.2 |
| 3 | Corregir la frase del LEEME sobre la detracción regenerada | estándar | Regenerar lo ya importado duplica en un destino que suma | — | — | A | 0.3 |
| 4 | Índice por comprobante: identidad, rango de líneas y huella | F | Tandas que se solapan; comprobante que cambió tras exportarse | Partición exacta; cuadre por rango; literal de `test_huella` intacto | `_asiento.comprobantes*` | A | 0.4 |
| 5 | Llevar la lectura de disco de `comparar_sire` a la CLI | puerta | La regla «sin disco en el núcleo» | Un vigilante de disco en `test_frontera`, salvo datos empaquetados | — | A | 0.5 |
| 6 | Tipo de cambio y tasa de detracción como texto en la línea | N · D | La regla de `Decimal` | Línea con texto; celda de CONCAR igual (snapshot intacto); huella en USD con literal nuevo y anuncio | — | B | 0.6 |
| 7 | CSV con `rol` y los `tipo_cp` | D | El CSV se ofrece como plantilla de driver y pierde lo que un driver necesita | Columnas nuevas presentes y llenas | — | B | B5 |
| 8 | Versión del motor en `_asiento` y `_exportacion` | F | Saber con qué versión salió una tanda tras un cambio anunciado | Igual a `__version__`; fuera de la huella | `motor*` | B | B2 |
| 9 | `cruzar_con_propuesta` y el primer `pedir_a: proveedor` | N · F | La propuesta del RCE como lista de control, la que EE. UU. no tiene (§1) | Tres cajones; ceros; RUC mal escrito | `cruzar_con_propuesta*` | B | C9 |
| 10 | `outputSchema` de `diagnosticar` | F | Un agente que valida la forma de la respuesta | Las dos formas de retorno validan contra el esquema | — | B | B2 |
| 11 | Plan de cuentas del destino y falta `cuenta_fuera_del_plan` | N · F · D | Nota K de la plantilla de CONCAR | Plan sin la cuenta bloquea y `exportar` lanza; sin plan, snapshot idéntico | `plan_de_cuentas*`, `cuenta_fuera_del_plan*` | C | C10 |
| 12 | `lleva_centro` por la marca del plan | N | Nota M; el propio docstring de `lleva_centro` | La marca manda sobre el prefijo (mutación) | — | C | C10 |
| 13 | Centro de costo contra la lista `centros_costo` | N | Nota M, «Ver T.G. 05» | Un centro inexistente bloquea solo si llega la lista | — | C | C10 |
| 14 | `aplicar_constancias` | N | Hoja de ruta; `_detraccion_pendiente` ya responde | De `PROVISIONADO` a `PAGADO` con el archivo real; sin pareja, igual | `aplicar_constancias*` | C | D1 |
| 15 | Lector de extracto del banco X y el movimiento | N | El Excel o TXT del portal bancario, el formato confirmado en el Perú | Archivo real anonimizado; un libro Excel no se desarma como ZIP; deduplica | `Movimiento*`, `leer_extracto*` | C | D2 |
| 16 | `conciliar` | N | Constancias primero; después cobros y pagos | Motivos legibles; cardinalidades; lo pendiente no se propone; tolerancia | `conciliar*` | C | D3 |
| 17 | Asiento de tesorería | N · D | Cobros y pagos hacia el destino | Archivo aceptado del sub-diario de bancos; ITF con su norma | — | C | D6 |
| 18 | `sugerir_imputacion` | N · F | La imputación repetida por proveedor | Determinista; mínimo; nunca escribe la imputación | `sugerir_imputacion*` | C | — |
| 19 | Pedir lo que falta desde el MCP (MRTR) | F | Pedir una cuenta sin guardar estado | — | — | D | — |
| 20 | Contrato de lector y *entry points* de lectores | N | El segundo banco | Un test de conformidad análogo al de drivers | `contaperu.lectores*` | D | B7 |
| 21 | `trazas` de un driver que consolide | D | El primer driver que agrupe líneas | Partición exacta; los importes suman | `trazas*` | D | — |
| 22 | `documento.id_externo` en la línea | estándar | Un driver `desde_lineas` que escriba el id del origen | Transporte puro; fuera de la huella | — | D | — |
| 23 | El resumen por contraparte de `diagnosticar` agrupa por moneda | F | Un proveedor que factura en PEN y en USD el mismo mes (`contaperu/operaciones.py:549-557`; §7) | Dos monedas del mismo RUC no dan un único total; con una sola moneda, la salida no cambia | — | A | 0.8 |
| 24 | El padrón admite `razon_social*`, sin aviso por diferencia de nombre | N · F | El de C8, con TIN Matching como referencia (§3) | Sin padrón no cambia nada; un nombre distinto no produce observación (mutación) | `razon_social*` | C | C8 |
| 25 | Tolerancia de importe en porcentaje y en diferencia absoluta | N | Las tres vías de NetSuite (§6) | Dentro del porcentaje y fuera del absoluto no da certeza alta | — | D | D3 |
| 26 | IGV por utilización de servicios de no domiciliados: par de líneas y archivo del RCE | N · estándar · D | Un 91 real con su pago por el Formulario 1662 y un asiento aceptado por CONCAR (§7) | Cuatro líneas que cuadran; una 01 idéntica (snapshot); el rol entra por su enmienda | `igv_no_domiciliado*` | C | C12 |
| 27 | Archivo de 4ta del PLAME, análogo del 1099-NEC | D | Un archivo que PLAME haya importado, y el de C7 (§7) | Las cuatro capas de prueba de un driver | `plame_4ta*` | C | — |
| 28 | Cuenta del proveedor distinta de la conocida, en `conciliar` | N · F | D2 y un caso real de cambio de cuenta (§6) | Sin el dato no cambia nada; con una cuenta nueva no hay certeza alta | `cuentas_conocidas*` | D | — |
| 29 | Los padrones que deciden una retención llegan como dato | N | El de C4 (§7) | — | — | D | C4 |
| 30 | La puerta a otra jurisdicción | N · D · estándar | Un cliente real fuera del Perú (§11) | Los criterios de J0-J6 en la hoja de ruta | `jurisdiccion*`, `impuestos[]*` | D | J0-J6 |
| — | ¿Debe `generar_asiento` exigir lo que exige el destino? | F | §3 | — | — | pregunta | — |

### Lo que se descartó o queda en vigilancia

Cada descarte tiene su motivo en la sección de su etapa, bajo «Qué no se toma». Aquí solo se listan, para que el
inventario sea uno.

| Qué | Estado | Motivo en |
|---|---|---|
| Emparejar órdenes de compra y recepciones, las tres vías de EE. UU. | descartado | §2 |
| Un buzón, estados de borrador o la aprobación de facturas | descartado | §2 |
| Redes EDI, portales, DBNAlliance o Peppol dentro del motor | descartado | §2 |
| Leer `cbc:AccountingCost` | espera un XML real que lo traiga | §2 |
| Imputar por ítem de la factura | hueco declarado | §2 |
| La factura negociable como canal del motor | en vigilancia | §2 |
| Un lenguaje de requisitos declarativos | descartado | §3 |
| Los estados de intercambio de OCA y el `blocking_level` de Odoo | descartado | §3 |
| TIN Matching o el padrón en línea, y retenciones calculadas por el motor | descartado | §3 |
| Llamar CUO a la identidad del comprobante, o hacerla un hash opaco | descartado | §4 |
| Una huella de la configuración aplicada | descartado | §4 |
| Log con hash encadenado, secuencia sin huecos y fechas de bloqueo | descartado | §5 |
| Guardar aparte el tipo de cambio usado, o tres fechas nuevas | descartado | §5 |
| `Idempotency-Key`, webhooks y sincronización incremental | descartado | §5 |
| Redis como recomendación contable | descartado | §5 |
| La cuenta transitoria inmediata | descartado | §6 |
| *Embeddings* y aprendizaje estadístico dentro del motor | descartado | §6 |
| Doble aprobación o un registro de cuentas bancarias de proveedores | descartado | §6 |
| Un resumen anual por tercero, o la DAOT | descartado | §7 |
| Sales tax, nexo y certificados de exención | descartado | §7 |
| Calendarios de vencimientos, pagos a cuenta y plazos de conservación | descartado | §7 |
| Asentar el tipo 91 como costo | descartado | §7 |
| Convertir monedas dentro de un resumen | descartado | §7 |
| Numscript o cualquier lenguaje de reglas contables | descartado | §8 |
| Importes en enteros de la unidad mínima | descartado | §8 |
| Modelos definidos por el usuario y *field mappings* por conexión | descartado | §8 |
| Del MCP: tareas, *sampling*, *roots*, prompts, el modo dinámico de Apideck y los interruptores de escritura de QBO | descartado | §10 |
| Adelantar la puerta a otra jurisdicción | espera un cliente real fuera del Perú | §11 |

---

## 13 · Fuentes

Consultadas el 13-sep-2026, igual que las que venían de la hoja de ruta; las de EE. UU. y las normas peruanas
verificadas, el 14-sep-2026 (al final). Lo ya citado en [REFERENCIAS.md](REFERENCIAS.md) (QuickBooks, Xero, Merge, Codat, Rutter,
Apideck en lo general) no se repite.

**Normas y guías peruanas**
- PLE, Libro Diario 5.1 y registros: RS 169-2015/SUNAT, Anexo 2 — https://spij.minjus.gob.pe/Graficos/Peru/2015/Junio/30/RS-169-2015-SUNAT-ANX-2.pdf
- Registro de Inventario Permanente Valorizado (CUO consolidado): RS 042-2018/SUNAT, anexo — https://www.sunat.gob.pe/legislacion/superin/2018/anexo-042-2018.pdf
- OSE — https://cpe.sunat.gob.pe/informacion_general/operador_servicios_electronicos
- SEE-Del Contribuyente (envío, CDR, puesta a disposición) — https://cpe.sunat.gob.pe/sistema_emision/see_contribuyente
- Depósito de detracciones — https://orientacion.sunat.gob.pe/02-deposito-de-detracciones-aspecto-generales
- Constancia de depósito de detracción — https://orientacion.sunat.gob.pe/3145-03-constancia-de-deposito-de-detraccion-empresas
- TUO de la Ley del ITF, DS 150-2007-EF — https://www.sunat.gob.pe/legislacion/itf/ds150_07.htm
- BCRP, interoperabilidad de pagos minoristas — https://www.bcrp.gob.pe/sistema-de-pagos/interoperabilidad/estrategia-de-interoperabilidad-de-los-pagos-minoristas.html
- SBS y *open finance* (según terceros) — https://iupana.com/2025/11/25/es-el-proyecto-mas-importante-que-tiene-la-sbs-dice-el-regulador-financiero-sobre-el-open-finance-en-peru/

**Estándares**
- SAF-T (XSD noruego 1.10) — https://raw.githubusercontent.com/Skatteetaten/saf-t/master/Norwegian_SAF-T_Financial_Schema_v_1.10.xsd
- XBRL GL — https://wp.itl.ee/wp-content/uploads/2021/02/ANNEX-I-XBRL-GL-accounting-entry-data-standard.pdf y https://www.xbrl.org/the-standard/what/global-ledger/
- OAGIS, `PostJournalEntry` — http://www.datypic.com/sc/oagis10/e-oag_PostJournalEntry.html
- EN 16931, BT-19/BT-133 — https://github.com/ConnectingEurope/eInvoicing-EN16931/issues/270 ; Peppol BIS Billing 3.0 — https://docs.peppol.eu/poacc/billing/3.0/bis/
- Peppol, modelo de cuatro esquinas — https://e-rechnung-bund.de/en/faq/peppols-technical-solution-the-four-corner-model/
- ISO 20022 camt.054 (guía de Standard Chartered) — https://www.sc.com/en/uploads/sites/66/content/docs/Standard-Chartered-ISO-20022-message-formatting-guideline-for-camt.054.pdf
- MT940 estructurado (Danske Bank) — https://danskeci.com/-/media/pdf/danskeci-com/swift-mt/reconciliation/mt940_structured.pdf ; MT942 — https://developer.huntington.com/enterprisepayments/docs/swift-mt942-intra-day ; BAI2 — https://developer.huntington.com/enterprisepayments/docs/bai2 ; OFX — https://www.online.fnb.co.za/rhelp_0_15/Downloads/Statement_File_Specifications/Statement_Type_-_OFX.pdf

**ERPs abiertos**
- ERPNext (rama `develop`): `GL Entry` — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/gl_entry/gl_entry.json ; `gl_entry.py` — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/gl_entry/gl_entry.py ; `Payment Ledger Entry` — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/payment_ledger_entry/payment_ledger_entry.json ; `Accounting Dimension Detail` — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/accounting_dimension_detail/accounting_dimension_detail.json ; `Accounting Dimension Filter` — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/accounting_dimension_filter/accounting_dimension_filter.json ; libro inmutable — https://docs.frappe.io/erpnext/user/manual/en/immutable-ledger-in-erpnext ; `Repost Accounting Ledger` — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/repost_accounting_ledger/repost_accounting_ledger.json ; `Bank Transaction` — https://docs.frappe.io/erpnext/user/manual/en/bank-transaction ; conciliación — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/bank_reconciliation_tool/bank_reconciliation_tool.py ; `Purchase Invoice` — https://github.com/frappe/erpnext/blob/develop/erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py
- Odoo 18: `account.move` — https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_move.py ; `account.move.line` — https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_move_line.py ; fechas de bloqueo — https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/company.py ; `account.lock_exception` — https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_lock_exception.py ; inalterabilidad — https://www.odoo.com/documentation/18.0/applications/finance/accounting/reporting/data_inalterability.html ; planes analíticos — https://raw.githubusercontent.com/odoo/odoo/18.0/addons/analytic/models/analytic_plan.py , https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_analytic_plan.py , https://raw.githubusercontent.com/odoo/odoo/18.0/addons/analytic/models/analytic_distribution_model.py
- Odoo 17: líneas de extracto — https://raw.githubusercontent.com/odoo/odoo/17.0/addons/account/models/account_bank_statement_line.py ; modelos de conciliación — https://raw.githubusercontent.com/odoo/odoo/17.0/addons/account/models/account_reconcile_model.py ; conciliación — https://www.odoo.com/documentation/17.0/applications/finance/accounting/bank/reconciliation.html ; facturas de proveedor — https://www.odoo.com/documentation/17.0/applications/finance/accounting/vendor_bills.html ; `account.edi.document` — https://raw.githubusercontent.com/odoo/odoo/17.0/addons/account_edi/models/account_edi_document.py
- OCA: `edi_oca` — https://raw.githubusercontent.com/OCA/edi-framework/17.0/edi_oca/models/edi_exchange_record.py ; bank-statement-import — https://github.com/OCA/bank-statement-import ; `unique_import_id` — https://raw.githubusercontent.com/OCA/bank-statement-import/18.0/account_statement_import_base/models/account_bank_statement_line.py ; account-reconcile — https://github.com/OCA/account-reconcile ; edi — https://github.com/OCA/edi ; `account_invoice_import` — https://github.com/OCA/edi/tree/12.0/account_invoice_import
- Apache Fineract — https://fineract.apache.org/docs/legacy/

***Ledgers* y librerías**
- TigerBeetle — https://docs.tigerbeetle.com/reference/transfer/ , https://docs.tigerbeetle.com/coding/data-modeling/ , https://docs.tigerbeetle.com/coding/linked-events/
- Formance Ledger v2 — https://raw.githubusercontent.com/formancehq/ledger/main/openapi/v2.yaml ; Formance Payments — https://docs.formance.com/modules/connectivity/payments
- Blnk — https://docs.blnkfinance.com/transactions/transaction-lifecycle , https://docs.blnkfinance.com/reconciliations/matching-rules , https://docs.blnkfinance.com/reconciliations/strategies.md
- django-hordak — https://django-hordak.readthedocs.io/en/latest/hordak-database-triggers.html
- python-accounting — https://github.com/ekmungai/python-accounting
- Beancount — https://beancount.github.io/docs/beancount_language_syntax/ ; beangulp — https://raw.githubusercontent.com/beancount/beangulp/master/beangulp/importer.py , https://raw.githubusercontent.com/beancount/beangulp/master/beangulp/extract.py ; smart_importer — https://github.com/beancount/smart_importer
- hledger, reglas CSV — https://hledger.org/1.40/hledger.html#csv
- invoice2data — https://github.com/invoice-x/invoice2data
- Patrón *transactional outbox* — https://microservices.io/patterns/data/transactional-outbox.html

**APIs unificadas abiertas y detalles nuevos de las cerradas**
- Panora — https://raw.githubusercontent.com/panoratech/Panora/main/packages/api/src/accounting/journalentry/types/model.unified.ts
- Nango — https://nango.dev/docs/implementation-guides/use-cases/unified-apis , https://nango.dev/docs/reference/api/sync/records-list
- Codat — https://docs.codat.io/using-the-api/push , https://docs.codat.io/using-the-api/modified-dates , https://docs.codat.io/bank-feeds/create-account , https://docs.codat.io/bank-feeds/pushing-transactions , https://docs.codat.io/payables/sync/bills
- Merge — https://docs.merge.dev/merge-unified/writing-data/programmatic-writes-with-meta/templates-and-conditional-fields , https://docs.merge.dev/accounting/journal-entries/ , https://docs.merge.dev/accounting/invoices/
- Xero Bank Feeds — https://github.com/XeroAPI/Xero-OpenAPI/blob/master/xero_bankfeeds.yaml ; bandeja de facturas — https://central.xero.com/s/question/0D53m00009ditslCAA/where-do-i-find-my-xero-bills-email-address
- QuickBooks, recibos por correo — https://quickbooks.intuit.com/learn-support/en-us/help-article/accounts-payable/email-receipts-bills-quickbooks-online/L7r2LAQ7C_US_en_US

**Banca y agregadores**
- Plaid — https://plaid.com/docs/api/products/transactions/ , https://plaid.com/docs/transactions/transactions-data/
- GoCardless Bank Account Data — https://docs.gocardless.com/bank-account-data/overview , https://bankaccountdata.gocardless.com/new-signups-disabled
- Open Banking UK — https://openbankinguk.github.io/read-write-api-site3/v3.1.10/profiles/event-notification-api-profile.html
- Midday — https://github.com/midday-ai/midday , https://midday.ai/docs/receipt-matching/ , https://midday.ai/updates/automatic-reconciliation-engine/
- Actual Budget — https://actualbudget.org/docs/transactions/importing/ ; Firefly III — https://docs.firefly-iii.org/references/data-importer/duplicate-detection/
- BCP Host to Host — https://www.viabcp.com/empresas/cobranzas-y-pagos/telecredito/host-to-host ; APIs de empresa (según terceros) — https://www.ecommercenews.pe/pagos-online/2026/bcp-optimiza-la-gestion-de-pagos-y-transferencias-de-empresas-con-apis-y-host-to-host.html/
- Prometeo, Perú (según el proveedor) — https://docs.prometeoapi.com/docs/per%C3%BA
- CONCAR CB — https://realsystems.com.pe/concar/concar-cb/ ; Starsoft — https://www.starsoft.com.pe/prod_contabilidad.html

**MCP**
- Changelogs — https://modelcontextprotocol.io/specification/2025-06-18/changelog , https://modelcontextprotocol.io/specification/2025-11-25/changelog , https://modelcontextprotocol.io/specification/2026-07-28/changelog
- Esquema 2025-11-25 (anotaciones, plantillas de recursos, tareas) — https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2025-11-25/schema.ts
- Herramientas — https://modelcontextprotocol.io/specification/2025-06-18/server/tools , https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- *Elicitation* — https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation ; MRTR — https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr ; tareas — https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks , https://modelcontextprotocol.io/seps/2663-tasks-extension
- Servidores — https://github.com/XeroAPI/xero-mcp-server , https://github.com/intuit/quickbooks-online-mcp-server , https://github.com/apideck-libraries/mcp , https://docs.merge.dev/merge-agent-handler/overview
- SDK de Python — https://github.com/modelcontextprotocol/python-sdk

**De la hoja de ruta** (§3, §6, §5, §9; consultadas el 13-sep-2026)

**Sistemas contables de escritorio (EE. UU.) y onboarding de integradores**
- IIF de QuickBooks Desktop — https://quickbooks.intuit.com/learn-support/en-us/help-article/list-management/iif-overview-import-kit-sample-files-headers/L5CZIpJne_US_en_US
- QuickBooks Web Connector — https://static.developer.intuit.com/qbSDK-current/doc/pdf/QBWC_proguide.pdf
- Codat, QuickBooks Desktop y Sage 50 — https://docs.codat.io/integrations/accounting/quickbooksdesktop/accounting-quickbooksdesktop/ , https://docs.codat.io/integrations/accounting/sage50/accounting-sage50
- Rutter, QuickBooks Desktop y respuestas asíncronas — https://docs.rutter.com/platforms/accounting/qbd , https://docs.rutter.com/rest/2024-08-31/basics
- Airbyte, contribuir un conector — https://docs.airbyte.com/platform/contributing-to-airbyte/submit-new-connector ; niveles — https://airbyte.com/blog/introducing-certified-community-connectors
- Fivetran Connector SDK — https://fivetran.com/docs/connector-sdk
- Intuit, requisitos técnicos para publicar — https://developer.intuit.com/app/developer/qbo/docs/go-live/publish-app/technical-requirements
- Xero, puntos de control de certificación — https://developer.xero.com/documentation/xero-app-store/app-partner-guides/certification-checkpoints

**Sistemas contables peruanos** (según el proveedor)
- SISCONT, descargas y SIRE — https://siscontonline.com/descargassiscont/ , https://siscontonline.com/siscont-6/
- STARSOFT, API de integración — https://starsoftweb.com/apisintegracion/Help

**SUNAT y el ecosistema abierto**
- Guías y manuales, reglas de validación — https://cpe.sunat.gob.pe/guias-y-manuales
- Padrón reducido del RUC — https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html
- API del BCRP — https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/api
- Greenter — https://github.com/thegreenter/greenter ; xml-parser — https://greenter.dev/packages/xml-parser/ ; lector del CDR — https://raw.githubusercontent.com/thegreenter/ws/master/src/Ws/Reader/DomCdrReader.php
- Lycet — https://github.com/giansalex/lycet
- Project OpenUBL — https://github.com/project-openubl
- Odoo, localización peruana — https://raw.githubusercontent.com/odoo/odoo/18.0/addons/l10n_pe/__manifest__.py ; licencias — https://www.odoo.com/documentation/18.0/legal/licenses.html

**Puerta abierta y conformidad**
- Speakeasy y Codat — https://www.speakeasy.com/customers/codat
- Apideck, especificaciones OpenAPI — https://github.com/apideck-libraries/openapi-specs
- Xero, OpenAPI — https://github.com/XeroAPI/Xero-OpenAPI
- Stainless — https://www.stainless.com/
- KoSIT — https://github.com/itplr-kosit/validator , https://github.com/itplr-kosit/validator-configuration-xrechnung
- Peppol BIS Billing 3 — https://github.com/OpenPEPPOL/peppol-bis-invoice-3
- EN 16931 — https://github.com/ConnectingEurope/eInvoicing-EN16931
- JSON Schema Test Suite y Bowtie — https://github.com/json-schema-org/JSON-Schema-Test-Suite , https://github.com/bowtie-json-schema/bowtie
- Odoo, manifiesto de módulo — https://www.odoo.com/documentation/18.0/developer/reference/backend/module.html
- Frappe, hooks — https://docs.frappe.io/framework/user/en/python-api/hooks

**Gobernanza de estándares**
- MCP, guía de SEP — https://modelcontextprotocol.io/community/sep-guidelines
- PEP 1 — https://peps.python.org/pep-0001/
- Peppol BIS, notas de versión — https://docs.peppol.eu/poacc/billing/3.0/release-notes/
- FDX 6.4 — https://financialdataexchange.org/fdx-feed/fdx-announces-spring-2025-api-release-fdx-api-version-6-4/
- Codat, política de cambios — https://docs.codat.io/using-the-api/change-policy
- SemVer — https://semver.org/

**Banca y pagos, EE. UU.**
- QuickBooks Online, banca con IA, match y reglas — https://quickbooks.intuit.com/learn-support/en-us/help-article/matching-rules/learn-updates-new-ai-powered-banking-page/L0hR7A9Zf_US_en_US , https://quickbooks.intuit.com/learn-support/en-us/help-article/bank-feeds/match-online-bank-transactions-quickbooks-online/L6qyw0PvP_US_en_US , https://quickbooks.intuit.com/learn-support/en-us/help-article/banking/set-bank-rules-categorize-online-banking-online/L0mjJl0nD_US_en_US
- Xero, `BankTransaction` — https://raw.githubusercontent.com/XeroAPI/Xero-OpenAPI/master/xero_accounting.yaml ; conciliación automática — https://blog.xero.com/product-updates/automatic-bank-reconciliation-jax-beta/
- Plaid Core Exchange 6.4 (FDX) — https://plaid.com/core-exchange/docs/reference/6.4/
- Yodlee, notificaciones — https://developer.yodlee.com/resources/yodlee/data-extracts/docs/event_notification ; MX, webhooks — https://docs.mx.com/resources/webhooks/
- Stripe, conciliación de liquidaciones — https://docs.stripe.com/payouts/reconciliation
- CFPB 1033, medida cautelar — https://bankingjournal.aba.com/2025/11/kentucky-federal-court-enjoins-cfpb-from-enforcing-current-1033-final-rule/ ; reconsideración — https://www.federalregister.gov/documents/2025/08/22/2025-16139/personal-financial-data-rights-reconsideration

**Banca y pagos, Perú**
- Culqi, webhooks — https://docs.culqi.com/es/documentacion/pagos-online/webhooks/
- Niubiz, callback de Pago Link — https://desarrolladores.niubiz.com.pe/docs/api-callback-de-pago-link.md
- Izipay, SDK con IPN — https://github.com/izipay-pe/PopIn-PaymentForm-Php-Sdk/blob/main/ipn.php
- Mercado Pago, reporte de liquidaciones — https://www.mercadopago.com.pe/developers/es/docs/checkout-pro-preferences/additional-content/reports/released-money/report-use
- Yape Empresa — https://www.yape.com.pe/productos/yape-empresa ; Plin — https://plin.pe/
- BBVA Perú, APIs — https://www.bbva.com/es/pe/innovacion/bbva-impulsa-la-transformacion-digital-empresarial-a-traves-de-sus-apis/
- MT940 en bancos peruanos (según terceros) — https://ramo.com.pe/sap-business-one-bancos-peru/
- SBS, lineamientos de finanzas abiertas — https://elperuano.pe/noticia/300693-finanzas-abiertas-estos-son-los-lineamientos-que-propone-la-sbs-para-el-sistema-en-peru
- BCRP, Circular 0017-2026 — https://actualidadcivil.pe/normas-legales/circular-0017-2026-bcrp/4d8622c5-a7c8-4097-bc64-8fe8b6d0caed

**El ciclo de EE. UU.: registros, factura y cuentas por pagar** (§1, §2, §3; consultadas el 14-sep-2026)
- IRC §6001 — https://www.law.cornell.edu/uscode/text/26/6001 ; 26 CFR 1.6001-1 — https://www.law.cornell.edu/cfr/text/26/1.6001-1
- IRS: Pub 583 — https://www.irs.gov/publications/p583 ; Pub 463 — https://www.irs.gov/publications/p463 ; cuánto conservar — https://irs.gov/businesses/small-businesses-self-employed/how-long-should-i-keep-records ; Rev. Proc. 98-25 — https://www.irs.gov/pub/irs-drop/rp-98-25.pdf
- W-9 — https://www.irs.gov/instructions/iw9 ; TIN Matching — https://www.irs.gov/tax-professionals/taxpayer-identification-number-tin-matching
- FAR 52.232-25 — https://www.acquisition.gov/far/52.232-25 ; DFARS 252.232-7006 — https://www.acquisition.gov/dfars/252.232-7006-wide-area-workflow-payment-instructions. ; IPP — https://www.ipp.gov/ ; OMB M-15-19 — https://www.whitehouse.gov/wp-content/uploads/legacy_drupal_files/omb/memoranda/2015/m-15-19.pdf , https://www.fedweek.com/federal-managers-daily-report/transition-to-electronic-invoicing-omb-tells-agencies/
- EDI X12 — https://x12.org/products/transaction-sets , https://www.cleo.com/edi-transactions/edi-810 ; SPS Commerce — https://www.spscommerce.com/edi-document/edi-810-electronic-invoice/
- SAP Business Network — https://www.sap.com/products/spend-management/ariba-network.html ; Coupa — https://docs.coupa.com/en/supplier-documentation/coupa-for-suppliers/the-coupa-supplier-portal-or-csp/features-and-processes-in-the-coupa-supplier-portal/invoices
- AvidXchange — https://www.avidxchange.com/suppliers/ ; BILL — https://www.bill.com/about-us
- DBNAlliance — https://dbnalliance.org/ ; conferencia de 2026 — https://www.prnewswire.com/news-releases/dbnalliance-to-host-united-states-e-invoicing-conference-in-new-york-city-on-april-22-302744325.html
- Billentis 2026 (según terceros) — https://qvalia.com/billentis-2026-key-report-findings/
- QuickBooks Online, facturas de proveedores — https://quickbooks.intuit.com/learn-support/en-us/help-article/pay-bills/enter-bills-record-bill-payments-quickbooks-online/L1e9Ce5J7_US_en_US ; envío de facturas — https://quickbooks.intuit.com/learn-support/en-us/help-article/invoicing/create-invoices-quickbooks-online/L7gSzvCld_US_en_US
- NetSuite: Bill Capture — https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/article_164726334180.html ; tres vías — https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_4096454192.html ; tolerancias — https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_4168980481.html

**Pagos y fraude en EE. UU.** (§6; consultadas el 14-sep-2026)
- AFP 2025, pagos digitales — https://www.financialprofessionals.org/training-resources/resources/survey-research-economic-data/Details/digitalpayments ; AFP 2026, fraude — https://www.financialprofessionals.org/about/learn-more/press-releases/Details/over-75-percent-of-us-firms-experienced-payments-fraud-in-2025-while-ai-adoption-for-fraud-mitigation-lags
- Nacha: Same Day ACH — https://www.nacha.org/news/same-day-ach-payment-limit-increase-10-million ; monitoreo de fraude — https://www.nacha.org/rules/risk-management-topics-fraud-monitoring-phase-1
- FedNow — https://www.frbservices.org/news/press-releases/090525-fednow-transaction-limit-increase ; ASC X9, remesa ISO 20022 — https://x9.org/iso-20022-remittance-market-practices-guide/
- FBI IC3 — https://www.ic3.gov/PSA/2017/PSA170504 , https://www.ic3.gov/PSA/2024/PSA240911

**La declaración en EE. UU.** (§7; consultadas el 14-sep-2026)
- CRS — https://www.congress.gov/crs-product/IF13037
- Renta: 1125-A — https://www.irs.gov/forms-pubs/about-form-1125-a ; Schedule M-3 — https://www.irs.gov/instructions/i1120sm3 ; 1120 — https://www.irs.gov/instructions/i1120
- South Dakota v. Wayfair — https://www.supremecourt.gov/opinions/17pdf/17-494_j4el.pdf
- Streamlined Sales Tax — https://www.streamlinedsalestax.org/Shared-Pages/faqs/faqs---about-streamlined ; archivos de tasas y límites — https://www.streamlinedsalestax.org/Shared-Pages/rate-and-boundary-files ; CSP — https://www.streamlinedsalestax.org/certified-service-providers/what-is-a-csp ; F0003 — https://www.streamlinedsalestax.org/docs/default-source/forms/exemption-certificate-instructions.pdf
- California — https://cdtfa.ca.gov/taxes-and-fees/sales-use-tax-returns-filing-dates.htm , https://cdtfa.ca.gov/taxes-and-fees/applying-tax-sales-purchases-faq.htm
- Texas — https://comptroller.texas.gov/taxes/sales/filing-requirements.php , https://comptroller.texas.gov/taxes/sales/use-tax.php
- Nueva York — https://www.tax.ny.gov/forms/current-forms/st/st100i.htm , https://www.tax.ny.gov/pubs_and_bulls/tg_bulletins/st/filing_requirements_for_sales_and_use_tax_returns.htm
- Puerto Rico — https://hacienda.pr.gov/ivu/planilla-mensual-de-ivu , https://hacienda.pr.gov/publicaciones/determinacion-administrativa-num-15-20
- 1099: P.L. 119-21 — https://www.congress.gov/119/plaws/publ21/PLAW-119publ21.pdf ; Pub 1099 — https://www.irs.gov/publications/p1099 ; instrucciones — https://www.irs.gov/instructions/i1099mec ; 1099-K — https://www.irs.gov/newsroom/irs-issues-faqs-on-form-1099-k-threshold-under-the-one-big-beautiful-bill-dollar-limit-reverts-to-20000 ; backup withholding — https://www.irs.gov/businesses/small-businesses-self-employed/backup-withholding ; TD 9972 — https://www.federalregister.gov/documents/2023/02/23/2023-03710/electronic-filing-requirements-for-specified-returns-and-other-documents
- FIRE e IRIS — https://www.irs.gov/e-file-providers/filing-information-returns-electronically-fire ; Pub 1220 — https://www.irs.gov/pub/irs-pdf/p1220.pdf ; Pub 5717 — https://www.irs.gov/pub/irs-pdf/p5717.pdf ; Pub 5718 — https://www.irs.gov/pub/irs-pdf/p5718.pdf

**Normas peruanas verificadas** (§2, §7; consultadas el 14-sep-2026)
- TUO de la Ley del IGV, capítulo I — https://www.sunat.gob.pe/legislacion/tributaria/igv/ley/capitul1.htm ; capítulo III — https://www.sunat.gob.pe/legislacion/igv/ley/capitul3.pdf
- RS 000047-2026/SUNAT, Formulario 1662 — https://www.sunat.gob.pe/legislacion/superin/2026/000047-2026.pdf ; anexo de la RS 040-2022/SUNAT, tipos 91, 97 y 98 — https://www.sunat.gob.pe/legislacion/superin/2022/anexo-040-2022.pdf
- Retención del IGV — https://orientacion.sunat.gob.pe/73-importe-de-la-operacion-y-tasa-de-retencion ; comprobante de retención — https://cpe.sunat.gob.pe/tipos_de_comprobantes/comprobante_de_retencion
- DAOT — https://orientacion.sunat.gob.pe/declaracion-anual-de-operaciones-con-terceros-daot , https://orientacion.sunat.gob.pe/03-operaciones-que-no-deben-considerarse-para-el-calculo-de-las-operaciones-con-terceros-daot ; PLAME 601 — https://www2.sunat.gob.pe/pdt/pdtModulos/independientes/p601/faq/regPrestadores.html
- Factura negociable: Plataforma de Confirmación — https://cpe.sunat.gob.pe/plataforma-de-confirmacion-del-rhe-y-de-la-fe ; RS 165-2021/SUNAT — https://busquedas.elperuano.pe/dispositivo/NL/2012062-1 ; DS 239-2021-EF — https://busquedas.elperuano.pe/normaslegales/aprueban-el-reglamento-del-titulo-i-del-decreto-de-urgencia-decreto-supremo-no-239-2021-ef-1992708-3/
- Puesta a disposición del comprobante, RS 206-2019/SUNAT — https://elperuano.pe/NormasElperuano/2019/10/22/1819173-1/1819173-1.htm ; manual de la API del SIRE de compras v24 — https://cpe.sunat.gob.pe/sites/default/files/inline-files/Manual%20de%20servicios%20Web%20Api%20-%20SIRE_Compras%20v24.pdf
- Guía de elaboración del XML de la factura UBL 2.1 — https://cpe.sunat.gob.pe/sites/default/files/inline-files/guia%2Bxml%2Bfactura%2Bversion%202-1%2B1%2B0%20%282%29_0%20%282%29.pdf
- SIRE para todos los obligados, RS 000125-2026/SUNAT — https://www.sunat.gob.pe/legislacion/superin/2026/000125-2026.pdf
