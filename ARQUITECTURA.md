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

### La decisión que lo ordena todo: la línea neutral es la fuente

Hasta la 0.6 el asiento nacía en las columnas del Excel de CONCAR (`'A'..'AO'`) y la línea neutral
se sacaba después releyéndolas. Funcionaba, pero la línea «neutral» heredaba el vocabulario de un
ERP —la sigla `FT` en vez del código SUNAT `01`, la glosa cortada a 30 caracteres, la tasa del IGV
redondeada a entero— y un segundo driver de asientos habría tenido que reinterpretar columnas de
CONCAR para escribir las suyas.

Desde la 0.7 la dirección está invertida. `asiento/motor.py` arma las líneas en el vocabulario de
`open-accounting` y CONCAR es una proyección más. Lo que hace posible el cambio sin riesgo es
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

- **La fachada** (`operaciones.py`) habla en documentos `open-accounting`: `leer_xml`,
  `leer_propuesta_sire`, `revisar`, `generar_asiento`, `exportar`, `diagnosticar`, `cuadrar`,
  `adaptar_pcge`. Todas puras: sin disco, sin red, sin estado. Los bytes salen en base64 porque un
  JSON no sabe llevar bytes.
- **Las puertas** son adaptadores delgados: traducen un protocolo y delegan. La CLI escribe archivos;
  el MCP devuelve adjuntos. Ninguna reimplementa trabajo, y `tests/test_frontera.py` lo convierte en
  algo que se rompe solo: el núcleo no puede importar una puerta, ni el SDK del protocolo, ni salir a
  la red, ni mirar el reloj; y cada puerta tiene que pasar por la fachada.
- **El portal** (otro repositorio) es una tercera puerta que importa `contaperu.asiento` y
  `contaperu.operaciones`. Desde la 0.10 el núcleo no conoce ningún formato: las columnas de CONCAR
  salen de su driver (`drivers.concar.filas_de_comprobante`), igual que las de CONTASIS.

## Cómo se enchufa un driver

Un driver expone `NOMBRE`, `FORMATOS`, `OPCIONES`, `nombre()` y **una** de cuatro formas,
de dos familias (`drivers/contrato.py`):

| Forma | Recibe | Para qué |
|---|---|---|
| `linea(c, libro, idx, opciones) -> str` | un comprobante | un registro tributario línea a línea (el SIRE) |
| `desde_comprobantes(libro, comprobantes, config, opciones)` | los comprobantes y la configuración, con la imputación de cada documento | el registro de un sistema contable que arma el asiento él mismo (CONTASIS) |
| `construir(libro, comprobantes, config, correlativos, opciones)` | los comprobantes | un archivo armado desde el comprobante (CONCAR, por historia) |
| `desde_lineas(libro, lineas, config, opciones)` | las **líneas neutrales**, ya numeradas y cuadradas | **un driver de asientos nuevo** |

Con `desde_lineas` el núcleo arma el asiento, lo numera y exige que cuadre **antes** de llamar al
driver; el driver solo traduce. Es la forma que hace que un driver de SISCONT o STARSOFT no pueda
equivocarse en una cuenta ni en un sentido, porque nunca los decide.

Con `desde_comprobantes` no hay asiento que armar ni que numerar, pero sí cuentas que llevar: el núcleo exige la
cuenta de cada documento antes de llamar al driver, y el driver la lee de la misma resolución que usa el asiento.
Tampoco decide ninguna. Lo que su formato no puede llevar —una moneda, un código más largo que su columna— lo
declara en `no_caben`: `diagnosticar` lo dice antes y el núcleo se niega antes de llamarlo.

Y **declara qué exige** (`EXIGE`, desde la 0.8): lo que ese ERP no puede importar sin y que el núcleo,
si no se lo dicen, deja pasar —`centro_costo` en las cuentas que lo llevan, `moneda` con código en el
destino—. La cuenta contable la exige el núcleo a todo driver que lleva cuentas, y la equivalencia del
tipo, de la que sale el sub-diario, a los de asientos (uno de registro puede exigir el centro, no la
moneda). Con eso
`diagnosticar` decide si un mes está listo **para ese destino** (el CSV no bloquea por centro; CONCAR
sí) y el núcleo lo hace cumplir antes de armar nada (`asiento.exigir_requisitos`). La idea es la de
Codat `options` y Merge `/meta` (`REFERENCIAS.md`): el destino dice qué necesita antes de escribir.

Y **declara lo que se configura** (desde la 0.10): las claves de su sección (`CONFIGURACION`) y en qué columnas de su
archivo puede ir un dato (`COLUMNAS_ELEGIBLES`). La configuración se guarda con lo general en la raíz y una sección
por sistema; `operaciones.config_aplicada(configuracion, driver)` la valida entera y le entrega al núcleo lo general
con la sección del destino encima. Así el motor sirve a cualquier aplicación: cada una guarda la configuración de sus
empresas y le pide al motor qué se configura (`contaperu://configuracion`), en vez de copiarlo. Un driver solo lee lo
que declara, y el núcleo solo lo general y lo del asiento: lo vigila `tests/test_contrato_drivers.py`.

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
por serie-número, qué falta para el destino (cuenta, centro de costo, tipos sin sigla, monedas,
correlativos), qué detracciones esperan constancia, el resumen por contraparte y desde qué correlativo
arranca cada sub-diario. No corrige ni inventa: describe. Está en la fachada, en el MCP y en la CLI, y
no añade ninguna regla contable —reúne comprobaciones que ya existían y las cuenta en vez de lanzarlas.

Desde la 0.8 responde además **para qué destino** (`exige`) y **a quién pedir** lo que falta
(`que_falta[].pedir_a`: `contador` si se resuelve mirando el documento o el plan de cuentas; `sistema`
si es configuración del destino o un dato público que no está en el papel; `proveedor` reservado). Y
cada exportación deja su **huella** (`_exportacion.huella`, `asiento/huella.py`): la misma tanda
exportada dos veces lleva la misma, que es lo que permite avisar de que ese contenido ya salió.

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

- **Nivel 1 — compatibilidad con lo que existe** (prioridad hoy): CONCAR, SIRE y CONTASIS
  listos; SISCONT y STARSOFT abiertos a la comunidad, por entry points, con un
  archivo real cada uno.
- **Nivel 2 — un lenguaje común**: cuando aparezcan más aplicaciones peruanas especializadas
  (compras, tesorería, logística), todas necesitarán representar facturas, proveedores, centros de
  costo, impuestos y asientos. `open-accounting` ya es ese idioma intermedio; crecerá con casos reales
  detrás, no por si acaso. Lo que las APIs unificadas de EE. UU. (Merge, Codat, Rutter, Apideck)
  enseñan sobre ese idioma, y los campos opcionales que de ahí se proponen, en
  [REFERENCIAS.md](REFERENCIAS.md).
- **Nivel 3 — agentes**: más preguntas respondidas desde el núcleo (`diagnosticar` es la primera),
  la conciliación de constancias de detracción cuando haya un archivo real del Banco de la Nación, y
  las equivalencias del PCGE 2026 con la cita del artículo al lado de cada mapeo.
