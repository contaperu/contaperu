# Arquitectura de ContaPerú

Este documento explica **cómo está construido** el proyecto y **por qué así**: qué es el núcleo, qué
es una puerta, por dónde entra un driver nuevo y qué es lo que no se puede tocar. Es la referencia
para quien vaya a contribuir, y la lista de decisiones que no hay que volver a discutir.

## Tres niveles

```
┌─────────────────────────────────────────────────────────────┐
│  3 · AGENTES                                                │
│      servidor MCP · `diagnosticar` · un agente que pregunta │
│      «¿qué falta?», «¿qué saldría?», «¿qué bloquea?»        │
├─────────────────────────────────────────────────────────────┤
│  2 · DRIVERS                                                │
│      sire (TXT) · concar y contasis (Excel) · csv · terceros│
│      cada uno traduce vocabulario; ninguno decide contabilidad│
├─────────────────────────────────────────────────────────────┤
│  1 · NÚCLEO                                                 │
│      modelo · lectores · validación · asiento · detracciones│
│      IGV · partida doble · PCGE · el estándar `open-accounting`   │
└─────────────────────────────────────────────────────────────┘
```

**El núcleo** sabe contabilidad peruana y no sabe nada más: ni de archivos, ni de red, ni de qué
ERP hay al otro lado. **Los drivers** conocen el formato de un sistema concreto y nada de
contabilidad: reciben el asiento resuelto y lo escriben. **Los agentes** hablan con el núcleo a
través de la fachada y de las puertas, y lo usan como riel determinista: la IA lee el PDF; el
núcleo decide el asiento.

La secuencia de construcción es esa, de abajo arriba, y no es casual: primero el núcleo de reglas,
después los drivers que lo conectan con lo que ya existe, y solo entonces los agentes. Es el orden en
que se puede confiar en cada capa porque la de abajo ya está probada con archivos reales.

## El flujo de un comprobante

```
XML UBL / TXT del SIRE / JSON open-accounting
          │
          ▼
   lectores/  ──►  Comprobante (modelo.py: Decimal, positivo, fechas date)
          │
          ▼
   validar.py  ──►  observaciones: error (bloquea) | aviso (se exporta igual)
          │
          ▼
   asiento/motor.py  ──►  LineaDiario × 2..5   ◄── ESTA ES LA FUENTE
          │                (cuenta, D/H, importe, rol, sub-diario, correlativo,
          │                 documento.tipo_cp, glosa entera, tasa exacta)
          │
          ├──► drivers/concar/proyeccion.py ──► 41 columnas ──► .xlsx
          ├──► drivers/csv                  ──► una fila por línea
          ├──► un driver de terceros (`desde_lineas`) ──► el formato de su ERP
          └──► operaciones.generar_asiento  ──► el bloque `asiento` del estándar
```

Aparte va la familia **registro**: una fila por comprobante, sin asiento, así que sus drivers no pasan por el
motor. El SIRE es un registro tributario y se escribe desde el comprobante (`linea(c, libro, idx, opciones)`). Un
sistema contable que importa su registro de compras o de ventas y arma el asiento él mismo (CONTASIS)
recibe los comprobantes con la configuración (`desde_comprobantes`) y lleva cuentas, pero no las
decide: las lee de `asiento.partes_de` y `asiento.cuenta_tercero`, la misma resolución que usa el motor para el
asiento de CONCAR.

### Un mes, paso a paso

![El recorrido de un mes dentro del motor: leer el XML o la propuesta del SIRE hasta open-accounting; preparar, revisar, seleccionar y exigir lo del destino; armar un asiento, un registro contable o un registro tributario; y responder con el archivo y cada comprobante](diagramas/recorrido-de-un-mes.svg)

Lo mismo, visto desde `pipeline/`. Si llegan archivos de SUNAT, el motor primero los **lee** (`pipeline/lectura`) y
los lleva al documento `open-accounting`: el XML de cada factura, suelto o en ZIP y sin los CDR, o el TXT de la
propuesta del SIRE. Desde ahí, cada mes recorre seis pasos:

