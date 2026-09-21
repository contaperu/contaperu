# ContaPerú — el núcleo contable abierto del Perú (guía del repositorio)

Este archivo es el mapa para trabajar en `contaperu`: qué es, de qué visión sale, cómo está construido, quién lo
consume y qué no se negocia. El detalle vive en los documentos de la raíz (tabla al final); aquí solo la línea que
dice dónde buscarlo.

## Qué es

`contaperu` es **el núcleo contable abierto del Perú**: el estándar de datos `open-accounting`, el motor que lee
comprobantes (el XML de SUNAT, la propuesta del SIRE), los valida, arma el asiento y lo exporta a CONCAR, a CONTASIS, al
SIRE y a un CSV genérico, y un servidor MCP para que un agente de IA lo use.

Parte de una tesis: **la contabilidad automatizada no es un problema organizacional de cada empresa, sino de
arquitectura colectiva** (open source). Por eso cumple dos papeles a la vez: es **la capa que trabaja encima de los
sistemas legacy** (CONCAR y CONTASIS hoy; SISCONT y STARSOFT cuando entren) mientras evolucionan, y es **la base
abierta —estándar y motor— sobre la que se construyen los ERP que vienen**. Sus destinos se agrupan en tres: **SIRE,
legacy y ERP**. Licencia **MIT**; lo mantiene **Global
Procesos AI S.A.C.** (Lima). El repositorio (`github.com/contaperu/contaperu`) es **público**, y el paquete está
**publicado en PyPI** desde el 19-sep-2026: **lo que entra en internet no sale**, tampoco del historial de git, así
que se escribe siempre como lo que es (nada real de nadie, nada de infraestructura ajena a este repo). **Distribuir
sigue siendo publicar**: sacar una versión a PyPI o a GHCR, o abrir la imagen del MCP, pide revisión y el OK
explícito de John, y el trabajo `pypi` de `release.yml` está fuera del camino automático por eso.

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
- **Ampliación de John (15-sep-2026):** ContaPerú ya no es solo la capa sobre los sistemas legacy; también monta las
  bases para los ERP que vienen. «Encima, no en lugar de» sigue valiendo para quien ya tiene su sistema contable, y a
  la vez un ERP nuevo no tiene que reimplementar el IGV ni las detracciones: parte del estándar y del motor. La
  contabilidad automatizada se trata como arquitectura colectiva, no organizacional: un estándar y un motor comunes,
  mejorados entre todos. Es el enfoque que ordena el README, `INTEROPERABILIDAD.md` y `HOJA-DE-RUTA.md`.
- Es una copia y no una importación, a propósito: este repo se abrirá y no puede depender de un archivo del disco de
  nadie. Si la visión cambia, se actualiza esta sección con la fecha.

## Cómo está construido

Por capas, de abajo arriba, que `tests/test_capas.py` hace cumplir: un **núcleo** que sabe contabilidad peruana y nada
más (`modelo`, `lectores`, `validar`, `asiento`, `igv`, `detracciones`, `partida_doble`, `pcge`); **drivers** que
conocen el formato de un destino y nada de contabilidad, cada uno con su canal (`drivers/concar` y `drivers/contasis`
legacy, `drivers/sire` tributario, `drivers/csv` y `drivers/asiento_neutral` intercambio, este con vocabulario neutral para los ERP, y los de terceros por *entry points*, con el contrato de
`drivers/contrato.py` y el kit común de `drivers/kit`); un **pipeline** único (`pipeline/`); la **api** pública
(`contaperu.api`, con la tabla de operaciones y el contrato OpenConta); y tres **puertas** que solo hablan con la api
(`puertas/cli`, `puertas/servidor_mcp`, `puertas/servidor_http`). La 2.0 retiró las rutas de la 0.x. El
asiento nace en las **líneas de diario neutrales** del estándar `open-accounting` y cada ERP es una proyección de ellas.
Todo esto, con sus porqués, en `ARQUITECTURA.md`; el estándar, en `estandar/LEEME.md`; cómo se integra, en
`INTEGRAR.md`.

