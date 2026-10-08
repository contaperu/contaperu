# Hoja de ruta de ContaPerú

## 0 · Cómo se lee

Este documento dice **en qué orden** crece el motor y **qué hace falta** para cada paso. **Toda la investigación que lo
sostiene** —lo que hacen EE. UU., los proyectos abiertos y SUNAT, el diseño y el pseudocódigo de cada pieza, y sus
fuentes— está en el §8 de esta hoja; lo que se tomó de las plataformas cerradas de EE. UU.
está en [REFERENCIAS.md](REFERENCIAS.md). Aquí solo se remite: cada hito cita su propuesta por número, en la columna
«Propuesta». Lo que ya está hecho se ve en la tabla «Estado» del [README.md](README.md).

Cinco principios la ordenan:

- **Arquitectura colectiva, no organizacional.** La contabilidad automatizada no la resuelve cada empresa por su
  cuenta: se resuelve una vez, en abierto y entre todos. Por eso el motor cumple dos papeles —trabajar encima de los
  sistemas legacy mientras evolucionan y ser la base de los ERP que vienen— y la comunidad es parte de la arquitectura,
  no un extra.
- **Encima, no en lugar de.** Nadie cambia de sistema contable: el motor traduce hacia el que ya existe, y un ERP nuevo
  parte del estándar y del motor en vez de reimplementarlos.
- **Crece con casos reales.** Una regla contable entra con su fuente, un driver o un lector con un archivo real que su
  sistema haya aceptado, y un campo del estándar con el caso que lo pide.
- **Sin fechas.** Lo que no está publicado es «próximo». Cada hito tiene, en cambio, un **criterio de salida
  verificable**: un test que pasa, un archivo aceptado, una versión etiquetada.
- **El núcleo no se mueve de su frontera**: sin red, sin disco, sin estado y sin reloj (`tests/test_frontera.py:75`). Lo
  que conecta, guarda o aprende vive fuera.

**Los frentes siguen el flujo** del diagrama del README: lo que **entra** (los comprobantes y el banco) → **el estándar
abierto y la comunidad** → **el motor** → las **salidas**, agrupadas en **SIRE**, **Legacy** y **ERP**. Cada hito
conserva el id con que nació (A1, B4, C9, D3, E1, J0…) aunque hoy viva en otro frente: la letra dice su origen, no su
sitio, y así ninguna remisión se rompe.

Cada frente sigue el mismo molde: objetivo, qué hay hoy, la etapa de la investigación que lo sostiene, una tabla de
hitos con su propuesta y lo que no se hace. La tabla usa estas columnas y marcas:

| Columna o marca | Significado |
|---|---|
| **Nivel** | `N` núcleo · `D` driver · `F` fachada o puerta (CLI, MCP) · `App` aplicación que consume el motor · `estándar` · `documentación` |
| **Arranca con** | `código` si se puede empezar ya; `dato: …` si espera un archivo real, una especificación o una norma |
| **Criterio de salida** | Lo que tiene que ser cierto para darlo por cumplido |
| **Propuesta** | El número de la propuesta en la tabla del §8; «—» si el hito no nació de una |
| `nombre*` | Nombre provisional: lo decide el mantenedor al pasar a código |
| *no verificado* · *según terceros* · *según el proveedor* | Calidad de la fuente, a la fecha de consulta (13-sep-2026) |

**Qué sigue** está antes que los frentes; lo que hay que conseguir para cada hito, en «Lo que hay que conseguir».

---

## 1 · Dónde estamos

Librería **6.1.0** y estándar **`open-accounting` 1.0**
(`contaperu/_version.py`).

| Pieza | Hoy |
|---|---|
| **Entradas** · lectores | XML UBL 2.1 con raíz `Invoice`, `CreditNote` o `DebitNote` (`contaperu/lectores/xml_ubl.py:31`); ZIP; propuesta del SIRE. El CDR se reconoce y se ignora. Un PDF o una foto quedan pendientes de leer |
| **Estándar y comunidad** | `open-accounting` 1.0 con su esquema, sus catálogos publicados, sus enmiendas y su batería de conformidad; drivers de terceros por el grupo `contaperu.drivers`, con el contrato v1 (`contaperu/drivers/contrato.py`); plantillas de aviso «Regla mal puesta», «Error», «Enmienda» y «El formato de mi sistema». El repositorio es público |
| **Motor** · validación | Observaciones propias, estables por contrato (`contaperu/validar.py`); duplicados dentro del lote y contra lo ya anotado |
| **Motor** · asiento | Línea del comprobante con `rol`, cuadre sin tolerancia, detracción en dos tiempos, huella por tanda |
| **Motor** · puertas | API pública `contaperu.api` sobre un pipeline único; CLI, servidor MCP con 14 herramientas y 13 recursos, y puerta HTTP con el contrato OpenConta; hay un `Dockerfile`. La 2.0 retiró las rutas de la 0.x |
| **Salida · SIRE** | El driver `sire` escribe el TXT de reemplazo del RVIE y del RCE, de canal tributario |
| **Salida · Legacy** | CONCAR (asientos) y CONTASIS (registro), de canal legacy; STARSOFT (asientos) en pruebas, a la espera de que alguien importe un archivo |
| **Salida · ERP** | El documento `open-accounting` en JSON, el CSV de canal intercambio y la puerta HTTP con OpenConta |
| Pendiente que depende de datos | SISCONT, la plantilla oficial de STARSOFT, la conciliación de constancias de detracción, las equivalencias del PCGE 2026 |

### Cumplidos

Cada hito cumplido se anota aquí como `id · versión`; el porqué, en el CHANGELOG.

- 0.0 · 1.0.0
- 0.1 · 1.0.0
- 0.2 · 1.0.0
- 0.3 · 1.0.0
- 0.4 · 1.0.0
- 0.5 · 1.0.0
- 0.6 · 1.0.0
- 0.7 · 1.0.0
- 0.8 · 1.0.0 (el serie-número de `diagnosticar` se igualó al de la línea después, por decisión de John del 15-sep-2026; ver el CHANGELOG)
- B1 · 1.0.0
- B2 · 1.0.0 (el esquema de `diagnosticar` viaja como recurso: el SDK no admite `outputSchema` sin cambiar la respuesta)
- B3 · 1.0.0 (el contrato se llama OpenConta; su archivo sigue el formato OpenAPI 3.1)
- B4 · 1.0.0 (adelantado sin esperar al integrador, por decisión de John del 14-sep-2026)
- B5 · 1.0.0
- B6 · 1.0.0
- J0 · 1.0.0 (14-sep-2026: el acoplamiento con lo peruano queda congelado en un test, sin mover código)
- J1 · 1.0.0 (14-sep-2026: las dependencias ocultas se cortaron al ordenar el motor en capas que un test hace cumplir)
- E6 · 1.4.0 (20-sep-2026: las plantillas «El formato de mi sistema» y «Enmienda»)
- E7 · 1.4.0 (20-sep-2026: el repositorio es público; el historial quedó sin revisar, ver la fila del hito)

