# ContaPerú — el núcleo contable abierto del Perú (guía del repositorio)

Este archivo es el mapa para trabajar en `contaperu`: qué es, de qué visión sale, cómo está construido, quién lo
consume y qué no se negocia. El detalle vive en los documentos de la raíz (tabla al final); aquí solo la línea que
dice dónde buscarlo.

## Qué es

`contaperu` es **el núcleo contable abierto del Perú**: el estándar de datos `open-accounting`, el motor que lee
comprobantes (el XML de SUNAT, la propuesta del SIRE), los valida, arma el asiento y lo exporta a CONCAR, a CONTASIS, al
SIRE y a un CSV genérico, y un servidor MCP para que un agente de IA lo use. Licencia **MIT**; lo mantiene **Global
Procesos AI S.A.C.** (Lima). El repositorio (`github.com/contaperu/contaperu`) está **privado por ahora** y se abrirá
cuando John lo decida: **lo que entra en internet no sale**, tampoco del historial de git, así que se escribe desde hoy
como si ya fuera público (nada real de nadie, nada de infraestructura ajena a este repo). **Distribuir es publicar**:
subirlo a PyPI o a GHCR, o abrir la imagen del MCP, pide revisión y el OK explícito de John.

## De qué visión sale (copia del `VISION.md` de Global Procesos AI, 13-sep-2026)

- **Misión:** devolverle a las personas el tiempo que hoy se les va en trabajo repetitivo, con automatización e IA al
  alcance de cualquier empresa, **montadas encima de los sistemas que ya usan**.
- Los principios que gobiernan este repo: **encima, no en lugar de** (nadie cambia de sistema contable: CONCAR se
  queda y el motor le quita la digitación); **resultados, no tecnología**; **solo se anuncia lo que ya está en
  producción**; **el conocimiento se queda en casa del cliente** (por eso el núcleo es abierto: quien lo use no
  depende de nadie).
- Su sitio en la hoja de ruta: es **el motor de la línea 2**, la capa contable inteligente sobre CONCAR o cualquier
  sistema (el producto Contabilidad Inteligente), cuyo MVP es cargar comprobantes → revisar → exportar a un clic el
  Excel de CONCAR o de CONTASIS y/o el TXT del SIRE. Regla vigente del producto: **se afina lo que existe, no se
  añaden módulos**; en el motor eso significa que cada regla entra con su fuente y su caso real, no por si acaso.
- Es una copia y no una importación, a propósito: este repo se abrirá y no puede depender de un archivo del disco de
  nadie. Si la visión cambia, se actualiza esta sección con la fecha.

## Cómo está construido

Tres niveles, de abajo arriba: un **núcleo** que sabe contabilidad peruana y nada más (`modelo`, `lectores`,
`validar`, `asiento`, `igv`, `detracciones`, `partida_doble`, `pcge`); **drivers** que conocen el formato de un
destino y nada de contabilidad (`drivers/concar`, `drivers/sire`, `drivers/csv`, `drivers/contasis`, y los de terceros por *entry
points*, con el contrato de `drivers/contrato.py`); y encima la capa para **agentes** (`operaciones`,
`servidor_mcp`, `cli`; `diagnosticar` es su primera pregunta). El asiento nace en las **líneas de diario neutrales**
del estándar `open-accounting` y cada ERP es una proyección de ellas: un driver nuevo solo traduce vocabulario. Todo esto,
con sus porqués, en `ARQUITECTURA.md`; el estándar, en `estandar/LEEME.md`.

## Quién lo consume, y el peaje

- **Una aplicación en producción.** Contabilidad Inteligente (`contab-core`, repositorio privado de Global Procesos
  AI) instala el motor como paquete —un wheel construido en su propio despliegue, porque este repo es privado— y
  declara la versión mínima que necesita (`MOTOR_MINIMO`, en su batería). **Romper una firma aquí rompe una
  aplicación en producción.** Un arreglo del motor son dos repositorios: se corrige, se prueba y se etiqueta aquí; se
  sube la versión mínima y se despliega allá. El circuito completo está en `contab-core/docs/FRONTERA.md`, y qué
  símbolos usa la app, en `contab-core/api/CLAUDE.md`: cuando el trabajo cruza, se leen primero.
- **Un MCP abierto en producción.** `contaperu-mcp` corre en `https://contaperu.globalprocesos.com/mcp` (Streamable
  HTTP, sin autenticación por diseño: no guarda nada de nadie, y el freno es de recursos). Actualizarlo es subir el
  repo al servidor y reconstruir su contenedor; el procedimiento y sus trampas (el `--dominio` que el SDK exige para
  no responder 421) están en el hub de infraestructura de Global Procesos AI, no aquí.
- **Se corrige aquí, nunca en la app.** La app no lleva copia del motor, y su batería lo vigila.

## Lo que no se negocia

Las siete reglas completas están en `ARQUITECTURA.md` §«Lo que no se negocia»; en una línea cada una:

1. **Ninguna regla contable sin fuente.** La norma, la resolución o el archivo real va al lado, en el código. Un
   refactor mueve reglas; no las escribe.