## Quién lo consume, y el peaje

- **Una aplicación en producción.** Contabilidad Inteligente (`contab-core`, repositorio privado de Global Procesos
  AI) usa el motor como lo usaría cualquier ERP: **fija una versión publicada** (en su `api/MOTOR.txt`, el número y
  el commit del tag) y adopta las nuevas cuando decide, después de leer su Release. Nada de allá lee la carpeta de
  este repo, así que un commit en `main` no la toca. **Romper una firma aquí la rompe el día que adopte esa versión**:
  por eso rige SemVer y lo que se retira avisa durante toda la mayor anterior. Un arreglo del motor es un commit en `main` y
  una versión con su tag; allá, cambiar la versión fijada y desplegar. Su lado del circuito está en
  `contab-core/docs/FRONTERA.md`: cuando el trabajo cruza, se lee primero.
- **Un MCP abierto en producción.** `contaperu-mcp` corre en `https://contaperu.globalprocesos.com/mcp` (Streamable
  HTTP, sin autenticación por diseño: no guarda nada de nadie, y el freno es de recursos). Actualizarlo es subir el
  repo al servidor y reconstruir su contenedor; el procedimiento y sus trampas (el `--dominio` que el SDK exige para
  no responder 421) están en el hub de infraestructura de Global Procesos AI, no aquí.
- **Se corrige aquí, nunca en la app.** La app no lleva copia del motor, y su batería lo vigila.
- **La 2.0 retiró las rutas de la 0.x** (`operaciones`, `generar`, `cli`, `servidor_mcp`, `formato` y
  `drivers.concar.construir`), que solo redirigían. No rompió a nadie: **ninguna versión 0.x llegó a PyPI** —la
  primera publicada es la 1.1.0— y la superficie pública de la 1.0 quedó intacta, lo que demuestra su test al pasar
  sin regenerarse. Antes de etiquetar una versión mayor se publica una pre-release (`vX.Y.ZrcN`) y quien integra la
  prueba en su batería, también con `-W error::contaperu._obsoleto.RutaObsoleta` (`INTEGRAR.md`, «Versiones»).

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
  `open-accounting-X.Y` para el estándar, que avanza con cada cambio aditivo del esquema. **Ninguna de las dos
  versiones puede ser prefijo de la otra** (`"1.0"` lo es de `"1.0.0"`): por eso el estándar 1.0 salió con la
  librería en 1.1.0, y un test lo prohíbe.
- **Un test por regla, y mutaciones cuando la regla es fina**: si al romper una línea ningún test cae, falta el test.
  El snapshot de CONCAR se corre en cada paso; si cambia, cambia a propósito y se dice.

## Cómo se trabaja

- `git pull` antes de empezar: el repo se trabaja desde dos máquinas.
- **Se trabaja directo en `main`, sin PR y sin ramas** (decisión de John, 14-sep-2026): commit y push cuando la
  batería pasa en local, y la CI de cada push a `main` lo confirma. Se puede porque cada consumidor fija una versión,
  así que lo que entra en `main` no le llega a nadie hasta que se etiqueta. La última rama larga fue `motor-v1`, la de
  la 1.0. Un contribuidor de fuera sí abre un PR (`CONTRIBUTING.md`).
- Entorno: `python -m venv .venv` y `pip install -e ".[dev]"` (trae `excel`, `schema`, `mcp`, `http`, `pytest`,
  `httpx` y `openapi-spec-validator`).
- Batería: `pytest` (unos segundos; el snapshot va dentro). Antes de etiquetar, `diagnosticar` y `exportar` sobre un
  caso real en local, solo lectura.
- **Publicar una versión es empujar su tag, y solo eso le llega a quien integra el motor**: un commit en `main` no le
  cambia nada a nadie, porque cada consumidor fija una versión exacta. Antes del tag, `contaperu/_version.py` con la
  versión nueva y en `CHANGELOG.md` su sección `## [X.Y.Z] — fecha` (con «Cómo migrar» si hay algo que adaptar).
  Luego `git tag vX.Y.Z` y `git push origin vX.Y.Z`: `.github/workflows/release.yml` corre la batería en ese commit,
  comprueba que la etiqueta es la versión y crea la Release de GitHub con la rueda, el sdist y `SHA256SUMS`, de donde
  se descarga. Una `vX.Y.ZrcN` sale como pre-release, con las notas de «Sin publicar». **Una Release no se
  reemplaza**: un error se arregla sacando otra versión. PyPI va aparte y a mano, con el OK de John.