---

## 2 · Qué sigue: orden de ejecución y dependencias

El orden de ejecución: **Fase 0 → el motor (reglas y validación), en paralelo con la salida Legacy → las entradas
y la salida SIRE a medida que llegan sus datos → el banco**, con **el estándar y la comunidad** acompañando desde el
principio, porque sus enmiendas tienen que existir antes del primer bloque nuevo del esquema. La salida ERP ya quedó
abierta en la 1.0 (B1-B6). **Otra jurisdicción** no entra en la secuencia hasta que llegue un cliente real fuera del
Perú; sus dos primeros hitos, J0 y J1, los cumplió la 1.0 al ordenar el motor en capas.

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
 E1 enmiendas ─┬─► C2 · C3 · C4 · C5 · C12             ├─► D3 conciliar ─► D5 pasarela [reporte] ─► D6 asientos
               ├─► D2 extracto [archivo] ──────────────┘                                           [fuente + aceptado]
               │     ├─► D4 reglas bancarias [reglas reales]
               │     ├─► B7 contrato de lector [segundo banco]
               │     └─► D7 conectores [primer conector]
               ├─► E2 conformidad
               └─► E3 política de retiro

Sin dependencias de código: A1-A5 [archivos aceptados] · C6 [04 real] · C7 [RHE real] · C10 [plan + rechazo]
                            · 0.6 · 0.7 · 0.8 · B5 · E5 guía de aporte · E6 plantilla de formato
                            · E7 abrir el repositorio [decisión de John]

OTRA JURISDICCIÓN [un cliente real fuera del Perú] · J0 y J1 cumplidos en la 1.0
 J0 ─► J1 ─┬─► J2 (tras C1 y C2) ─┬─► J4 ─► J5 (con E1 y E3) ─► J6 [archivo aceptado]
           └─► J3 ────────────────┘
