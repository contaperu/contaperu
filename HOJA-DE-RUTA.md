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

Librería **8.1.0** y estándar **`open-accounting` 1.0**
(`contaperu/_version.py`).

**Y escala, medido y reproducible.** Funciones puras, sin estado, sin red, sin disco y sin reloj: dos procesos nunca
se pisan, así que la escala horizontal es trivial. Lo vertical se mide con `herramientas/medir.py`, que multiplica
el golden de los doce casos:

| Filas | `revisar` | `exportar` (SIRE) | por fila |
|---|---|---|---|
| 100 | 0,02 s | 0,03 s | 0,16 ms |
| 1 000 | 0,12 s | 0,15 s | 0,12 ms |
| 3 000 | 0,36 s | 0,46 s | 0,12 ms |
| 5 000 | 0,62 s | 1,01 s | 0,13 ms |

Lo que importa no es el número —depende de la máquina— sino **la forma**: en línea recta. Una curva que se dobla es
una regresión cuadrática, y por eso el arnés viaja en el repositorio: una medida sin su arnés es una afirmación que
nadie puede contrastar. La primera vez que se corrió encontró una (`exportar` excluía por igualdad recorriendo una
lista: 5 000 filas tardaban 12,77 s), y se arregló en la 8.1.

El tope está declarado y explicado: `MAXIMO_COMPROBANTES = 5000`, con el mensaje «divídelo por periodo o por lote».
No es una limitación, es un contrato de lotes. **Lo que no escala no es el motor: es el ERP** —su base de datos, su
concurrencia, su almacén del mes—, y por eso el reparto que ya está decidido, que el estado es del ERP, es también
la decisión correcta de escalabilidad.

| Pieza | Hoy |
|---|---|
| **Entradas** · lectores | XML UBL 2.1 con raíz `Invoice`, `CreditNote` o `DebitNote` (`contaperu/lectores/xml_ubl.py:31`); ZIP; propuesta del SIRE. El CDR se reconoce y se ignora. Un PDF o una foto quedan pendientes de leer |
| **Estándar y comunidad** | `open-accounting` 1.0 con su esquema, sus catálogos publicados, sus enmiendas y su batería de conformidad; drivers de terceros por el grupo `contaperu.drivers`, con el contrato v1 (`contaperu/drivers/contrato/`); plantillas de aviso «Regla mal puesta», «Error», «Enmienda» y «El formato de mi sistema». El repositorio es público |
| **Motor** · validación | Observaciones propias, estables por contrato (`contaperu/tributos/validar.py`); duplicados dentro del lote y contra lo ya anotado |
| **Motor** · asiento | Línea del comprobante con `rol`, cuadre sin tolerancia, detracción en dos tiempos, huella por tanda |
| **Motor** · puertas | API pública `contaperu.api` sobre un pipeline único; CLI, servidor MCP con 15 herramientas y 13 recursos, y puerta HTTP con el contrato OpenConta; hay un `Dockerfile`. La 2.0 retiró las rutas de la 0.x |
| **Salida · SUNAT** | Canal `sunat`, que son **los dos regímenes**: el driver `sire` escribe el TXT de reemplazo del RVIE y del RCE; `ple` y `ple_plan`, el Libro Diario y el detalle del plan contable |
| **Salida · Legacy** | CONCAR (asientos) y CONTASIS (registro), de canal legacy; STARSOFT (asientos), con un mes de compras importado el 7-oct-2026 y uno de ventas el 8-oct-2026 |
| **Salida · ERP** | **La base está puesta.** De entrada, el documento `open-accounting` como forma canónica —un ERP no escribe un lector—; de salida, el asiento en el propio estándar y el CSV, los dos de canal `erp`. Cuatro puertas que dan el mismo documento (librería, CLI, MCP y HTTP), el contrato OpenConta generado de la tabla de operaciones, los catálogos citables por la URL de su tag, una batería de conformidad que se corre sin el motor y en cualquier lenguaje, `resumen` y `por_cuenta` para no reescribir «cuánto es este libro», `campos_del_comprobante` y `REGLAS` para quien monte su capa de agente, y la API del SIRE descrita como datos y funciones puras |
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
- B8 · 3.4.0 (`resumen` y `por_cuenta`: el caso lo trajo un conector que los escribió por su cuenta y le salió `07` donde el motor dice `("07","87")`)
- B9 · 3.4.0 (`campos_del_comprobante` y `REGLAS`, por el mismo conector, que había copiado la lista de campos a mano y se dejó cinco)
- A4 · 6.0.0 (STARSOFT Desktop: un mes de compras importado el 7-oct-2026 y uno de ventas el 8-oct; la `V` del archivo de ventas se corrigió en la 6.3.2)
- J0 · 1.0.0 (14-sep-2026: el acoplamiento con lo peruano queda congelado en un test, sin mover código)
- J1 · 1.0.0 (14-sep-2026: las dependencias ocultas se cortaron al ordenar el motor en capas que un test hace cumplir)
- E6 · 1.4.0 (20-sep-2026: las plantillas «El formato de mi sistema» y «Enmienda»)
- E7 · 1.4.0 (20-sep-2026: el repositorio es público; el historial quedó sin revisar, ver la fila del hito)

---

## 2 · Qué sigue: orden de ejecución y dependencias

**El eje cambió el 10-oct-2026** (John): el motor dejó de ordenarse por los sistemas que ya existen y se ordena
por **ser la base de cualquier ERP**. La capa encima se mantiene —CONCAR y CONTASIS siguen, y nadie tiene que
cambiar de sistema— pero ya no es lo que manda el orden. Lo que lo manda es que **la app que integra el motor está
creciendo hacia un ERP**: bancos, conciliaciones y más SUNAT. Y la secuencia que eso impone, que es la regla del §7:
**el motor va primero, se etiqueta una versión, y el producto adopta después.**