- Un driver nuevo pide **un archivo real que ese ERP haya aceptado**: `CONTRIBUTING.md` §«Añadir un driver de
  salida». El contrato (`NOMBRE`, `CANAL`, `FORMATOS`, `OPCIONES`, una forma —`desde_lineas` o `desde_comprobantes`
  para lo nuevo—, `EXIGE`, `VOCABULARIO` —legacy o neutral—, y lo que se configura: `CONFIGURACION` y `COLUMNAS_ELEGIBLES`) lo comprueba
  `drivers.contrato.incumplimientos()`.
- Tras cambiar una operación, un esquema de `contaperu/api/esquemas/` o la versión: `python
  herramientas/generar_openconta.py`. La batería falla si `contaperu/api/openconta.json` no está al día.
- Se planifica y se ejecuta por partes, con el OK de John entre cada una.

## Los documentos

| Documento | Qué responde |
|---|---|
| `README.md` | La portada, para contadores y para quien integra: la tesis de la arquitectura colectiva y qué resuelve en palabras de contador; cómo funciona, con los destinos en tres grupos (SIRE, legacy y ERP); el motor por dentro, y las puertas y la API pública, con sus diagramas (`diagramas/`); un glosario, qué sabe hacer y qué no, estado, cómo aportar sin programar, instalar y las puertas, y las palabras clave con las que se encuentra el repositorio |
| `ARQUITECTURA.md` | Las capas, el flujo de un comprobante, la línea neutral, la api y las puertas, cómo se enchufa un driver (contrato v1, canales, STARSOFT), lo que queda preparado, lo que no se negocia |
| `INTEGRAR.md` | Cómo integrar el motor en un ERP: qué puerta elegir, la librería, la CLI por lotes, HTTP con OpenConta, el MCP, un driver propio y lo que promete la 2.x; sus ejemplos se ejecutan en la batería |
| `CONTRIBUTING.md` | La regla que manda (ninguna regla sin fuente), nunca datos reales, cómo añadir un driver, estilo, antes de un PR |
| `estandar/LEEME.md` | El estándar `open-accounting`: sus bloques, sus reglas, la detracción en dos tiempos, las anotaciones del motor, los nombres reservados, su versionado |
| `REFERENCIAS.md` | Lo que se tomó (y lo que no) de QuickBooks, Xero y las APIs unificadas de EE. UU.; de aquí salió la 0.8.0 |
| `API-DE-REGISTRO.md` | El escalón de antes del asiento: cómo se manda una compra o una venta por API. La de STARSOFT Gold como punto de partida, cómo lo resuelven QuickBooks, Xero, Business Central, NetSuite, Intacct y las unificadas, qué enseñan EN 16931 y Peppol, y el borrador del JSON universal: el cuerpo de la llamada **es** el documento del estándar, con `imputaciones` dentro |
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
- **El catálogo completo de detracciones** (`contaperu/datos/sunat/detracciones.json`): la tabla del motor trae los 14
  códigos que ya se reconocían; los demás del Catálogo 54 entran con los apéndices vigentes del SPOT como fuente. El ERP
  que integra el motor puede sumar o sobreescribir mientras tanto (`detraccion_tasas`, `detraccion_nombres`).
- **Equivalencias del PCGE 2026**: con la cita del artículo al lado de cada mapeo; el cargador rechaza un mapeo sin
  fuente.
- **El plazo de anotación en compras** (`validar.PLAZO_ANOTACION_MESES`): hoy 12 meses (Ley 29215, art. 2); el
  D.Leg. 1669 lo baja a 0/2/3 meses el día que SUNAT publique la resolución que lo pone en vigencia.