```

| Orden | Hitos | Arranca con |
|---|---|---|
| 1 | 0.0 → 0.1, 0.4 · 0.2 · 0.3 · 0.5 · 0.6 · 0.7 · 0.8 | código |
| 2 | E1 | código |
| 3 | C1 | dato público, ya disponible |
| 4 | C9 · C2 | código |
| 5 | E2 · E3 · E5 · E6 | código |
| 6 | B1 · B2 · B5 · B3 · B6 | código |
| en paralelo | A1-A5 | dato: archivos aceptados |
| cuando llegue el dato | C3 · C4 · C5 · C6 · C7 · C8 · C10 · C11 · C12 | dato |
| cuando llegue el dato | D1 · D2 → D3 · D4 → D5 → D6 | dato (D3 es código, tras D1 y D2) |
| cuando haga falta | B4 · B7 · D7 · E4 | dato o decisión |
| cuando John lo decida | E7 | decisión |
| con un cliente real fuera del Perú | J0 → J1 → J2 · J3 → J4 → J5 → J6 | dato: el cliente, su destino y un archivo aceptado |

---

## 3 · Fase 0 · Afinar lo que existe

Antes de abrir frentes se afina lo que ya está en uso. Todo arranca con **código**; varias piezas desbloquean frentes
posteriores. Las propuestas de origen están en la tabla del §8, y cada hito cita la suya en la columna
«Propuesta».

| id | Hito | Nivel | Criterio de salida | Depende de | Propuesta |
|---|---|---|---|---|---|
| **0.0** | **Decidir la identidad del comprobante**: `libro.ruc` + `libro.tipo` + `Comprobante.clave` (`contaperu/modelo/comprobante.py`), sin periodo, y si en ventas lleva la contraparte (`comparar_sire` la deja fuera por la misma razón) | estándar · F | Escrita en `estandar/LEEME.md` | — | — |
| **0.1** | **`claves_previas` en la fachada**: `revisar`, `diagnosticar`, `generar_asiento`, `exportar`, CLI y MCP. `validar.revisar` ya lo acepta (`contaperu/validar.py:244`). En JSON viaja como `[tipo_cp, serie, numero, contraparte_doc]`, normalizado con `clave_de`, y con un tope como `MAXIMO_COMPROBANTES` (`contaperu/pipeline/preparacion.py:26`) | F | Por las tres puertas sale `DUPLICADO_PERIODO_ANTERIOR` con `pedir_a: contador`; «00000123» casa con «123»; por encima del tope, `DocumentoInvalido`; sin claves, el snapshot de CONCAR sale idéntico | 0.0 | 1 |
| **0.2** | **Anotaciones MCP**: `readOnlyHint: true` y `openWorldHint: false` en las 11 herramientas, y subir el mínimo del pin `mcp` al primero que las acepte (*no verificado* cuál) | F | `tests/test_servidor_mcp.py` recorre `list_tools()`; un trabajo de CI instala el mínimo declarado y pasa | — | 2 |
| **0.3** | **La frase de la detracción regenerada**: `estandar/LEEME.md`, «La detracción, que ocurre en dos tiempos», dice que el asiento «puede regenerarse». En un destino que suma, regenerar lo ya importado duplica | estándar | El texto dice que el segundo tiempo es una decisión contable que entra con fuente y archivo real | — | 3 |
| **0.4** | **Índice por comprobante** `_asiento.comprobantes*` y `_exportacion.comprobantes*`: identidad, rango de líneas y huella por comprobante. En la familia registro, sin huella | F | Los rangos son una partición exacta; cada rango cuadra; `HUELLA_FACTURA` (`tests/test_huella.py:24`) no cambia | 0.0 | 4 |
| **0.5** | **El disco sale del núcleo**: `comparar_sire.leer` y `pcge.adaptar.cargar_equivalencias(ruta)` (`contaperu/pcge/adaptar.py:89`) reciben bytes o `dict`, y un único `datos_empaquetados*()` con `importlib.resources` lee lo que viaja dentro del paquete | puerta · N | Un test cae si otro módulo del núcleo abre un archivo | — | 5 |
| **0.6** | **Tipo de cambio y tasa de detracción como texto** en la línea del comprobante (hoy `float`, `contaperu/asiento/motor.py:71` y `:111`); `float` solo al escribir la columna | N · D | Snapshot de CONCAR intacto; la huella de las tandas en dólares o con detracción cambia con literal nuevo y **se anuncia** en el CHANGELOG | — | 6 |
| **0.7** | **Un PDF o una foto enviados a `leer_xml` cuentan como pendientes de leer**, no como «XML inválido» (hoy los cuenta `lectores/archivos.py` como `ilegibles`) | F | Test por el MCP y por la CLI: `_lectura.pendientes_de_leer` = 1 | — | — |
| **0.8** | **Coherencia de `diagnosticar`**: que `totales.saldrian` y la lista `saldrian` cuenten lo mismo, que el serie-número se escriba igual que en la línea (a confirmar al empezar), y que el resumen por contraparte no sume soles con dólares (`contaperu/pipeline/diagnostico.py:279`) | F | Test que fija la misma cifra y el mismo nombre; dos monedas del mismo RUC no dan un único total | — | 23 |

---

## 4 · Los frentes, de lo que entra a lo que sale

### Entradas · Leer más, sin emitir

**Objetivo.** Que el motor lea más documentos de los que ya recibe una empresa y los lleve al estándar, igual para
todos los destinos. **Nunca emite**: no genera, no firma, no envía y no consulta la validez de un comprobante; eso es de
quien tenga red y credenciales.

**Investigación.** Cómo llega la factura en EE. UU. y en el Perú, y los proyectos que leen el UBL de SUNAT:

**Qué hay hoy.** Tres raíces de XML, y cualquier otra da «Raíz XML no reconocida» (`contaperu/lectores/xml_ubl.py:31`);
el CDR se ignora; la propuesta del SIRE se lee entera; un PDF o una foto quedan pendientes de leer.

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de | Propuesta |
|---|---|---|---|---|---|---|
| C3 | `leer_cdr*`: aceptado, observado y rechazado; abrir el ZIP en que suele llegar | N · F | dato: CDR reales | Un rechazo produce su observación con el código oficial | C1, E1 | — |
| C5 | Comprobantes de **retención (20)** y **percepción (40)** en un bloque propio | N · estándar | dato: XML reales + la fuente de su tratamiento | No entran al RCE ni al RVIE; ningún driver los escribe sin fuente | C1, E1 | — |
| C6 | **Liquidación de compra (04)**: la contraparte es el vendedor, no quien emite | N | dato: XML real | Sin falso `XML_PARA_OTRO_RUC` (test de mutación) | — | — |
| C7 | **Recibo por honorarios electrónico** leído del archivo de SOL | N | dato: archivo real | Tipo 02 con `retencion`; sin falso `RETENCION_TASA` | — | — |
| B7 | **Contrato de lector** y entry points `contaperu.lectores*`, el espejo de entrada del contrato de driver (el `Importer` de beangulp: identificar, extraer, deduplicar) | N | dato: el segundo lector bancario | Test de conformidad análogo a `tests/test_contrato_drivers.py` | D2 | 20 |

**No se hace.** Leer guías de remisión (09/31), que no tienen efecto contable; portar código PHP (se toman las rutas
XPath con la cita a SUNAT); usar los XML de prueba de Greenter como fixtures (se hacen con los RUC seguros o con
archivos reales en `privado/`); leer PDF o fotos.

### Entradas · El banco inicia el proceso contable

**Objetivo.** Que un hecho bancario —una línea de extracto o la liquidación de una pasarela de pagos— se lea, se
deduplique, se empareje con lo que salda y, cuando haya fuente, se asiente. Al estilo de EE. UU., y con el núcleo sin
red.

**Investigación.** Lo que hace EE. UU. de verdad, los canales peruanos a la fecha de consulta, los proyectos
abiertos, los rieles de pago y el fraude.

**Qué hay hoy.** Nada de banco. La conciliación de constancias de detracción está pendiente de un archivo real, pero la
mitad existe: `diagnosticar` ya lista las detracciones que esperan constancia (`_detraccion_pendiente`,
`contaperu/detracciones.py:151`) y el monto en soles enteros tiene su regla con fuente
(`contaperu/detracciones.py:57`). Hay dos trampas para un lector de extractos: un `.xlsx` empieza como un ZIP y se
desarma (`contaperu/lectores/archivos.py:56-58`), y un `.txt` se ignora como archivo auxiliar (`archivos.py:26`).

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de | Propuesta |
|---|---|---|---|---|---|---|
| D1 | `aplicar_constancias*`: casar el archivo del banco con cada comprobante y escribirle su número y su fecha (el `estado` ya se deduce de los dos desde la 3.2, `detracciones.estado_de`) | N · F | dato: constancias reales (la consulta de pagos de detracciones de SOL o los movimientos de la cuenta del Banco de la Nación) | Con pareja, quedan número y fecha y la detracción pasa a `detracciones_pagadas`; sin pareja, queda igual | 0.3 | 14 |
| D2 | `Movimiento*`, el lector del primer extracto y la deduplicación | N · estándar | dato: extracto real anonimizado | Un libro Excel no se desarma como ZIP; una relectura con solape no duplica | E1 | 15 |
| D3 | `conciliar*` con `metodo*` y `certeza*`, la tabla `aplicaciones*`, `emparejar_transferencias*` y la tolerancia en porcentaje y en importe absoluto | N · F | código, tras D1 y D2 | Motivos legibles; la detracción como pago parcial; solo certeza alta va a lote; dentro del porcentaje y fuera del absoluto no hay certeza alta | D1, D2 | 16, 25 |
| D4 | `ReglaBanco*` y `aplicar_reglas*` | N | dato: reglas reales de un contador | Primera coincidencia por prioridad, con motivo; nunca confirma | D2 | — |
| D5 | `LiquidacionPasarela*` y `Aviso*` | N · estándar | dato: el reporte real de una pasarela | El invariante del neto se cumple; los avisos nunca asientan | D3, E1 | — |
| D6 | Asientos de tesorería y de liquidación | N · D | dato: cuentas del PCGE con su cita, el ITF con su norma, el tratamiento del IGV de la comisión y un archivo aceptado del sub-diario de bancos de CONCAR | Archivo aceptado; snapshot de CONCAR idéntico | D3, D5 | 17 |
| D7 | Dónde viven los conectores de entrada | `App` o paquete aparte | dato: el primer conector real | Decisión escrita con el criterio de abajo | D2 o D5 | — |

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

### El estándar abierto y la comunidad

Es **transversal**: acompaña a todos los frentes. Es también donde la arquitectura se vuelve colectiva: el estándar y el
motor mejoran porque cualquiera puede aportar por un camino escrito.

**Objetivo.** Que `open-accounting` cambie por un proceso escrito —caso real, fuente, test y compatibilidad declarada—,
que un tercero pueda comprobar que su implementación cumple, y que un contador, un desarrollador o una empresa sepan
cómo aportar: la regla con su norma, el driver con su contrato, el formato de su sistema con un archivo aceptado.

**Investigación.** Cómo gobiernan sus cambios MCP, Python, FDX, Peppol y JSON Schema, y la plantilla y los estados de
una enmienda: `estandar/LEEME.md`, «El estándar y su gobierno».

**Qué hay hoy.** `estandar/LEEME.md` ya tiene una regla de versionado (lo aditivo no sube la versión; lo que cambia de
significado, sí), siete nombres reservados y un tag del estándar que avanza con cada cambio aditivo;
`tests/test_estandar.py` valida el esquema. La salida de `cuenta_contable` en la 0.3 fue legado y retiro el mismo día:
no hubo aviso previo. Para aportar: `CONTRIBUTING.md` con la regla que manda y la receta de un driver, las plantillas de
aviso «Regla mal puesta», «Error», «Enmienda» y «El formato de mi sistema» (`.github/ISSUE_TEMPLATE/`) y el grupo de
entry points para drivers de terceros. El repositorio es público, y lo que hace falta conseguir de la comunidad está
en [§5](#5--lo-que-hay-que-conseguir).

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de | Propuesta |
|---|---|---|---|---|---|---|
| E1 ✅ | `estandar/enmiendas*/NNNN-titulo.md`: plantilla, estados, y los siete nombres reservados migrados como enmiendas en estado `reservada`. El LEEME sigue siendo el texto normativo | estándar · documentación | código | Cada reservado del LEEME tiene su enmienda; cada enmienda `final` cita un test que existe | — | — · **hecho el 18-sep-2026** |
| E2 ✅ | `estandar/conformidad*/`: casos de esquema `{description, data, valid}` y casos de `diagnosticar` con lo esperado (`listo`, motivos, `pedir_a`) | estándar | código | Los corre la batería; hay un caso por regla de `validar` y por fila de `FALTAS`; los de esquema se ejecutan sin el motor | E1 ✅ | — · **hecho el 18-sep-2026** |
| E3 | Política escrita de retiro: legado en una versión, rechazo en la siguiente; cada cambio con su fecha de vigencia | estándar | código | Revisada; `tests/test_estandar.py` sigue verde | E1 | — |
| E4 | Revisión cuando SUNAT cambia la fecha «actualizado al» de sus reglas | proceso | dato: la nueva versión de SUNAT | JSON de C1 regenerado; las diferencias, en el CHANGELOG | C1 | — |
| E5 | **Guía de aporte por rol** en `CONTRIBUTING.md`: qué aporta un contador (la regla con su norma), un desarrollador (el driver con su contrato) y una empresa (el formato de su sistema con un archivo aceptado, anonimizado) | documentación | código | La sección existe y el README la enlaza desde «Cómo aportar» | — | — |
| E6 ✅ | Plantilla de aviso **«Formato de mi sistema»** para compartir la plantilla de importación y un archivo aceptado de un sistema sin driver | documentación | código | La plantilla está en `.github/ISSUE_TEMPLATE/`, pide los RUC seguros y el README la enlaza | — | — · **hecho el 20-sep-2026**, junto con la plantilla «Enmienda» |
| E7 ✅ | **Abrir el repositorio** | proceso | decisión de John | El repositorio es público, con el historial revisado para que no quede nada real de nadie | — | — · **hecho el 20-sep-2026**. La mitad del criterio queda debiendo: el historial **no** se revisó antes de abrir y conserva correos de trabajo del autor en buena parte de los commits. Reescribirlo ahora rompería los hashes y los tags publicados |

La **conformidad declarada** —pasar la suite del estándar (E2) y, si es un driver, tener su archivo aceptado— es el
análogo de la certificación de Xero o Intuit, sin sellos ni tercero que la otorgue.

### El motor · Reglas y validación de SUNAT

Es el **primer frente tras la Fase 0**, en paralelo con la salida Legacy.

**Objetivo.** Que el motor valide con las reglas y los códigos oficiales de SUNAT tomados como datos, y que su asiento
cubra los casos que faltan, con la misma regla para todos los destinos.

**Investigación.** Las reglas de SUNAT como datos y los datos públicos que un motor puede recibir:

**Qué hay hoy.** Desde la 1.1, los catálogos de tipos de comprobante, documentos de identidad y monedas viven en datos
con su fuente (`contaperu/datos/sunat/catalogos.json`), igual que la tabla de detracciones
(`contaperu/datos/sunat/detracciones.json`): es el primer paso de C1. Faltan los códigos de retorno y las reglas de
validación de SUNAT, que esperan su hoja oficial. Los códigos de observación son propios, ninguno igual a uno oficial;
y hay un precedente de norma convertida en datos con su cita, `herramientas/extraer_pcge2026.py`.

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de | Propuesta |
|---|---|---|---|---|---|---|
| C1 | `herramientas/extraer_reglas_sunat*.py` → JSON empaquetado con `actualizado_al`, hoja y fila de cada dato: códigos de retorno, catálogos y solo las reglas con efecto contable | N · herramienta | dato público, ya disponible | Reproducible; lo que hoy está a mano en `catalogos.py` está contenido en el JSON o la diferencia queda listada; la hoja de cálculo no entra al repositorio | 0.5 | — |
| C2 | `codigo_sunat*` en la observación, como campo añadido: los códigos propios no se renombran | N · estándar | código | Cada código citado existe en el JSON; la tabla `PEDIR_A` no cambia | C1, E1 | — |
| C4 | `retencion_igv` (nombre reservado) desde `PaymentTerms` de la factura | N · estándar | dato: un destino que lo pida | `retencion` (renta de 4ta) intacta; snapshot idéntico | E1 | 29 |
| C8 | `padron*` como argumento, con forma `{ruc: {activo*, habido*, razon_social*}}`, y aviso de proveedor no habido | N · F | dato: la fuente legal del aviso + tope | Sin padrón no cambia nada; un nombre distinto del padrón no produce observación | 0.1 | 24 |
| C11 | `tipos_de_cambio*` como argumento: **contrasta, no rellena** | N · F | dato: la fuente del tipo de cambio que rige | Un tipo de cambio distinto del publicado da un aviso | C8 | — |
| C12 | **IGV por utilización de servicios de no domiciliados (91, 97, 98)**: el par de líneas autoliquidado con su `rol` y el archivo de no domiciliados del RCE | N · estándar · D | dato: un comprobante 91 real con su pago por el Formulario 1662 y un asiento aceptado por CONCAR | El 91 da cuatro líneas que cuadran; una factura 01 sale idéntica (snapshot); el `rol` entra por su enmienda | C1, E1 | 26 |
| C13 | **Calcular el pago a cuenta del mes** con los dos registros delante: la base de la casilla 301 y la cuota de la 312, a partir de la tasa que ya publica `regimenes_tributarios` | N · F · D | dato: un formulario mensual presentado, con sus casillas | La base y la cuota coinciden celda a celda con el formulario; el régimen lo dice quien llama y el motor no lo deduce de los importes | 0.8, B8 | 31 |

**No se hace.** Ejecutar las XSL; sustituir la Tabla 10 del SIRE por el Catálogo 01, que incluye menos tipos.

### El motor · Otra jurisdicción

Es **condicional**: salvo J0 y J1, que la 1.0 cumplió al ordenar el motor en capas, ningún hito arranca sin un cliente
real fuera del Perú.

**Objetivo.** Que otra jurisdicción entre como un perfil que se enchufa, igual que un driver, sin que el Perú cambie una
celda del Excel de CONCAR ni un carácter de la huella.

**Investigación.** El mapa de lo universal y lo peruano, la partición en perfiles, el contrato de una jurisdicción, el
cambio del estándar.

**Qué hay hoy.** El núcleo sabe contabilidad peruana y nada más (`ARQUITECTURA.md:25`). Ya son universales la partida
doble, la línea del comprobante, la huella, la imputación, las faltas, la maquinaria de configuración y el registro de drivers.
Son peruanos el `Libro` (`contaperu/modelo/libro.py`), los impuestos en campos fijos, la validación
(`contaperu/validar.py:16`), los roles del asiento (`contaperu/asiento/motor.py:40`), las claves del contrato de driver
(`contaperu/drivers/contrato.py:227-230`, `:280-286`) y el esquema del estándar. Desde la 1.0, `tests/test_capas.py`
congela el acoplamiento con lo peruano (J0).

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de | Propuesta |
|---|---|---|---|---|---|---|
| J0 | **El acoplamiento se ve**: un test de frontera lista los módulos que importan lo peruano y los que lo son por contenido (`Libro`, `CONFIGURACION_GENERAL`, `asiento/configuracion`). No mueve código | N (test) | dato: un cliente real fuera del Perú | Pasa con la lista de hoy; un import peruano nuevo en un módulo universal lo rompe | — | 30 |
| J1 | **Cortar las dependencias ocultas**. **Hecho en la 1.0** al ordenar el motor en capas: lo que describía este hito —`formato` → `igv` → `validar` → `catalogos`, y el registro de drivers dentro de `generar`— eran módulos de la 0.x que la 2.0 retiró, y hoy `tests/test_capas.py` no admite una sola importación fuera de su capa (`TOLERADAS` está vacía), con re-exportación en las rutas viejas | N | dato: un cliente real fuera del Perú | La lista de J0 se reduce; snapshot de CONCAR y huella idénticos; los símbolos que usa la aplicación se importan igual | J0 | 30 |
| J2 | **La validación en dos tablas**: reglas universales y reglas peruanas registradas con código, nivel, `pedir_a` y fuente | N | dato: un cliente real fuera del Perú | Las mismas observaciones en toda la batería; `PEDIR_A` igual clave a clave | J1; después de C1 y C2, para no mover las reglas dos veces | 30 |
| J3 | **Impuestos que emiten líneas**: el motor arma el principal y el tercero; el IGV, la 4ta y la detracción salen del perfil peruano; los roles son los universales más los de la jurisdicción | N | dato: un cliente real fuera del Perú | Snapshot de CONCAR y huella idénticos | J1 | 30 |
| J4 | **El perfil peruano como paquete** `contaperu/jurisdicciones/pe*`, con el grupo de entry points `contaperu.jurisdicciones*` y `pe` por defecto | N · D | dato: un cliente real fuera del Perú | Test de conformidad de jurisdicción verde para `pe`; ningún módulo universal importa `pe`; rutas viejas re-exportadas | J2, J3 | 30 |
| J5 | **`open-accounting` 1.1**: `libro.jurisdiccion*` con perfiles; `pe` conserva los campos de la 1.0 y las demás jurisdicciones usan `impuestos[]*` | estándar | dato: un cliente real fuera del Perú | Todo documento 1.0 valida y significa lo mismo —la 1.0 promete no romper hasta una 2.0—; enmienda en `final`; tag `open-accounting-1.1` | J4, E1, E3 | 30 |
| J6 | **La segunda jurisdicción**, en paquete propio por entry points o en el repositorio | N · D | dato: su archivo aceptado por su destino y la fuente de cada regla | Conformidad de jurisdicción; archivo aceptado; `pe` sin cambios | J5 | 30 |

**No se hace.** Adelantar J2-J6 sin el cliente; tasas de impuestos sin fuente; traducir al inglés el vocabulario del
estándar; poner la jurisdicción en la configuración (es del libro).

### Salida · SIRE

**Objetivo.** Que lo que se presenta a SUNAT salga del mismo documento que los asientos y cuadre con lo que SUNAT ya
tiene: el TXT de reemplazo del RVIE y del RCE, y la propuesta como lista de control.

**Investigación.** El SIRE frente a las declaraciones de EE. UU. y la propuesta del RCE como lista de control:

**Qué hay hoy.** El driver `sire` escribe el TXT de reemplazo del RVIE (Anexo 3) y del RCE (Anexo 11), contrastado con
archivos reales aceptados, y lo comprime en su ZIP; deja fuera los recibos por honorarios. `comparar_sire` compara ese
TXT con lo que SUNAT exporta del SIRE (`contaperu/comparar_sire.py`). Y el FORMATO está publicado columna a columna
(`datos/sunat/sire_campos.json`, `api.campos_del_sire()`, 3.8.0): de cada campo del anexo, dónde cae o por qué no cae,
con un test que lo confronta con el lector y con el escritor. Cubre del hito B9 la mitad que mira al registro; la que
mira al documento es `campos_del_comprobante*`.

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de | Propuesta |
|---|---|---|---|---|---|---|
| C9 | `cruzar_con_propuesta*`: lo cargado contra la propuesta del RCE, y el primer uso de `pedir_a: proveedor`; es la lista de control que EE. UU. no tiene | N · F | código | Tres cajones; ceros a la izquierda; un RUC mal escrito | 0.0 | 9 |

**No se hace.** Descargar la propuesta ni presentar el registro: eso necesita red y Clave SOL, y es de quien use el
motor.

### Salida · Legacy: CONCAR, CONTASIS, SISCONT y STARSOFT

**Objetivo.** Que SISCONT y STARSOFT Desktop salgan del mismo documento que CONCAR y CONTASIS, cada uno con su archivo aceptado,
y que el motor conozca lo que el destino exige antes de que el sistema rechace una importación. Es la prioridad por uso:
son, con CONCAR y CONTASIS, los sistemas contables que más estudios peruanos tienen instalados, y el motor trabaja
encima de ellos mientras evolucionan.

**Investigación.** Los tres escalones con que EE. UU. integra sistemas de escritorio sin API, y lo que se toma de
ellos. Para A4 y A5, la forma de la API de STARSOFT Gold campo a
campo, comparada con las API de EE. UU. y con los estándares abiertos de factura: `API-DE-REGISTRO.md`.

**Qué hay hoy.** CONCAR (asientos) y CONTASIS (registro) en uso, de canal legacy. Las formas del contrato
(`contaperu/drivers/contrato.py`) y la receta con la que entró CONTASIS (`CONTRIBUTING.md`, «Añadir un driver de
salida»; `CHANGELOG.md` 0.10.0):

1. Pedir dos archivos al sistema: su plantilla y un mes que haya importado.
2. Elegir la forma: `desde_comprobantes` si importa registros, `desde_lineas` si importa asientos.
3. Llevar al núcleo, antes del driver, lo que no es del driver.
4. `datos.py` con cada columna y su fuente; `proyeccion.py` que solo traduce; el escritor del archivo.
5. Pruebas en cuatro capas: snapshot con datos inventados, driver por la fachada, plantilla contra los archivos privados,
   contrato.
6. Revisión humana del primer archivo y configuración declarada por sección.
7. Aceptación real importando un mes; recién entonces documentación y etiqueta.

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de | Propuesta |
|---|---|---|---|---|---|---|
| A1 | SISCONT, registro de compras y ventas → `desde_comprobantes` | D | dato: plantilla + un mes importado | Las cuatro capas de prueba; un mes importado; fila en «Estado»; CHANGELOG y tag | — | — |
| A2 | ¿Acepta SISCONT el TXT que genera el driver `sire`? (SISCONT importa la propuesta del SIRE, *según el proveedor*; qué formato, *no verificado*) | documentación | dato: una prueba | Nota en la guía; ningún código | — | — |
| A3 | SISCONT, asientos → `desde_lineas` | D | dato: un caso que A1 no cubra | Igual que A1 | A1 | — |
| A4 | **STARSOFT Desktop**, asientos → `desde_lineas`. **Hecho y aceptado** (2.0-2.3, cerrado en la 6.0): las dos plantillas calcadas del archivo real, y un **mes importado de verdad el 7-oct-2026**, que destapó lo que ningún vídeo decía — el nombre empieza por `C` y el TXT va suelto, sin el ZIP. Falta el archivo de **ventas** aceptado, que confirme la `C` en ese libro | D | dato: un mes de ventas importado | Igual que A1 | — | — |
| A5 | **`starsoft_web`**: el cuerpo JSON de la API de STARSOFT Web (Gold Edition), como proyección pura de las líneas. **Abierto a la comunidad**: lo que resolvió A4 le sirve casi entero —siglas, sub-diarios, destino del IGV, cuentas y la proyección—; lo distinto es a dónde van los datos | D | dato: una respuesta aceptada guardada en `privado/` | Test contra el cuerpo aceptado; autenticarse y enviar es de la aplicación | A4 | — |
| C10 | `plan_de_cuentas*` del destino, falta `cuenta_fuera_del_plan*`, marca de centro de costo y lista de centros | N · F · D | dato: plan exportado de CONCAR + un rechazo real de importación | Sin plan, snapshot idéntico; un plan sin la cuenta bloquea y `exportar` lanza | — | 11, 12, 13 |

**No se hace.** Un formato común para todos los legacy: el TXT del SIRE no lleva cuentas y pierde la imputación, y no
consta que ninguno importe el Libro Diario 5.1 del PLE (*no verificado* en negativo). Ningún driver sale a la red.

### Salida · ERP: la puerta abierta para los que vienen

**Objetivo.** Que un ERP escrito en cualquier lenguaje mande un documento `open-accounting` y reciba el asiento o el
archivo de su destino, con un kit que le diga cómo integrarse y cómo comprobar que lo hizo bien. Es la otra mitad de la
arquitectura colectiva: un ERP nuevo no reimplementa el IGV, las detracciones ni los sub-diarios, sino que parte del
estándar y del motor.

**La puerta ya existe**: el documento del estándar es la entrada canónica, y un ERP no necesita un lector propio. La
1.0 la publicó para quien no escribe Python (B1-B6).

**Investigación.** Contratos publicados, motor y reglas versionados aparte, reglas escritas para entrar y cómo
embeberse en un ERP abierto; la puerta MCP, «Arquitectura y
puertas».

**Qué hay hoy.** La API pública `contaperu.api`, la tabla `OPERACIONES` de la que salen las rutas HTTP, las herramientas
del MCP y el contrato OpenConta (`contaperu/api/openconta.json`), la puerta HTTP sin estado (`contaperu-http`), el CSV
con `rol` y los `tipo_cp`, y la guía [INTEGRAR.md](INTEGRAR.md), cuyos ejemplos se ejecutan en la batería.

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de | Propuesta |
|---|---|---|---|---|---|---|
| B1 | Las dos operaciones pasan a la fachada, y una tabla `OPERACIONES*` declara cada operación con su entrada y su salida (con `$ref` al esquema del estándar) | F | código | Cada herramienta MCP llama a una operación de la tabla; ninguna puerta importa `pcge` ni `detracciones` | 0.5 | — |
| B2 | `motor*` (la versión) en `_asiento` y `_exportacion`, y `outputSchema` de `diagnosticar` que cubra también la respuesta con configuración inválida | F | código | Las dos formas validan; `motor` queda fuera de la huella | 0.2, 0.4 | 8, 10 |
| B3 | **OpenAPI 3.1** generado por una herramienta desde `OPERACIONES*` | F · documentación | código | Regenerarlo no cambia bytes; los documentos de ejemplo validan como cuerpos | B1, B2 | — |
| B4 | Puerta **HTTP sin estado**, `servidor_http*`, con el extra `contaperu[http]*` | puerta | dato: un integrador no Python que lo necesite | Está en `PUERTAS` de `tests/test_frontera.py`; las tres puertas dan el mismo documento; comparte topes y la defensa de `Host` del MCP; publicar su imagen pide OK | B3 | — |
| B5 | El CSV lleva `rol` y los `tipo_cp`, lo que un driver necesita para no adivinar | D | código | Columnas nuevas llenas; **se anuncia** porque cambia una salida | — | 7 |
| B6 | **Guía «integrar ContaPerú en un ERP»**: la librería (Odoo, Frappe), la CLI por lotes, el MCP y, con B4, HTTP; niveles *de serie* (con archivo aceptado) y *comunidad* (paquete propio por entry points); checklist de contribución | documentación | código | Los ejemplos en Python se ejecutan en la batería; `contaperu://drivers` dice si cada driver es de serie | B1 | — |
| **B9** | **Lo que una capa de agente se trae sin copiarlo**: `campos_del_comprobante*` —qué campos pone el documento, cuáles el sistema y cuáles la revisión— y `REGLAS*`, las reglas del dominio sin el camino de las herramientas de este servidor pegado | N · F · documentación | código | Los tres tramos cubren el comprobante entero y no se solapan; ninguna herramienta ni recurso de este servidor se nombra en `REGLAS`; la fila «Reportes y análisis» de `INTEGRAR.md` queda partida en dos | B6, B8 | — |
| **B8** | **`resumen*` y `por_cuenta*`**: cuánto es un libro —base gravada, IGV y total, cada moneda por su lado, con agrupación por contraparte— y el pre-mayor con su cuadre por moneda. **Sin driver y sin configuración**: es del libro y del asiento, no de un destino | N · F | código | Una nota de crédito de no domiciliado (87) resta; ninguna clave suma dos monedas; el cuadre es el mismo dict que `cuadrar`; una cuenta con dos papeles los dice los dos; el `resumen_por_contraparte` de `diagnosticar` no cambia de cifra | B1 | — |