El orden de ejecución: **el ERP primero** —los tres hitos que le faltan al contrato para que un ERP pueda mandar lo
que hoy no puede (B13-B15)— **→ el banco como contrato** (D8 hoy; D1 y D2 en cuanto lleguen sus dos archivos)
**→ SUNAT, que no necesita un frente nuevo sino desbloquearse** (C16 con un token, B10 como decisión, C17 cuando la
app pida la siguiente API), con **la salida Legacy en paralelo** esperando sus archivos y **el estándar y la
comunidad** acompañando desde el principio, porque sus enmiendas tienen que existir antes del primer bloque nuevo
del esquema. La puerta del ERP se abrió en la 1.0 (B1-B6) y lo que la 3.4 y la 8.1 le pusieron encima (B8, B9 y
`contaperu/sunat/`) es lo que la hace una base y no una promesa. **Otra jurisdicción** no entra en la secuencia
hasta que llegue un cliente real fuera del Perú; sus dos primeros hitos, J0 y J1, los cumplió la 1.0 al ordenar el
motor en capas.

```
LA BASE DEL ERP (lo primero) ─────────────────────────────────────────────────────────────────────
 E1 enmiendas ─┬─► B13 libro.tipo del PLE ──► B15 nivel fino de la cuenta
               ├─► E8 el importe numérico
               └─► B14 determinación con dimensiones
 B8 · B9 (3.4.0) ─► B11 propuesta y aprobación [un mes imputado por un agente] ─► B12 trazabilidad

EL BANCO ─────────────────────────────────────────────────────────────────────────────────────────
 D8 cuentas_bancarias [norma: CCI y códigos de banco]   ← sin esperar archivo
 0.3 frase del LEEME ─► D1 constancias [archivo del BN] ──┐
 E1 enmiendas ─┬─► D2 extracto [archivo real] ────────────┴─► D3 conciliar ─► D5 pasarela [reporte]
               │     ├─► D4 reglas bancarias [reglas reales]                        └─► D6 asientos
               │     ├─► B7 contrato de lector [segundo banco]                 [fuente + aceptado]
               │     └─► D7 conectores [primer conector]
               ├─► C2 · C3 · C4 · C5 · C12
               ├─► E2 conformidad
               └─► E3 política de retiro

SUNAT ────────────────────────────────────────────────────────────────────────────────────────────
 contaperu/sunat/ (8.1) ─┬─► C16 lectores de la respuesta [una respuesta real por operación]
                         ├─► C17 más APIs descritas [la siguiente que la app necesite]
                         └─► B10 perfiles del MCP [decisión, antes de que algo pida credenciales]
 C1 reglas SUNAT ─┬─► C2 código oficial · C3 CDR [CDR reales] · C5 20 / 40 [XML + fuente]
                  ├─► C14 la norma como dato
                  └─► E4 revisión [nueva versión SUNAT]
 C8 padrón ─► C11 tipos de cambio          ·  C13 pago a cuenta [formulario presentado]
 C15 consecuencia de `confianza` [un mes cargado desde PDF]

Sin dependencias de código: A1-A3 [archivos aceptados] · C6 [04 real] · C7 [RHE real] · C10 [plan + rechazo]
                            · E5 guía de aporte

OTRA JURISDICCIÓN [un cliente real fuera del Perú] · J0 y J1 cumplidos en la 1.0
 J0 ─► J1 ─┬─► J2 (tras C1 y C2) ─┬─► J4 ─► J5 (con E1 y E3) ─► J6 [archivo aceptado]
           └─► J3 ────────────────┘

La Fase 0 (0.0-0.8) y la puerta del ERP (B1-B6) están cumplidas: su grafo vive en el historial.
```

Lo cumplido —la Fase 0 entera, E1, C1, C9, C2, E2, E3, E5, E6, la puerta del ERP (B1-B6) y B8 y B9— está en
«Cumplidos» con su versión. Lo que queda, en el orden del eje nuevo:

| Orden | Hitos | Arranca con |
|---|---|---|
| 1 · la base del ERP | **B13** `libro.tipo` con el catálogo del PLE → **B15** el nivel fino de la cuenta · **E8** el importe numérico | código, con su enmienda |
| 2 · el banco, lo que no espera archivo | **D8** `cuentas_bancarias*` como argumento | norma: el CCI y los códigos de banco |
| 3 · SUNAT, desbloquear | **C16** los lectores de la respuesta | dato: una respuesta real por operación, que se captura con `herramientas/comprobar_sire.py` |
| 4 · antes de que algo pida credenciales | **B10** perfiles de herramientas del MCP | decisión |
| en paralelo | A1-A3 legacy | dato: la plantilla de SISCONT y un mes importado |
| cuando la app pida la siguiente API | **C17** más APIs de SUNAT descritas | dato: cuál, y su manual |
| cuando llegue el dato | **B14** determinación con dimensiones · C3 · C4 · C5 · C6 · C7 · C8 · C10 · C11 · C12 · C13 · C14 (tras C1) | dato |
| cuando lleguen los dos archivos | **D1** constancias del BN · **D2** extracto → **D3** conciliar · D4 → D5 → D6 | dato (D3 es código, tras D1 y D2) |
| cuando haya un mes imputado por un agente | B11 → B12 · C15 consecuencia de `confianza` | caso real |
| cuando haga falta | B7 · D7 · E4 | dato o decisión |
| con un cliente real fuera del Perú | J0 → J1 → J2 · J3 → J4 → J5 → J6 | dato: el cliente, su destino y un archivo aceptado |

---

## 3 · Fase 0 · Afinar lo que existe

Antes de abrir frentes se afina lo que ya está en uso. Todo arranca con **código**; varias piezas desbloquean frentes
posteriores. Las propuestas de origen están en la tabla del §8, y cada hito cita la suya en la columna
«Propuesta».

