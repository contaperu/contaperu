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
│      sire (TXT) · concar (Excel) · csv · los de terceros    │
│      cada uno traduce vocabulario; ninguno decide contabilidad│
├─────────────────────────────────────────────────────────────┤
│  1 · NÚCLEO                                                 │
│      modelo · lectores · validación · asiento · detracciones│
│      IGV · partida doble · PCGE · el estándar `pe-ledger`   │
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
XML UBL / TXT del SIRE / JSON pe-ledger
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

Aparte va el SIRE: es un **registro tributario**, no un asiento. Se escribe desde el comprobante
(`linea(c, libro, idx, op)`), una línea por documento, y por eso su driver no pasa por el motor.

### La decisión que lo ordena todo: la línea neutral es la fuente

Hasta la 0.6 el asiento nacía en las columnas del Excel de CONCAR (`'A'..'AO'`) y la línea neutral
se sacaba después releyéndolas. Funcionaba, pero la línea «neutral» heredaba el vocabulario de un
ERP —la sigla `FT` en vez del código SUNAT `01`, la glosa cortada a 30 caracteres, la tasa del IGV
redondeada a entero— y un segundo driver de asientos habría tenido que reinterpretar columnas de
CONCAR para escribir las suyas.

Desde la 0.7 la dirección está invertida. `asiento/motor.py` arma las líneas en el vocabulario de
`pe-ledger` y CONCAR es una proyección más. Lo que hace posible el cambio sin riesgo es
`tests/test_snapshot_concar.py`: 42 casos con las 41 columnas congeladas celda a celda **antes** del
refactor. Ese Excel lleva un año importándose en CONCARs de producción; el snapshot es la garantía de
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

## Núcleo, fachada y puertas

```
   cli.py ─────────┐                  ┌───────── servidor_mcp.py
   (argv, stdout)  │                  │          (JSON-RPC, adjuntos)
                   ▼                  ▼
              operaciones.py  ── la FACHADA: dict entra, dict sale
                   │
                   ▼
                NÚCLEO  (no sabe que las puertas existen)
```

- **La fachada** (`operaciones.py`) habla en documentos `pe-ledger`: `leer_xml`,
  `leer_propuesta_sire`, `revisar`, `generar_asiento`, `exportar`, `diagnosticar`, `cuadrar`,
  `adaptar_pcge`. Todas puras: sin disco, sin red, sin estado. Los bytes salen en base64 porque un
  JSON no sabe llevar bytes.
- **Las puertas** son adaptadores delgados: traducen un protocolo y delegan. La CLI escribe archivos;
  el MCP devuelve adjuntos. Ninguna reimplementa trabajo, y `tests/test_frontera.py` lo convierte en
  algo que se rompe solo: el núcleo no puede importar una puerta, ni el SDK del protocolo, ni salir a
  la red, ni mirar el reloj; y cada puerta tiene que pasar por la fachada.
- **El portal** (otro repositorio) es una tercera puerta que importa `contaperu.asiento` y
  `contaperu.operaciones`. Por eso `asiento.asiento()` conserva su firma aunque ya no contenga la
  lógica: es API pública.

## Cómo se enchufa un driver

Un driver expone `NOMBRE`, `FORMATOS`, `OPCIONES`, `nombre()` y **una** de tres formas
(`drivers/contrato.py`):

| Forma | Recibe | Para qué |
|---|---|---|
| `linea(c, libro, idx, op) -> str` | un comprobante | un registro tributario línea a línea (el SIRE) |
| `construir(libro, comprobantes, contab, correlativos, op)` | los comprobantes | un archivo armado desde el comprobante (CONCAR, por historia) |
| `desde_lineas(libro, lineas, contab, op)` | las **líneas neutrales**, ya numeradas y cuadradas | **un driver de asientos nuevo** |

Con `desde_lineas` el núcleo arma el asiento, lo numera y exige que cuadre **antes** de llamar al
driver; el driver solo traduce. Es la forma que hace que un driver de SISCONT o STARSOFT no pueda
equivocarse en una cuenta ni en un sentido, porque nunca los decide.

Se publica de dos maneras:

- **Como paquete propio**, por entry points (`[project.entry-points."contaperu.drivers"]`). El
  registro (`drivers/__init__.py`) lo carga al importarse; los de serie ganan ante un nombre repetido
  y uno que no cumple el contrato se ignora con un `AvisoDriver` en vez de tumbar el registro. Así la
  comunidad mantiene el driver de su ERP a su ritmo.
- **Dentro del repositorio**, en `drivers/<sistema>/` y en `DE_SERIE`. Para eso hace falta un archivo
  real que ese ERP haya aceptado: un driver que nadie ha importado no se publica.

Esté donde esté, `tests/test_contrato_drivers.py` lo examina: cumple el contrato y exporta el golden
de compras con el asiento cuadrado.

## La capa para agentes

`diagnosticar` es la operación pensada para que un agente —o una persona con prisa— pregunte **antes**
de exportar y reciba, en una sola respuesta: si el mes está listo y por qué no, qué bloquea y qué avisa
por serie-número, qué falta para el destino (cuenta, centro de costo, tipos sin equivalencia, monedas,
correlativos), qué detracciones esperan constancia, el resumen por contraparte y desde qué correlativo
arranca cada sub-diario. No corrige ni inventa: describe. Está en la fachada, en el MCP y en la CLI, y
no añade ninguna regla contable —reúne comprobaciones que ya existían y las cuenta en vez de lanzarlas.

Esa es la forma en que crecerá esta capa: **cada pregunta de un agente se responde con reglas que ya
tienen fuente**, nunca con una regla nueva escrita para el agente.

## Lo que no se negocia

1. **Ninguna regla contable sin fuente.** La norma, la resolución o el archivo real que la justifica va
   al lado, en el código. Un refactor mueve reglas; no las escribe.
2. **El Excel de CONCAR validado no cambia.** `test_snapshot_concar.py` lo vigila celda a celda.
3. **Un tipo sin equivalencia detiene la exportación.** Nunca se inventa una sigla.
4. **Sin red, sin disco, sin estado, sin reloj en el núcleo.** `test_frontera.py` y `conftest.py`.
5. **`Decimal` de punta a punta**, `float` solo en el borde de escritura del archivo.
6. **Nunca datos reales en el repositorio.** Dos RUC seguros: `20131312955` y `20601234567`.
7. **Código y comentarios en español**, porque es el idioma del dominio.

## Hoja de ruta

- **Nivel 1 — compatibilidad con lo que existe** (prioridad hoy): CONCAR y SIRE listos; SISCONT,
  STARSOFT y CONTASIS abiertos a la comunidad, por entry points, con un archivo real cada uno.
- **Nivel 2 — un lenguaje común**: cuando aparezcan más aplicaciones peruanas especializadas
  (compras, tesorería, logística), todas necesitarán representar facturas, proveedores, centros de
  costo, impuestos y asientos. `pe-ledger` ya es ese idioma intermedio; crecerá con casos reales
  detrás, no por si acaso.
- **Nivel 3 — agentes**: más preguntas respondidas desde el núcleo (`diagnosticar` es la primera),
  la conciliación de constancias de detracción cuando haya un archivo real del Banco de la Nación, y
  las equivalencias del PCGE 2026 con la cita del artículo al lado de cada mapeo.
