# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
El versionado del **paquete** es [SemVer](https://semver.org/lang/es/); el del **estándar
`pe-ledger`** va por su cuenta y se documenta en `estandar/LEEME.md`.

## [Sin publicar]

### Añadido
- **`REFERENCIAS.md`**: cómo modelan el asiento, los impuestos, las dimensiones, la escritura y la
  idempotencia la API de QuickBooks Online, la de Xero y las APIs unificadas de EE. UU. (Merge, Codat,
  Rutter, Apideck), comparado campo a campo con `pe-ledger`; qué no se toma y por qué; y una propuesta
  de campos **opcionales** para el estándar (`id_externo`, `dimensiones`, `estado` de la línea,
  `_exportacion.huella`, `faltantes[].pedir_a`, `EXIGE` en el contrato de driver), pendiente de decidir.
  Solo documentación: ni el código ni el esquema cambian.

## [0.7.0] — 2026-09-11

Infraestructura para escalar: el núcleo deja de estar atado al formato de un ERP, un driver nuevo se
enchufa sin tocar el repositorio, y un agente puede preguntar qué falta antes de exportar. **Ninguna
regla contable cambia**: el Excel de CONCAR sale idéntico celda a celda (lo prueba un snapshot de 42
casos congelado antes del refactor).

### Cambiado
- **El asiento nace en líneas neutrales; CONCAR pasa a ser una proyección.** La lógica contable sale
  de `asiento.construir.asiento()` a `asiento/motor.py` (`asiento_neutral`, `lineas_del_libro`), que
  arma las líneas de `pe-ledger` directamente; el Excel se proyecta desde ellas en
  `drivers/concar/proyeccion.py`. Hasta ahora la línea «neutral» se sacaba releyendo las columnas de
  CONCAR y heredaba su vocabulario. `asiento()` conserva su firma y su salida: es API pública.
- **La línea neutral dice más**: `rol` (`principal`, `igv`, `retencion_4ta`, `tercero`,
  `detraccion_tercero`, `detraccion`), `documento.tipo_cp` y `referencia.tipo_cp` (el código SUNAT,
  al lado de la sigla del ERP), `detraccion.codigo`, la glosa **entera** (el corte a 40/30 es de
  CONCAR) y `tasa_igv` como texto exacto (`"10.5"`; redondear es cosa del ERP). Son campos opcionales
  añadidos: el estándar sigue en `pe-ledger` 0.2.
- **El registro de drivers carga los de terceros** por entry points (grupo `contaperu.drivers`). Los de
  serie ganan ante un nombre repetido; uno que no cumple el contrato o revienta al importarse se ignora
  con un `AvisoDriver` en vez de tumbar el registro. `drivers.DRIVERS` se muta en sitio, así que quien
  ya lo importó ve lo mismo; `drivers.recargar()` vuelve a buscar.
- **El driver CSV pasa a la forma `desde_lineas`** y sirve de plantilla; conserva `construir` por
  compatibilidad.
- **La CLI llega a todos los drivers.** `desde-json --driver csv|concar` reventaba con un `TypeError`
  porque nunca pasaba la configuración ni los correlativos (venía así desde antes); ahora entran por
  `--config` y los correlativos arrancan en 1, como en `operaciones.exportar`. Lo que falte se dice y
  remite a `contaperu diagnosticar`. Los JSON de entrada se leen con `utf-8-sig`: el Bloc de notas y
  `Out-File` de PowerShell escriben BOM.

### Añadido
- **`operaciones.diagnosticar`**, herramienta MCP `diagnosticar` y comando `contaperu diagnosticar`:
  en una sola respuesta, si el mes está listo y por qué no, bloqueantes y avisos por serie-número, qué
  falta para el destino (cuenta, centro de costo, tipos sin equivalencia, monedas, sub-diarios sin
  correlativo), detracciones sin constancia, resumen por contraparte y desde qué correlativo arranca
  cada sub-diario. No añade reglas: reúne comprobaciones que ya existían y las describe en vez de
  lanzarlas. Deja fijado que el centro de costo lo **avisa** el diagnóstico pero el driver de CONCAR
  sigue sin pararlo: cambiar eso es una decisión aparte.
- **`drivers/contrato.py`**: las tres formas de driver (`linea`, `construir` y la nueva
  `desde_lineas`, que solo ve líneas neutrales ya numeradas y cuadradas), `incumplimientos()` para
  decir qué le falta a uno, y `tests/test_contrato_drivers.py`, el examen que pasa cualquier driver
  registrado.
- **`tests/test_snapshot_concar.py`**: 42 casos con las 41 columnas del Excel congeladas celda a celda
  (y las líneas neutrales aparte). Regenerarlo es una decisión contable con fuente, no un trámite.
- **`ARQUITECTURA.md`**: los tres niveles, el flujo comprobante → línea neutral → proyección, núcleo /
  fachada / puertas, cómo se enchufa un driver y lo que no se negocia.

### Corregido
- El README decía nueve herramientas y tres recursos en el MCP; eran diez y cuatro (faltaban
  `buscar_cuenta_pcge` y el catálogo del PCGE 2026). Ahora son once y cuatro.

## [0.6.0] — 2026-09-11

### Cambiado
- **La base y el IGV son siempre netos; los descuentos ya no entran en el total** (estándar `pe-ledger` 0.2).
  `dscto_base`/`dscto_igv` pasan a decir qué parte de la base y del IGV informa el SIRE en sus campos 16 y 18.
  Una nota de crédito de descuento global —la FC01-45 del contraste de agosto— llegaba distinta por cada
  puerta, y las dos se bloqueaban con `TOTAL_NO_CUADRA`: del XML, con la base **y** el descuento, y el TXT del
  SIRE la contaba dos veces; de la propuesta de SUNAT, con base e IGV en cero, así que el asiento de CONCAR
  perdía la línea del IGV y el portal la pintaba «Inafecto». Ahora las dos dan base 9985.36, IGV 1797.36 y el
  descuento igual, validan, y el TXT la escribe como SUNAT (15 = 0.00, 16 = −9985.36).
- El TXT del SIRE escribe el campo 15 como `signo · base + descuento` (y el 17 igual): el total es la suma con
  signo de los campos, como en la exportación real de SUNAT. El lector de la propuesta hace lo inverso, y
  rechaza un descuento en positivo.
- El lector XML solo llena el descuento en una NC de ventas cuyo descuento de documento es todo su importe;
  en facturas, notas de débito y compras queda en cero, porque la base del XML ya es neta. Cada descuento de
  documento queda anotado en `datos_raw["descuentos_globales"]`.
- `igv.aplicar_igv` devuelve también los dos descuentos: una nota entera como descuento sigue entera.

### Añadido
- `igv.aplicar_total()`: el total que dice el papel sin tocar el IGV; lo absorbe el importe principal (la
  regla de la celda «Total» del portal, que hasta hoy calculaba el navegador).
- Error `DSCTO_MAYOR_QUE_BASE`.

## [0.5.0] — 2026-09-10

### Cambiado
- **El monto de la detracción tiene una sola cifra: la del motor.** El cálculo que vivía privado en el
  asiento (total × tasa en soles enteros, con el T.C. si es en dólares) es ahora `detracciones.monto()`, y
  lo usan el asiento y `detracciones.normalizar()`, que desde hoy anota en cada detracción su `monto` y la
  tasa de la tabla para ese código (`tasa_tabla`). Hasta ahora el portal enseñaba otra cifra —calculada en
  el navegador con decimales, o la que la IA leyó del PDF— que no siempre era la que iba a CONCAR.
  `normalizar()` no toca la tasa del comprobante: la huella del asiento depende de ella.

### Añadido
- `detracciones.monto()`, `detracciones.tasa()` y `detracciones.tasa_de_tabla()`.
- **Aviso `DETRACCION_TASA_DISTINTA`** cuando la tasa con la que va a salir la detracción no es la de la
  tabla del contribuyente para ese código: el caso de una IA que lee un 10 % en un código del 12 %. Aviso
  y no error, porque la del comprobante puede ser legítima.

## [0.4.0] — 2026-09-10

### Cambiado
- **La tasa del IGV ya no se supone en ninguna parte: sale de cada comprobante** (decisión de John,
  10-sep-2026: puede ser 18, 10.5 o 0). `asiento.tasa_igv()` —la columna AO del Excel de CONCAR— es
  ahora la tasa del comprobante (IGV ÷ base) redondeada a entero, porque CONCAR solo admite enteros.
  Desaparecen el **18 de respaldo** para un IGV sin base (ese comprobante no llega al asiento: la
  validación lo para con `IGV_NO_CUADRA`) y la regla que llevaba el **10.5 al 10**; las dos suponían
  una tasa en vez de leerla. Sale también `tasa_igv` de `asiento.DEFAULTS`. **Cambio de
  comportamiento:** un comprobante al 10.5 % sale ahora con AO = 11, no 10 — y la plantilla describe
  la columna con «valores validos 0,10,18», así que hay que comprobarlo con la primera importación real
  que lo traiga. Hoy no hay ninguno en producción: los 99 comprobantes con IGV están al 18 %.

### Añadido
- **`contaperu.igv`**: `tasa(igv, base)` y `aplicar_igv(comprobante, igv)`, el recálculo de importes
  cuando se escribe el IGV que trae el papel, sin tocar el total. Con IGV el comprobante es afecto y
  la base se deduce; sin IGV cae en inafecto. Lo consume el portal, que hasta ahora hacía esta cuenta
  en el navegador dividiendo entre 1.18.

### Corregido
- **La versión se escribía a mano en dos sitios y se separaron.** Llegaron a convivir **tres**:
  `0.3.0` en `pyproject.toml`, `0.2.0` en `contaperu/__init__.py` y `0.1.0` en la metadata de la
  instalación editable — y la del medio era la que el servidor MCP le decía a su cliente al
  presentarse, y la que imprimía `contaperu --version`. Ahora se escribe **una sola vez**, en
  `contaperu/_version.py`, y `pyproject.toml` la lee de ahí (`[tool.hatch.version]`). No al revés:
  leerla con `importlib.metadata` parece más limpio pero en una instalación editable esa metadata se
  congela el día que se instaló — así apareció el `0.1.0`. `PE_LEDGER` también estaba duplicado
  (`__init__.py` y `operaciones.py`) y ahora sale del mismo módulo.
- **La línea de comandos no pasaba por la fachada.** No importaba `operaciones` ni una vez:
  construía `Libro` y `Comprobante` por su cuenta y serializaba el documento a mano, así que emitía
  un JSON **sin la clave `pe_ledger`** mientras el servidor MCP sí la ponía — el mismo comprobante,
  dos documentos distintos según la puerta, hasta el punto de que un test tenía que añadir la clave
  para poder validar contra el esquema. Ahora las dos puertas leen y escriben por `operaciones`, y
  `desde-json` gana de paso lo que se saltaba: el motivo legible cuando falta el bloque `libro` y el
  tope de 5.000 comprobantes.

### Añadido
- **`tests/test_frontera.py`** — la frontera deja de sostenerse por convención. Comprueba que el
  núcleo no importa ninguna puerta ni el SDK del protocolo, que no sale a la red ni lee variables de
  entorno ni mira el reloj, que cada puerta pasa por la fachada, y que **las dos puertas producen el
  mismo documento para el mismo XML** (normalizando `archivo_nombre`, que es procedencia: el CLI
  recibe una ruta y el MCP bytes).
- **`tests/conftest.py`** — los tests corren **sin red de verdad**. Antes era un comentario en el
  YAML del CI; ahora un candado bloquea toda conexión que no sea a localhost y hay un test que
  comprueba que el candado muerde, con una IP y no con un nombre — con un nombre, la resolución DNS
  falla antes en una máquina sin red y el test pasaría en verde sin ejercitar nada.

### Cambiado
- **La línea de la detracción se calca de un Excel que CONCAR ACEPTÓ** (set-2026), no del borrador de
  la plantilla. El tipo de documento pasa de **`DT` a `DR`**: el `DT` anterior nunca llegó a
  importarse en un CONCAR de verdad. **Es un cambio de comportamiento** — quien ya exporte facturas
  con detracción verá `DR` donde antes veía `DT`—, y por eso la sigla queda además configurable
  (`detraccion_tipo_doc`): la Tabla General 06 la numera cada contribuyente.
- La misma línea estrena la **referencia al documento del que sale la detracción** (columnas Z, AA y
  AB: tipo, serie-número y fecha de emisión del comprobante). Es lo que traía el archivo validado, y
  solo la lleva esa línea: las otras cuatro del asiento siguen sin referencia. **En una nota de
  crédito o débito no se pisa la que ya había** —la del documento que la nota corrige—, porque no
  hay ningún archivo validado que diga que deba ser otra; queda pendiente de comprobar con una nota
  real.

### Añadido
- **`detraccion_area`**: el código de área (Tabla General 26 de CONCAR) de la línea de la detracción,
  columna V. Va **vacío de fábrica** a propósito: es un número propio de cada empresa, no una
  constante contable, y ponerle uno por defecto metería los apuntes de todo el mundo en un área que
  nadie eligió. **No se recorta a los 3 caracteres** que pide la plantilla: cortar `0612` a `061`
  mandaría el apunte a otra área en silencio, mientras que entero CONCAR lo rechaza y se ve. Es la
  diferencia con la glosa, que sí se corta — ahí sobra texto, aquí sobraría significado.
- **`detraccion_tipo_doc`**, la sigla de arriba, con `DR` de serie.
- **El catálogo oficial del PCGE 2026**: `contaperu/pcge/catalogo2026.json`, 1615 cuentas con su
  nombre y la **página impresa** de la norma que lo dice (77 madre · 311 de tres dígitos · 641 de
  cuatro · 586 de cinco). Es el dato que le faltaba al motor: sin él, quien registra una compra
  escribe `631101` y no hay nada contra lo que contrastarlo.
- `contaperu/pcge/catalogo.py` — `existe()`, `nombre_de()`, `buscar()` y **`resolver()`**. La regla
  que gobierna el módulo: **una cuenta que no está en el catálogo NO es un error**. El PCGE llega a
  cinco dígitos y cada empresa abre sus divisionarias debajo, así que `resolver()` devuelve la
  cuenta exacta o **su antecesora más larga** —de `603201` sale `6032 Suministros`—, que es
  información útil y no un rechazo. Medido contra un plan de cuentas real en producción: **137 de
  137 cuentas son de seis dígitos, ninguna existe literalmente en la norma y las 137 resuelven a su
  madre**. Un `existe()` que bloqueara habría bloqueado el plan entero.
- `herramientas/extraer_pcge2026.py`, que genera ese JSON desde el PDF oficial. El PDF **no entra
  al repositorio** (2 MB y no es nuestro); entra el extracto y el script con el que se hizo, para
  poder rehacerlo y auditarlo cuando salga una modificatoria.
- En el servidor MCP, el recurso **`contaperu://catalogos/pcge2026`** y la herramienta
  **`buscar_cuenta_pcge`** (por nombre o por código). Son **diez** herramientas ahora.

### Cambiado
- `adaptar_pcge2026` sigue con la tabla vacía, pero ahora dice **por qué**: este proyecto nace en
  2026 y trabaja con el PCGE 2026 desde el primer asiento, así que no hay plan anterior del que
  traducir. No es una tarea pendiente — es el riel para el día que una modificatoria sustituya
  cuentas, y ese día entrará como datos con su cita, no como código.

### Corregido
- Dentro de `contaperu.pcge` conviven **dos `cargar()`**: el de la tabla de adaptación, que devuelve
  `(mapeos, datos)`, y el del catálogo, que devuelve el diccionario de la norma. El servidor MCP
  llamaba al que no era y servía una lista donde el cliente esperaba un objeto — no reventaba,
  devolvía otra cosa. Ahora el submódulo `catalogo` se exporta con nombre propio y las llamadas se
  escriben `pcge.catalogo.…`; lo vigila el test que lee el recurso por el protocolo.

## [0.2.0] — 2026-09-10

**La primera versión pública.** La 0.1.0 existió pero nunca salió del disco: se instaló como wheel
local en el servidor de Global Procesos y no llegó ni a PyPI ni a un tag. Queda documentada abajo
porque ese wheel sigue corriendo en producción, y porque reutilizar su número para un código que se
comporta distinto es justo lo que SemVer sirve para evitar.

### Añadido
- **`cuentas_con_centro`** y **`cc_referencia_en_x`** en la configuración de CONCAR, y los helpers
  `lleva_centro()` y `cuenta_de_fila()`.
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, este `CHANGELOG.md` y las plantillas de issue y de pull
  request.
- El esquema `pe-ledger` estrena **`$id` canónico**, colgado del tag del **estándar**
  (`pe-ledger-0.1`) y no del de la librería: quien lo cite no tiene por qué verlo cambiar cada vez
  que sale una versión del paquete.
- CI endurecido: acciones fijadas por SHA, permisos mínimos, CodeQL, Dependabot y publicación en
  PyPI por OIDC —sin ningún token guardado en el repositorio.
- Los tests de la regla del centro de costo: **152 en total**, sin red y sin credenciales, sobre
  Python 3.11, 3.12 y 3.13.

### Cambiado
- **El centro de costo lo decide la CUENTA, no un interruptor global.** Hasta ahora la columna M se
  rellenaba en toda línea principal con `usa_centros_costo` encendido, fuera cual fuera la cuenta. En
  CONCAR la marca «C. Costo habilitado» vive en cada cuenta del plan. El contador (09-sep-2026): «la
  cuenta 63 y 65 tiene habilitado el centro de costo en la columna M, pero cuando es una cuenta 60 por
  defecto no se debe asignar un centro de costo». Ahora `cuentas_con_centro` lo declara por prefijo,
  de fábrica `["63", "65", "70"]` — el `70` para que las ventas no cambien. Una cuenta fuera de la
  lista deja la M vacía y **deja de bloquear la exportación**: exigir un centro que no se escribe en
  ningún sitio obligaba a inventarlo.
- Y para esas cuentas, `cc_referencia_en_x` (apagado de fábrica) manda el centro a la **X de su propia
  línea** como referencia: «algunas empresas optan en colocar la columna X como referencia el centro de
  costo». Es independiente de `cc_en_anexo_auxiliar`, la X del tercero, que no cambia.
- `filas_sin_centro()` acepta `venta=False` como tercer parámetro opcional, igual que su hermana
  `filas_sin_cuenta()`: sin él, un libro de ventas resolvería la cuenta como si fuera de gasto.
- Los datos de los tests no dejan rastro de terceros: RUC, razones sociales y nombres son ficticios
  con dígito verificador correcto, siguiendo el patrón repetitivo del propio repositorio. Se conserva
  a propósito un RUC **inválido**, porque hay un caso que comprueba que el módulo 11 lo rechaza.

## 0.1.0 — 2026-09-09 (nunca publicada)

La primera versión que sirve para algo: lee un comprobante de SUNAT, arma la partida doble y la
exporta al formato que pide un sistema contable. Sin estado, sin base de datos y sin salir a la red.

### Añadido
- **El estándar `pe-ledger` 0.1**: la especificación escrita (`estandar/LEEME.md`) y su esquema
  formal (`estandar/pe-ledger.schema.json`, JSON Schema 2020-12), validable desde el CLI.
- **El núcleo contable**: modelo canónico del comprobante, validación previa, construcción del
  asiento y **partida doble comprobada antes de escribir un solo byte** — si no cuadra, no se
  exporta.
- **Lectores**: XML UBL de SUNAT (con `defusedxml`), TXT del SIRE y archivos sueltos.
- **Drivers de salida**: CONCAR (`.xlsx`, 41 columnas), SIRE (`.txt`) y CSV genérico.
- **Reglas peruanas que rompen cualquier modelo genérico**: detracción en dos tiempos, recibo por
  honorarios sin crédito fiscal, nota de crédito que invierte el asiento, moneda extranjera con su
  tipo de cambio, y la fecha del asiento del comprobante extemporáneo.
- **Comparador contra SUNAT**: enfrenta nuestro TXT con la exportación del detalle del SIRE.
- **PCGE 2026**: adaptación del plan contable.
- **CLI** (`contaperu`) y **servidor MCP** (`contaperu-mcp`), que devuelve el Excel como archivo, no
  como texto, y admite publicarse tras un proxy declarando el dominio.
- 148 tests, sin red y sin credenciales, sobre Python 3.11, 3.12 y 3.13.

[Sin publicar]: https://github.com/contaperu/contaperu/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/contaperu/contaperu/releases/tag/v0.2.0