**El caso real de B8**, que es lo que esta hoja de ruta exige para admitir un hito: el conector MCP de una aplicación
que integra el motor (25-sep-2026) tuvo que escribir por su cuenta «suma este libro» y «agrupa este asiento por
cuenta» para poder contestar «¿cuánto compré en agosto?» sin generar un archivo — porque el motor solo sumaba dinero
dentro del `resumen` de una exportación, y `base_gravada` no se agregaba en ningún sitio. Y le salió con el `07` donde
el motor dice `("07", "87")`, así que una nota de crédito de no domiciliado le sumaba en vez de restarle: el dato de
que la regla estaba en el sitio equivocado. **Y el de B9**: la misma aplicación escribió a mano la lista de campos
que su puerta de entrada acepta y se dejó cinco que su propia base ya guardaba —los dos descuentos, el ICBPER, el valor
no gravado y el destino del IGV—, que se perdían sin error y sin aviso; y no pudo traerse las reglas que este servidor le
da a un agente, porque venían con el camino de sus herramientas pegado.

**No se hace.** SDKs generados (esperan un integrador que los pida), WASM o Pyodide (antes habría que probar que sus
dependencias cargan), OAuth, estado ni sellos de certificación.

---

## 5 · Lo que hay que conseguir

Para cada hito que espera un dato: qué hay que conseguir y con quién, en el orden del flujo.