1. **Preparar** (`preparacion`). Separa el libro de los comprobantes, aplica la configuración general y la sección
   del destino, y le pone a cada comprobante su imputación por el `id_externo`. Una imputación que no es de ningún
   comprobante se rechaza.
2. **Revisar** (`validar.revisar`, en el núcleo). Valida el RUC, el IGV, el total, la fecha y los duplicados, también
   contra lo ya anotado en otros periodos. Un error detiene la exportación; un aviso deja pasar el comprobante.
3. **Seleccionar** (`seleccion`). Quedan fuera los excluidos, los duplicados y los tipos que el destino no lleva
   (`EXCLUYE_TIPOS`), como los recibos por honorarios en el SIRE y en CONTASIS.
4. **Exigir lo del destino** (`exigir_requisitos` y `contrato.no_caben`). Si el destino lleva cuentas, el núcleo
   comprueba, antes de armar nada, que cada comprobante tenga su cuenta, su centro de costo y su sigla, y que quepa
   en el formato.
5. **Armar, según la forma del driver** (`armado`).
   - **Asiento** (`desde_lineas`: CONCAR, CSV): el núcleo arma las líneas neutrales, las numera por sub-diario, exige
     que cuadren al céntimo y les calcula la huella; el driver solo traduce cada línea.
   - **Registro contable** (`desde_comprobantes`: CONTASIS): el driver recibe los comprobantes y lee las cuentas de
     la misma resolución que usa el asiento.
   - **Registro tributario** (`linea`: el SIRE): una línea por comprobante, sin cuentas, en un TXT con su ZIP.
6. **Responder** (`salida`). El archivo, el resumen y `_exportacion`: por cada comprobante, su identidad, su tramo de
   líneas y su huella, con la versión del motor que lo produjo.

No todas las operaciones hacen el recorrido completo:
- `revisar` llega hasta el paso 2.
- `diagnosticar` recorre hasta el 4 sin detenerse y cuenta lo que bloquea, lo que falta y a quién pedírselo.
- `generar_asiento` se queda en el asiento, sin escribir el archivo.
- `exportar` lo recorre entero.

### La decisión que lo ordena todo: la línea neutral es la fuente

Hasta la 0.6 el asiento nacía en las columnas del Excel de CONCAR (`'A'..'AO'`) y la línea neutral
se sacaba después releyéndolas. Funcionaba, pero la línea «neutral» heredaba el vocabulario de un
ERP —la sigla `FT` en vez del código SUNAT `01`, la glosa cortada a 30 caracteres, la tasa del IGV
redondeada a entero— y un segundo driver de asientos habría tenido que reinterpretar columnas de
CONCAR para escribir las suyas.

Desde la 0.7 la dirección está invertida. `asiento/motor.py` arma las líneas en el vocabulario de
`open-accounting` y CONCAR es una proyección más. Lo que hace posible el cambio sin riesgo es
`tests/test_snapshot_concar.py`: 42 casos con las 41 columnas congeladas celda a celda **antes** del
refactor (hoy son 52). Ese Excel lleva un año importándose en CONCARs de producción; el snapshot es la garantía de
que no cambió ni una celda, y la regla para el futuro: **regenerarlo es una decisión contable con
fuente, nunca un trámite.**

### Lo que lleva cada línea

`LineaDiario` (`asiento/lineas.py`) es el bloque `asiento` del estándar. Además de cuenta, sentido e
importe lleva lo que un driver necesita para traducir **sin adivinar**:

| Campo | Para qué |
|---|---|
| `rol` | `principal`, `igv`, `retencion_4ta`, `tercero`, `detraccion_tercero`, `detraccion`. Un ERP que pida el IGV en su columna encuentra la línea por su rol, no por su cuenta (que la elige cada empresa). |
| `documento.tipo_cp`, `referencia.tipo_cp` | El código SUNAT (Tabla 10). `tipo` conserva la sigla del ERP por compatibilidad. |
| `glosa` | Entera, con su prefijo. El corte lo decide cada ERP. |
| `tasa_igv` | La del comprobante, como texto exacto (`"10.5"`). Redondear es cosa del que solo admite enteros. |
| `detraccion.codigo` | El código SUNAT del bien o servicio, al lado del interno del contribuyente. |

