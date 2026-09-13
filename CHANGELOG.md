# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
El versionado del **paquete** es [SemVer](https://semver.org/lang/es/); el del **estándar
`pe-ledger`** va por su cuenta y se documenta en `estandar/LEEME.md`.

## [0.10.0] — sin etiquetar: espera a que CONTASIS importe un archivo generado

**CONTASIS entra como driver de serie**, con lo que hizo falta para que un segundo sistema contable salga del mismo
documento que CONCAR. CONTASIS importa su registro de compras y de ventas —una fila por comprobante, con la cuenta
de la base y la del total— y arma el asiento él mismo: cada columna sale de la misma función del núcleo que usa el
asiento de CONCAR, y ningún driver decide una cuenta.

**El documento lleva los hechos; las cuentas llegan aparte.** Decisión de John (12-sep-2026) al integrar CONTASIS:
el JSON universal `open-accounting` es el riel que recibe cualquier input, y las cuentas contables viven en la
aplicación —en la configuración de cada entorno y en lo que el contador decide en su Revisión—. El motor recibe
tres piezas: el documento, la imputación de cada documento y la configuración. **El Excel de CONCAR no cambia**:
los 42 casos de `tests/test_snapshot_concar.py` salen idénticos celda a celda. El estándar pasa a la `0.3` y se llama `open-accounting`.

### Añadido
- **El driver `contasis`** (`drivers/contasis/`): el Excel de «FORMATO REGISTRO DE COMPRAS» y «FORMATO REGISTRO DE
  VENTAS» del Sistema Experto Contable 26.00 (NewContaSis), con sus 50 y 44 columnas transcritas de la plantilla
  oficial, sin sus filas de notas y con su pestaña. Las reglas de formato las revisó John contra un registro que
  CONTASIS importó (12-sep-2026):
  - textos rellenos con espacios hasta su largo, y serie y número sin ceros a la izquierda;
  - importes en soles: en dólares, cada columna × T.C. y el total en «equivalente en dólares»;
  - la nota de crédito en negativo, el % IGV legal y la glosa cortada a 60;
  - la boleta de compras, entera en no gravadas, y la detracción vacía;
  - el recibo por honorarios queda fuera del archivo (`EXCLUYE_TIPOS`);
  - una cuenta por documento (`cuenta_unica`) y el medio de pago del entorno (`medio_pago`, `001` de fábrica);
  - anchos de columna para que el archivo se lea al abrirlo: los de la plantilla, los que ensanchó John al revisar
    el primer archivo generado, y ninguna fecha por debajo de lo que la deja ver.

  Lo que no cabe —otra moneda, dólares sin T.C., un rango de boletas, IVAP, un código más largo que su columna— lo
  dice `no_caben`. `tests/test_snapshot_contasis.py` congela las filas celda a celda, y
  `tests/test_plantilla_contasis.py` compara columnas y celdas con la plantilla y el registro validado cuando están
  en `tests/fixtures/privado/contasis/` (fuera de Git).
- **`condicion_pago`** (`contado` | `credito`) en el comprobante: lo que declara el documento sobre su pago. En la
  factura electrónica es obligatorio (`PaymentTerms FormaPago`), y el lector de XML ya lo leía y lo dejaba en
  `datos_raw.forma_pago`; ahora es campo, y una factura con cuotas es a crédito. Vacío no es contado: es que el
  documento no lo dice. «Crédito» o «CONTADO» se normalizan; otro valor se rechaza.
- **`id_externo`** en el comprobante (era un nombre reservado): el id con el que la aplicación conoce el
  documento, y la llave de su imputación.
- **La imputación** (`asiento.Imputacion`): la cuenta, el centro de costo, la cuenta del total y el **reparto** de
  un documento, que llegan aparte, en la configuración bajo `imputaciones` y por `id_externo`; en la fachada, el
  argumento `imputacion` de `exportar`, `diagnosticar` y `generar_asiento`. Cada campo manda sobre su gemelo de
  legado del comprobante. El reparto divide solo la base —el caso: una factura con una parte de sistemas y otra de
  desarrollo; la plantilla de CONTASIS admite varias filas por documento—, y el asiento lleva una línea de gasto o
  ingreso por parte. Un reparto con cuenta o centro al lado, o la imputación de un `id_externo` que no está, se
  rechazan en la puerta.
- **`reparto_no_cuadra`** (en `diagnosticar` y `faltantes_para`) y **`asiento.RepartoNoCuadra`**: las partes suman
  la base del asiento, sin tolerancia; si no, el mes no está listo y `asiento_neutral` no arma ese asiento. La
  excepción hereda de `SinCuenta`, así que quien ya la atrapaba la atrapa igual.
- **`asiento.partes_de` y `asiento.cuenta_tercero`**: resuelven la cuenta de la base y la del total una sola vez
  para todos los drivers. La del total vivía dentro de `asiento_neutral`; se sacó primero sin cambiar nada.
- **`igv.base_imputable` e `igv.igv_del_asiento`**: la regla de que en compras la boleta y el recibo por
  honorarios no dan crédito fiscal salió de `asiento_neutral`, porque la comprobación del reparto la necesita
  igual.
- `estandar/LEEME.md`: **documento, imputación y configuración**, con la forma de la imputación, y **las dos
  familias de salida** (registro y asiento). Y los nombres reservados que pide CONTASIS: `medio_pago`,
  `retencion_igv`, `percepcion` y `no_domiciliado`.
- **La familia registro en el contrato de drivers: la forma `desde_comprobantes(libro, comprobantes, contab,
  op)`**, para un sistema contable que importa su registro de compras o de ventas y arma el asiento él mismo
  (CONTASIS). El driver recibe los comprobantes y la configuración, con la imputación dentro,
  y lee cada cuenta de `asiento.partes_de` y `asiento.cuenta_tercero`: no decide ninguna. El núcleo no le arma
  asiento ni le numera nada, y le exige la cuenta antes de llamarlo (`contrato.EXIGE_NUCLEO_REGISTRO`); puede
  exigir además el centro de costo (`EXIGE_POSIBLES_REGISTRO`). La equivalencia del tipo y el código de la
  moneda son de la configuración del asiento y no le aplican. `diagnosticar` le cuenta la cuenta, el reparto y
  el centro, sin sub-diarios.
- **`contrato.familia(mod)`** (`registro` | `asiento`) y **`contrato.necesita_config(mod)`**: la configuración la
  pide todo driver que lleva cuentas; los correlativos, solo el que arma asientos (`necesita_asiento`, que no
  cambia). El recurso `contaperu://drivers` del MCP dice la familia de cada driver.
- **`igv.por_destino`**: la base y el IGV de una compra en las tres parejas del destino de la adquisición (DG,
  DGNG, DNG). Vivía dentro de `formato.columnas_igv_compras`, la del SIRE, y la plantilla de importación de
  CONTASIS lleva las mismas seis columnas (J–O): la regla no puede vivir dos veces. El TXT del SIRE no cambia.
- **La imputación entra por las dos puertas**: `--imputacion` en `contaperu desde-json` y en `contaperu
  diagnosticar`, y el argumento `imputacion` en las herramientas `generar_asiento`, `diagnosticar` y `exportar`
  del MCP. `operaciones.con_imputacion` es pública: la CLI escribe bytes y llama al núcleo sin pasar por
  `exportar`.
- **`igv.tasa_legal`**: la tasa legal del IGV que cuadra con la base y el IGV (la general o una reducida del
  catálogo), con la tolerancia de `validar`; si ninguna cuadra, la del cociente a 2 decimales. Es la que pide un
  registro («Porcentaje I.G.V. — Ejemplo: 18.00», plantilla de CONTASIS): el registro que CONTASIS validó escribe
  18 aunque base e IGV, redondeados ítem a ítem, den 17.98. `igv.tasa` no cambia, ni la tasa entera de CONCAR.
- **`cuenta_unica`**, un requisito que puede declarar un driver de registro: su destino lleva una cuenta por
  documento y no admite un reparto de la base (CONTASIS arma un asiento por fila, John 12-sep-2026).
  `diagnosticar` lo dice como `reparto_no_admitido` —a quién pedirlo: al contador— y el núcleo se niega con
  `asiento.RepartoNoAdmitido`, que hereda de `SinCuenta`. A quien no lo declara no le aparece.
- **`no_caben(libro, comprobantes, contab)`**, opcional en el contrato de drivers: lo que un formato no puede
  llevar aunque la contabilidad esté completa (una moneda que no tiene, un código más largo que su columna).
  `diagnosticar` lo lista en `faltantes.no_caben`, por motivo, y deja el mes «no listo»; el núcleo se niega con
  `drivers.contrato.NoCabe` antes de llamar a un driver `desde_comprobantes`, y la CLI lo dice sin traceback.

### Cambiado
- **El estándar se llama `open-accounting`** (antes `pe-ledger`) y pasa a la `0.3`: la clave del documento es
  `open_accounting`, el esquema `estandar/open-accounting.schema.json`, la constante `OPEN_ACCOUNTING` y el recurso
  del MCP `contaperu://estandar/open-accounting`. `datos_raw` pasa a `datos_originales`. Rompe a quien lea los
  nombres viejos; contab-core se ajusta en la misma tanda.
- `contrato.incumplimientos` explica de otra manera por qué un driver de la forma `linea` no declara `EXIGE`
  («no lleva cuentas»): ya no es cosa solo de los de asientos, porque uno de registro también lo declara.

### Retirado
- **`cuenta_contable` y `centro_costo` salen del comprobante** (`open-accounting 0.3`): la cuenta y el centro de cada
  documento llegan solo en la imputación, y un documento que todavía los trae se rechaza en vez de perderlos en
  silencio. En esta rama hubo antes un `cuenta_tercero` y unas `imputaciones` dentro del comprobante: nunca se
  publicaron, y salieron al separar la imputación del documento.

## [0.9.0] — 2026-09-12

Una regla que estaba sin fuente, corregida contra la norma: **un comprobante de compras del mes anterior no
es una observación**. John lo vio en pantalla (un recibo de luz del 29/08 pintado de ámbar dentro del mes 09)
y la Ley 29215, art. 2, dice que la compra se anota en el mes de emisión **o en los 12 siguientes**.

### Cambiado
- **En compras, el comprobante emitido en un mes anterior ya no produce observación** mientras esté dentro
  del plazo de anotación (Ley 29215, art. 2, texto del D.Leg. 1116: «el mes de su emisión o del pago del
  Impuesto, según sea el caso, o … los 12 (doce) meses siguientes»). Hasta ahora `PERIODO_ANTERIOR` avisaba
  a cualquier fecha anterior —de un mes o de dos años— sin norma detrás, y como todo aviso convertía la fila
  en «observada». Es un **cambio de comportamiento**: las filas que hoy salen observadas solo por eso pasan a
  «ok» al revalidar. En un documento aduanero la referencia es la fecha de pago del impuesto (campo 6 del
  RCE): el «o del pago del Impuesto» del artículo.
- **En ventas el aviso `PERIODO_ANTERIOR` se queda** —ahí no hay plazo: el IGV nace con la emisión (Ley del
  IGV, art. 4)— y su texto ahora lo dice así. Deja de hablar del Excel de CONCAR: eso ya lo dice el resumen
  de la exportación («extemporáneos al 01/MM»).

### Añadido
- **`CREDITO_FISCAL_FUERA_DE_PLAZO`** (aviso, no bloquea): la compra emitida hace más de 12 meses. Dice el
  hecho —fuera del plazo de anotación— y deja la decisión sobre el crédito fiscal al contador. Está en
  `PEDIR_A` (contador).
- `validar.PLAZO_ANOTACION_MESES = 12`, con la nota de relevo: el **D.Leg. 1669** (28-sep-2024) lo baja a 0
  meses para los electrónicos, 2 para los físicos y 3 con detracción, pero rige recién con la Resolución de
  Superintendencia que SUNAT no ha publicado (verificado el 12-sep-2026), y lo emitido antes de esa vigencia
  conserva los 12. Ese día cambia la constante y entra la distinción por `origen` y `detraccion`, con su cita.

## [0.8.0] — 2026-09-11

Lo que `REFERENCIAS.md` proponía y tenía un caso real detrás (decisión de John, 11-sep-2026): el
destino declara qué exige, cada exportación deja su huella, y `diagnosticar` dice a quién pedir lo que
falta. **El Excel de CONCAR validado no cambia**: los 42 casos de `tests/test_snapshot_concar.py` siguen
idénticos celda a celda.

### Cambiado
- **El driver de CONCAR se detiene sin centro de costo** donde la cuenta lo lleva (`SinCentro`) y cuando
  un sub-diario pasaría de 9999 (`CorrelativoDesborda`). Las dos reglas existían —la del contador del
  06-sep-2026 y la de los cuatro dígitos de CONCAR— pero las aplicaba solo el portal antes de llamar al
  motor; el driver generaba igual. Es un **cambio de comportamiento** para quien use el motor sin el
  portal: un mes que antes salía con la M vacía ahora se niega y dice cuáles. Lo declara `EXIGE`.
- **`diagnosticar` decide «listo» por lo que exige el destino** (`exige` en la respuesta): el CSV no
  bloquea por centro ni por moneda; CONCAR sí. `faltantes` conserva sus cinco claves, informando.
- La CLI remite a `contaperu diagnosticar` también ante `SinCentro` y `CorrelativoDesborda`.

### Añadido
- **`EXIGE` en el contrato de driver** (`drivers/contrato.py`): lo que ese ERP no puede importar sin y
  que el núcleo, si no se lo dicen, deja pasar (`centro_costo`, `moneda`). La cuenta y la equivalencia
  del tipo las exige el núcleo a todo driver de asientos. `contrato.exige(mod)` devuelve la unión;
  `incumplimientos()` rechaza un requisito fuera del catálogo y un `EXIGE` en un driver de texto. El
  recurso MCP `contaperu://drivers` lo publica.
- `asiento.faltantes_para()` y `asiento.exigir_requisitos()`: una sola lista de comprobaciones para el
  driver (que lanza), el núcleo (`generar._desde_lineas`, para los drivers `desde_lineas`) y
  `diagnosticar` (que describe).
- **La huella del asiento** (`asiento/huella.py`): sha256 del contenido de las líneas neutrales, en su
  orden y sin el correlativo. Va en `resumen["huella"]` de todo driver de asientos, en `_asiento.huella`
  de `generar_asiento` y en **`_exportacion`** de `exportar` (`{driver, archivo, huella, fecha}`). La
  misma tanda exportada otra vez —tras un «deshacer»— lleva la misma huella: es lo que permite avisar
  de que ese contenido ya salió, porque el Excel de CONCAR se **suma** al importarlo dos veces. La
  `fecha` la pone quien llama (`exportar(..., fecha="AAAA-MM-DD")`, también en el MCP); el núcleo no
  mira el reloj. La fórmula es contrato y `tests/test_huella.py` la fija con un valor literal.
- **`que_falta` y `pedir_a` en `diagnosticar`**: lo que bloquea para ese destino, agrupado por motivo,
  con a quién pedírselo —`contador` si se resuelve mirando el documento o el plan de cuentas,
  `sistema` si es configuración del destino o un dato público que no está en el papel—. La tabla
  (`operaciones.PEDIR_A`) cubre todos los códigos de `validar.py` y un test lo comprueba recorriendo el
  módulo. `proveedor` queda reservado. La CLI lo imprime.
- **`REFERENCIAS.md`**: cómo modelan el asiento, los impuestos, las dimensiones, la escritura y la
  idempotencia la API de QuickBooks Online, la de Xero y las APIs unificadas de EE. UU. (Merge, Codat,
  Rutter, Apideck), comparado campo a campo con `pe-ledger`; qué no se toma y por qué; y la propuesta
  de campos opcionales de la que sale esta versión. `id_externo`, `dimensiones` y `estado` de la línea
  quedan como **nombres reservados** (`estandar/LEEME.md`) hasta que haya un caso real.

### Corregido
- `README.md` y `estandar/LEEME.md` decían pe-ledger 0.1; es 0.2 desde la 0.6.0. Y el docstring de
  `test_frontera` decía que el portal instala solo `[excel]`: instala también `[mcp]` desde que monta su
  conector.

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