| id | Hito | Nivel | Criterio de salida | Depende de | Propuesta |
|---|---|---|---|---|---|
| **0.0** | **Decidir la identidad del comprobante**: `libro.ruc` + `libro.tipo` + `Comprobante.clave` (`contaperu/modelo/comprobante.py`), sin periodo, y si en ventas lleva la contraparte (`comparar_sire` la deja fuera por la misma razón) | estándar · F | Escrita en `estandar/LEEME.md` | — | — |
| **0.1** | **`claves_previas` en la fachada**: `revisar`, `diagnosticar`, `generar_asiento`, `exportar`, CLI y MCP. `validar.revisar` ya lo acepta (`contaperu/tributos/validar.py`). En JSON viaja como `[tipo_cp, serie, numero, contraparte_doc]`, normalizado con `clave_de`, y con un tope como `MAXIMO_COMPROBANTES` (`contaperu/pipeline/preparacion/documento.py:21`) | F | Por las tres puertas sale `DUPLICADO_PERIODO_ANTERIOR` con `pedir_a: contador`; «00000123» casa con «123»; por encima del tope, `DocumentoInvalido`; sin claves, el snapshot de CONCAR sale idéntico | 0.0 | 1 |
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
red. **El registro va antes de conciliar**: sin saber qué cuentas tiene el contribuyente no hay contra qué casar
nada, y por eso D8 es el primero del frente y el único que no espera un archivo.

**Las tres conciliaciones, que no son la misma y estaban repartidas.** Conviene verlas juntas, porque la palabra
tapa tres trabajos con tres estados distintos:

| Conciliación | Qué hay hoy | Qué la destraba |
|---|---|---|
| **Las constancias de detracción** contra las compras del mes | **Media hecha.** `contaperu/tributos/detracciones.py` deduce `PROVISIONADO` o `PAGADO` del número y la fecha de la constancia, y `diagnosticar` lista las que esperan (`detraccion_pendiente`). Lo que falta es el casado: leer el archivo del banco y escribirle a cada comprobante su número y su fecha, sin que nadie teclee | Un archivo real del Banco de la Nación — la consulta de pagos de detracciones de SOL o los movimientos de esa cuenta. Es el hito **D1** |
| **El extracto bancario** contra el libro | **Nada**, y es el que más código pide. Hay dos trampas ya localizadas para su lector: un `.xlsx` empieza como un ZIP y se desarma solo, y un `.txt` se ignora como archivo auxiliar (`contaperu/lectores/archivos.py`) | Un extracto real anonimizado (**D2**); con él, **D3** ya arranca con código |
| **La propuesta del SIRE** contra lo que el contribuyente anotó | **Hecha y en uso**: `contaperu/tributos/comparar_sire.py`, expuesta como `api.comparar_sire`, compara el TXT de reemplazo contra la exportación del detalle del SIRE. Lo que falta no es la comparación, es de dónde sale el archivo: hoy lo baja una persona a mano | La otra mitad del hito **C16**, los lectores de la respuesta del SIRE |

El paquete **`contaperu/banco/` está reservado** en la capa núcleo (`ARQUITECTURA.md`, «Lo que queda preparado») y
todavía no existe: lo crea D2. Los conectores de entrada **nunca** viven dentro de `contaperu`, que es lo que D7
decide y lo que `tests/test_frontera.py` hace cumplir.

**Investigación.** Lo que hace EE. UU. de verdad, los canales peruanos a la fecha de consulta, los proyectos
abiertos, los rieles de pago y el fraude.

**Qué hay hoy.** Nada de banco. La conciliación de constancias de detracción está pendiente de un archivo real, pero la
mitad existe: `diagnosticar` ya lista las detracciones que esperan constancia (`detraccion_pendiente`,
`contaperu/tributos/detracciones.py`) y el monto en soles enteros tiene su regla con fuente
(`contaperu/tributos/detracciones.py`). Hay dos trampas para un lector de extractos: un `.xlsx` empieza como un ZIP y se
desarma (`contaperu/lectores/archivos.py:56-58`), y un `.txt` se ignora como archivo auxiliar (`archivos.py:26`).

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de | Propuesta |
|---|---|---|---|---|---|---|
| D8 | **`cuentas_bancarias*` como argumento, no como tabla.** El maestro de cuentas que aporta quien llama —banco, número, CCI, moneda, y la cuenta contable con la que se asienta— con las funciones puras que lo validan. Es el **registro antes de conciliar**, y es la única forma que el §6 admite: el estado es del ERP, y lo que puede vivir aquí es su contrato. El patrón está en producción y no hay que inventarlo: `imputaciones`, `correlativos`, `claves_previas` y la propia `configuracion` son argumentos que el motor recibe y no guarda. (`plan_de_cuentas*`, `padron*` y `tipos_de_cambio*` seguirán el mismo molde, pero **todavía no existen**: son C10, C8 y C11.) **Es el único hito de este frente que no espera un archivo** | N · F | dato: el formato del CCI y los códigos de banco con su fuente, que son norma publicada | Sin cuentas declaradas nada cambia; un CCI que no cumple su formato da observación y no excepción; una cuenta que no está en el maestro no se adivina | — | 46 |
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
| E8 | **Cerrar el importe numérico de más de dos decimales.** El estándar manda los importes en texto y acepta número por compatibilidad: `$defs.importe` limita la cadena con su patrón, pero el número no lleva `multipleOf`, así que un `118.005` todavía valida. Es lo que un ERP manda sin saberlo, y la contabilidad no perdona el céntimo | estándar | código: es un agujero del esquema, verificado a mano el 9-oct-2026 | Un documento con `118.005` numérico no valida; los que mandan texto siguen validando igual; un caso de conformidad lo fija | E1 | 37 |
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
(`contaperu/tributos/validar.py`), los roles del asiento (`contaperu/asiento/motor.py:40`), las claves del contrato de driver
(`contaperu/drivers/contrato/:227-230`, `:280-286`) y el esquema del estándar. Desde la 1.0, `tests/test_capas.py`
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

### Salida · SUNAT