## Capas, api y puertas

Desde la 1.0 el motor se ordena en capas, y cada una solo importa de las de abajo. No es una convención:
`tests/test_capas.py` lo comprueba módulo a módulo, y la lista de excepciones está vacía.

```
 ENTRADA                                                         SALIDA (drivers, por canal)
 ERP en otro lenguaje ─HTTP/OpenConta─► puertas/servidor_http ─┐        ┌─ legacy:      concar · contasis
 Agente de IA ────────MCP────────────► puertas/servidor_mcp ──┼─► api ─► pipeline ─► núcleo ─┼─ tributario:  sire
 Contador ────────────CLI────────────► puertas/cli ───────────┘        └─ intercambio: csv
```

| Capa | Módulos | Qué sabe |
|---|---|---|
| base | `_version`, `_obsoleto`, `_datos`, `errores` | la versión, el aviso de las rutas viejas, los datos empaquetados, la base de los errores |
| núcleo | `modelo`, `catalogos`, `configuracion`, `igv`, `detracciones`, `validar`, `partida_doble`, `asiento`, `pcge`, `lectores`, `comparar_sire` | contabilidad peruana, sin disco, sin red y sin reloj |
| drivers | `drivers/` (`contrato`, `kit`, cada driver) | el formato de un destino, nada de contabilidad |
| pipeline | `pipeline/` (`preparacion`, `lectura`, `seleccion`, `armado`, `salida`, `diagnostico`) | cómo se prepara y se orquesta un mes, escrito una vez |
| api | `api/` (`operaciones`, `tabla`, `documento`, `errores`, `openconta`, `esquemas/`) | lo que una aplicación usa, estable durante la 1.x |
| puertas | `puertas/` (`cli`, `servidor_mcp`, `servidor_http`, `comun`) | un protocolo; solo hablan con la api |
| compat | `_compat/` | las rutas de la 0.10; nadie las importa |

- **El pipeline** es el único dueño de la preparación: del documento al libro y los comprobantes, la configuración
  aplicada hacia un destino con la imputación dentro, las claves previas, la selección de lo que sale, lo que exige el
  destino y lo que no cabe en su formato, la numeración, las líneas con su índice, el cuadre y la huella. `revisar`,
  `diagnosticar`, `generar_asiento` y `exportar` recorren los mismos pasos, cada una hasta donde le toca;
  `generar_asiento` es `exportar` sin escribir el archivo.
- **La api** (`contaperu.api`) habla en documentos `open-accounting`: el documento primero, lo demás por su nombre,
  `driver` sin valor por defecto. Su superficie queda congelada con su firma (`tests/test_superficie_publica.py`), y
  debajo queda el nivel de extensión —`modelo`, `asiento`, `drivers.contrato`, `drivers.kit`…— para quien escribe un
  driver. Cada error hereda de `ErrorContaperu` y lleva una `clave` estable; `api.problema` lo dice como RFC 9457.
- **La tabla de operaciones** (`api.OPERACIONES`) declara de cada operación su entrada (JSON Schema 2020-12, sacada de
  su firma), su salida, su ruta HTTP y su nombre en el MCP. De ella salen las herramientas y recursos del MCP, las
  rutas de la puerta HTTP y **OpenConta**, el contrato en formato OpenAPI 3.1 que se versiona en
  `api/openconta.json`.
- **Las puertas** traducen un protocolo y delegan. Comparten en `puertas/comun.py` los topes y la defensa del `Host`,
  y `tests/test_frontera.py` impide que el núcleo importe una puerta, el SDK del MCP, la red o el reloj. Las tres dan
  el mismo documento y el mismo diagnóstico.
