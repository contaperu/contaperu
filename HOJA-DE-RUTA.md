# Hoja de ruta de ContaPerú

## 0 · Cómo se lee

Este documento dice **en qué orden** crece el motor y **qué hace falta** para cada paso. El diseño y el pseudocódigo de
cada pieza viven en [INTEROPERABILIDAD.md](INTEROPERABILIDAD.md) y aquí solo se remite a ellos; lo que se tomó de las
plataformas cerradas de EE. UU. está en [REFERENCIAS.md](REFERENCIAS.md). Lo que ya está hecho se ve en la tabla «Estado»
del [README.md](README.md).

Cuatro principios la ordenan:

- **Encima, no en lugar de.** Nadie cambia de sistema contable: el motor traduce hacia el que ya existe.
- **Crece con casos reales.** Una regla contable entra con su fuente, un driver o un lector con un archivo real que su
  sistema haya aceptado, y un campo del estándar con el caso que lo pide.
- **Sin fechas.** Lo que no está publicado es «próximo». Cada hito tiene, en cambio, un **criterio de salida
  verificable**: un test que pasa, un archivo aceptado, una versión etiquetada.
- **El núcleo no se mueve de su frontera**: sin red, sin disco, sin estado y sin reloj (`tests/test_frontera.py:75`). Lo
  que conecta, guarda o aprende vive fuera.

Cada frente (A-E) sigue el mismo molde: objetivo, **cómo lo resuelve EE. UU.** (la referencia que guía la
implementación), qué hay hoy y una tabla de hitos. La tabla usa estas columnas y marcas:

| Columna o marca | Significado |
|---|---|
| **Nivel** | `N` núcleo · `D` driver · `F` fachada o puerta (CLI, MCP) · `App` aplicación que consume el motor · `estándar` · `documentación` |
| **Arranca con** | `código` si se puede empezar ya; `dato: …` si espera un archivo real, una especificación o una norma |
| **Criterio de salida** | Lo que tiene que ser cierto para darlo por cumplido |
| `nombre*` | Nombre provisional: lo decide el mantenedor al pasar a código |
| *no verificado* · *según terceros* · *según el proveedor* | Calidad de la fuente, a la fecha de consulta (13-sep-2026) |

El documento sigue el orden de los frentes; **el orden de ejecución está en el §4**.

---

## 1 · Dónde estamos

Librería **0.10.0** y estándar **`open-accounting` 0.3** (`contaperu/_version.py`).

| Pieza | Hoy |
|---|---|
| Lectores | XML UBL 2.1 con raíz `Invoice`, `CreditNote` o `DebitNote` (`contaperu/lectores/xml_ubl.py:31`); ZIP; propuesta del SIRE. El CDR se reconoce y se ignora. PDF y fotos quedan pendientes para quien use IA |
| Validación | Observaciones propias, estables por contrato (`contaperu/validar.py`); duplicados dentro del lote |
| Asiento | Línea neutral con `rol`, cuadre sin tolerancia, detracción en dos tiempos, huella por tanda |
| Drivers de serie | CONCAR (asientos), CONTASIS (registro), SIRE (TXT) y CSV, más los de terceros por el grupo `contaperu.drivers` (`contaperu/drivers/__init__.py:37`) |
| Puertas | Fachada `operaciones`, CLI y servidor MCP con 11 herramientas y 5 recursos; hay un `Dockerfile` |
| Pendiente que depende de datos | SISCONT y STARSOFT, la conciliación de constancias de detracción, las equivalencias del PCGE 2026 |

---

## 2 · Fase 0 · Afinar lo que existe

Antes de abrir frentes se afina lo que ya está en uso. Todo arranca con **código**; varias piezas desbloquean frentes
posteriores. Las propuestas de origen están en `INTEROPERABILIDAD.md` §9.