| Para | Qué | Cómo |
|---|---|---|
| **Entradas** | | |
| C3 · C5 · C6 · C7 | CDR (aceptado, observado, rechazado), XML de retención, percepción y liquidación de compra, recibo por honorarios de SOL | De empresas que los emitan o reciban, anonimizados |
| D1 | La consulta de pagos de detracciones de SOL o los movimientos de la cuenta del Banco de la Nación | Descargados por el contribuyente |
| D2 | Tres meses de extracto de un banco, y la especificación de su MT940 o su archivo host-to-host | Con el ejecutivo del banco |
| D5 | El reporte de liquidación de una pasarela, y cómo trata el IGV de su comisión (las páginas públicas de Culqi se contradicen) | Con un comercio real |
| D6 | Las cuentas del PCGE, el ITF con su norma y un archivo aceptado del sub-diario de bancos de CONCAR | Norma citada y un estudio |
| **Estándar y comunidad** | | |
| E7 | La decisión de abrir el repositorio y la revisión de su historial | John |
| **Motor** | | |
| C1 | La hoja oficial de SUNAT con los códigos de retorno y las reglas de validación, con su fecha «actualizado al» (no entra al repositorio) | Descargada de SUNAT a `privado/` |
| C8 · C11 | La fuente legal del aviso de no habido y del tipo de cambio que rige | Norma citada |
| C12 | Un comprobante 91 con su pago por el Formulario 1662, y el asiento que CONCAR aceptó | De una empresa que pague servicios a un no domiciliado |
| C13 | Un formulario mensual de IGV-Renta presentado, con sus casillas, para contrastar la base y la cuota | De un contribuyente del régimen que se calcule |
| C13 | Los libros obligatorios, los topes y el pago a cuenta del Régimen General, el MYPE Tributario y el Nuevo RUS, cada uno con su artículo (el Especial ya está) | Norma citada |
| J2-J6 | Un cliente real fuera del Perú, su sistema contable de destino y un archivo que ese sistema haya aceptado | Con el cliente |
| **Legacy** | | |
| A1-A5 | Plantillas y un mes importado de SISCONT y de STARSOFT; una respuesta aceptada de la API de STARSOFT Gold | Con quien use cada sistema |
| C10 | El plan de cuentas exportado de CONCAR y un rechazo de importación | Con un estudio que use CONCAR |