- **Las rutas de la 0.10** (`operaciones`, `generar`, `cli`, `servidor_mcp`, `formato`, `drivers.concar.construir`)
  siguen resolviendo al mismo objeto, con sus firmas, y avisan con `RutaObsoleta` al usarse. Se retiran en la 2.0.
- **El portal** (otro repositorio) usa la api y el nivel de extensión; el `resumen` de cada exportación, que guarda tal
  cual, conserva sus claves.
- **Lo peruano, a la vista** (hito J0): qué módulos importan uno peruano queda congelado en
  `tests/fixtures/capas/acoplamiento_pe.json`, y un acoplamiento nuevo no entra sin verse. Separar la jurisdicción
  (J2-J6) espera un cliente real fuera del Perú.

## Cómo se enchufa un driver

Un driver expone `NOMBRE`, `CANAL`, `FORMATOS`, `OPCIONES`, `nombre()` y **una** forma (`drivers/contrato.py`):

| Forma | Recibe | Para qué |
|---|---|---|
| `linea(c, libro, idx, opciones) -> str` | un comprobante | un registro tributario línea a línea (el SIRE) |
| `desde_comprobantes(libro, comprobantes, config, opciones)` | los comprobantes y la configuración, con la imputación | el registro de un sistema contable que arma el asiento él mismo (CONTASIS) |
| `desde_lineas(libro, lineas, config, opciones, *, indice=())` | las **líneas neutrales**, numeradas y cuadradas, y el índice de cada comprobante | **todo driver de asientos**, CONCAR incluido desde la 1.0 |
| `construir(libro, comprobantes, config, correlativos, opciones)` | los comprobantes | la forma de CONCAR hasta la 0.10; un tercero que la use sigue funcionando con aviso hasta la 2.0 |

Con `desde_lineas` el pipeline arma el asiento, lo numera y exige que cuadre **antes** de llamar al driver; el driver
solo traduce. Si su firma acepta `indice`, recibe además qué tramo de líneas es de qué comprobante y una **cabecera**
con sus hechos (`asiento.indice.Cabecera`: identidad, contraparte, glosa, base, IGV y total en texto exacto), fuera de
las líneas y de la huella. Es lo que permite escribir en cada fila lo que la línea no guarda: CONCAR saca de ahí la
glosa de su columna F y la tasa entera de la AO, que se redondea una sola vez desde el IGV y la base del comprobante.

**El canal dice a quién se entrega** (la familia dice qué se entrega), y el contrato hace cumplir sus reglas:

| Canal | Qué es | Reglas | Drivers |
|---|---|---|---|
| `legacy` | un sistema contable instalado que importa un archivo | lleva cuentas; declara `EXIGE` | concar, contasis; STARSOFT y SISCONT cuando entren |
| `tributario` | un registro que se presenta a SUNAT | forma `linea`, sin cuentas ni configuración | sire |
| `intercambio` | un formato neutral para leer o integrar | forma `desde_lineas` | csv, asiento_neutral |

Cada canal se presenta en uno de los tres grupos de destinos del motor (`contrato.GRUPOS`): `tributario` es **SIRE**,
`legacy` es **Legacy** e `intercambio` es **ERP**.

`api_erp` —escribir el cuerpo de la API de un ERP moderno— queda **reservado** (hito A5): el contrato lo rechaza. Un
driver de terceros sin `CANAL` se registra con un `AvisoDriver` y se trata como `legacy` durante la 1.x.

**El vocabulario dice con qué palabras llegan las líneas** (`VOCABULARIO`, 1.1). `legacy`, el de siempre: siglas,
sub-diarios, correlativos y el documento comodín de la detracción, lo que importan CONCAR y los de su familia.
`neutral`: las líneas del estándar sin nada de eso, por `rol` y código SUNAT. Es el de `asiento_neutral`, la salida para
un ERP nuevo, que parte del estándar en vez de reimplementar el IGV. Un driver neutral es de canal `intercambio`, no
declara claves legacy en su configuración y el núcleo solo le exige la cuenta. La contabilidad es la misma que la de
CONCAR: `tests/test_driver_asiento_neutral.py` compara cuentas, sentidos, importes y roles línea a línea.