**Objetivo.** Que lo que se presenta a SUNAT salga del mismo documento que los asientos y cuadre con lo que SUNAT ya
tiene: el TXT de reemplazo del RVIE y del RCE, y la propuesta como lista de control.

**La API del SIRE ya está descrita y armada** (8.1): `contaperu/sunat/` arma la petición de las once operaciones,
lee el estado de un ticket y clasifica el rechazo de SUNAT, todo desde su catálogo y sin salir a la red — el núcleo
puede saber la URL, lo que no puede es llamarla. `herramientas/comprobar_sire.py` la contrasta contra la API real
con un token que trae quien lo tenga. **Lo que falta es evidencia**: ver el hito C16.

**Son dos regímenes y un solo canal** (`sunat`, desde la 8.0). El **SIRE** manda compras y ventas (RS 112-2021 y
RS 040-2022) y es de lo que hablan los hitos de abajo. El **PLE** manda el Libro Diario y los demás libros, más el
detalle del plan contable (RS 234-2006 y RS 286-2009), y lo escriben `ple` y `ple_plan` desde la 4.2 y la 4.3: su
fila es una línea del asiento, no un comprobante. Lo que el PLE tiene pendiente no es un driver, es **de qué sacar
los asientos que no vienen de compras ni de ventas** —la planilla, la depreciación, el asiento de destino—, que es
595 de 1 441 en el mes contrastado y entra por su libro del PLE, que es fuente normativa, no por un rol nuevo que
habría que inventar y después mantener.

**Investigación.** El SIRE frente a las declaraciones de EE. UU. y la propuesta del RCE como lista de control:

**Qué hay hoy.** El driver `sire` escribe el TXT de reemplazo del RVIE (Anexo 3) y del RCE (Anexo 11), contrastado con
archivos reales aceptados, y lo comprime en su ZIP; deja fuera los recibos por honorarios. `comparar_sire` compara ese
TXT con lo que SUNAT exporta del SIRE (`contaperu/tributos/comparar_sire.py`). Y el FORMATO está publicado columna a columna
(`datos/sunat/sire_campos.json`, `api.campos_del_sire()`, 3.8.0): de cada campo del anexo, dónde cae o por qué no cae,
con un test que lo confronta con el lector y con el escritor. Cubre del hito B9 la mitad que mira al registro; la que
mira al documento es `campos_del_comprobante*`.

| id | Hito | Nivel | Arranca con | Criterio de salida | Depende de | Propuesta |
|---|---|---|---|---|---|---|
| C9 | `cruzar_con_propuesta*`: lo cargado contra la propuesta del RCE, y el primer uso de `pedir_a: proveedor`; es la lista de control que EE. UU. no tiene | N · F | código | Tres cajones; ceros a la izquierda; un RUC mal escrito | 0.0 | 9 |
| C17 | **Más APIs de SUNAT descritas, con el molde de la 8.1.** `contaperu/sunat/` demostró la forma: el catálogo con su `actualizado_al` y la fuente de cada ruta, armar la petición, leer el estado de un ticket, clasificar el rechazo — y **cero llamadas**, porque el núcleo puede saber la URL y no puede llamarla. Cada API nueva entra igual: su catálogo, sus funciones puras y su herramienta de contraste en `herramientas/`. Lo que **no** entra es enviar, que es del integrador | N · F | dato: **la siguiente API que la aplicación necesite**, con su manual — el motor va primero y el producto adopta después (§7) | `tests/test_frontera.py` sigue verde: el núcleo sabe la URL y no sale a la red; las credenciales no se nombran; la herramienta de contraste solo llama a las operaciones de lectura | — | 45 |
| C16 | **Los lectores de la respuesta del SIRE**, que la 8.1 dejó fuera a propósito: la forma de lo que SUNAT contesta —el número de ticket con sus tres grafías, la lista de archivos con las dos erratas del manual— **no la sostiene un catálogo, la sostendría una respuesta real**, y no hay ninguna guardada. Mudar un lector no comprobado a un repositorio abierto no rompe nada: congela un mapeo que nadie verificó, con la solidez aparente que da estar en un motor con tests | N · F | dato: una respuesta real por operación, capturada con `herramientas/comprobar_sire.py` y anonimizada | Cada operación de lectura tiene su fixture y su lector, y el flujo de traer la propuesta —pedir, ticket, consultar, bajar— pasa entero en la batería **sin red** | — | 36 |

**No se hace.** Descargar la propuesta ni presentar el registro: eso necesita red y Clave SOL, y es de quien use el
motor.

### Salida · Legacy: CONCAR, CONTASIS, SISCONT y STARSOFT

**Objetivo.** Que los cuatro sistemas instalados salgan del mismo documento, cada uno con su archivo aceptado, y que
el motor conozca lo que el destino exige antes de que el sistema rechace una importación. **Tres ya salen** —CONCAR,
CONTASIS y STARSOFT Desktop—; queda SISCONT. Este frente **no se retira ni tiene plazo**, aunque desde el
10-oct-2026 ya no sea el que ordena el trabajo: son, con los otros dos, los sistemas contables que más estudios
peruanos tienen instalados, y la promesa es que el motor trabaje encima de ellos mientras evolucionan.

**Investigación.** Los tres escalones con que EE. UU. integra sistemas de escritorio sin API, y lo que se toma de
ellos. Lo que un sistema espera recibir, comparado entre nueve plataformas y los estándares abiertos de factura, en
[REFERENCIAS.md](REFERENCIAS.md), «El registro del comprobante, comparado».