---

## 6 · Lo que no está en esta hoja de ruta, y por qué

- **Nunca, por decisión:** emitir, firmar o enviar comprobantes; consultar la validez de un comprobante; descargar la
  propuesta del SIRE, el padrón o los tipos de cambio; leer PDF o fotos ([README.md](README.md), «Qué no hace»).
- **Sin caso real todavía:** guías de remisión; SDKs generados; WASM; `sugerir_imputacion` (tiene la misma forma que la
  acción de una regla bancaria y entra con D4 si hace falta); `trazas` de un driver que consolide; `documento.id_externo`
  en la línea; pedir datos desde el MCP con el patrón de la especificación 2026-07-28, que espera un SDK que la hable; el archivo de 4ta del PLAME, análogo del 1099
  (espera un archivo importado y C7); `cuentas_conocidas*`, la cuenta del proveedor distinta de la conocida (espera D2
  y un caso); emparejar órdenes de compra y recepciones (espera un cliente cuyo ERP las lleve).
- **En vigilancia:** las finanzas abiertas de la SBS y un perfil FAPI peruano, cuando exista la regulación; la factura negociable y su
  Plataforma de Confirmación, si un cliente la usa como canal de conformidad.
- **Descartado en el diseño** (`ARQUITECTURA.md`, «Lo que no se hace, y por qué»): la cuenta transitoria inmediata, *embeddings* en el motor, un
  lenguaje de requisitos declarativos, log con hash encadenado y fechas de bloqueo.