Y **declara qué exige** (`EXIGE`): lo que ese ERP no puede importar sin y que el núcleo, si no se lo dicen, deja pasar
—`centro_costo` en las cuentas que lo llevan, `moneda` con código en el destino; en uno de registro, `centro_costo` y
`cuenta_unica`—. La cuenta contable la exige el núcleo a todo driver que lleva cuentas, y la equivalencia del tipo, de
la que sale el sub-diario, a los de asientos. Con eso `diagnosticar` decide si un mes está listo **para ese destino**,
y el pipeline lo hace cumplir antes de armar nada. Lo que su formato no puede llevar —una moneda, un código más largo
que su columna— lo declara en `no_caben`: `diagnosticar` lo dice antes y el pipeline se niega con `NoCabe`, en toda
forma que lleva cuentas.

Y **declara lo que se configura**: las claves de su sección (`CONFIGURACION`) y en qué columnas de su archivo puede ir
un dato (`COLUMNAS_ELEGIBLES`). La configuración se guarda con lo general en la raíz y una sección por sistema, se
valida entera y el núcleo recibe lo general con la sección del destino encima. Un driver solo lee lo que declara, y el
núcleo solo lo general, lo del asiento y `MONEDAS_CODIGO`: lo vigila `tests/test_contrato_drivers.py`. Lo que todos los
drivers comparten para escribir —las opciones, el formato de texto, las celdas y el libro de Excel— está en
`drivers/kit/`.

Se publica de dos maneras:

- **Como paquete propio**, por entry points (`[project.entry-points."contaperu.drivers"]`). El registro lo busca la
  primera vez que se consulta; los de serie ganan ante un nombre repetido y uno que no cumple el contrato se ignora con
  un `AvisoDriver` en vez de tumbar el registro.
- **Dentro del repositorio**, en `drivers/<sistema>/` y en `DE_SERIE`. Para eso hace falta un archivo real que ese ERP
  haya aceptado, salvo en un driver cuyo formato es el propio estándar, como `asiento_neutral`: lo valida su esquema.

Esté donde esté, `tests/test_contrato_drivers.py` lo examina: cumple el contrato, declara su canal y exporta el golden
de compras con el asiento cuadrado.

### STARSOFT: qué se sabe y qué falta

- **Qué se sabe.** STARSOFT importa asientos, y su API lista seis endpoints sin esquema publicado. El contrato v1 ya
  cubre lo que un driver así necesita: canal `legacy`, forma `desde_lineas` con el índice y la cabecera de cada
  comprobante, un cuerpo que no es un Excel y un `no_caben` propio. Lo prueba un driver de mentira,
  `tests/drivers_de_prueba/diario_json.py`, enchufado por entry points.
- **Qué falta.** Un archivo o una respuesta de su API que STARSOFT haya aceptado, y el esquema de su cuerpo; su libro
  «Standar» pediría enmendar `libro.tipo` en el estándar. Hasta entonces no se publica ningún driver ni esqueleto: uno
  dentro del paquete quedaría congelado por SemVer sin haber importado nada.
- **Si se escribe en su API y no en un archivo**, el envío y los reintentos son de la aplicación, no del motor: la
  identidad y la huella de cada comprobante (`_exportacion.comprobantes`) son la clave de idempotencia. Lo que le falte
  a la línea va en la cabecera, no en la huella.

### Lo que queda preparado, sin símbolo público