2. **El Excel de CONCAR validado no cambia.** `tests/test_snapshot_concar.py` lo vigila celda a celda (52 casos).
3. **Un tipo sin sigla detiene la exportación.** Nunca se inventa una sigla.
4. **Sin red, sin disco, sin estado, sin reloj en el núcleo** (`tests/test_frontera.py`): la fecha la pone quien llama.
5. **`Decimal` de punta a punta**, `float` solo en el borde de escritura del archivo.
6. **Nunca datos reales en el repositorio.** RUC seguros: `20131312955` y `20601234567`. Un archivo real se usa solo
   en local, de lectura, y vive en `privado/` (que `.gitignore` bloquea).
7. **Código, comentarios, commits y documentación en español**: es el idioma del dominio.

Y las de trabajo, que no están en `ARQUITECTURA.md`:

- **Commits en prosa, sin prefijos**, que cuenten la decisión, terminando con la línea `Co-Authored-By` del modelo que
  los hizo (`Co-Authored-By: Claude <modelo> <noreply@anthropic.com>`).
- **La versión vive en `contaperu/_version.py`**: `__version__` del paquete y `OPEN_ACCOUNTING` del estándar son dos
  relojes distintos. `CHANGELOG.md` explica cada versión con su porqué, y **un cambio de comportamiento se anuncia
  como tal** (quien use el motor sin la app lo nota). Dos series de tags: `vX.Y.Z` para el paquete y
  `open-accounting-0.X` para el estándar, que avanza con cada cambio aditivo del esquema.
- **Un test por regla, y mutaciones cuando la regla es fina**: si al romper una línea ningún test cae, falta el test.
  El snapshot de CONCAR se corre en cada paso; si cambia, cambia a propósito y se dice.

## Cómo se trabaja

- `git pull` antes de empezar: el repo se trabaja desde dos máquinas.
- Entorno: `python -m venv .venv` y `pip install -e ".[dev]"` (trae `excel`, `schema`, `mcp` y `pytest`).
- Batería: `pytest` (unos segundos; el snapshot va dentro). Antes de etiquetar, `diagnosticar` y `exportar` sobre un
  caso real en local, solo lectura.
- Un driver nuevo pide **un archivo real que ese ERP haya aceptado**: `CONTRIBUTING.md` §«Añadir un driver de
  salida». El contrato (`NOMBRE`, `FORMATOS`, `OPCIONES`, una de las cuatro formas, `EXIGE`, y lo que se
  configura: `CONFIGURACION` y `COLUMNAS_ELEGIBLES`) lo comprueba `drivers.contrato.incumplimientos()`.
- Se planifica y se ejecuta por partes, con el OK de John entre cada una.

## Los documentos

| Documento | Qué responde |
|---|---|
| `README.md` | La portada: el problema, instalar, un ejemplo de diez líneas, el MCP, qué sabe hacer y qué no, estado |
| `ARQUITECTURA.md` | Los tres niveles, el flujo de un comprobante, la línea neutral, cómo se enchufa un driver, lo que no se negocia |
| `CONTRIBUTING.md` | La regla que manda (ninguna regla sin fuente), nunca datos reales, cómo añadir un driver, estilo, antes de un PR |
| `estandar/LEEME.md` | El estándar `open-accounting`: sus bloques, sus reglas, la detracción en dos tiempos, las anotaciones del motor, los nombres reservados, su versionado |
| `REFERENCIAS.md` | Lo que se tomó (y lo que no) de QuickBooks, Xero y las APIs unificadas de EE. UU.; de aquí salió la 0.8.0 |
| `INTEROPERABILIDAD.md` | Su continuación, y toda la investigación en un solo lugar, en cuatro partes: el marco (el ciclo de EE. UU. comparado con el peruano); las etapas del ciclo (recibir la factura, validar, asentar, exportar al destino, pagar y conciliar, declarar); lo transversal (modelos de referencia, el estándar, la arquitectura con MCP, otra jurisdicción); y el inventario de propuestas y descartes, con sus fuentes. Cada propuesta cita su hito y espera su caso real |
| `HOJA-DE-RUTA.md` | En qué orden crece el motor: qué sigue, la Fase 0 y los seis frentes (drivers legacy, puerta para cualquier ERP, leer y validar más, el banco, el estándar y otra jurisdicción), hitos con criterio de salida y el dato que destraba cada uno. Solo orden: cada hito cita su propuesta de `INTEROPERABILIDAD.md` por número |
| `CHANGELOG.md` | Cada versión con su porqué; la bitácora del motor vive aquí y en ningún otro sitio |
| `SECURITY.md` · `CODE_OF_CONDUCT.md` | Cómo reportar una vulnerabilidad; cómo se convive en el proyecto |

## Pendiente que depende de datos, no de código

El orden completo y qué destraba cada hito, en `HOJA-DE-RUTA.md` (§5, «Lo que hay que conseguir»). Aquí, lo que ya
espera un archivo o una norma:

- Drivers de **SISCONT y STARSOFT**: cada uno exige un archivo real que ese sistema haya importado, como pasó con
  **CONTASIS**, aceptado el 13-sep-2026 al importar los archivos que genera su driver.
- **Conciliación de constancias de detracción**: un archivo real del Banco de la Nación.
- **Equivalencias del PCGE 2026**: con la cita del artículo al lado de cada mapeo; el cargador rechaza un mapeo sin
  fuente.
- **El plazo de anotación en compras** (`validar.PLAZO_ANOTACION_MESES`): hoy 12 meses (Ley 29215, art. 2); el
  D.Leg. 1669 lo baja a 0/2/3 meses el día que SUNAT publique la resolución que lo pone en vigencia.