**Qué hay hoy.** CONCAR (asientos) y CONTASIS (registro) en uso, de canal legacy. Las formas del contrato
(`contaperu/drivers/contrato/`) y la receta con la que entró CONTASIS (`CONTRIBUTING.md`, «Añadir un driver de
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
| A4 ✅ | **STARSOFT Desktop**, asientos → `desde_lineas`. **Hecho y aceptado** (2.0-2.3, cerrado en la 6.0): las dos plantillas calcadas del archivo real, un **mes de compras importado de verdad el 7-oct-2026** —que destapó lo que ningún vídeo decía: el TXT va suelto, sin el ZIP— y un **mes de ventas el 8-oct-2026**, que desmintió la simetría que se esperaba: el fichero no empieza por `C` en los dos libros, la letra es la del libro y el de ventas es `V-VENTAS_…` (6.0.2 y 6.3.2) | D | — | Igual que A1 | — | — |
| C10 | `plan_de_cuentas*` del destino, falta `cuenta_fuera_del_plan*`, marca de centro de costo y lista de centros | N · F · D | dato: plan exportado de CONCAR + un rechazo real de importación | Sin plan, snapshot idéntico; un plan sin la cuenta bloquea y `exportar` lanza | — | 11, 12, 13 |
| C14 | **La fuente de cada regla, como dato**: hoy la norma está en prosa al lado del código (regla 1, lo mejor del proyecto) y **un agente no la puede citar: tiene que creérsela**. Con `norma`, `articulo` y `vigencia` legibles por máquina, una observación puede decir «no te doy el crédito fiscal porque la Ley 29215 art. 2 da 12 meses y van 14» **citando**. El precedente existe: el cargador del PCGE rechaza un mapeo sin fuente, y `regimenes.json` exige la cita por bloque | N · F | código, tras C1 | Cada observación con regla detrás trae su fuente; una regla nueva sin ella no carga, como en el PCGE | C1 | 32 |
| C15 | **Darle consecuencia a `confianza`**: el campo existe en el comprobante desde antes de que nadie lo usara (`origen`, `confianza`, por defecto `1.00`) y **hoy no lo mira nadie**. Falta el umbral y qué pasa debajo: un dato extraído por IA con 0,7 no puede tratarse como uno leído de un XML | N · F | caso real: un mes cargado desde PDF con su confianza por campo | Un dato por debajo del umbral sale como propuesta y no como hecho; el umbral lo pone quien llama, no el motor | B11 | 33 |

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
| B10 | **Perfiles de herramientas en el MCP**: qué publica el servidor abierto y qué solo un integrador. Hoy publica las 14 siempre, con la misma anotación de solo lectura | F | decisión, antes de que exista algo que pida credenciales | Una herramienta marcada de integrador no aparece en el servidor público; la foto del MCP lo fija | B1 | 35 |
| B11 | **Propuesta y aprobación con rastro**: el camino «el agente propone la cuenta, el humano confirma», con quién propuso qué y con qué huella. Hoy el motor valida o bloquea, y ese camino no existe | N · F | caso real: un mes imputado por un agente y revisado por un contador | Una propuesta no se exporta hasta que alguien la confirma; el rastro viaja en el documento y no en una base | 0.4 | 34 |
| B12 | **Trazabilidad del agente** en `_exportacion`: hoy graba el driver, el archivo, la huella, la fecha y el motor, nunca quién lo pidió | F | B11 | Quien pidió la exportación queda en la anotación, y la huella no cambia por ello | B2, B11 | — |
| B4 | Puerta **HTTP sin estado**, `servidor_http*`, con el extra `contaperu[http]*` | puerta | dato: un integrador no Python que lo necesite | Está en `PUERTAS` de `tests/test_frontera.py`; las tres puertas dan el mismo documento; comparte topes y la defensa de `Host` del MCP; publicar su imagen pide OK | B3 | — |
| B5 | El CSV lleva `rol` y los `tipo_cp`, lo que un driver necesita para no adivinar | D | código | Columnas nuevas llenas; **se anuncia** porque cambia una salida | — | 7 |
| B6 | **Guía «integrar ContaPerú en un ERP»**: la librería (Odoo, Frappe), la CLI por lotes, el MCP y, con B4, HTTP; niveles *de serie* (con archivo aceptado) y *comunidad* (paquete propio por entry points); checklist de contribución | documentación | código | Los ejemplos en Python se ejecutan en la batería; `contaperu://drivers` dice si cada driver es de serie | B1 | — |
| **B9 ✅** | **Lo que una capa de agente se trae sin copiarlo**: `campos_del_comprobante*` —qué campos pone el documento, cuáles el sistema y cuáles la revisión— y `REGLAS*`, las reglas del dominio sin el camino de las herramientas de este servidor pegado | N · F · documentación | código | Los tres tramos cubren el comprobante entero y no se solapan; ninguna herramienta ni recurso de este servidor se nombra en `REGLAS`; la fila «Reportes y análisis» de `INTEGRAR.md` queda partida en dos | B6, B8 | — |
| B13 | **`libro.tipo` crece con el catálogo del PLE.** Es el hueco grande del eje nuevo: el catálogo tiene dos valores, `venta` y `compra`, así que **un ERP no tiene con qué nombrar un asiento de planilla, de depreciación o de destino** —595 de los 1 441 de un mes real—. No hace falta para *producir*, porque el driver ya escribe el Libro Diario 5.1; hace falta para **recibir**. Y entra con cuidado: `tipos_de_libro` **no degrada** como el `rol` —quien recibe un libro que no conoce no puede adivinar qué hacer con él—, así que la degradación es del destino y el driver que no lo declara en sus `FORMATOS` lo rechaza limpio, diciendo qué libros lleva | N · estándar | código, con su enmienda. El dato ya está: un Libro Diario 5.1 presentado y aceptado, con sus 1 441 asientos | Un libro del catálogo entra y sale intacto; un driver que no lo declara lo rechaza nombrando los que sí lleva; el snapshot de CONCAR no se mueve | E1 | 39 |
| B14 | **La tabla de determinación, con dimensiones**: `configuracion.cuentas` como papel × quién × qué → cuenta, resuelto por lo más específico, como lo hacen OFBiz, iDempiere y Business Central. La jerarquía de tres capas **ya existe** —fábrica → driver → empresa, resuelta por `contaperu/drivers/contrato/`—; lo que no existe es que la cuenta dependa de con quién o de qué | N · F | caso real: un contribuyente cuya cuenta de proveedor cambie según el proveedor o la línea de negocio | La resolución elige siempre lo más específico; sin dimensiones declaradas el resultado es byte a byte el de hoy | — | 42 |
| B15 | **El nivel fino de la cuenta**, las dos mitades juntas porque son el mismo escalón: la **divisionaria normativa** en la línea (el nivel del artículo 6 de la RS 234-2006) y **`tipo_de_cuenta`** derivado de ella, con los 18 valores de Odoo cuyos grupos ya coinciden con las cinco `clases`. Opcionales, nunca `required`, para no tocar la regla de degradación | N · estándar | caso real: un ERP que pida más que las cinco `clases`, o un destino que exija el nivel normativo por línea | Cada valor sale de la divisionaria con el artículo del PCGE al lado, como en el cargador del PCGE; el documento sigue validando sin ellos | B13 | 40, 41 |
| **B8 ✅** | **`resumen*` y `por_cuenta*`**: cuánto es un libro —base gravada, IGV y total, cada moneda por su lado, con agrupación por contraparte— y el pre-mayor con su cuadre por moneda. **Sin driver y sin configuración**: es del libro y del asiento, no de un destino | N · F | código | Una nota de crédito de no domiciliado (87) resta; ninguna clave suma dos monedas; el cuadre es el mismo dict que `cuadrar`; una cuenta con dos papeles los dice los dos; el `resumen_por_contraparte` de `diagnosticar` no cambia de cifra | B1 | — |

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
| 43 | Las dos cuentas que el plan real de STARSOFT usa y el motor no sabe elegir: a dónde va el IGV sin derecho a crédito fiscal, y la cuenta de ingreso de una devolución | Con un contador, y el PCGE delante |
| J2-J6 | Un cliente real fuera del Perú, su sistema contable de destino y un archivo que ese sistema haya aceptado | Con el cliente |
| **Legacy** | | |
| A1-A3 | La plantilla de SISCONT y un mes que haya importado | Con quien use SISCONT |
| C10 | El plan de cuentas exportado de CONCAR y un rechazo de importación | Con un estudio que use CONCAR |

---

## 6 · Lo que no está en esta hoja de ruta, y por qué

- **Nunca, por decisión:** emitir, firmar o enviar comprobantes; consultar la validez de un comprobante; descargar la
  propuesta del SIRE, el padrón o los tipos de cambio; leer PDF o fotos ([README.md](README.md), «Qué no hace»).
- **Nunca, porque esto no es un ERP y es correcto que no lo sea:** interfaz, usuarios, permisos, multiempresa y
  **persistencia**. Y con ellos **el estado**: el periodo y su cierre, el saldo de apertura, el plan de cuentas como
  tabla viva. El motor recibe el estado en rodajas —los correlativos, las claves ya anotadas— y no lo guarda, que es
  lo que lo deja sin reloj y sin base y por tanto reutilizable y escalable. La frontera es la misma que ya rige con
  la aplicación que lo integra: *si cambia según cuándo o cuántas veces lo llames, no es del núcleo*. Lo que sí
  puede entrar un día es el **esquema publicado** de esos conceptos y las funciones puras que los validan —eso es
  contrato, no estado—, y entraría por el frente ERP con su caso real delante.
- **Sin caso real todavía:** guías de remisión; SDKs generados; WASM; `sugerir_imputacion` (tiene la misma forma que la
  acción de una regla bancaria y entra con D4 si hace falta); `trazas` de un driver que consolide; `documento.id_externo`
  en la línea; pedir datos desde el MCP con el patrón de la especificación 2026-07-28, que espera un SDK que la hable; el archivo de 4ta del PLAME, análogo del 1099
  (espera un archivo importado y C7); `cuentas_conocidas*`, la cuenta del proveedor distinta de la conocida (espera D2
  y un caso); emparejar órdenes de compra y recepciones (espera un cliente cuyo ERP las lleve).
- **En vigilancia:** las finanzas abiertas de la SBS y un perfil FAPI peruano, cuando exista la regulación; la factura negociable y su
  Plataforma de Confirmación, si un cliente la usa como canal de conformidad.
- **El tercer libro, `libro.tipo: honorario`: no se hace** (John, 18-sep-2026). Un recibo por honorarios entra en
  el libro de compras, que es donde SUNAT lo pide, y el hecho de que sea honorario ya lo dice su `tipo_cp: 02`.
  Abrir un libro propio costaba cuatro cosas y ninguna se pagaba con nada: partir en dos el documento de un mes que
  hoy es uno; un valor más en un catálogo que promete no quitar nada; un camino nuevo en cada driver, que tendría
  que decidir si lo escribe o lo ignora; y romper la identidad del comprobante, que es `libro.ruc` + `libro.tipo` +
  la clave. **`libro` es el libro tributario**, no una categoría de gasto.
- **Un driver para la API Web de STARSOFT (Gold Edition): tampoco** (John, 10-oct-2026). Fue el hito A5 y se retira
  con la investigación que lo sostenía: era un cuerpo JSON sobre una API con IP pública y licencia por servidor, que
  además no interesa al repositorio. Lo que resolvió A4 —siglas, sub-diarios, destino del IGV, cuentas y la
  proyección— sigue sirviendo a quien quiera escribirlo fuera; el canal `api_erp` sigue reservado por su propio
  criterio, que es que exista un formato que `erp` no pueda llevar.
- **Descartado en el diseño** (`ARQUITECTURA.md`, «Lo que no se hace, y por qué»): la cuenta transitoria inmediata, *embeddings* en el motor, un
  lenguaje de requisitos declarativos, log con hash encadenado y fechas de bloqueo.
- **Resuelta en la 1.0:** `generar_asiento` exige lo que exige el destino, igual que `exportar` (CHANGELOG, «Cambiado»).

---

## 7 · Cómo se mantiene

- **Quién la propone y quién la toca.** Cualquiera propone un hito —un contador, un desarrollador, una empresa— abriendo
  un aviso con su caso real o el dato que lo destraba: es la forma colectiva de la hoja de ruta. El mantenedor decide y
  fusiona. Un hito nuevo entra solo si nombra su caso real o el dato que lo destraba. Los nombres con `*` se deciden al
  pasar a código.
- **El motor va primero y el producto adopta después** (John, 10-oct-2026). Nada se construye primero en la
  aplicación: se hace aquí, se etiqueta una versión y allá se cambia el número fijado y se despliega. Es por qué esta
  hoja ordena el motor y no un producto, y por qué **un hito no se da por cumplido porque una aplicación ya lo
  tenga**: se da por cumplido con su test, su versión y su entrada en el CHANGELOG.
- **Dónde va un hito nuevo.** En el frente del flujo que le toca, con la letra de ese frente y el número siguiente
  (E9, C18…). Un id no se reutiliza ni se renombra al moverse de frente.
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

Las propuestas que ha levantado la investigación, cada una con el caso real que la destraba y el
hito que le toca; «—» si todavía no tiene uno. Es a esta tabla a la que remite la columna
**Propuesta** de los frentes. Son **46**, en cuatro tandas: las 31 del ciclo contable (13-14 de
setiembre de 2026), las cinco del diagnóstico de la arquitectura (9-oct-2026), las ocho que quedaron
al limpiar la raíz y las dos del cambio de eje (las dos, del 10-oct-2026). Las tres últimas tandas
van al final, cada una con su tabla.

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
| 14 | `aplicar_constancias` | N | Hoja de ruta; `detraccion_pendiente` ya responde | De `PROVISIONADO` a `PAGADO` con el archivo real; sin pareja, igual | `aplicar_constancias*` | C | D1 |
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

### Las cinco del diagnóstico de la arquitectura (9-oct-2026)

La pregunta era si esto tiene arquitectura de ERP, si la IA está integrada de verdad y si escala. Las respuestas, en
corto: **no es un ERP y es correcto que no lo sea** (§6); **escala por construcción y está medido** (§1); y la IA
**sí** está en la api y no en la puerta —el MCP se deriva de la tabla, `diagnosticar` describe y no decide, y las
reglas del dominio no nombran ninguna herramienta, con un test que lo impone—. Lo que falta para que sea nativa de
verdad es corto, y es esto:

| # | Propuesta | Nivel | Caso real que la destraba | Test que la fijaría | Nombre | Prio | Hito |
|---|---|---|---|---|---|---|---|
| 32 | La fuente de cada regla, legible por máquina: un agente no puede citar la norma, tiene que creérsela | N · F | Hoy la norma está en prosa al lado del código; un agente que dice «la Ley 29215 art. 2 da 12 meses» lo está inventando | Cada observación con regla detrás trae `norma`, `articulo` y `vigencia`; una regla sin ellos no carga, como en el PCGE | `fuente*` en la observación | B | C14 |
| 33 | Darle consecuencia a `confianza`, que existe y no la mira nadie | N · F | Un mes cargado desde PDF: hoy un dato con 0,7 se trata igual que uno leído de un XML | Un dato bajo el umbral sale como propuesta y no como hecho; el umbral lo pone quien llama | umbral en la configuración | B | C15 |
| 34 | Propuesta y aprobación con rastro: el agente propone, el humano confirma | N · F | Un mes imputado por un agente y revisado por un contador. Hoy el motor valida o bloquea, y ese camino no existe | Una propuesta no se exporta sin confirmación; el rastro viaja en el documento, no en una base | `propuesta*`, `confirmada_por*` | C | B11 |
| 35 | Perfiles de herramientas en el MCP: qué ve el servidor abierto y qué un integrador | F | Una herramienta que arme peticiones con credenciales no puede estar en el servidor público, y la API del SIRE ya existe (8.1) | Una herramienta de integrador no aparece en el servidor público; la foto del MCP lo fija | `perfil*` | B | B10 |
| 36 | Los lectores de la respuesta del SIRE, con evidencia detrás | N · F | No hay ni una respuesta real guardada, y el `verificado` de cada operación está vacío. Mudar un lector no comprobado congela un mapeo que nadie verificó | El flujo de traer la propuesta pasa entero en la batería, sin red, desde fixtures capturados | `leer_respuesta_*` | C | C16 |

### Las ocho que quedaron al limpiar la raíz (10-oct-2026)

Al retirar `API-DE-REGISTRO.md`, `STARSOFT-INTEGRACION.md` y `LIBROS-Y-CUENTAS.md` casi todo lo suyo estaba o ya
ejecutado —las enmiendas 0008 a 0011, la gobernanza del estándar, el driver de STARSOFT en producción— o era
investigación, que se fue a [REFERENCIAS.md](REFERENCIAS.md). Lo que no era ni lo uno ni lo otro son estas ocho:
propuestas vivas que no tenían dónde esperar su caso. Las cuatro de en medio son las candidatas A, B, C y D de
`LIBROS-Y-CUENTAS.md`, que dejaban dicho que entrarían aquí «con su número, cuando el refinado cierre».

| # | Propuesta | Nivel | Caso real que la destraba | Test que la fijaría | Nombre | Prio | Hito |
|---|---|---|---|---|---|---|---|
| 37 | **Cerrar el importe numérico con más de dos decimales.** El estándar manda los importes en texto y acepta número por compatibilidad; `$defs.importe` limita la cadena con su patrón pero el número no lleva `multipleOf`, así que un `118.005` todavía valida y la contabilidad no perdona el céntimo | estándar · F | Ninguno hace falta: es un agujero del esquema, verificado a mano el 9-oct-2026 | Un documento con `118.005` numérico no valida; los que mandan texto siguen validando igual | — | B | E8 |
| 38 | **El centro de costo en todas las líneas, con `reparto`.** Hoy `asiento/motor.py` lo pone solo en la línea principal y solo si la cuenta lo lleva; Xero, QuickBooks y NetSuite lo admiten en cada línea | N · F | Un mes con un gasto repartido entre dos centros de costo, de un contribuyente que lo lleve así | El centro viaja a la línea del impuesto y a la del tercero cuando el destino lo exige, y el snapshot de CONCAR no cambia si nadie lo pide | `reparto[]` | C | — |
| 39 | **`libro.tipo` crece con el catálogo del PLE** (candidata A). No hace falta para *producir* —el driver ya escribe el Libro Diario 5.1 como el `sire` escribe el RVIE—, hace falta para **recibir** un diario de un ERP: hoy un asiento de planilla o de depreciación no tiene libro que lo nombre | N · estándar | Un ERP que mande un diario con asientos que no vienen de compras ni de ventas | Un libro del catálogo del PLE entra y sale intacto; `tipos_de_libro` no degrada, así que el que no se conoce se rechaza | `tipos_de_libro` | C | B13 |
| 40 | **La divisionaria normativa en la línea** (candidata B, su mitad abierta). La otra mitad ya se resolvió al leer la estructura oficial: la **denominación** no es de la línea, vive en el formato 5.3 del PLE, una vez por cuenta | N · estándar | Un destino que exija el nivel del artículo 6 por línea y no lo pueda derivar del plan | La divisionaria entra opcional y el documento sigue validando sin ella | `cuenta_normativa*` | D | B15 |
| 41 | **`tipo_de_cuenta`: los 18 `account_type` de Odoo, derivados de la divisionaria** (candidata C). No es copiar los ~250 subtipos de QuickBooks, que está descartado: son 18, sus grupos ya coinciden con las cinco `clases` y la asignación se deriva del PCGE, no se mantiene a mano | N · estándar | Un ERP que pida más que las cinco `clases` | Cada valor sale de la divisionaria con el artículo del PCGE al lado, como en el cargador del PCGE; entra opcional, nunca `required` | `tipo_de_cuenta*` | D | B15 |
| 42 | **La tabla de determinación, con dimensiones** (candidata D). Formalizar `configuracion.cuentas` como papel × quién × qué → cuenta, resuelto por lo más específico, como OFBiz, iDempiere y Business Central. **Es la que cubre el hueco de investigación real**: la jerarquía de tres capas ya existe, lo que no existe es que la cuenta dependa de con quién o de qué | N · F | Un contribuyente cuya cuenta de proveedor cambie según el proveedor o la línea de negocio | La resolución elige siempre lo más específico, y sin dimensiones declaradas el resultado es byte a byte el de hoy | `cuentas` con ejes | C | B14 |
| 43 | **Dos cuentas que un asiento real usa y el motor no sabe elegir**, las dos del plan de la empresa que lleva STARSOFT: el **IGV sin derecho a crédito fiscal**, que va a gasto (elemento 64) y no a la cuenta del IGV —eso es el prorrateo—, y la **devolución**, cuyo ingreso va a la 7091 del PCGE y no a la cuenta de venta. Si el motor arma la nota de crédito revirtiendo signos sobre la misma cuenta, no produce lo que ese contribuyente espera | N · F · D | Un contador y el PCGE: hay que confirmar las dos cuentas antes de escribir una regla | La nota de crédito de una devolución usa la cuenta de devoluciones, y el IGV no acreditable la de gasto, con su artículo al lado | — | C | — |
| 44 | **Darle cuerpo a `no_caben()` con las longitudes del manual de STARSOFT**, que desde el 10-oct-2026 están en `contaperu/drivers/starsoft/datos.py` como dato y no como validación. Hoy la función devuelve `{}` a propósito | F · D | Un archivo que STARSOFT rechace por longitud, que es lo único que prueba que el límite es el que dice el manual | Un campo que se pasa de largo sale como observación antes de escribir el archivo, no como un rechazo de la máquina | — | C | — |

La que se retira de la tabla de arriba: **«¿Debe `generar_asiento` exigir lo que exige el destino?»**, que no era
una propuesta sino una pregunta, y que el §6 declara resuelta en la 1.0 desde hace siete mayores.

### Las dos del cambio de eje (10-oct-2026)

El eje pasó de «una capa encima de tu sistema contable» a «la base para cualquier ERP», y con él la regla de
secuencia del §7: el motor va primero y el producto adopta después. Dos cosas que hasta ahora no tenían forma
quedaron con una, y las dos salen de lo que el motor ya construyó, no de un plan nuevo.

| # | Propuesta | Nivel | Caso real que la destraba | Test que la fijaría | Nombre | Prio | Hito |
|---|---|---|---|---|---|---|---|
| 45 | **La API de SUNAT se integra describiendo, no llamando**: cada API entra con su catálogo fechado, sus funciones puras y su herramienta de contraste en `herramientas/`, como hizo la 8.1 con el SIRE. El motor sabe la URL y no la llama; quien envía es la aplicación, con sus credenciales | N · F | La siguiente API que la aplicación necesite, con su manual. No se describen por si acaso | La frontera sigue verde: ni red, ni credenciales nombradas, ni reloj. La herramienta de contraste se niega a llamar lo que no es de lectura | `sunat.*` | B | C17 |
| 46 | **El registro de bancos como contrato y no como estado**: `cuentas_bancarias*` lo aporta quien llama, con el molde de `imputaciones` y `correlativos`, que ya lo hacen. Es la única forma que el §6 admite, y es el paso que va antes de cualquier conciliación: sin registro no hay contra qué conciliar | N · F | El formato del CCI y los códigos de banco con su fuente, que son norma publicada | Sin cuentas declaradas nada cambia; un CCI mal formado da observación y no excepción | `cuentas_bancarias*` | B | D8 |