| Punto | Qué hay en la 1.0 | Hito |
|---|---|---|
| Lectores de terceros | nombre reservado `lectores.contrato` y grupo `contaperu.lectores`: identificar, extraer, deduplicar | B7 |
| El banco | paquete reservado `contaperu/banco/` en la capa núcleo; los conectores, fuera del paquete | D1-D7 |
| Reglas de SUNAT como datos | `_datos.leer_json("datos/sunat/…")`; `catalogos` las cargará sin cambiar sus nombres | C1-C2 |
| CDR y no domiciliados | `lectores/cdr.py` reservado; los roles pueden crecer sin romper un driver | C3, C12 |
| Otra jurisdicción | J0 como test, J1 como efecto de las capas, `jurisdicciones/pe` reservado, `open-accounting` 1.1 para J5 | J0-J6 |
| La API de un ERP moderno | canal `api_erp` reservado y rechazado | A5 |

## La capa para agentes

`diagnosticar` es la operación pensada para que un agente —o una persona con prisa— pregunte **antes**
de exportar y reciba, en una sola respuesta: si el mes está listo y por qué no, qué bloquea y qué avisa
por serie-número, qué falta para el destino (cuenta, centro de costo, tipos sin sigla, monedas,
correlativos, un reparto que no suma la base o que el destino no admite, y lo que no cabe en su formato: la tabla
es `asiento.FALTAS`), qué detracciones esperan constancia, el resumen por contraparte y desde qué correlativo
arranca cada sub-diario. No corrige ni inventa: describe. Está en la fachada, en el MCP y en la CLI, y
no añade ninguna regla contable —reúne comprobaciones que ya existían y las cuenta en vez de lanzarlas.

Desde la 0.8 responde además **para qué destino** (`exige`) y **a quién pedir** lo que falta
(`que_falta[].pedir_a`: `contador` si se resuelve mirando el documento o el plan de cuentas; `sistema`
si es configuración del destino o un dato público que no está en el papel; `proveedor` reservado). Y
cada exportación deja su **huella** (`_exportacion.huella`, `asiento/huella.py`): la misma
exportación repetida lleva la misma, que es lo que permite avisar de que ese contenido ya salió.

Esa es la forma en que crecerá esta capa: **cada pregunta de un agente se responde con reglas que ya
tienen fuente**, nunca con una regla nueva escrita para el agente.

## Lo que no se negocia

1. **Ninguna regla contable sin fuente.** La norma, la resolución o el archivo real que la justifica va
   al lado, en el código. Un refactor mueve reglas; no las escribe.
2. **El Excel de CONCAR validado no cambia.** `test_snapshot_concar.py` lo vigila celda a celda.
3. **Un tipo sin sigla detiene la exportación.** Nunca se inventa una sigla.
4. **Sin red, sin disco, sin estado, sin reloj en el núcleo.** `test_frontera.py` y `conftest.py`.
5. **`Decimal` de punta a punta**, `float` solo en el borde de escritura del archivo.
6. **Nunca datos reales en el repositorio.** Dos RUC seguros: `20131312955` y `20601234567`.
7. **Código y comentarios en español**, porque es el idioma del dominio.

## Hoja de ruta

El orden en que crece el motor, y el dato o el código que destraba cada paso, viven en
[HOJA-DE-RUTA.md](HOJA-DE-RUTA.md): una fase para afinar lo que existe y seis frentes —los drivers de SISCONT y
STARSOFT, la puerta para que cualquier ERP integre el motor, leer y validar más con las reglas oficiales de SUNAT, el
banco como punto de partida del proceso contable, un estándar que mejora siempre y la puerta a otra jurisdicción,
condicionada a un cliente real fuera del Perú—, cada uno con sus hitos y su criterio de salida. Aquí no se repiten. La
investigación y el diseño de cada pieza, ordenados por el ciclo contable y con el de EE. UU. como referencia, están en
[INTEROPERABILIDAD.md](INTEROPERABILIDAD.md), y lo tomado de las APIs de EE. UU., en [REFERENCIAS.md](REFERENCIAS.md).

La idea que la ordena sigue siendo la de esta arquitectura: primero la compatibilidad con los sistemas que ya existen,
después un lenguaje común (`open-accounting`, que crece con casos reales detrás) y, encima, más preguntas de agentes
respondidas con reglas que ya tienen fuente.