| id | Hito | Nivel | Criterio de salida | Depende de |
|---|---|---|---|---|
| **0.0** | **Decidir la identidad del comprobante**: `libro.ruc` + `libro.tipo` + `Comprobante.clave` (`contaperu/modelo.py:300`), sin periodo, y si en ventas lleva la contraparte (`comparar_sire` la deja fuera por la misma razón) | estándar · F | Escrita en `estandar/LEEME.md` | — |
| **0.1** | **`claves_previas` en la fachada**: `revisar`, `diagnosticar`, `generar_asiento`, `exportar`, CLI y MCP. `validar.revisar` ya lo acepta (`contaperu/validar.py:244`). En JSON viaja como `[tipo_cp, serie, numero, contraparte_doc]`, normalizado con `clave_de`, y con un tope como `MAXIMO_COMPROBANTES` (`contaperu/operaciones.py:33`) | F | Por las tres puertas sale `DUPLICADO_PERIODO_ANTERIOR` con `pedir_a: contador`; «00000123» casa con «123»; por encima del tope, `DocumentoInvalido`; sin claves, el snapshot de CONCAR sale idéntico | 0.0 |
| **0.2** | **Anotaciones MCP**: `readOnlyHint: true` y `openWorldHint: false` en las 11 herramientas, y subir el mínimo del pin `mcp` al primero que las acepte (*no verificado* cuál) | F | `tests/test_servidor_mcp.py` recorre `list_tools()`; un trabajo de CI instala el mínimo declarado y pasa | — |
| **0.3** | **La frase de la detracción regenerada**: `estandar/LEEME.md`, «La detracción, que ocurre en dos tiempos», dice que el asiento «puede regenerarse». En un destino que suma, regenerar lo ya importado duplica | estándar | El texto dice que el segundo tiempo es una decisión contable que entra con fuente y archivo real | — |
| **0.4** | **Índice por comprobante** `_asiento.comprobantes*` y `_exportacion.comprobantes*`: identidad, rango de líneas y huella por comprobante (diseño: `INTEROPERABILIDAD.md` §3). En la familia registro, sin huella | F | Los rangos son una partición exacta; cada rango cuadra; `HUELLA_FACTURA` (`tests/test_huella.py:24`) no cambia | 0.0 |
| **0.5** | **El disco sale del núcleo**: `comparar_sire.leer` y `pcge.adaptar.cargar_equivalencias(ruta)` (`contaperu/pcge/adaptar.py:89`) reciben bytes o `dict`, y un único `datos_empaquetados*()` con `importlib.resources` lee lo que viaja dentro del paquete | puerta · N | Un test cae si otro módulo del núcleo abre un archivo | — |
| **0.6** | **Tipo de cambio y tasa de detracción como texto** en la línea neutral (hoy `float`, `contaperu/asiento/motor.py:71` y `:111`); `float` solo al escribir la columna | N · D | Snapshot de CONCAR intacto; la huella de las tandas en dólares o con detracción cambia con literal nuevo y **se anuncia** en el CHANGELOG | — |
| **0.7** | **Un PDF o una foto enviados a `leer_xml` cuentan como pendientes de leer**, no como «XML inválido» (hoy `_nombre_de` los llama `comprobante.xml`, `contaperu/operaciones.py:240`) | F | Test por el MCP y por la CLI: `_lectura.pendientes_de_leer` = 1 | — |
| **0.8** | **Coherencia de `diagnosticar`**: que `totales.saldrian` y la lista `saldrian` cuenten lo mismo, y que el serie-número se escriba igual que en la línea (a confirmar al empezar) | F | Test que fija la misma cifra y el mismo nombre | — |

---

## 3 · Los cinco frentes

### A · Drivers legacy: SISCONT y STARSOFT

**Objetivo.** Que SISCONT y STARSOFT salgan del mismo documento que CONCAR y CONTASIS, cada uno con su archivo aceptado.
Es la prioridad por uso: son, con CONCAR y CONTASIS, los sistemas contables que más estudios peruanos tienen instalados.

**Cómo lo resuelve EE. UU.** Los sistemas de escritorio sin API se integran en tres escalones, y cada uno tiene su
análogo peruano:

| Escalón | EE. UU. | Aquí |
|---|---|---|
| **1 · Archivo** | QuickBooks Desktop importa **IIF**, texto tabulado con `!TRNS`/`!SPL`/`!ENDTRNS`, con «only limited error checking» ([Intuit](https://quickbooks.intuit.com/learn-support/en-us/help-article/list-management/iif-overview-import-kit-sample-files-headers/L5CZIpJne_US_en_US)) | El Excel de CONCAR y el de CONTASIS |
| **2 · SDK o API local** | **qbXML** (`JournalEntryAddRq` con líneas de débito y crédito) | La API web de STARSOFT Contabilidad Gold Edition (`POST Api/RegistrarAsientoCompras`, `…Ventas`, `…Standar`…; [ayuda](https://starsoftweb.com/apisintegracion/Help)) |
| **3 · Agente en la PC del cliente** | **QuickBooks Web Connector**: un `.QWC` y un servicio SOAP al que «QuickBooks llama» (`authenticate`, `sendRequestXML`, `receiveResponseXML`; [guía](https://static.developer.intuit.com/qbSDK-current/doc/pdf/QBWC_proguide.pdf)). Codat y Rutter lo usan con **escrituras en cola** y restricciones declaradas: la PC encendida, un usuario, horario de sincronización ([Codat](https://docs.codat.io/integrations/accounting/quickbooksdesktop/accounting-quickbooksdesktop/), [Rutter](https://docs.rutter.com/platforms/accounting/qbd)) | Un conector local, **de la aplicación y nunca del motor** |

Lo que se toma: la escritura hacia un legacy es asíncrona y se confirma después —el nombre reservado `estado` de la
línea, `exportado → importado`, lo pondrá quien importó—, y las limitaciones del destino se declaran antes de escribir
(`EXIGE`, `no_caben`).

**Qué hay hoy.** Las cuatro formas del contrato (`contaperu/drivers/contrato.py:71`) y la receta con la que entró
CONTASIS (`CONTRIBUTING.md` §«Añadir un driver de salida», `CHANGELOG.md` 0.10.0):

1. Pedir dos archivos al sistema: su plantilla y un mes que haya importado.
2. Elegir la forma: `desde_comprobantes` si importa registros, `desde_lineas` si importa asientos.
3. Llevar al núcleo, antes del driver, lo que no es del driver.
4. `datos.py` con cada columna y su fuente; `proyeccion.py` que solo traduce; el escritor del archivo.
5. Pruebas en cuatro capas: snapshot con datos inventados, driver por la fachada, plantilla contra los archivos privados,
   contrato.
6. Revisión humana del primer archivo y configuración declarada por sección.
7. Aceptación real importando un mes; recién entonces documentación y etiqueta.

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de |
|---|---|---|---|---|---|
| A1 | SISCONT, registro de compras y ventas → `desde_comprobantes` | D | dato: plantilla + un mes importado | Las cuatro capas de prueba; un mes importado; fila en «Estado»; CHANGELOG y tag | — |
| A2 | ¿Acepta SISCONT el TXT que genera el driver `sire`? (SISCONT importa la propuesta del SIRE, *según el proveedor*; qué formato, *no verificado*) | documentación | dato: una prueba | Nota en la guía; ningún código | — |
| A3 | SISCONT, asientos → `desde_lineas` | D | dato: un caso que A1 no cubra | Igual que A1 | A1 |
| A4 | STARSOFT, asientos → `desde_lineas` | D | dato: plantilla + un mes importado | Igual que A1 | — |
| A5 | El **cuerpo JSON** de la API de STARSOFT Gold, como proyección pura de las líneas | D | dato: una respuesta aceptada guardada en `privado/` | Test contra el cuerpo aceptado; autenticarse y enviar es de la aplicación | A4 |

**No se hace.** Un formato común para todos los legacy: el TXT del SIRE no lleva cuentas y pierde la imputación, y no
consta que ninguno importe el Libro Diario 5.1 del PLE (*no verificado* en negativo). Ningún driver sale a la red.

### B · La puerta abierta para cualquier ERP

**Objetivo.** Que un ERP escrito en cualquier lenguaje mande un documento `open-accounting` y reciba el asiento o el
archivo de su destino, con un kit que le diga cómo integrarse y cómo comprobar que lo hizo bien.

**La puerta ya existe**: el documento del estándar es la entrada canónica, y un ERP no necesita un lector propio. Lo que
falta es publicarla para quien no escribe Python.

**Cómo lo resuelve EE. UU.**

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

**Qué hay hoy.** La fachada `operaciones` («dict entra, dict sale»; `diagnosticar`, `generar_asiento` y `exportar` en
`contaperu/operaciones.py`), el grupo de entry points de drivers, la CLI, el MCP y un `Dockerfile`. Dos herramientas del
MCP tienen su lógica en la puerta y no en la fachada: `buscar_cuenta_pcge` y `normalizar_detracciones`
(`contaperu/servidor_mcp.py:339` y `:381`). La fachada tipa todo como `dict`, así que un OpenAPI no sale de sus firmas:
hace falta declararlo.

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de |
|---|---|---|---|---|---|
| B1 | Las dos operaciones pasan a la fachada, y una tabla `OPERACIONES*` declara cada operación con su entrada y su salida (con `$ref` al esquema del estándar) | F | código | Cada herramienta MCP llama a una operación de la tabla; ninguna puerta importa `pcge` ni `detracciones` | 0.5 |
| B2 | `motor*` (la versión) en `_asiento` y `_exportacion`, y `outputSchema` de `diagnosticar` que cubra también la respuesta con configuración inválida | F | código | Las dos formas validan; `motor` queda fuera de la huella | 0.2, 0.4 |
| B3 | **OpenAPI 3.1** generado por una herramienta desde `OPERACIONES*` | F · documentación | código | Regenerarlo no cambia bytes; los documentos de ejemplo validan como cuerpos | B1, B2 |
| B4 | Puerta **HTTP sin estado**, `servidor_http*`, con el extra `contaperu[http]*` | puerta | dato: un integrador no Python que lo necesite | Está en `PUERTAS` de `tests/test_frontera.py`; las tres puertas dan el mismo documento; comparte topes y la defensa de `Host` del MCP; publicar su imagen pide OK | B3 |
| B5 | El CSV lleva `rol` y los `tipo_cp`, lo que un driver necesita para no adivinar | D | código | Columnas nuevas llenas; **se anuncia** porque cambia una salida | — |
| B6 | **Guía «integrar ContaPerú en un ERP»**: la librería (Odoo, Frappe), la CLI por lotes, el MCP y, con B4, HTTP; niveles *de serie* (con archivo aceptado) y *comunidad* (paquete propio por entry points); checklist de contribución | documentación | código | Los ejemplos en Python se ejecutan en la batería; `contaperu://drivers` dice si cada driver es de serie | B1 |
| B7 | **Contrato de lector** y entry points `contaperu.lectores*`, el espejo de entrada del contrato de driver (el `Importer` de beangulp: identificar, extraer, deduplicar) | N | dato: el segundo lector bancario | Test de conformidad análogo a `tests/test_contrato_drivers.py` | D2 |

La **conformidad declarada** —pasar la suite del estándar (E2) y, si es un driver, tener su archivo aceptado— es el
análogo de la certificación de Xero o Intuit, sin sellos ni tercero que la otorgue.

**No se hace.** SDKs generados (esperan un integrador que los pida), WASM o Pyodide (antes habría que probar que sus
dependencias cargan), OAuth, estado ni sellos de certificación.

### C · Leer y validar más, sin emitir

Es el **primer frente tras la Fase 0**, en paralelo con A.

**Objetivo.** Que el motor valide con las reglas y los códigos oficiales de SUNAT tomados como datos, y que lea más
documentos de los que ya recibe una empresa. **Nunca emite**: no genera, no firma, no envía y no consulta la validez de
un comprobante; eso es de quien tenga red y credenciales.

**Cómo lo resuelven los proyectos abiertos y SUNAT.**

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

**Qué hay hoy.** Catálogos escritos a mano (`contaperu/catalogos.py`); tres raíces de XML, y cualquier otra da «Raíz XML
no reconocida» (`contaperu/lectores/xml_ubl.py:31`); el CDR se ignora; códigos de observación propios, ninguno igual a
uno oficial; y un precedente de norma convertida en datos con su cita, `herramientas/extraer_pcge2026.py`.

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de |
|---|---|---|---|---|---|
| C1 | `herramientas/extraer_reglas_sunat*.py` → JSON empaquetado con `actualizado_al`, hoja y fila de cada dato: códigos de retorno, catálogos y solo las reglas con efecto contable | N · herramienta | dato público, ya disponible | Reproducible; lo que hoy está a mano en `catalogos.py` está contenido en el JSON o la diferencia queda listada; la hoja de cálculo no entra al repositorio | 0.5 |
| C2 | `codigo_sunat*` en la observación, como campo añadido: los códigos propios no se renombran | N · estándar | código | Cada código citado existe en el JSON; la tabla `PEDIR_A` no cambia | C1, E1 |
| C3 | `leer_cdr*`: aceptado, observado y rechazado; abrir el ZIP en que suele llegar | N · F | dato: CDR reales | Un rechazo produce su observación con el código oficial | C1, E1 |
| C4 | `retencion_igv` (nombre reservado) desde `PaymentTerms` de la factura | N · estándar | dato: un destino que lo pida | `retencion` (renta de 4ta) intacta; snapshot idéntico | E1 |
| C5 | Comprobantes de **retención (20)** y **percepción (40)** en un bloque propio | N · estándar | dato: XML reales + la fuente de su tratamiento | No entran al RCE ni al RVIE; ningún driver los escribe sin fuente | C1, E1 |
| C6 | **Liquidación de compra (04)**: la contraparte es el vendedor, no quien emite | N | dato: XML real | Sin falso `XML_PARA_OTRO_RUC` (test de mutación) | — |
| C7 | **Recibo por honorarios electrónico** leído del archivo de SOL | N | dato: archivo real | Tipo 02 con `retencion`; sin falso `RETENCION_TASA` | — |
| C8 | `padron*` como argumento, con forma `{ruc: {activo*, habido*}}`, y aviso de proveedor no habido | N · F | dato: la fuente legal del aviso + tope | Sin padrón no cambia nada | 0.1 |
| C9 | `cruzar_con_propuesta*`: lo cargado contra la propuesta del RCE, y el primer uso de `pedir_a: proveedor` (diseño: `INTEROPERABILIDAD.md` §6) | N · F | código | Tres cajones; ceros a la izquierda; un RUC mal escrito | 0.0 |
| C10 | `plan_de_cuentas*` del destino, falta `cuenta_fuera_del_plan*`, marca de centro de costo y lista de centros (diseño: `INTEROPERABILIDAD.md` §2) | N · F · D | dato: plan exportado de CONCAR + un rechazo real de importación | Sin plan, snapshot idéntico; un plan sin la cuenta bloquea y `exportar` lanza | — |
| C11 | `tipos_de_cambio*` como argumento: **contrasta, no rellena** | N · F | dato: la fuente del tipo de cambio que rige | Un tipo de cambio distinto del publicado da un aviso | C8 |

**No se hace.** Ejecutar las XSL; leer guías de remisión (09/31), que no tienen efecto contable; portar código PHP (se
toman las rutas XPath con la cita a SUNAT); usar los XML de prueba de Greenter como fixtures (se hacen con los RUC
seguros o con archivos reales en `privado/`); sustituir la Tabla 10 del SIRE por el Catálogo 01, que incluye menos tipos.

### D · El banco inicia el proceso contable

**Objetivo.** Que un hecho bancario —una línea de extracto o la liquidación de una pasarela de pagos— se lea, se
deduplique, se empareje con lo que salda y, cuando haya fuente, se asiente. Al estilo de EE. UU., y con el núcleo sin
red.

**Cómo lo resuelve EE. UU., de verdad.**

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

**Perú, a la fecha de consulta.**

| Canal | Qué hay | Calidad |
|---|---|---|
| Pasarelas | Culqi con webhooks ([docs](https://docs.culqi.com/es/documentacion/pagos-online/webhooks/)); Niubiz con callback firmado `NBZ-Signature` ([docs](https://desarrolladores.niubiz.com.pe/docs/api-callback-de-pago-link.md)); Izipay con IPN y `kr-hash`; Mercado Pago con webhooks `x-signature` y un **reporte de liquidaciones por API** con columnas documentadas ([MP](https://www.mercadopago.com.pe/developers/es/docs/checkout-pro-preferences/additional-content/reports/released-money/report-use)) | Según el proveedor |
| Yape y Plin | Yape Empresa descarga reportes de 90 días, sin API; Yape en línea entra por las pasarelas; Plin no publica API y solo se ve como abono en el extracto | Según el proveedor |
| APIs de bancos | BBVA Perú anuncia API Pay con saldos y movimientos en tiempo real ([BBVA](https://www.bbva.com/es/pe/innovacion/bbva-impulsa-la-transformacion-digital-empresarial-a-traves-de-sus-apis/)); APIs de empresa del BCP | BBVA según el banco; BCP según terceros |
| Extractos | Excel o TXT de la banca por internet; MT940 en los bancos grandes | MT940 según terceros; columnas sin fuente |
| Agregadores | Prometeo consulta movimientos por sondeo con las credenciales del usuario | Según el proveedor |
| Regulación | SBS: lineamientos de finanzas abiertas del 20-jul-2026 que priorizan ahorro y tarjetas de crédito, sin cuentas corrientes ni empresas; regulación hacia 2027. BCRP: pagos inmediatos con alias, interoperabilidad de pagos y no de datos | Según terceros |

**Qué hay hoy.** Nada de banco. La conciliación de constancias de detracción está pendiente de un archivo real, pero la
mitad existe: `diagnosticar` ya lista las detracciones que esperan constancia (`_detraccion_pendiente`,
`contaperu/operaciones.py:405`) y el monto en soles enteros tiene su regla con fuente
(`contaperu/detracciones.py:57`). Hay dos trampas para un lector de extractos: un `.xlsx` empieza como un ZIP y se
desarma (`contaperu/lectores/archivos.py:56-58`), y un `.txt` se ignora como archivo auxiliar (`archivos.py:26`).

**El diseño**, ya detallado en `INTEROPERABILIDAD.md` §5, con cinco precisiones:

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

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de |
|---|---|---|---|---|---|
| D1 | `aplicar_constancias*`: de `PROVISIONADO` a `PAGADO` con número y fecha de constancia | N · F | dato: constancias reales (la consulta de pagos de detracciones de SOL o los movimientos de la cuenta del Banco de la Nación) | Con pareja, pasa a `PAGADO`; sin pareja, queda igual; bajan las pendientes de `diagnosticar` | 0.3 |
| D2 | `Movimiento*`, el lector del primer extracto y la deduplicación | N · estándar | dato: extracto real anonimizado | Un libro Excel no se desarma como ZIP; una relectura con solape no duplica | E1 |
| D3 | `conciliar*` con `metodo*` y `certeza*`, la tabla `aplicaciones*` y `emparejar_transferencias*` | N · F | código, tras D1 y D2 | Motivos legibles; la detracción como pago parcial; solo certeza alta va a lote | D1, D2 |
| D4 | `ReglaBanco*` y `aplicar_reglas*` | N | dato: reglas reales de un contador | Primera coincidencia por prioridad, con motivo; nunca confirma | D2 |
| D5 | `LiquidacionPasarela*` y `Aviso*` | N · estándar | dato: el reporte real de una pasarela | El invariante del neto se cumple; los avisos nunca asientan | D3, E1 |
| D6 | Asientos de tesorería y de liquidación | N · D | dato: cuentas del PCGE con su cita, el ITF con su norma, el tratamiento del IGV de la comisión y un archivo aceptado del sub-diario de bancos de CONCAR | Archivo aceptado; snapshot de CONCAR idéntico | D3, D5 |
| D7 | Dónde viven los conectores de entrada | `App` o paquete aparte | dato: el primer conector real | Decisión escrita con el criterio de abajo | D2 o D5 |

**D7 · Dónde viven los conectores: decisión abierta.** Webhooks de pasarelas, APIs de bancos, agregadores y lectura de
correo necesitan red, credenciales, cursor y reintentos. Hay dos caminos:

| Camino | A favor | En contra |
|---|---|---|
| **Un paquete abierto aparte del núcleo** (como Formance separa sus conectores de pagos de su *ledger*, o Airbyte sus conectores) | Lo reutilizan varias aplicaciones; la normalización de cada fuente se hace y se revisa una sola vez | Mantener clientes de APIs que cambian; términos de uso de cada proveedor; pruebas sin red; responsabilidad pública de seguridad |
| **Cada aplicación** | Credenciales, cursor y reintentos junto a su estado; su propio ritmo | Cada una rehace la normalización y repite los errores de deduplicación |

El criterio para decidir: ¿hay más de un consumidor real del mismo conector?; ¿los términos del proveedor permiten
publicar el cliente?; ¿se puede probar sin red ni credenciales?; ¿quién responde cuando cambia la API?; ¿la normalización
se separa del transporte? —si es así, la lectura de bytes puede entrar al motor y solo el transporte queda fuera—.

Lo que no cambia en ninguno de los dos: **ningún conector vive dentro del paquete `contaperu`**, porque rompería la
frontera del núcleo (`tests/test_frontera.py:75`), y la firma de un webhook, el cursor y las credenciales viajan con el
conector, no con el motor.

**No se hace.** Una cuenta transitoria por cada línea bancaria (el destino suma y duplicaría asientos); aprendizaje
estadístico dentro del motor (lo aprendido llega como dato); confirmar automáticamente; seguir las finanzas abiertas de
la SBS como hito: se vigilan y se adoptan cuando exista la regulación.

### E · El estándar mejora siempre

Es **transversal**: acompaña a todos los frentes.

**Objetivo.** Que `open-accounting` cambie por un proceso escrito —caso real, fuente, test y compatibilidad declarada— y
que un tercero pueda comprobar que su implementación cumple.

**Cómo lo resuelven otros estándares.**

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

**Qué hay hoy.** `estandar/LEEME.md` ya tiene una regla de versionado (lo aditivo no sube la versión; lo que cambia de
significado, sí), siete nombres reservados y un tag del estándar que avanza con cada cambio aditivo;
`tests/test_estandar.py` valida el esquema. La salida de `cuenta_contable` en la 0.3 fue legado y retiro el mismo día:
no hubo aviso previo.

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de |
|---|---|---|---|---|---|
| E1 | `estandar/enmiendas*/NNNN-titulo.md`: plantilla, estados, y los siete nombres reservados migrados como enmiendas en estado `reservada`. El LEEME sigue siendo el texto normativo | estándar · documentación | código | Cada reservado del LEEME tiene su enmienda; cada enmienda `final` cita un test que existe | — |
| E2 | `estandar/conformidad*/`: casos de esquema `{description, data, valid}` y casos de `diagnosticar` con lo esperado (`listo`, motivos, `pedir_a`) | estándar | código | Los corre la batería; hay un caso por regla de `validar` y por fila de `FALTAS`; los de esquema se ejecutan sin el motor | E1 |
| E3 | Política escrita de retiro: legado en una versión, rechazo en la siguiente; cada cambio con su fecha de vigencia | estándar | código | Revisada; `tests/test_estandar.py` sigue verde | E1 |
| E4 | Revisión cuando SUNAT cambia la fecha «actualizado al» de sus reglas | proceso | dato: la nueva versión de SUNAT | JSON de C1 regenerado; las diferencias, en el CHANGELOG | C1 |

**Plantilla de enmienda:** `# NNNN · título` · **Estado** · **Compatibilidad** (aditivo o cambio de significado) ·
**Nivel** · **Motivación** (el caso real) · **Fuente** · **Especificación** · **Test** · **Versión**.

**Estados:** `borrador → con caso real → aceptada → final`, y además `reservada`, `rechazada` y `reemplazada`.

---

## 4 · Secuencia y dependencias

El orden de ejecución: **Fase 0 → C (en paralelo con A) → B y D**, con E acompañando desde el principio porque sus
enmiendas tienen que existir antes del primer bloque nuevo del esquema.

```
FASE 0 (código) ──────────────────────────────────────────────────────────────────────────────────
 0.0 identidad ──┬─► 0.1 claves_previas ──┬─► C8 padrón ─► C11 tipos de cambio
                 │                        └─► C9 cruzar con la propuesta
                 └─► 0.4 índice ─────────────┐
 0.2 anotaciones MCP ────────────────────────┴─► B2 ─┐
 0.5 disco fuera del núcleo ─┬─► C1 reglas SUNAT ─┬─► C2 código oficial
                             │                    ├─► C3 CDR          [CDR reales]
                             │                    ├─► C5 20 / 40      [XML + fuente]
                             │                    └─► E4 revisión     [nueva versión SUNAT]
                             └─► B1 fachada ─────────┴─► B3 OpenAPI ─► B4 HTTP [integrador]
                                   └─► B6 guía
 0.3 frase del LEEME ─► D1 constancias [archivo] ─────┐
 E1 enmiendas ─┬─► C2 · C3 · C4 · C5                   ├─► D3 conciliar ─► D5 pasarela [reporte] ─► D6 asientos
               ├─► D2 extracto [archivo] ──────────────┘                                           [fuente + aceptado]
               │     ├─► D4 reglas bancarias [reglas reales]
               │     ├─► B7 contrato de lector [segundo banco]
               │     └─► D7 conectores [primer conector]
               ├─► E2 conformidad
               └─► E3 política de retiro

Sin dependencias de código: A1-A5 [archivos aceptados] · C6 [04 real] · C7 [RHE real] · C10 [plan + rechazo]
                            · 0.6 · 0.7 · 0.8 · B5
```

| Orden | Hitos | Arranca con |
|---|---|---|
| 1 | 0.0 → 0.1, 0.4 · 0.2 · 0.3 · 0.5 · 0.6 · 0.7 · 0.8 | código |
| 2 | E1 | código |
| 3 | C1 | dato público, ya disponible |
| 4 | C9 · C2 | código |
| 5 | E2 · E3 | código |
| 6 | B1 · B2 · B5 · B3 · B6 | código |
| en paralelo | A1-A5 | dato: archivos aceptados |
| cuando llegue el dato | C3 · C4 · C5 · C6 · C7 · C8 · C10 · C11 | dato |
| cuando llegue el dato | D1 · D2 → D3 · D4 → D5 → D6 | dato (D3 es código, tras D1 y D2) |
| cuando haga falta | B4 · B7 · D7 · E4 | dato o decisión |

**Lo que hay que conseguir, y dónde.**

| Para | Qué | Cómo |
|---|---|---|
| A1-A5 | Plantillas y un mes importado de SISCONT y de STARSOFT; una respuesta aceptada de la API de STARSOFT Gold | Con quien use cada sistema |
| C3 · C5 · C6 · C7 | CDR (aceptado, observado, rechazado), XML de retención, percepción y liquidación de compra, recibo por honorarios de SOL | De empresas que los emitan o reciban, anonimizados |
| C8 · C11 | La fuente legal del aviso de no habido y del tipo de cambio que rige | Norma citada |
| C10 | El plan de cuentas exportado de CONCAR y un rechazo de importación | Con un estudio que use CONCAR |
| D1 | La consulta de pagos de detracciones de SOL o los movimientos de la cuenta del Banco de la Nación | Descargados por el contribuyente |
| D2 | Tres meses de extracto de un banco, y la especificación de su MT940 o su archivo host-to-host | Con el ejecutivo del banco |
| D5 | El reporte de liquidación de una pasarela, y cómo trata el IGV de su comisión (las páginas públicas de Culqi se contradicen) | Con un comercio real |
| D6 | Las cuentas del PCGE, el ITF con su norma y un archivo aceptado del sub-diario de bancos de CONCAR | Norma citada y un estudio |
| B4 | Un integrador que no escriba Python | — |

---

## 5 · Lo que no está en esta hoja de ruta, y por qué

- **Nunca, por decisión:** emitir, firmar o enviar comprobantes; consultar la validez de un comprobante; descargar la
  propuesta del SIRE, el padrón o los tipos de cambio; leer PDF o fotos ([README.md](README.md), «Qué no hace»).
- **Sin caso real todavía:** guías de remisión; SDKs generados; WASM; `sugerir_imputacion` (tiene la misma forma que la
  acción de una regla bancaria y entra con D4 si hace falta); `trazas` de un driver que consolide; `documento.id_externo`
  en la línea; pedir datos desde el MCP con el patrón de la especificación 2026-07-28, que espera un SDK que la hable.
- **En vigilancia:** las finanzas abiertas de la SBS y un perfil FAPI peruano, cuando exista la regulación.
- **Descartado en el diseño** (`INTEROPERABILIDAD.md` §8): la cuenta transitoria inmediata, *embeddings* en el motor, un
  lenguaje de requisitos declarativos, log con hash encadenado y fechas de bloqueo.
- **Pregunta abierta:** ¿debe `generar_asiento` exigir lo que exige el destino, como ya hace `exportar`?

---

## 6 · Cómo se mantiene

- **Quién la toca.** El mantenedor decide y fusiona. Un hito nuevo entra solo si nombra su caso real o el dato que lo
  destraba. Los nombres con `*` se deciden al pasar a código.
- **Cuándo un hito está cumplido.**
  - De código: su test en la rama principal, una versión `vX.Y.Z` etiquetada y su entrada en `CHANGELOG.md`.
  - Un driver o un lector: además, el archivo aceptado o leído, con su fecha, como CONTASIS.
  - Del estándar: su enmienda en `final`, con test, y el tag `open-accounting-0.X` avanzado o nuevo.
  - De documentación: el cambio fusionado.
- **Dónde se marca.** En el mismo cambio que pone la fecha de la versión en el CHANGELOG. La fila del hito pasa a
  «Cumplidos» con solo `id · versión`: el porqué vive en el CHANGELOG y en ningún otro sitio.
- **Lo que se descarta o cambia de dependencia** pasa al §5 con su motivo. No se borra en silencio.
- **Reparto con los otros documentos.** Si cambia el diseño, se corrige `INTEROPERABILIDAD.md`; aquí solo cambia el
  orden. `ARQUITECTURA.md` y la tabla «Estado» del README cambian cuando algo pasa a estar listo.
- **Cuándo se revisa.** Al etiquetar una versión y cuando SUNAT publica una nueva versión de sus reglas (E4). Nunca por
  calendario de entregas.

### Cumplidos

Ninguno todavía. Cada hito cumplido se anota aquí como `id · versión`.

---

## 7 · Fuentes

Consultadas el 13-sep-2026. Lo citado en [REFERENCIAS.md](REFERENCIAS.md) e [INTEROPERABILIDAD.md](INTEROPERABILIDAD.md)
se remite y no se repite.

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
- BCP, APIs de empresa (según terceros) — https://www.ecommercenews.pe/pagos-online/2026/bcp-optimiza-la-gestion-de-pagos-y-transferencias-de-empresas-con-apis-y-host-to-host.html/
- MT940 en bancos peruanos (según terceros) — https://ramo.com.pe/sap-business-one-bancos-peru/
- SBS, lineamientos de finanzas abiertas — https://elperuano.pe/noticia/300693-finanzas-abiertas-estos-son-los-lineamientos-que-propone-la-sbs-para-el-sistema-en-peru
- BCRP, Circular 0017-2026 — https://actualidadcivil.pe/normas-legales/circular-0017-2026-bcrp/4d8622c5-a7c8-4097-bc64-8fe8b6d0caed