- **Resuelta en la 1.0:** `generar_asiento` exige lo que exige el destino, igual que `exportar` (CHANGELOG, «Cambiado»).

---

## 7 · Cómo se mantiene

- **Quién la propone y quién la toca.** Cualquiera propone un hito —un contador, un desarrollador, una empresa— abriendo
  un aviso con su caso real o el dato que lo destraba: es la forma colectiva de la hoja de ruta. El mantenedor decide y
  fusiona. Un hito nuevo entra solo si nombra su caso real o el dato que lo destraba. Los nombres con `*` se deciden al
  pasar a código.
- **Dónde va un hito nuevo.** En el frente del flujo que le toca, con la letra de ese frente y el número siguiente
  (E8, C13…). Un id no se reutiliza ni se renombra al moverse de frente.
- **Cuándo un hito está cumplido.**
  - De código: su test en la rama principal, una versión `vX.Y.Z` etiquetada y su entrada en `CHANGELOG.md`.
  - Un driver o un lector: además, el archivo aceptado o leído, con su fecha, como CONTASIS.
  - Del estándar: su enmienda en `final`, con test, y el tag `open-accounting-0.X` avanzado o nuevo.
  - De documentación: el cambio fusionado.
- **Dónde se marca.** En el mismo cambio que pone la fecha de la versión en el CHANGELOG. La fila del hito pasa a
  «Cumplidos» con solo `id · versión`: el porqué vive en el CHANGELOG y en ningún otro sitio.
- **Lo que se descarta o cambia de dependencia** pasa a «Lo que no está en esta hoja de ruta», con su motivo. No se
  borra en silencio.
- **Reparto con los otros documentos.** **La investigación nueva y todo cambio de diseño se escriben en
  el §8**, con el caso real que destraba cada una; aquí solo cambian el orden y los hitos.
  `ARQUITECTURA.md` y la tabla «Estado» del README cambian cuando algo pasa a estar listo.
- **Remisiones por identificador.** Entre los dos documentos se cita por número de propuesta y por id de hito, nunca
  por número de sección; una etapa de la investigación se nombra por su título. Así cualquiera de los dos se puede
  reordenar sin romper una remisión.
- **Cuándo se revisa.** Al etiquetar una versión y cuando SUNAT publica una nueva versión de sus reglas (E4). Nunca por
  calendario de entregas.

---

## 8 · De dónde salió cada hito: el inventario de propuestas

Las 31 propuestas que levantó la investigación del ciclo contable (13-14 de setiembre de 2026),
cada una con el caso real que la destraba y el hito que le toca; «—» si todavía no tiene uno. Es a
esta tabla a la que remite la columna **Propuesta** de los frentes.

Vivió en `INTEROPERABILIDAD.md` hasta el 8-oct-2026, y se mudó aquí al retirarlo: la tabla la usa
esta hoja y nadie más, así que dejar de ser una remisión a otro documento es lo que la mantiene
viva. Lo que se fue con aquel documento es la investigación comparada que la originó —el ciclo de
EE. UU. frente al peruano, los modelos de referencia, las etapas—, que ya había dado todo lo que
tenía que dar y queda en el historial de git.

Prioridad **A**: afina lo que existe, tiene un caso visto y no necesita datos de fuera. **B**: tiene
caso, pero cambia una salida (y se anuncia) o es una función nueva que decide el mantenedor. **C**:
espera un archivo real. **D**: espera un segundo caso o una versión del SDK.

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
| 9 | `cruzar_con_propuesta` y el primer `pedir_a: proveedor` | N · F | La propuesta del RCE como lista de control, la que EE. UU. no tiene | Tres cajones; ceros; RUC mal escrito | `cruzar_con_propuesta*` | B | C9 |
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
| 22 | `documento.id_externo` en la línea | estándar | Un driver de forma `desde_lineas` que escriba el id del origen | Transporte puro; fuera de la huella | — | D | — |
| 23 | El resumen por contraparte de `diagnosticar` agrupa por moneda | F | Un proveedor que factura en PEN y en USD el mismo mes | Dos monedas del mismo RUC no dan un único total; con una sola moneda, la salida no cambia | — | A | 0.8 |
| 24 | El padrón admite `razon_social*`, sin aviso por diferencia de nombre | N · F | El de C8, con TIN Matching como referencia | Sin padrón no cambia nada; un nombre distinto no produce observación (mutación) | `razon_social*` | C | C8 |
| 25 | Tolerancia de importe en porcentaje y en diferencia absoluta | N | Las tres vías de NetSuite | Dentro del porcentaje y fuera del absoluto no da certeza alta | — | D | D3 |
| 26 | IGV por utilización de servicios de no domiciliados: par de líneas y archivo del RCE | N · estándar · D | Un 91 real con su pago por el Formulario 1662 y un asiento aceptado por CONCAR | Cuatro líneas que cuadran; una 01 idéntica (snapshot); el rol entra por su enmienda | `igv_no_domiciliado*` | C | C12 |
| 27 | Archivo de 4ta del PLAME, análogo del 1099-NEC | D | Un archivo que PLAME haya importado, y el de C7 | Las cuatro capas de prueba de un driver | `plame_4ta*` | C | — |
| 28 | Cuenta del proveedor distinta de la conocida, en `conciliar` | N · F | D2 y un caso real de cambio de cuenta | Sin el dato no cambia nada; con una cuenta nueva no hay certeza alta | `cuentas_conocidas*` | D | — |
| 29 | Los padrones que deciden una retención llegan como dato | N | El de C4 | — | — | D | C4 |
| 30 | La puerta a otra jurisdicción | N · D · estándar | Un cliente real fuera del Perú | Los criterios de J0-J6 en la hoja de ruta | `jurisdiccion*`, `impuestos[]*` | D | J0-J6 |
| 31 | El régimen tributario del contribuyente como datos, y el cálculo de su pago a cuenta | N · F | La tabla entró en la 6.1.0 con los arts. 118, 120 y 124 de la LIR; **calcular** la cuota espera un formulario mensual presentado | La tasa, los topes y los libros contra su artículo; la cuota contra las casillas 301 y 312 de un formulario real | `regimenes_tributarios`, `pago_a_cuenta*` | C | C13 |
| — | ¿Debe `generar_asiento` exigir lo que exige el destino? | F | — | — | — | pregunta | — |
