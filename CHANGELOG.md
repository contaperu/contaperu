# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
El versionado del **paquete** es [SemVer](https://semver.org/lang/es/); el del **estándar
`open-accounting`** (antes `pe-ledger`) va por su cuenta y se documenta en `estandar/LEEME.md`.

## [Sin publicar]

### Añadido

- **El archivo del driver `asiento_neutral` lleva `_exportacion` en su raíz**: la huella del asiento y, por
  comprobante, su identidad y el tramo de líneas que le toca. Hasta ahora eso solo existía en la respuesta del
  API, así que **quien recibiera el JSON a secas se quedaba sin la clave con la que no repetir un comprobante** —
  que es justo lo que `INTEGRAR.md` le pide a un ERP—. El driver tenía el índice en la mano y lo descartaba.

  **No hace falta enmendar el estándar**: su raíz ya admite cualquier clave `_` y `estandar/LEEME.md` dice que un
  productor puede llevar ahí `_exportacion`. Los 24 casos de conformidad siguen pasando sin tocarlos.
- **`asiento.exportacion_de(libro, lineas, indice)`**, que es quien lo arma, y `Cabecera.clave`, para que
  `modelo.identidad_de` sirva igual con un comprobante y con la cabecera de su tramo. `pipeline/armado` pasa a
  delegar en ella: una sola implementación para la respuesta del API y para el archivo, y por eso lo que va
  dentro del documento es idéntico a lo que dice el API, no una versión reducida.

## [3.0.0] — 2026-09-23

### Cambiado — **incompatible: es una 3.0**

- **La cuenta de un comprobante es de su imputación, y nada la suple.** `CONFIGURACION_GENERAL` pierde las dos
  cuentas que la suplían —`cuentas.gasto` (vacía de fábrica) y `cuentas.ventas` (`701101`)— y `asiento.partes_de` se
  queda sin respaldo: lo que nadie imputó se cuenta como `sin_cuenta` y `exigir_requisitos` detiene la exportación.

  Hasta aquí una cuenta por defecto hacía que el motor **dejara de contar** como `sin_cuenta` los comprobantes a los
  que nadie les había puesto una: salían imputados a ella y el mes se daba por listo para exportar. En ventas pasaba
  siempre, porque la de fábrica era real. Es la decisión de John (23-sep-2026) tras verlo en producción: cada
  comprobante tiene su cuenta y un comodín la esconde.

  **Qué hacer al subir:** lo que estaba en `cuentas.gasto` o `cuentas.ventas` pasa a la imputación de cada
  comprobante, por `id_externo` —el argumento `imputacion` o el bloque `imputaciones` del documento—. Una
  configuración que todavía las traiga se rechaza con `ConfiguracionInvalida`, que es lo contrario de perderlas en
  silencio.

- **`CUENTAS_POR_DEFECTO` de un driver tiene dos oficios, y lo dice la clave.** Las de la contrapartida —`cxp`,
  `cxp_detraccion`, `honorarios`, `retencion_4ta`, `igv`, `clientes`— siguen siendo configuración. Las dos nuevas,
  **`compras` y `ventas`** (`contrato.CLAVES_DEL_PLAN`), no: son la cuenta con la que ese sistema registra
  habitualmente una compra y una venta, y **siembran el plan de cuentas** de la empresa que lo abre, para que las
  elija comprobante a comprobante. No imputan solas. Se leen con `contrato.plan_base(driver)`, y
  `contrato.cuentas_por_defecto(driver)` ya no las devuelve.

- **Los tres drivers legacy declaran su bloque entero.** CONCAR era la última excepción —declaraba una sola cuenta
  «porque lo general ya era lo suyo»— y se retiró: un driver se lee de un vistazo y no obliga a ir a buscar qué
  hereda. Sus planes: CONCAR y CONTASIS `631101`/`701101` (PCGE a seis dígitos; la de compras de CONTASIS va marcada
  `# prevista`, porque no consta en ningún manual), STARSOFT `60110100`/`70410001`, las dos de su manual y de una
  instalación real.

### Corregido

- **Un caso de conformidad comprobaba `pedir_a` contra la constante del propio motor**, no contra la respuesta
  del diagnóstico que dice estar verificando (`tests/test_conformidad.py`). Si `diagnosticar` dejara de poner
  `pedir_a`, o lo pusiera mal, los tres casos que lo usan seguirían en verde. Ahora se lee de `que_falta`, y al
  mutar la respuesta caen los tres.

### Añadido

- **Test de las tres cifras del IGV** (`TASA_IGV`, `TASAS_IGV_REDUCIDAS`, `TOLERANCIA_IGV`): no las fijaba
  ninguno. Son de las que depende que el IGV cuadre —`validar` decide con ellas `IGV_NO_CUADRA` e `igv.tasa_legal`
  reconoce con ellas la tasa que un registro declara—, así que cambiarlas movía en silencio lo que el motor acepta.
  Se fija además que la tolerancia sea **la misma** en `validar` y en `igv`: si se separaran, un comprobante
  podría declarar 18 % en el registro y ser `IGV_NO_CUADRA` a la vez.
- **Las cuentas de CONTASIS, comparadas con las que el núcleo decidiría.** `docs/contasis/LEEME.md` promete que
  «el driver no decide ninguna cuenta» y esa frase no la afirmaba ningún test. No sustituye al snapshot, que caza
  que una celda cambie: lo que añade es una fuente independiente —el asiento del núcleo para los mismos
  comprobantes—, que cazaría una divergencia que hubiera estado ahí desde el primer día. Es la pareja que CONCAR
  ya tiene con `test_driver_asiento_neutral`.

## [2.7.0] — 2026-09-22

### Añadido

- **Linter (`ruff check .`), en el CI y antes de un PR.** Acotado a propósito a **código muerto y errores**
  —imports y variables que no usa nadie, redefiniciones, nombres sin definir—, **nunca a estilo**: aquí los
  comentarios se escriben en prosa y 442 líneas pasan de 120 caracteres. Había cuatro `# noqa` en el
  repositorio silenciando a un guardián que no estaba instalado.
- `formatear_fecha` reconoce el **ISO** (`AAAA-MM-DD`), que es lo que el CSV declaraba en sus `Opciones` y lo
  que la línea neutral lleva. Antes ese valor levantaba `ValueError`: no se notaba porque el CSV no pasa por
  ahí, pero su docstring lo ofrece como plantilla para un driver de terceros, que sí lo habría hecho.
- `tests/test_kit_texto.py`: el formateo compartido del kit, probado por sí mismo. No tenía ni un test directo.
- Un guardián de que **todo driver de serie esté en `__all__`**: `starsoft` y `asiento_neutral` llevaban
  tiempo fuera de la lista pública del registro, y no lo cazaba nada porque importarlos seguía funcionando.

- **CONTASIS declara sus `CUENTAS_POR_DEFECTO`** (John, 22-sep-2026), con la misma forma que las de STARSOFT.
  Hoy coinciden una a una con las de fábrica —usa el PCGE a seis dígitos, como CONCAR—, y se declaran igualmente
  para que el día que alguien traiga el plan real de una instalación tenga dónde escribirlo cuenta por cuenta, en
  vez de descubrir que hereda las de otro sistema. Repetir un dato exige un vigilante: `test_cuentas_del_sistema`
  compara el bloque con lo general y se pone rojo si se separan sin que nadie lo decida. **`gasto` no se declara**,
  como en STARSOFT: poner una cuenta real imputaría en silencio toda compra a la que nadie le puso ninguna.
- **Seis reglas nuevas en el examen de los drivers** (`test_contrato_drivers.py`), contra la clase de fallo que
  costó siete versiones al entrar STARSOFT: nadie escribe un importe ni una fecha a mano teniendo el kit, ningún
  corte de texto lleva el número escrito en la proyección —el largo vive junto a su columna—, el nombre del
  archivo sale del kit, y todo driver `legacy` declara con qué cuentas nace. Lo que hoy no las cumple está en
  `TOLERADAS`, con su motivo escrito y un test que avisa cuando una excepción deja de hacer falta.
- **`concar.datos.LARGOS_DE_GLOSA`**: los dos cortes de CONCAR (40 y 30) estaban escritos dentro de la
  proyección, donde no se ven al mirar el formato. Ahora están donde ya los llevan CONTASIS y STARSOFT.
- **`contrato.excluye_tipos(modulo)`**, el accesor que le faltaba a `EXCLUYE_TIPOS`. Era lo único del contrato que
  se leía con un `getattr` crudo desde fuera, mientras `exige`, `no_caben` y `canal` ya tenían el suyo.

### Cambiado

- **`asiento.constancia_de(comprobante)`: la constancia de la detracción, una sola regla.** Estaba escrita dos
  veces, comodín incluido, y el propio docstring de CONTASIS lo admitía: es un driver de REGISTRO, no ve la línea
  de detracción donde el núcleo la deja resuelta, así que la reescribía. Ahora los dos caminos preguntan lo mismo,
  y hay un test que comprueba que responden lo mismo — que es para lo que se extrajo.
- **`kit.forma`**: lo que todo driver `desde_lineas` comprueba y recorre antes de escribir. Las dos guardas
  estaban en CONCAR y en STARSOFT carácter a carácter salvo el nombre del sistema.
- **Los rangos de sub-diario de CONCAR se quedan donde están, y se escribe por qué.** Se miró si sobraban: no
  sobran. Los del núcleo llevan tres cifras y CONCAR añade la etiqueta, los dos códigos `MMNNNN` y el desborde,
  que es lo que un ERP guarda para proponer el correlativo del mes siguiente. Y manda el del driver, porque
  `pipeline/armado.py` funde su resumen al final.


- **Un formateador por cosa, y ningún archivo cambia.** `kit.formatear_monto` acepta ahora lo que trae una línea
  —texto, `Decimal` o nada— y decide el cero por `opciones.cero`, así que el `con_dos_decimales` de STARSOFT pasa
  a ser una llamada a él con las opciones de STARSOFT. `kit.formatear_fecha` acepta el texto ISO además del
  `date`, y con eso desaparece el `formatear_fecha(celdas.fecha(...))` de STARSOFT: dos pasos para decir una
  cosa. `OpcionesArchivo` declara su `cero`, como `Opciones`.
- **Dos conversores de celda salen del driver al kit**: `celdas.importe_exacto` (vivía escondido en CONCAR con
  guion bajo) y `celdas.importe_o_vacia`, que es la regla «un cero deja la celda vacía» que CONTASIS llevaba
  escrita dentro de una expresión. Se documenta que `importe_exacto` **no** es `texto_exacto`: en dinero los
  decimales son parte del dato y `4` no es `4.00`; en un tipo de cambio los ceros de más son ruido.
- **`starsoft.destino_de` NO se unifica con `igv.por_destino`**, y queda escrito por qué: las dos leen
  `destino_igv`, pero aquella reparte base e IGV en tres parejas de importes y esta devuelve un código de la
  tabla de STARSOFT con dos valores que en el estándar no existen.
- `TOLERADAS` del examen de drivers queda **vacía**: nació con dos excepciones y las dos se fueron el mismo día.


- **CONCAR declara `no_caben`, y deja de cortar la serie-número en silencio.** Cortaba a 20 caracteres desde el
  refactor de la 0.7, que es justo lo que la doctrina escrita en CONTASIS prohíbe: un código cortado es otro
  código, y el asiento entraría con un documento que no existe. Los largos que consta que aplica van declarados
  en `datos.LARGOS_DE_CODIGO`; las dos glosas se siguen cortando, porque son texto libre.

  **Con datos peruanos válidos esto no puede dispararse** —serie de 4 más número de hasta 8—, así que no cambia
  ningún archivo. Lo único que se mueve es la respuesta de `diagnosticar/concar`, que **gana la clave `no_cabe`
  vacía**: aparece cuando el driver declara la función, así que ahora los tres legacy responden a la misma
  pregunta. Tres líneas en los fixtures de caracterización, una por documento.

### Corregido

- **Tres variables muertas en `asiento/motor.py`** —`es_usd`, `serie` y `numero`—, del refactor de la 0.7.
  Se calculaban en cada comprobante y se tiraban. No cambian ninguna salida: eran cálculos puros.
- **`COLUMNA_A_CAMPO` de CONCAR**, una tabla de quince líneas que no leía nadie. Lo que documentaba está
  mejor dicho en `datos.CABECERAS`, con los títulos literales de la plantilla oficial y sus notas.
- Veintidós imports muertos, entre ellos el `glosa_de` que CONCAR arrastraba «por compatibilidad con la
  0.10» — compatibilidad que la 2.0 retiró.
- **El bloque `detraccion` de `kit/columnas.py` no declaraba `nro_constancia` ni `fecha_constancia`**, que la
  2.6.0 sí escribe en la línea: un driver de terceros que declarara esa columna lo rechazaba el contrato.
- `starsoft` entra en el guardián de OpenConta (`test_openconta.py`), del que se había quedado fuera: era el
  único driver de serie que no validaba sus respuestas reales contra el contrato HTTP.
- `ARQUITECTURA.md`: la sección de STARSOFT decía que escribía un **Excel** levantado de **dos vídeos**, con el
  número **con ceros** y cinco siglas sin constar. Desde la 2.3-2.5.1 es un TXT en ZIP recalcado de su
  documentación oficial, el número va sin ceros y las siglas sin constar son dos. Y se escribe de una vez
  **dónde vive el asiento estándar**, que se confundía con el driver `asiento_neutral`.

## [2.6.1] — 2026-09-22

### Corregido

- **La glosa larga de STARSOFT se CORTA en vez de detener la exportación.** Era su único `no_caben`, y con
  cuatro comprobantes de más de 60 caracteres el mes entero se quedaba sin archivo. La glosa es **texto libre**:
  cortada sigue diciendo lo que decía. Lo que no se corta es un **código** —una cuenta o una serie cortadas
  serían otra cuenta y otra serie—, y ese criterio ya estaba escrito en CONTASIS; STARSOFT era el único driver
  que no lo seguía, mientras CONCAR cortaba a 40 y 30 y CONTASIS a los largos de sus columnas.

  `no_caben` **se queda declarada y devuelve vacío**: es el sitio donde entrará el día que aparezca un límite de
  verdad, de los que hacen que el sistema rechace la fila.

### Cómo migrar

Nada que tocar. Un mes con glosas largas que antes no se podía exportar, ahora sale, con esas glosas recortadas
al largo de la plantilla.

## [2.6.0] — 2026-09-22

**La detracción tiene dos tiempos y ahora el segundo llega al archivo.** Se provisiona al registrar el comprobante y
se deposita días después —«casi pasando el otro mes»—; hasta hoy esa constancia no volvía a ninguna parte.

### Añadido

- **La línea de detracción transporta `nro_constancia` y `fecha_constancia`** (`asiento.motor._detraccion`), que ya
  estaban declarados en el estándar (`detraccion` del comprobante) y no los usaba nadie. El número cae al
  **comodín** cuando no hay constancia, que es el caso normal al cerrar el mes; la fecha no tiene comodín, porque
  una fecha inventada es peor que ninguna. Se resuelve en el núcleo y no en cada driver: es la contabilidad la que
  dice «esto está pendiente», el driver solo elige en qué columna lo escribe.
- **STARSOFT escribe sus campos 25 y 26**, que estaban declarados y se rellenaban con `""` literal. Van solo en la
  fila del proveedor, como el código y la tasa.
- **CONTASIS escribe sus columnas U y V** —«Constancia de depósito de detracción: número» y «: fecha»—, que
  estaban declaradas con su largo y se escribían vacías. **Revierte la decisión del 12-sep-2026** («no pongas
  nada»), a petición de John del 22: la constancia sale en cualquier destino que tenga el campo.
- El esquema del estándar declara las dos claves nuevas en el bloque `detraccion` de la **línea**, que era
  `additionalProperties: false`.

### Cambiado

- ⚠️ **El comodín pasa de `9999999999` a `999999999`** — de diez nueves a **nueve**, contados por John. **Esto
  mueve el asiento de CONCAR**, no solo el de STARSOFT: es el número del documento comodín de la línea `DR`, y así
  se ha importado ya en un CONCAR real. Los asientos con detracción que se exporten a partir de ahora llevan un
  dígito menos que los que ya están importados.
- La **huella del asiento** de un comprobante con detracción cambia, por lo anterior y porque su línea lleva ahora
  la constancia. Las de soles sin detracción y las de dólares no se mueven.

### Cómo migrar

La API pública no cambia. Lo que cambia es **el archivo** de tres destinos, y el comodín en todos ellos. Quien
guarde `nro_constancia` en el bloque `detraccion` de un comprobante lo verá salir; quien no, verá el comodín donde
antes había un hueco.

## [2.5.1] — 2026-09-22

### Corregido

- **El número del documento de STARSOFT va SIN ceros a la izquierda** (John, 22-sep-2026, viéndolo dentro de su
  sistema): en la columna Documento de su asiento salía `E00100000105` y lo quiere `E001105`. Afecta a las dos
  columnas que dicen el documento —`NRO DOCUMENTO` y la `GLOSA`—, porque no puede escribirse de dos formas en la
  misma fila. **La serie se sigue rellenando a cuatro**, y no es lo mismo: ahí el hueco marca dónde empieza el
  número, como pide el manual («si es de 3, un espacio en blanco y el numero desde la quinta»).

  Hasta ahora se rellenaba a ocho, leído de una captura de la hoja `PLANTILLA`; eso era cómo guarda los números
  **esa** instalación, no lo que el formato exige. Con esto STARSOFT deja de ser la excepción: el SIRE, CONCAR y
  CONTASIS ya escribían el número así, y era la regla de la casa desde antes. Se reutiliza
  `modelo.numero_sin_ceros`, que ya existía.

### Cómo migrar

Nada que tocar. Cambia **el archivo de STARSOFT** en dos columnas, en la dirección que pidió quien lo importa.

## [2.5.0] — 2026-09-22

**Las cuentas dejan de ser unas para todos, y el archivo de STARSOFT se recalca de sus ejemplos oficiales.** Dos
trabajos que empezaron por sitios distintos y acabaron en el mismo: lo que el motor daba por universal era, en
realidad, lo que hace CONCAR.

### Añadido

- **Un driver puede declarar con qué cuentas nace una empresa que lleva su sistema** (`CUENTAS_POR_DEFECTO`). Las
  cuentas se apilan en tres capas: las de fábrica, encima las del sistema al que se exporta y encima las que la
  empresa guardó. Se declaran **solo las que cambian**, así que lo que un driver no diga lo sigue heredando de lo
  general, hoy y el día que lo general mejore. El contrato las valida contra el bloque `cuentas` de lo general.
- `configuracion_por_defecto` acepta un `driver` y devuelve entonces lo general con las cuentas de ese sistema y
  solo su sección, igual que `describir_configuracion`. Es con lo que una aplicación siembra una empresa que ya
  dijo con qué sistema trabaja: sembrar la de todos le daba a un contribuyente de STARSOFT las cuentas de CONCAR.
  El parámetro es opcional y quien llamaba sin él sigue llamando igual.
- **STARSOFT declara las suyas, de ocho dígitos.** Cuatro constan en el manual —facturas por pagar `42120001`,
  IGV `40111000`, clientes `12120001`, ingresos `70410001`— y siete valores se deducen de su patrón (la subcuenta
  del PCGE de cuatro dígitos más un correlativo de cuatro; las de raíz de cinco completan con tres), marcados uno
  a uno como defecto configurable. `gasto` NO se declara: en lo general va vacía a propósito y la del manual
  (`62010001`) es una cuenta de gasto real, que de respaldo imputaría en silencio toda compra sin cuenta.
- **CONCAR declara su cuenta de gasto** (`631101`). Es la única en la que se aparta, porque las demás cuentas de
  lo general ya son las suyas — el PCGE a seis dígitos salió de ahí y hasta hoy no estaba dicho en ninguna parte.

### Corregido

- ⚠️ **Las cuentas 62 llevan centro de costo** (`cuentas_con_centro` pasa de `["63", "65", "70"]` a
  `["62", "63", "65", "70"]`), **para cualquier sistema**. La regla se escribió de una frase que no decía nada del
  62 y nadie lo echó de menos. **Tiene dos caras:** una 62 pasa a escribir su centro y pasa a exigirlo, así que un
  mes con cuentas 62 y sin centro deja de estar «listo para exportar». Quien tenga la lista guardada no lo recibe.
- ⚠️ **En STARSOFT la detracción no es un asiento: son campos de la fila del proveedor.** Su tabla le dedica seis
  —24 afecto, 25 número, 26 fecha, 31 código, 34 tasa, 35 importe— y sus ejemplos llevan tres filas por
  comprobante. Hasta ahora se escribían cinco, porque el driver proyectaba tal cual lo que el núcleo le daba: en
  CONCAR el traslado a la cuenta de detracciones son dos líneas más. **Una compra con detracción sale ahora con
  las mismas tres filas que una sin ella**, y el archivo cuadra igual. El asiento del motor no cambia.
- ⚠️ **La nota de débito de STARSOFT es `CD` y no `ND`**, heredada de CONCAR y marcada «por confirmar». Es el
  mismo error que `NC` en vez de `CC`: el archivo entra igual y el sistema clasifica el comprobante como otra
  cosa. Los mismos ejemplos confirman `TK` y `RC`; de las cinco siglas sin constar quedan dos.
- **El orden de las filas de STARSOFT es el de sus ejemplos**: una compra va IGV, proveedor, gasto; una venta,
  cliente, IGV, ingreso. Se ordena en el driver y no en el núcleo, porque el orden entra en la huella del asiento.
  El caso que lo destapó es la nota de crédito de ventas, que al invertirse los sentidos salía al revés.
- **La columna `GLOSA` de STARSOFT vuelve a llevar el documento** (`FT E001-00000871 /`), con el concepto en
  `GLOSA MOVIMIENTO`: es lo que hacen sus treinta ejemplos, y revierte la decisión del 21-sep-2026.
- **La tasa del IGV sale `18.00`** y no `18`, y los importes que no aplican van `0.00` y no vacíos en compras
  (porcentaje de operaciones mixtas, valor CIF, tasa e importe de detracción). En ventas no: los suyos van en
  blanco.

### Cómo migrar

Quien integre el motor no tiene nada que tocar: la API pública no cambia y el parámetro nuevo es opcional. Lo que
cambia es **el archivo de STARSOFT**, en la dirección correcta, y **qué cuentas exigen centro de costo**, que
afecta a todos los destinos. Si una empresa ya tenía `cuentas_con_centro` guardada, no se mueve. Si prefieres que
el motor siga avisando de las compras sin cuenta hacia CONCAR, deja `cuentas.gasto` en blanco en su configuración:
lo guardado manda sobre lo que traiga el driver.

## [2.4.0] — 2026-09-22

**Las huellas NO cambian.** Esto toca la proyección de STARSOFT a columnas, no el asiento: ni un fixture de
snapshot ni el de líneas neutrales se movió.

**STARSOFT se recalca de su documentación oficial.** Hasta hoy el driver se levantó de dos vídeos y de cuatro
capturas de la hoja `PLANTILLA` de Excel. John consiguió la documentación de STARSOFT —«Sistema de Contabilidad ·
Documentación», compras y ventas, con la tabla de campos y **ejemplos de TXT sacados del propio sistema**— y la
importó de verdad: el archivo entró, y al compararlo con los ejemplos aparecieron dos errores que la hoja de
Excel escondía. Lo que dice el manual está volcado en `STARSOFT-INTEGRACION.md`, campo a campo; los PDF no
entran al repositorio, que es público y son de otra empresa.

### Corregido

- ⚠️ **La línea llevaba campos de más: 38 en compras y 34 en ventas, cuando son 35 y 27.** La regla que la
  plantilla de Excel escondía es que **el número del ítem en el manual no es su posición en la línea**: varias
  columnas dependen de un «concepto general» de cada instalación y, dice literal, «si el concepto está en falso,
  **no incluir la columna**» — así que no ocupan sitio. La hoja las tiene todas; el archivo, no. Quedan
  declaradas en `datos.CONDICIONALES`, con el concepto del que depende cada una, para que conste que existen y
  por qué no se escriben. En compras salían de más `NRO FILE`, `OTROS TRIBUTOS` e `IMP BOLSA`; en ventas esas
  tres y además `NUM DOC FINAL`, `VALOR ISC`, `OTROS TRIB` y `EXONERADO`.
- ⚠️ **Las dos fechas estaban cruzadas, y solo se notaba con un comprobante extemporáneo.** El manual pide que
  la del DOCUMENTO sea la emisión y que la de REGISTRO caiga dentro del periodo; el driver escribía la del
  asiento en la primera y la emisión en la segunda. Con una factura de julio anotada en agosto rompía las dos
  reglas a la vez: la del documento salía **mayor** que la de registro, y la de registro **no era del periodo**.
  Dentro de su propio mes las dos coinciden, y por eso ningún ejemplo lo delataba. En ventas van en posiciones
  cambiadas respecto a compras (5 registro, 10 emisión) y también se corrige.
- El centro de costo de ventas se mueve de la columna `AA` a la `X`, que es su posición real ahora.

### Añadido

- Tres pruebas contra el manual: el número de campos de cada libro, las dos fechas con un comprobante
  extemporáneo, y que **el tipo de conversión (`VTA`) va en TODAS las líneas** y no solo en la del tercero —
  los ejemplos oficiales lo traen en las tres y el manual de compras lo da por obligatorio sin distinguir por
  cuenta. Era una duda razonable; sin prueba, volvería.

### Cómo migrar

Nada que tocar en quien integre el motor: la API pública no cambia. Lo que cambia es **el archivo**, y en la
dirección correcta — si alguien guardaba archivos de STARSOFT generados antes, los nuevos tienen menos campos y
las fechas en su sitio. Los tres fixtures de caracterización se regeneraron: su diff es exactamente `|D|||||` →
`|D||` en compras y el recorte equivalente en ventas.

## [2.3.0] — 2026-09-22

**Las huellas NO cambian.** Esto toca cómo se escriben los bytes, no el asiento, y la batería lo confirma sin
regenerar un solo fixture del SIRE ni de los snapshots.

### Cambiado

- **STARSOFT escribe un TXT de palotes envuelto en un ZIP, y ya no un CSV** (John, 22-sep-2026). Es una de las
  dos vías de carga del sistema —la otra es su plantilla de Excel— y el formato sale de un TXT de STARSOFT de
  verdad: campos separados por `|`, **sin fila de cabecera** y sin palote al final. El CSV era provisional,
  para poder revisarlo columna por columna mientras no se conocía la plantilla; ahora se conoce.

  El archivo pasa a `STARSOFT_COMPRAS_202507_20601234567.txt` dentro de su `.zip`, y el formato, de
  `starsoft_csv` a `starsoft_txt`.

- **Las fechas de STARSOFT salen en `DD/MM/AAAA` y no en ISO.** Es un defecto que llevaba ahí desde el primer
  día y que el CSV también tenía: el driver escribía `2025-07-01` donde su hoja y su TXT dicen `01/07/2025`.
  Son **cinco columnas en compras y cuatro en ventas**, y se traducen **por la clase declarada de la columna**,
  así que la columna de fecha que se añada mañana sale bien sin acordarse de nada.

### Añadido

- **Un driver de archivo puede pedir que su salida viaje comprimida**, con `comprimir=True` en sus
  `OpcionesArchivo`. Hasta ahora el ZIP estaba atado a la FORMA del driver: solo lo hacía la rama de texto, que
  es la del SIRE, y un driver de asientos como STARSOFT no podía usarla sin dejar de recibir el asiento y de
  declarar su configuración. Comprimir es del formato, no de la forma.

  Quien comprime sale además como el SIRE en toda la superficie —`texto` legible, `zip_base64` y `archivo_zip`
  en la respuesta, el TXT y el ZIP en disco desde la CLI, los dos adjuntos en el MCP— **sin que nada de eso
  cambiara**, y conservando lo que la rama de texto no da: el resumen con el cuadre y la huella.

- **`OpcionesArchivo` gana `fecha`**, con los mismos valores que `Opciones`. Vacío —el defecto— deja las fechas
  como vienen, en ISO, que es lo que quiere un formato de intercambio como el CSV o el asiento neutral.

### Documentación

- **Este driver es el de STARSOFT *Desktop*, y ahora lo dice.** Existe además **STARSOFT Web (Gold Edition)**,
  con API pública, que será `starsoft_web` — el hito A5 de la hoja de ruta, **abierto a quien quiera
  escribirlo**. Lo que este driver resolvió le sirve casi entero: las siglas, los sub-diarios, el destino del
  IGV, las cuentas y la proyección son los mismos; lo distinto es a dónde van los datos.

## [2.2.0] — 2026-09-21

> ⚠️ **Todas las huellas de asiento cambian.** Es lo primero que hay que mirar al subir: la fórmula es la
> misma, pero el contenido que resume no. Quien guarde huellas para reconocer una tanda ya exportada verá las
> de antes como distintas. **Ni un importe, ni una cuenta, ni un sentido se mueven**, y no es una impresión:
> al regenerar los snapshots congelados se comparó celda a celda contra los anteriores.
>
> Cambian por dos motivos, los dos comprobados:
>
> - **la glosa pierde sus prefijos** — 57 celdas por snapshot, todas glosas y ninguna otra;
> - **el asiento de una venta reordena sus líneas** — 7 de los 52 casos, todos de venta, y en los 7 la lista
>   de *(cuenta, sentido, importe)* es la misma permutada.
>
> Las huellas de los asientos de COMPRA solo cambian por lo primero; su orden no se toca.

### Añadido

- **El canal del SIRE, descrito como datos**: `catalogos_api_sire()`, `GET /v1/catalogos/sire-api` y el recurso
  `contaperu://catalogos/sire-api`, leídos de `datos/sunat/sire_api.json`. Trae los dos caminos de OAuth de SUNAT,
  las rutas **por libro**, los parámetros obligatorios de cada operación, la metadata de TUS, los estados del
  ticket y los códigos de retorno, cada bloque con su fuente y su `actualizado_al`.

  **Esto NO es un cliente y no lo será.** El motor sigue sin salir a la red: `tests/test_frontera.py` prohíbe
  importar `httpx` o `socket` y `conftest.py` mata cualquier conexión. Es la descripción de una API ajena, el
  mismo papel que ya cumplen los formatos de CONCAR, CONTASIS y STARSOFT —describir un sistema ajeno sin hablar
  con él— y lo que el criterio del hito D7 llama separar la normalización del transporte. El transporte, las
  credenciales y el estado se quedan fuera.

  Existe porque el conocimiento del FORMATO ya estaba resuelto una vez para todos y el del CANAL no: cada casa de
  software lo vuelve a reunir a mano desde dos manuales de SUNAT que **se contradicen entre sí** (`codTipoArchivo`
  es `1=csv` en compras y `1=excel` en ventas, y está así en los dos PDF). Incluye lo que más caro cuesta
  descubrir a base de rechazos: que RVIE y RCE no comparten rutas y cruzarlas devuelve **500 de nginx** y no 404;
  que desde la v24 `archivoreporte` exige cuatro parámetros más o responde 500; que el código útil del 422 vive
  dentro de `errors[]` y no en el `cod` de arriba; que el error **1024** significa «ya entró» y no «falló»; y que
  **«Generar el registro» no existe por API** (RS 000040-2022 art. 8.3), así que el techo de cualquier
  integración es dejar el mes en preliminar.

- **`INTEGRAR.md` explica el SIRE de punta a punta**: de dónde salen los bytes y el nombre, que el nombre lo
  impone SUNAT y renombrarlo hace que lo rechace, que ese nombre ES la política de idempotencia, que el ZIP es
  reproducible, que el SIRE no lleva huella, y dónde acaba el motor y empieza tu conector.

### Cambiado

- **La glosa es la misma en todas las líneas del comprobante, sin prefijos.** Las líneas derivadas
  anteponían lo que las identificaba —`IGV - `, `RET 4TA - `, `DETRACCION - `— y era información repetida:
  qué es cada línea lo dicen su `rol` y su cuenta, que es como la buscan los seis drivers. Ninguno leía la
  glosa para decidir nada.

  El prefijo además se comía el dato. CONCAR admite 30 caracteres en su columna de detalle: con un concepto
  real, la línea de la detracción llegaba como `DETRACCION - SERVICIO DE TRANS` —sobrevivía la etiqueta y se
  perdía el concepto—. Ahora llega `SERVICIO DE TRANSPORTE DE MATE`.

  Vale para **todos los drivers y para el asiento neutral**, porque se quita en el motor y no en la salida.
  Enmienda [0013](estandar/enmiendas/0013-glosa-sin-prefijos.md); el esquema no se toca y `open-accounting`
  sigue en **1.0**. Quien busque sus líneas por `rol` no nota nada; quien buscara la del IGV por el texto
  `"IGV - "` deja de encontrarla.

- **El asiento de una VENTA sale `cliente · IGV · ingreso`**, y no `cliente · ingreso · IGV`. Lo piden dos
  archivos reales de STARSOFT —una hoja de su plantilla y un TXT de otro generador— y era la única asimetría
  entre los dos libros: en compras el motor ya ponía el IGV justo detrás del principal. Las cuentas, los
  sentidos y los importes son los mismos, y la partida cuadra igual; **cambian las huellas de los asientos de
  venta**, porque el orden entra en la huella. Las de compras no se mueven.

  Se comprobó caso por caso al regenerar los snapshots: de los 52 congelados cambian 7, **todos de venta y en
  todos solo el orden** —misma cuenta, mismo sentido, mismo importe—.

- **STARSOFT: las dos columnas de glosa dicen lo mismo, el concepto del comprobante** (John, 21-sep-2026). La
  principal llevaba el documento (`FT F001-00000202 /`), que es lo que muestra una de las hojas, pero el tipo y
  el número ya viajan en sus propias columnas: repetirlos gastaba la glosa en decir dos veces lo mismo.

- **El tipo de cambio viaja en la línea del asiento aunque la moneda sea soles.** Es un hecho del comprobante,
  y hasta ahora el núcleo lo descartaba en PEN — lo que dejaba sin él a un destino que lo pide en todas sus
  filas: STARSOFT (John, 21-sep-2026, confirmado por la hoja real, que lo muestra en comprobantes en soles).
  Cuándo se escribe pasa a ser decisión de formato, que es de cada driver: **el Excel de CONCAR no cambia ni una
  celda**, porque sigue llenando su columna `G` y su `H` solo en moneda extranjera, que es como está validado.

  El motor **no inventa un tipo de cambio**: si el comprobante no lo trae, la columna sale vacía. No tiene tabla
  de tipos de cambio ni sale a la red.

- **STARSOFT: la plantilla de COMPRAS se calca del archivo real y pasa de 32 columnas a 38.** Cuatro capturas
  más de la hoja `PLANTILLA` (John, 21-sep-2026). Faltaban las tres columnas de la detracción que van juntas
  —`DETRACCION`, `NRO DOC DETRACCION`, `FECHA DETRACCION`— y `FECHA DOC REF`, así que **desde la `X` todo
  estaba corrido cuatro posiciones**; al final aparecen `OTROS TRIBUTOS` e `IMP BOLSA`. Los nombres pasan a ser
  los de la hoja (`CTA CONTABLE`, `FECHA DOCUMENTO`, `DOCUMENTO ANULADO`, `DEBE / HABER`, `NRO FILE`…).

  La captura **confirma el `04`** del sub-diario de compras, los cuatro dígitos del comprobante, el `03` del
  tipo de anexo y la serie rellenada a cuatro (`020 00044419`). Y cierra una duda: **`IGV POR APLICAR` pasa a
  `0`** —el `1` sería que el IGV está pendiente de aplicación—, porque la hoja la muestra con `0` en todas las
  filas. Estuvo vacía mientras la única fuente fue la narración del vídeo.

- **STARSOFT: la plantilla de VENTAS se calca del archivo real y pasa de 25 columnas a 34.** Cuatro capturas de
  la hoja `PLANTILLA` abierta en Excel con datos dentro (John, 21-sep-2026) corrigieron el mapa entero: faltaban
  `TIPO ANEXO` (`F`) y `CODIGO CLIENTE` (`G`), así que **de la `G` en adelante todo estaba corrido una
  posición**, y aparecen `VALOR ISC`, `OTROS TRIB`, `FECHA DOC REFERENCIA`, `NRO FILE`, `EXONERADO`,
  `OTROS CARGOS` e `IMP BOLSA`. Los nombres pasan a ser los literales de la hoja (`CTA CONTABLE`,
  `DOCUMENTO ANULADO`, `DEBE / HABER`, `CENTRO DE COSTOS`…), que **no son los de compras**: son dos plantillas y
  cada una se calca de su fuente. La de compras sigue levantada del vídeo.

  Con ellas se corrigen tres reglas que el vídeo no dejaba ver: **la serie se rellena a cuatro caracteres** —el
  número ocupa 12 siempre, `F00100000202` y `001 00036207`, así que una boleta salía con 11—; **`RUC CLIENTE` y
  `RAZON SOCIAL` van solo en la fila del cliente**, no repetidos en las tres; y la glosa del documento es
  `BV 001 -00036207 /`.

- **STARSOFT: la columna `D` se llama `COMPROBANTE`** (John, 21-sep-2026), en los dos libros, que es como la
  llama la plantilla real. La función que la calcula sigue llamándose `voucher`, superficie pública congelada.

- **STARSOFT: el tipo de anexo se parte en dos, y los dos traen valor de fábrica.** El maestro de proveedores
  y el de clientes son distintos en STARSOFT, así que `tipo_anexo` —una sola clave, vacía— pasa a
  `tipo_anexo_proveedor` (`03`, compras) y `tipo_anexo_cliente` (`02`, ventas). Antes había que elegir cuál de
  los dos maestros salía bien.

- **STARSOFT: la plantilla de VENTAS gana la columna `TIPO ANEXO` en la `F`**, que este repositorio daba por
  inexistente porque el vídeo no la mostraba. La confirma una captura de la hoja `PLANTILLA` abierta en Excel
  (John, 21-sep-2026), la fuente más fuerte que tiene el driver: no es una narración, es el archivo. Las veinte
  columnas siguientes se corren una letra.

- **El sub-diario de compras de STARSOFT es `04` y no `4`** (John, 21-sep-2026). El vídeo dice «cuatro» y de
  ahí salió un `4` a secas; el formato lleva los dos dígitos, como el `03` de ventas —que sí estaba bien desde el
  principio y venía delatando la inconsistencia—. Es un valor por defecto configurable, así que quien ya lo tenga
  puesto a mano no se entera; quien use el de fábrica verá `04` en la columna y en las claves de
  `resumen["sub_diarios"]`.

- **La columna `ANULADO` de STARSOFT sale `0` y no en blanco**, en compras y en ventas. Un comprobante que está
  entrando al registro no está anulado, y afirmarlo es más claro que callarlo (John, 21-sep-2026). Su hoja admite
  las dos formas —«Blanco o `0` por defecto»— y se elige la que afirma, que además es lo que ya hacían
  `IMPORTACION` y `EXPORTACION` en la misma fila. Con la captura de la hoja real, `IGV POR APLICAR` y
  `DETRACCION` se sumaron al mismo criterio: en una fila de compras las cuatro banderas dicen `0`.

## [2.1.0] — 2026-09-21

**El archivo que produce cada driver cambia de nombre.** Si tienes un script que lo busca por su nombre, es lo
primero que hay que mirar de esta versión.

La regla nueva es **`SISTEMA_LIBRO_PERIODO_RUC`** y vale para los cinco drivers de sistema:

| Antes | Ahora |
|---|---|
| `CONCAR_20601234567_202507_COMPRAS.xlsx` | `CONCAR_COMPRAS_202507_20601234567.xlsx` |
| `CONTASIS_20601234567_202507_COMPRAS.xlsx` | `CONTASIS_COMPRAS_202507_20601234567.xlsx` |
| `STARSOFT_20601234567_202507_COMPRAS.csv` | `STARSOFT_COMPRAS_202507_20601234567.csv` |
| `asiento_20601234567_202507_compra.csv` | `CSV_COMPRAS_202507_20601234567.csv` |
| `asiento_neutral_20601234567_202507_compra.json` | `ASIENTO_NEUTRAL_COMPRAS_202507_20601234567.json` |

El sistema delante y el RUC al final es cómo se busca un archivo cuando se llevan 30-80 contribuyentes: por
sistema y por mes. Hasta aquí convivían tres convenciones —la de los tres ERP, la del CSV en minúscula y con el
libro en singular, y la del SIRE— porque cada driver repetía su propia `f-string`.

**El TXT del SIRE NO cambia** y es la única excepción: su nombre lo impone SUNAT (Tablas 6 y 13), y además
`comparar_sire.registro_de()` lo lee para saber si un archivo es de ventas o de compras. Queda escrito en
`drivers/sire/txt.py`, junto a la función, para que nadie lo unifique «por coherencia».

### Añadido

- **`drivers.kit.nombre_de_archivo(sistema, libro, opciones)`** — la regla, escrita una vez. Un driver de
  terceros la llama y su archivo se llama como los demás sin decidir nada.

### Cambiado

- **El voucher de STARSOFT conserva sus cuatro dígitos: `0001`, no `1`.** El motor numera `070001` (mes +
  correlativo, que es lo que pide CONCAR) y a STARSOFT se le quita el mes; hasta ahora ese recorte pasaba por
  `int()` y se llevaba por delante los ceros, que son el ancho del campo. **CONCAR no cambia**: su columna C
  sigue llevando `070001`, como dice su plantilla. Ojo al revisar el CSV: Excel muestra `0001` como `1` — el
  archivo es correcto, engaña el visor.

### Arreglado

- **STARSOFT devolvía `sub_diarios` como lista** (`["4"]`) en vez del diccionario de rangos que devuelven los
  demás, y como el `resumen` del driver se funde ENCIMA del que calcula el núcleo, borraba `desde`, `hasta`,
  `desde_codigo`, `hasta_codigo` y `desborda`. Eso es justo lo que un ERP guarda para proponer el correlativo del
  mes siguiente: quien lo leyera esperando un diccionario —como hace la aplicación que integra el motor— se
  encontraba una lista. Ahora el driver no pone esa clave y manda la del núcleo.

### Nota para quien integra

Ninguna huella se mueve y la API pública no pierde ni cambia un nombre: el correlativo no entra en la huella y el
voucher se calcula al proyectar, no en la línea neutral. Los archivos ya exportados y guardados conservan el
nombre que tenían — la regla vale para lo que se exporte de aquí en adelante.

## [2.0.0] — 2026-09-21

**Se retira la compatibilidad con la 0.x. Quien integró con la 1.x no tiene que cambiar una línea.**

Esta versión mayor **no cambia la API pública**: `contaperu.api` conserva cada nombre con su firma, y
`tests/test_superficie_publica.py` lo demuestra al seguir pasando contra el mismo
`fixtures/superficie/1.0.json`, sin regenerarlo. Lo que desaparece es la capa que traducía las rutas de la 0.x.

**Por qué ahora, y por qué no rompe a nadie.** El repositorio prometía que lo que una aplicación importaba en la
0.10 seguiría resolviendo hasta la 2.0. Esa promesa **no protegía a un solo usuario**: ninguna versión 0.x llegó a
publicarse en PyPI. La primera publicada es la **1.1.0** (19-sep-2026); las 0.7 a 0.10 y la propia 1.0.0 existen
solo como tags de git, y entre `v0.10.0` y `v1.0.0` pasaron 101 minutos. Nadie pudo instalar nunca una 0.x.

### Retirado

- **Cinco módulos que no contenían nada** —`contaperu.operaciones`, `contaperu.generar`, `contaperu.cli`,
  `contaperu.formato` y `contaperu.servidor_mcp`— y el paquete `_compat/` que los sostenía. Eran tablas de
  redirección: cero `def`, cero `class`. Lo que hacían lo hace `contaperu.api`, y los comandos instalados
  (`contaperu`, `contaperu-mcp`, `contaperu-http`) ya apuntaban a `contaperu.puertas.*` y no cambian. En su lugar,
  `python -m contaperu.puertas.cli`.
- **`drivers.concar.construir`**, la forma de CONCAR hasta la 0.10. El archivo se pide a `api.exportar_archivo`.
- **`comparar_sire.leer(ruta)`**: el núcleo no lee disco. Entra `leer_bytes(datos)`.
- **La tabla del PCGE por ruta de archivo** (`pcge.adaptar(lineas, ruta)`, `pcge.cargar_equivalencias(ruta)`). La
  tabla entra como diccionario; el archivo lo abre quien llama. `adaptar` pierde su segundo parámetro posicional.
- **Los nombres que `asiento.motor` y `drivers.concar.xlsx` reexportaban** de la 0.10 (`Opciones`,
  `formatear_numero`, `numerar`, `huella`…). Viven en `contaperu.drivers.kit` y en su módulo.

### Cambiado

- **`_obsoleto.RETIRO` pasa a `"3.0"`.** El módulo se queda, sin un solo usuario, a propósito: `RutaObsoleta` es
  parte de la API pública —una aplicación la filtra con precisión— y el circuito ya está escrito y probado para la
  próxima vez que algo cambie de sitio. Lo cubre `test_api.py`, sobre un módulo de mentira.
- **La batería baja de 1117 a 1015 tests.** Se van `test_compat_superficie.py` y `test_compat_firmas.py`, que
  congelaban la superficie de la 0.10 y cuyo propio docstring decía que la promesa duraba «hasta la 2.0».
  `test_caracterizacion.py` deja de caracterizar por dos rutas y queda con una: lo que congelan sus JSON **no
  cambió** al retirar la otra.

### Cómo migrar

Desde la 1.x, `pip install -U contaperu` y nada más. Si tu código importa alguno de los nombres retirados —cosa
que solo podría pasar si copiaste código de un tag de git—, la tabla de la 1.0 en este mismo CHANGELOG dice dónde
vive cada uno hoy.

## [1.4.0] — 2026-09-20

**Un driver de asientos ya puede leer los hechos tributarios del comprobante, y hay un driver de STARSOFT.**
Lo segundo destapó lo primero.

### Añadido

- **El driver `starsoft`**, el cuarto de canal `legacy`. STARSOFT importa asientos desde un Excel con una
  plantilla que él publica: cada fila es una cuenta con su debe o haber, y las de un comprobante comparten
  cabecera. Es `desde_lineas`, como CONCAR, y el núcleo sigue poniendo toda la contabilidad.

  Lo que lo separa de CONCAR, con el mismo documento delante: el sub-diario de compras es `4` y el de ventas
  `03`, no `11` y `05`; el voucher va limpio (`1`) y no con el mes delante (`070001`); el número del documento va
  pegado y con ceros (`F13600000431`), al revés que en CONCAR y el SIRE; la nota de crédito se llama **`CC`** y
  no `NC` —`FT` y `BV` sí coinciden, que es lo que hace la trampa peligrosa—; y lleva una columna que CONCAR no
  tiene, **`DESTINO`**, porque su plantilla mezcla el asiento con el registro tributario en la misma fila.

  **Está EN PRUEBAS, y se dice donde se ve.** El formato se levantó de dos vídeos y sus capturas
  (`STARSOFT-INTEGRACION.md`), no de una plantilla oficial: cinco de sus columnas están inferidas de una
  narración y cinco de sus ocho siglas son las de CONCAR como punto de partida, todas marcadas en el código.
  Por eso escribe **un CSV revisable y no el `.xlsx` definitivo**, y su docstring dice «EN PRUEBAS» donde el de
  CONTASIS dice «Aceptado (13-sep-2026)». Nadie ha importado todavía en STARSOFT un archivo que genere.

- **La cabecera del índice lleva ahora todos los hechos del comprobante**: 32 campos donde había 13.

  Un driver de REGISTRO —el SIRE, CONTASIS— recibe el comprobante entero. Uno de ASIENTOS solo ve las líneas y
  la cabecera, y esa cabecera tenía los trece campos que CONCAR necesita. Bastó mientras el único driver de
  asientos escribiera contabilidad pura: de las 41 columnas de CONCAR **ninguna es el destino del IGV**, así que
  el dato podía caerse sin que nadie lo notara. Un comprobante con `destino_igv: "DGNG"` producía exactamente el
  mismo Excel que uno con `DG`.

  Se caían diecinueve campos, y diecisiete son columnas oficiales del registro de compras y ventas de SUNAT.
  Entran todos: `numero_final`, `contraparte_tipo_doc`, los dos descuentos, `exonerado`, `inafecto`,
  `exportacion`, `isc`, `base_ivap`, `ivap`, `icbper`, `otros`, `retencion`, `destino_igv`, `valor_no_gravado`
  —ya resuelto—, `anio_dua`, `cod_dep_aduanera`, `clasif_bienes` e `id_contrato`.

  **Lo que entra de verdad es la regla**, y `tests/test_cabecera.py` la hace cumplir contra el esquema publicado
  y no contra una lista escrita a mano: la cabecera lleva **todo hecho contable o tributario del comprobante y
  ningún dato del proceso que lo produjo**. Un campo nuevo del estándar o entra en la cabecera, o se declara como
  lo que no es un hecho, con su motivo. Fuera quedan siete —`origen`, `confianza`, `archivo_nombre`,
  `datos_originales`, `estado`, `excluida`, `observaciones`—: un driver que mirara `confianza` estaría decidiendo
  contabilidad con la certeza de un modelo de lenguaje.

  **Va a la cabecera y no a la huella, por razones medidas.** La huella del motor responde «¿este asiento ya
  salió?» y va sobre las líneas; si los hechos tributarios entraran, dos exportaciones con el mismo asiento
  darían huellas distintas y el aviso de lote repetido dejaría de dispararse. Hay un test que lo fija. Y cambiar
  la fórmula invalidaría todas las guardadas por quien las persista; añadir a la cabecera no invalida ninguna.

### Cambiado

- **`ARQUITECTURA.md` deja de contradecir a `CONTRIBUTING.md`.** Uno invitaba a escribir un driver «sin esperar a
  nadie» y el otro decía que «hasta entonces no se publica ningún driver ni esqueleto». Un colaborador que
  quisiera hacer el de SISCONT, o mejorar el de CONCAR, leía el segundo y se iba, que es lo contrario de un
  núcleo contable abierto. Lo que esa regla protegía —no prometer que un formato funciona cuando nadie lo ha
  importado— se consigue **declarando el estado, no prohibiendo el código**, que es lo que ya hacía el docstring
  de CONTASIS con su línea de «Aceptado».

  En su lugar queda escrito el criterio: **las mejoras se evalúan y lo que haga falta se cambia**, con el precio
  de cada tipo de cambio en una tabla —añadir es barato, tocar el estándar pide una fuente, cambiar la huella
  invalida las guardadas—. No son prohibiciones: es lo que cuesta, escrito antes de hacerlo.

## [1.3.0] — 2026-09-20

**La puerta MCP deja de decidir por el contribuyente.** Cuatro divergencias con las otras dos puertas, una de
ellas contable. Nada de esto toca la api pública ni el contrato OpenConta: lo que se ha hecho es alinear con
ellos la única puerta que se había desviado.

### Cambiado

- **`driver` se declara siempre en `diagnosticar`, `generar_asiento` y `exportar`.** Traían `"concar"` de
  fábrica y eran las únicas de las tres puertas que lo hacían: la api lo exige, el contrato ya lo declaraba
  obligatorio y la línea de comandos lo enseña en su `--help`. Un agente que olvidara el parámetro le daba un
  **Excel de CONCAR a un contribuyente de CONTASIS**, y eso no se nota hasta que el archivo ya está importado.
  **Es un cambio de comportamiento**: una llamada que hoy omita `driver` pasa a negarse. Era justo la llamada
  que salía mal.
- **Las doce herramientas contestan un `CallToolResult`**, como ya hacía `exportar`: el resultado en JSON, o el
  rechazo como «problem details» del RFC 9457 con su `clave` estable y `isError`. Antes el SDK envolvía
  cualquier excepción en un `ToolError` con el texto pegado, así que un cliente no podía ramificar por nada —y,
  peor, un error que **no** es del motor salía con su texto entero, que puede llevar una ruta interna. Por HTTP
  eso se enmascara desde siempre; esta es la puerta publicada sin autenticación.
- **`claves_previas` acepta el número como número.** La api y el esquema de la puerta HTTP admiten texto,
  entero o nulo; el MCP solo texto. El peligro no era el rechazo sino lo que hace un agente al encontrárselo:
  quitar las claves para que pase deja entrar un comprobante ya anotado en otro periodo, y eso SUNAT lo rechaza.
- **`fecha` es una fecha que puede no venir** (`format: date`), y no una cadena con `""` de fábrica.

### Añadido

- **`drivers_disponibles` también como herramienta**, sin dejar de ser el recurso `contaperu://drivers`. Es la
  única que sale por las dos vías, y es la pareja del cambio de arriba: en MCP los recursos los gobierna la
  aplicación cliente, que puede ofrecérselos al modelo o dejarlos como adjuntos que elige la persona, así que
  preguntar qué destinos hay no podía seguir dependiendo de esa decisión.
- **`validar_comprobantes` recibe `imputacion`**, que `api.revisar` y `POST /v1/revisar` ya aceptaban: una
  llave huérfana sale ahora al revisar y no al exportar.
- **El test que impide que esto vuelva.** `test_la_puerta_mcp_recibe_lo_mismo_que_la_http` compara las doce
  contra `api.OPERACIONES`, con los dos únicos renombres deliberados declarados a la vista. La causa de la
  divergencia contable era que el MCP escribía sus parámetros a mano mientras la puerta HTTP los deriva de
  `api/tabla.py`: dos fuentes para un contrato divergen solas. Con él llegan los primeros tests de `main()`.
- **El README ya no dice de memoria cuántas herramientas hay.** `test_documentacion.py` cuenta las que publica
  el servidor y las compara con lo que dicen `README.md` e `INTEGRAR.md`; decían 11 y 6 cuando eran 12 y 7.

### Retirado

- **`--transporte sse`.** Quedaba fuera del bloque que pone `stateless_http` y la defensa del `Host`, así que
  ignoraba `--dominio` en silencio y acumulaba sesiones. Nunca se documentó ni se probó, y el transporte está
  obsoleto en la especificación desde 2025-03-26. El que sirve en red es `http`, que es *streamable HTTP*.

### Documentación

- El paquete **está publicado en PyPI** desde el 19-sep-2026 y el repositorio es público. `README.md`,
  `INTEGRAR.md` y `CLAUDE.md` seguían diciendo lo contrario y recomendando instalar desde un commit de git.

## [1.2.1] — 2026-09-20

**Las dos puertas dan lo mismo.** Dos defectos que encontró el primer consumidor real al cruzar de
`contaperu.generar` a `contaperu.api`, y los dos venían de lo mismo: `preparar` se adelantaba al driver, decidiendo
cosas que son del **destino** y no del documento.

- **El resumen volvía a contar lo que se dejó fuera.** `preparar` descartaba los comprobantes excluidos antes de que
  `generar` los contara, así que `exportar_archivo` devolvía **`resumen.excluidos` siempre en 0** mientras la ruta de
  la 0.x lo contaba bien. Ese número se persiste: quien lo guardara vería cero excluidos para siempre, sin un error
  que lo delatara. Ahora `preparar` devuelve **todos** los comprobantes y quien llama selecciona —que es lo que ya
  hacían los dos, `salida.generar` y `armado.generar_asiento`—.
- **Un error en un comprobante que ese destino no lleva ya no impide el archivo.** El recibo por honorarios no va en
  el TXT del SIRE (`EXCLUYE_TIPOS`), así que su retención mal puesta no puede impedir declarar a SUNAT. La API
  pública comprobaba los errores **antes** de aplicar la regla del driver y se plantaba; la ruta de la 0.x, que
  filtra primero, dejaba salir el archivo. Lo que bloquea se mira ahora sobre lo que ese destino lleva de verdad, y
  un error en lo que **sí** va sigue deteniéndolo todo — hay un test para cada mitad.

Los dos casos entran en la batería como **la misma propiedad**: la ruta de la 0.x y la API pública tienen que
responder igual sobre el mismo documento. Es el tipo de fallo que solo aparece cuando alguien cruza la frontera de
verdad, y por eso vale más que el arreglo.

## [1.2.0] — 2026-09-19

**`api.config_aplicada`: la configuración tal como la preparan las operaciones.** La pide el primer consumidor real
del estándar, y el hueco que tapa es este: la API pública entregaba las piezas que **consumen** la configuración
aplicada y no la que la **construye**.

`asiento.faltantes_para`, `asiento.sub_diario`, `asiento.cuenta_tercero` y `asiento.lleva_centro` están en la
superficie congelada, y las cuatro reciben la configuración **ya aplicada** —plana, con la sección de su sistema
fundida en la raíz—. La forma en que se guarda es otra, anidada por sistema, y es la única que daba
`configuracion_por_defecto`. Pasarles la guardada **no falla**: devuelve vacío. Un `sub_diario` en blanco y una sigla
en blanco, que es peor que un error, porque el pre-vuelo le dice al contador que le falta algo que sí tiene.

**Exportar no la necesita y no cambia**: ahí se sigue entregando la configuración como se guarda y el motor la aplica
por dentro. Esto es para quien hace su propio pre-vuelo —decir qué falta ANTES de generar el archivo, o pintar una
pantalla con lo que está configurado—, que es lo que hace cualquier ERP con una pantalla de revisión delante.

La imputación llega como en cualquier operación, en el bloque `imputaciones` del documento o por el argumento, nunca
las dos, y con las mismas comprobaciones. **Una imputación exige el documento**: sin los comprobantes no hay contra
qué casar las llaves, y aceptarla a ciegas devolvería el agujero que esas comprobaciones existen para tapar.

**No sale por HTTP ni por MCP, y es una decisión, no un olvido** (`api/tabla.py`): solo le sirve a quien puede llamar
a las funciones que la consumen, y esas son de la librería. Por esas dos puertas la misma pregunta ya tiene una
respuesta mejor —`diagnosticar`, que dice qué falta y a quién pedírselo— sin que nadie tenga que interpretar una
configuración.

Sube a **1.2.0** y no a 1.1.1 porque un nombre público nuevo es una funcionalidad, no un arreglo. Nada más cambia: la
superficie congelada gana una línea y ninguna firma se toca.

## [1.1.0] — 2026-09-19

**El estándar de datos llega a `open-accounting` 1.0**, su primera versión estable, y con ella un compromiso: nada de
lo que existe se quita ni cambia de significado hasta una 2.0. Lo que hace sostenible esa promesa entra en esta misma
versión — los catálogos, que crecen sin tocar el esquema, y las enmiendas, donde cada cambio queda con su
compatibilidad y su test.

Tres cosas cambian en el documento. **La imputación viaja dentro**, así que un archivo guardado explica su propio
asiento. **Cada línea del asiento lleva su `clase`** —derivada del primer dígito de la cuenta, no del rol—, así que una
línea suelta se entiende sin mirar de qué libro salió. Y **`rol` y `libro.tipo` salen del esquema a catálogos
publicados**, así que el día que entre un hecho nuevo sus valores no cuesten otra versión.

La librería sube a **1.1.0** en la misma tanda, y no por conveniencia: `"1.0"` es prefijo de `"1.0.0"`, y ahí es donde
los dos relojes se confunden. Ahora un test lo prohíbe.

**El motor no acepta documentos de la 0.3**: nadie de fuera los escribía todavía, así que se hizo la limpieza en vez de
cargar con dos caminos en el lector. El Excel de CONCAR validado no cambia ni una celda, y **ninguna huella emitida se
mueve**.


### Añadido
- **La batería de conformidad del estándar** (`estandar/conformidad/`, hito E2), para que un tercero compruebe que lo
  que produce es correcto **sin escribirle a nadie**. Dos juegos: los casos de esquema, con la forma de la *JSON Schema
  Test Suite* (`{description, data, valid}`), que se corren con cualquier validador de draft 2020-12 y **sin el
  motor**; y los casos de `diagnosticar`, con su documento, su destino y lo que se espera. **Los corre la batería de
  aquí**: si el motor no pasa su propia conformidad, no la pasa nadie. Casi todos los casos salen de algo que se
  equivocó de verdad al escribir esta versión.
- **`clase` en cada línea del asiento** —`activo`, `pasivo`, `patrimonio`, `ingreso`, `gasto`—, **obligatoria** desde
  `open-accounting` 1.0. Es lo único que un ERP de fuera entiende sin conocer el PCGE: hasta ahora los roles
  `principal` y `tercero` solo significaban algo mirando `libro.tipo` —en una compra `principal` es el gasto y en una
  venta el ingreso—, y la línea que recibe un sistema de fuera es justo eso, una línea suelta. Son los cinco valores
  idénticos en QuickBooks, Xero, Merge y Rutter.
- **La clase sale del primer dígito de la cuenta**, que es el elemento del PCGE (`contaperu/pcge/clases.py`): 1, 2 y 3
  son `activo`; el 4, `pasivo`; el 5, `patrimonio`; el 6 y el **9** —quien imputa por destino y no por naturaleza—,
  `gasto`; el 7, `ingreso`. **No sale del rol**, y el caso que lo prueba es diario: una compra de mercadería imputada
  a `201101` tiene `rol: principal` y es un **activo**; deducirla del rol daría `gasto` en miles de facturas al mes.
  Consecuencia: el IGV (`401111`, elemento 4) es `pasivo`, y con `debe_haber: D` la línea dice exactamente lo que pasa
  —reduce un tributo por pagar, que es el crédito fiscal—; llamarlo `activo` al debe afirmaría otra cosa.
- **Los elementos 8 y 0 no tienen clase, y no se fuerzan**: son de cierre y de control. Una imputación a una de esas
  cuentas no genera asiento y se dice con su motivo (`sin_clase` en la tabla de faltas, que se le pide al contador
  porque es quien eligió la cuenta). Las cinco clases siguen siendo cinco, que es lo que las hace universales.
  **Se miran TODAS las cuentas del asiento**, no solo la de la base: la del tercero, la del IGV, la de la retención y
  la de la detracción vienen de la imputación y de la configuración, y con solo la base el diagnóstico decía
  `listo_para_exportar: true` mientras el archivo que salía llevaba una línea **sin `clase`** —un documento que el
  propio esquema del estándar rechaza, y sin un aviso—. Lo enumera `resolucion.cuentas_del_asiento`, un test lo ata a
  las líneas que arma el motor de verdad, y la fábrica de líneas se planta si alguna vez se separan.
- **El lector de una línea exige la `clase` y la comprueba contra su cuenta** (`asiento.LineaDiario.de_dict`). Sin eso
  el motor era más laxo que el esquema que publica —que la pide en `required`—, y sobre todo: que la clase pueda quedar
  **fuera de la huella** se sostiene en que no puede contradecir a su cuenta, que sí entra. También en el esquema, la
  `clase` pide `minLength: 1`: `required` sola no atrapaba la clase vacía, porque el texto vacío es un texto. Y una
  equivalencia del PCGE no puede llevar a una cuenta sin clase (`pcge.cargar_equivalencias`), que era el único sitio
  desde donde podía salir una línea con la clase contradiciendo a su cuenta.
- **El CSV gana dos columnas al final**, `clase` y `doc_id_externo`, sin mover las de siempre. **Cambia los bytes de
  esa salida**; el Excel de CONCAR y el registro de CONTASIS no cambian ni una celda.
- **La imputación viaja DENTRO del documento** (decisión de John del 18-sep-2026), en el bloque `imputaciones` de la
  raíz del estándar, llaveado por el `id_externo` de cada comprobante: un archivo guardado explica su propio asiento,
  que antes no podía porque las cuentas llegaban solo como argumento de la llamada. **El argumento `imputacion` sigue
  valiendo** para quien ya integraba así, y **las dos formas a la vez se rechazan**: adivinar cuál manda sería elegir
  en silencio la cuenta de un comprobante. Un test comprueba que las dos vías dan exactamente lo mismo por `revisar`,
  `diagnosticar`, `generar_asiento` y `exportar`, porque una vía que ignorara el bloque contabilizaría con la cuenta
  por defecto sin decir nada.
- **`id_externo` obligatorio cuando el documento trae `imputaciones`**, con un condicional en el esquema: sin la llave
  no hay con qué casar la decisión. Un documento sin imputaciones no lo pide, así que nada de lo que ya valía deja de
  valer. Y el motor añade lo que el esquema no puede expresar: **ningún `id_externo` repetido**. Las dos
  comprobaciones valen solo por la vía del documento; por el argumento se puede seguir imputando 3 de 10 comprobantes
  con los otros 7 sin id, y esa es la única asimetría entre las dos vías.
- **`documento.id_externo` en cada línea del asiento**: el id con el que el sistema que **produjo** el comprobante lo
  conoce, para que la línea enlace con su comprobante y su imputación sin depender de la serie y el número, que son
  la identidad tributaria y no la del sistema. Es el papel que cumplen `SourceID` en Xero y `SourceDocumentID` en
  SAF-T. No confundirlo con `id_en_destino`, reservado para el id que le pone el sistema que **recibe** el asiento
  ([enmienda 0001](estandar/enmiendas/0001-id-en-destino.md)).
- **Las enmiendas del estándar** (`estandar/enmiendas/`, hito E1): una por cambio, con su estado, su compatibilidad,
  su caso real, su fuente y el test que la sostiene. Entran los siete nombres que estaban reservados en el LEEME, y
  el primero ya renombrado — `linea.id_externo` pasa a **`linea.id_en_destino`** antes de existir, para que no se
  confunda con el campo nuevo de la línea. `tests/test_enmiendas.py` hace cumplir el criterio de salida del hito:
  cada reservado tiene su enmienda y una enmienda `final` cita un test que existe.
- **La gobernanza de los catálogos**, en `estandar/LEEME.md`: quién aprueba un valor nuevo, cómo se propone, qué se
  responde, y que un valor publicado no se quita ni cambia de significado. Con lo que **no** se gobierna dicho
  también: los catálogos de SUNAT se copian de la norma.

### Cambiado
- **Cambio de comportamiento: una llave de imputación que nombra a dos comprobantes se rechaza también cuando la
  imputación llega por el argumento.** Hasta ahora eso pasaba en silencio y la misma cuenta se aplicaba a los dos, con
  las dos líneas llevando un `documento.id_externo` que no dice de cuál vienen. Se cierra ahora porque el `id_externo`
  pasa a ser el enlace oficial entre la línea, el comprobante y su imputación. El alcance no es el mismo por las dos
  vías, y es a propósito: en el documento no puede repetirse ningún id —lo pide el condicional del esquema—, y por el
  argumento solo los que la imputación nombra, porque ahí se sigue pudiendo imputar 3 de 10.
- **`rol` y `libro.tipo` salen del esquema a catálogos publicados** (`estandar/catalogos.json`, junto al esquema y
  citable por la URL del tag del estándar), con `clases` al lado. Vivían como enums cerrados **y repetidos** —`ROLES`
  en `asiento/motor.py` y `TIPOS_LIBRO` en `modelo.py`—, sin ningún test que comparara las copias; ahora hay una sola
  fuente (`contaperu/vocabulario.py`) y un test que la ata al código y al esquema. **Los valores no cambian:** los seis
  roles son los de compras y ventas, y abrir el catálogo es para que un hecho nuevo traiga los suyos sin subir la
  versión, no para que estos crezcan. Se sirven en `api.catalogos_del_estandar()`, en `GET /v1/catalogos/estandar` y en
  el recurso MCP `contaperu://catalogos/estandar`, aparte de los de SUNAT, que se copian de la norma y no se gobiernan.
- **Un `libro.tipo` fuera del catálogo lo rechaza el modelo, no el esquema.** El rechazo no desaparece: cambia de
  sitio, porque el esquema ya no enumera. Y es a propósito que `libro.tipo` **no** degrade como el `rol`: quien recibe
  un registro que no conoce no puede adivinar qué hacer con él, así que quien degrada es el destino — el driver que no
  lo declara en sus `FORMATOS` lo rechaza limpio.
- **`_datos.del_estandar(ruta)`**: la doble búsqueda de un archivo del estándar —dentro del paquete instalado o en la
  raíz del repositorio— estaba escrita solo para el esquema. Ahora está una vez, y un archivo nuevo en `estandar/`
  necesita su línea de `force-include` y nada más.
- **`pcge.adaptar` re-deriva la clase al reescribir una cuenta.** Antes solo cambiaba el número, así que un mapeo que
  cruzara de elemento dejaba la línea con una clase que su cuenta contradice — justo lo que el motor promete rechazar,
  y lo que sostiene que la clase quede fuera de la huella.
- **La vuelta desde el Excel de CONCAR también deriva la clase** (`drivers/concar/desde_fila`): CONCAR no lleva una
  columna de clase —no le hace falta, su plan de cuentas vive en su sistema—, así que al volver a línea neutral se
  deriva de la cuenta. Sin eso, un documento reconstruido desde un archivo importado no validaría.
- **El driver neutral se llama `asiento_neutral`** (antes `open_accounting`, que era el nombre del estándar y hacía
  tropezar: uno es el formato que entra y el otro una de las salidas). Cambian el valor de `driver`, el formato
  `asiento_neutral_json` y el nombre del archivo que produce. Nada publicado llevó el nombre viejo. **La clave
  `open_accounting` del documento no cambia.**
- **La huella del asiento deja fuera `clase` y `documento.id_externo`**, además del `correlativo` que ya excluía, y
  `SIN` pasa a admitir rutas con punto para alcanzar un campo de un bloque. **Ninguna huella emitida cambia**: los
  tres campos quedan fuera precisamente porque no cambian el contenido contable, y `tests/test_huella.py` sigue
  fijando los mismos valores literales. El `id_externo` es el caso que la huella existe para atajar — al reexportar
  tras un «deshacer» la aplicación recrea sus filas con ids nuevos, así que con el id dentro el aviso de lote
  repetido se apagaría justo cuando hace falta.
- **La tabla de detracciones vive en el motor** (`contaperu/datos/sunat/detracciones.json`, decisión de John del
  15-sep-2026): el código, el nombre y la tasa de cada detracción, con su fuente, iguales para todos. El ERP que integra
  el motor la sobreescribe en lo general de su configuración: `detraccion_tasas` cambia una tasa o suma un código
  (`null`: se reconoce sin tasa), y `detraccion_nombres` cambia el nombre de uno que ya está. Por eso las dos claves
  **vienen vacías** en `configuracion_por_defecto()`, y una configuración guardada con los 14 códigos de la 1.0 da
  exactamente lo mismo. Lo que ya no se puede es **reconocer menos códigos** que la tabla quitándolos de la
  configuración: sobreescribir cambia o suma, no quita. `detraccion_codigos`, el código interno de cada sistema, sigue
  en la sección de ese sistema.
- **`exportar` y `generar_asiento` dejan en blanco la detracción que la tabla no reconoce**, como ya hacían `revisar` y
  `diagnosticar`: un mismo documento da la misma respuesta por cualquier operación. Una factura con un código que no
  está en la tabla va al sub-diario de compras y no al de detracciones: en el Excel de CONCAR, el caso
  `detraccion_codigo_sin_tasa` (código 031) pasa del 10 al 11 por el camino de exportar. La vista previa de
  `filas_de_comprobante` y su snapshot no cambian.
- **`diagnosticar` escribe el serie-número como la línea del asiento de ese destino** (`asiento.serie_numero_de`): el
  número sin ceros a la izquierda cuando el destino los quita, así un comprobante se nombra igual en el diagnóstico y en
  el archivo. Cierra el punto «a confirmar» del hito 0.8.

### Añadido
- `detracciones.tabla_del_motor()` y `detracciones.tabla_de_detracciones(config)`. `api.catalogos_sunat()` lleva
  `detracciones`, la tabla del motor con su fuente, para que una pantalla nombre cada código aunque el ERP no
  sobreescriba nada (también en `contaperu://catalogos/sunat` y `GET /v1/catalogos/sunat`).
- `asiento.serie_numero_de(comprobante, opciones)`.
- **Los tres grupos de destinos del motor en el código**: `drivers.contrato.GRUPOS` y `grupo(modulo)` presentan cada
  canal como **SIRE** (`tributario`), **Legacy** (`legacy`) o **ERP** (`intercambio`), y `drivers_disponibles` suma
  `grupo` a cada driver (también en `contaperu://drivers` y `GET /v1/drivers`). Los canales no cambian: siguen siendo la
  regla del contrato.
- **`contaperu verificar-driver mi_paquete.mi_driver`** y `api.verificar_driver`: un driver propio contra el contrato
  antes de registrarlo, con su forma, su canal, su grupo, lo que le falta y los avisos con que el registro lo aceptaría
  en la 1.x. Sale con 0 si cumple, 1 si le falta algo y 2 si no se puede importar. Importa código por su nombre, así
  que no está en la tabla de operaciones: nunca se expone por HTTP ni por MCP.
- **El driver `asiento_neutral`, la salida para los ERP que vienen**: el documento del estándar con su asiento **sin
  vocabulario legacy** —sin sub-diario ni correlativo, sin la sigla del documento ni de su referencia, y con la
  detracción sobre el propio comprobante en vez del documento comodín `DR`/`9999999999`—, con el `rol` de cada línea y
  el código SUNAT. La contabilidad es la de CONCAR: las mismas cuentas, sentidos, importes y roles, en el mismo orden
  (`tests/test_driver_asiento_neutral.py`). Un tipo sin sigla no lo detiene y `diagnosticar` no le mira vocabulario
  legacy. Lo hace posible el atributo nuevo del contrato **`VOCABULARIO`** (`legacy` por defecto, o `neutral`), que
  `drivers_disponibles` también dice; un driver neutral es de canal `intercambio`, no declara claves legacy y el
  núcleo solo le exige la cuenta. `asiento.lineas_del_comprobante` y `lineas_e_indice_del_libro` aceptan
  `vocabulario`. CONCAR, CONTASIS, el CSV y sus snapshots no cambian.
- **Drivers declarativos para formatos simples** (`drivers.kit.columnas`): un CSV o un TXT de columnas se describe como
  una tabla de `ColumnaDeLinea` —cabecera, campo de la línea neutral que la llena y su **fuente**, obligatoria— en
  `COLUMNAS_DE_LINEA`, y `escribir_csv` lo escribe, sin código de proyección. El contrato examina la tabla. El driver
  CSV de serie pasa a estar escrito así y sale byte a byte igual; su `COLUMNAS` de pares (ruta, cabecera) se conserva
  para quien lo lea. Declarar el largo de una columna y negarse con `no_caben` queda para cuando un formato real lo
  pida: los largos se miden en la línea, y `no_caben` recibe los comprobantes.
- **Los catálogos de SUNAT viven en datos, con su fuente** (`contaperu/datos/sunat/catalogos.json`, primer paso del
  hito C1): los tipos de comprobante, los documentos de identidad y las monedas dejan de estar escritos a mano en
  `catalogos.py`, que los lee con los mismos nombres, tipos y valores (un test congela los de la 1.0). `catalogos.FUENTES`
  y `api.catalogos_sunat()["fuentes"]` dicen de dónde sale cada uno. Los códigos de retorno y las reglas de validación
  de SUNAT esperan su hoja oficial, y el código SUNAT en cada observación (C2), las enmiendas del estándar (E1).

## [1.0.0] — 2026-09-14

**La 1.0.0**, probada antes como la candidata **1.0.0rc1**. La 1.0 fija una API pública estable (`contaperu.api`) y deja las rutas de la 0.10 funcionando con aviso de obsoleto durante toda la 1.x; ordena el motor en capas que un test hace cumplir, con una sola preparación para diagnosticar, generar el asiento y exportar; separa la salida hacia los sistemas legacy (drivers por canal) de la puerta de entrada para ERPs nuevos (servidor HTTP y contrato OpenConta); y cumple la Fase 0 de la hoja de ruta. El Excel de CONCAR validado no cambia. El detalle de cada cambio entra aquí con su commit.

### Añadido
- **`ErrorContaperu`** (`contaperu.errores`): la base común de todas las excepciones del motor, con una `clave` estable
  por clase («sin_cuenta», «configuracion_invalida», «xml_invalido»). Las excepciones de siempre conservan sus bases:
  atraparlas como en la 0.10 sigue funcionando.
- **`RutaObsoleta`**: el aviso con que las rutas de la 0.10 que cambian de sitio dicen qué usar. Avisa al usar la ruta,
  no al importar el módulo, y se silencia con `warnings.filterwarnings("ignore", category=contaperu.RutaObsoleta)`.
- `Libro.a_dict` y `Libro.de_dict`, `LineaDiario.de_dict` (rechaza claves ajenas y un sentido que no es D ni H),
  `modelo.numero_sin_ceros`, `asiento.numerar_en_orden` (el número de cada comprobante en su posición, sin depender del
  `id()` de los objetos), `comparar_sire.leer_bytes` y `pcge.adaptar(lineas, datos=...)`.
- `modelo.identidad_de`: la identidad estable del comprobante del hito 0.0 (RUC y tipo del libro, tipo, serie y número
  sin ceros; en compras, el proveedor). Todavía no la usa ninguna salida.
- Una red de seguridad de tests antes de mover nada: la superficie pública de la 0.10 congelada, lo que usa
  `contab-core`, la respuesta de la fachada por documento y destino, el Excel de CONCAR por el camino de producción
  caso a caso y la forma de las hojas de Excel.
- `tests/test_capas.py`: cada módulo pertenece a una capa y solo importa de las de abajo; el núcleo y los drivers no
  abren archivos (hito 0.5); el acoplamiento con lo peruano queda congelado y visible (hito J0).

- **`contaperu.api`**, la API pública de la 1.0: `leer_xml`, `leer_propuesta_sire`, `leer_archivos`, `documento_de`,
  `revisar`, `normalizar_detracciones`, `diagnosticar`, `generar_asiento`, `exportar`, `exportar_archivo` (el archivo
  en bytes, como `Exportado`), `cuadrar`, `buscar_cuenta_pcge`, `adaptar_pcge`, la configuración, los drivers y
  catálogos disponibles, el esquema del estándar, `comparar_sire` y todos los errores. **El documento va primero y lo
  demás por su nombre, y `driver` no tiene valor por defecto.** Su superficie queda congelada con su firma
  (`tests/test_superficie_publica.py`), junto con los nombres del nivel de extensión.
- `api.OPERACIONES`: cada operación con la ruta HTTP y el nombre del MCP por los que se expone. Es la fuente de las
  puertas; un test comprueba que el MCP expone exactamente esas herramientas y recursos.
- `api.problema(error)`: un error como «problem details» del RFC 9457, con su `clave`; lo que no es un error del motor no
  enseña su texto.
- `contaperu.pipeline` (interno): la preparación, la lectura, la selección, el armado del asiento, la salida y el
  diagnóstico, cada uno en su módulo y escritos una sola vez.
- `contaperu.puertas`: la CLI y el servidor MCP, que hablan solo con la api, y lo que comparten (topes y nombres de host
  permitidos). `test_capas` lo hace cumplir y la lista de excepciones queda vacía.

- **El canal de cada driver** (`CANAL`): a quién se entrega lo que sale. `legacy`, un sistema contable instalado que
  importa un archivo (CONCAR, CONTASIS); `tributario`, un registro que se presenta a SUNAT (el SIRE); `intercambio`, un
  formato neutral (el CSV). El contrato hace cumplir las reglas de cada uno y rechaza `api_erp`, reservado para escribir
  en la API de un ERP moderno (hito A5). `api.drivers_disponibles` y el recurso `contaperu://drivers` dicen el canal.
- **El índice del asiento** (`asiento.indice`, hito 0.4 en el motor): `asiento.lineas_e_indice_del_libro` devuelve,
  con las líneas, qué tramo es de qué comprobante y una `Cabecera` con sus hechos (identidad, contraparte, glosa,
  importes), fuera de las líneas y de la huella. Un driver `desde_lineas` que acepta `indice` lo recibe.
- `drivers.kit`: lo que comparten los drivers —`Opciones`, `OpcionesArchivo` para un driver de archivo nuevo, el formato
  de texto, las celdas y el libro de Excel—.
- `drivers.contrato.canal`, `declara_canal`, `acepta_indice`, `CANALES` y `CANALES_RESERVADOS`;
  `asiento.MONEDAS_CODIGO`, la única clave de la sección de un sistema que lee el núcleo, con nombre.
- Un driver de prueba de asientos por JSON (`tests/drivers_de_prueba/diario_json.py`), de canal `legacy`, con índice y
  `no_caben`: prueba que el contrato ya cubre lo que pedirá STARSOFT, sin publicar ningún driver.

- **`claves_previas` por las tres puertas** (hito 0.1): `api.revisar`, `diagnosticar`, `generar_asiento`, `exportar` y
  `exportar_archivo`, las herramientas del MCP y `--claves-previas` en `contaperu desde-json` y `diagnosticar`. Lo ya
  anotado en otros periodos del mismo RUC viaja como `[tipo_cp, serie, numero, contraparte_doc]`, se normaliza igual
  que la clave del comprobante («00000123» casa con «123») y lo que coincide sale con `DUPLICADO_PERIODO_ANTERIOR`,
  que se pide al contador. Tope: `api.MAXIMO_CLAVES_PREVIAS`, 50 000; por encima, `DocumentoInvalido`.
- **La identidad de un comprobante, escrita** (hito 0.0, `estandar/LEEME.md`): el RUC y el tipo del libro, más el
  tipo, la serie y el número sin ceros; en compras, el documento del proveedor; en ventas, no el del cliente; nunca el
  periodo.

- **Cada comprobante en la respuesta** (hito 0.4): `_asiento.comprobantes` y `_exportacion.comprobantes` dicen de
  cada uno su identidad, el tramo `[desde, hasta)` de las líneas del asiento que le toca y la huella de ese tramo. Los
  tramos son una partición exacta y cada uno cuadra; la huella de la tanda no cambia. En un registro (el SIRE,
  CONTASIS), solo la identidad. `Exportado.por_comprobante` lo lleva en Python.
- **`motor`** (hito B2): la versión de la librería que produjo la respuesta, en `_asiento` y `_exportacion`, fuera de
  toda huella.

- **Anotaciones MCP** (hito 0.2): las once herramientas se anuncian con `readOnlyHint: true` y `openWorldHint: false`,
  así un cliente puede llamarlas sin pedir confirmación por un efecto que no tienen.

- **OpenConta** (hito B3): el contrato de la puerta HTTP, en formato OpenAPI 3.1, generado desde `api.OPERACIONES` y
  versionado en `contaperu/api/openconta.json` (`api.contrato_openconta()`). Cada operación con su cuerpo, su salida y sus
  rechazos RFC 9457; los esquemas del estándar y de la api, en `components.schemas`; sin `servers`.
  `herramientas/generar_openconta.py` lo reescribe y, con `--comprobar`, falla si no está al día; un test exige que
  regenerarlo no cambie ni un byte, que las respuestas reales validen contra su salida y los documentos de ejemplo
  contra su entrada.
- **La tabla de operaciones declara su entrada y su salida** (hito B1): cada `Operacion` trae `entrada`, el JSON Schema
  2020-12 de sus parámetros sacado de su firma, y `esquema_de_salida`, con `$ref` al esquema del estándar. Los esquemas
  de las salidas viajan en `contaperu/api/esquemas/`.
- **El esquema de la respuesta de `diagnosticar`** (hito B2), también en la forma de una configuración que no se puede
  aplicar: `api.esquema_diagnostico()` y el recurso `contaperu://esquemas/diagnostico`. El SDK del MCP no deja
  declararlo como `outputSchema` de la herramienta sin cambiar lo que responde.

- **La puerta HTTP** (hito B4): `contaperu-http`, con el extra `contaperu[http]` (Starlette y uvicorn). Cada operación
  de `api.OPERACIONES` es una ruta —`POST /v1/exportar`, `GET /v1/drivers`…—, más `/salud` y `/openconta.json`, que
  sirve el contrato. Sin estado; comparte con el MCP la defensa del `Host` (421 a un nombre que no se declaró con
  `--dominio`) y los topes: el cuerpo se lee por trozos y se corta a 10 MiB (413), y el archivo que devuelve
  `exportar`, a 4 MiB. Los rechazos son RFC 9457: 400 cuerpo mal formado, 422 con la `clave` del error, 500 sin
  detalle. `puertas.servidor_http.crear_app` la da como aplicación ASGI. Las tres puertas dan el mismo documento y el
  mismo diagnóstico.

- **`INTEGRAR.md`** (hito B6): cómo integrar el motor en un ERP —qué puerta elegir, la librería, la CLI por lotes, HTTP
  con OpenConta, el MCP, un driver propio en sus dos niveles y lo que promete la 1.x—. Sus ejemplos se ejecutan en la
  batería (`tests/test_integrar.py`).
- CI: la batería también en Windows con Python 3.12; comprobar que OpenConta está al día; un trabajo que construye la
  rueda, la instala en un entorno limpio y arranca los tres comandos con sus datos empaquetados. Publicar una versión
  es empujar su tag: `release.yml` corre la batería en ese commit, comprueba que la etiqueta sea `v` más la versión del
  código y que el CHANGELOG la traiga fechada, pasa `twine check` y crea la Release de GitHub con la rueda, el sdist y
  `SHA256SUMS`. PyPI va aparte y a mano.

### Cambiado
- **Un ZIP ya no se descomprime sin tope.** `archivos.expandir` y la propuesta del SIRE dentro de su ZIP leen cada
  entrada con tres topes (`lectores/_zip.py`):
  - 64 MB por archivo descomprimido;
  - 128 MB por ZIP;
  - una proporción de compresión de 200 a 1.

  Lo que pasa de uno queda como error del lote, con su motivo, y el resto sigue; en la propuesta del SIRE es
  `SireInvalido`. Antes, un ZIP de unos kilobytes podía expandirse hasta agotar la memoria de quien lo abría.
- **La puerta HTTP limita sus conexiones.** Atiende a lo sumo 16 peticiones a la vez (503 si llegan más) y cierra a los
  5 segundos una conexión inactiva (`puertas/comun.py`). El tiempo para leer una petición lenta lo pone el proxy, como
  explica `INTEGRAR.md`.
- **Importar `contaperu` ya no carga todos sus submódulos**: cada uno se importa la primera vez que se pide, así que
  `import contaperu.modelo` no arrastra los drivers ni openpyxl. `from contaperu import asiento` funciona igual.
- El registro de drivers busca los de terceros la primera vez que alguien lo mira, no al importar el paquete.
- **El núcleo no abre archivos** (hito 0.5): el catálogo y la tabla del PCGE se leen como datos empaquetados
  (`contaperu/_datos.py`, con `importlib.resources`), y la CLI lee el disco antes de comparar con el SIRE.
- `igv` deja de importar la validación entera por una constante: la tolerancia vive en `catalogos.TOLERANCIA_IGV`
  (`validar.TOLERANCIA` e `igv.TOLERANCIA` siguen siendo el mismo valor).
- El asiento deja de depender de las opciones de los drivers: `lineas_del_comprobante` y `lineas_del_libro` leen
  `sin_ceros` de las opciones que lleguen, y sin opciones quitan los ceros como siempre.

- **La CLI habla solo con la api.** `contaperu desde-json` revisa siempre el documento, la imputación y cada comprobante
  —`--revisar` ahora solo enseña la tabla—, y un rechazo se imprime con el mensaje de la api. Un documento o una
  imputación que no se pueden usar responden con el código 2 y el motivo en una sola línea; en `contaperu generar`, un
  RUC o un periodo mal escritos también, en vez de un traceback.
- Los comandos `contaperu` y `contaperu-mcp` arrancan desde `contaperu.puertas`. Las herramientas y los recursos del MCP
  conservan sus nombres, sus argumentos y sus respuestas.
- `api.revisar` acepta la `imputacion` y comprueba que cada una hable de un documento que está.

- **CONCAR pasa a la forma `desde_lineas`** y la orquestación del asiento queda en un solo sitio, el pipeline. El
  Excel no cambia ni una celda: la glosa de la columna F y la tasa de la AO salen de la cabecera del comprobante, y la
  AO se sigue redondeando una sola vez desde su IGV y su base (IGV 175.00 sobre 1000.03 da 17, no 18). El resumen
  conserva sus claves y sus valores; el desborde de un sub-diario se detecta igual, antes de escribir.
- **`no_caben` detiene también a un driver `desde_lineas`**, antes de armar el asiento; hasta ahora solo lo hacía con
  la forma `desde_comprobantes`. Ningún driver de serie de asientos lo declara, así que sus salidas no cambian.
- Un driver de terceros sin `CANAL` se registra con un `AvisoDriver` y se trata como `legacy`; uno con la forma
  `construir` sigue exportando, con un `AvisoDriver`.
- CONTASIS y CONCAR escriben su Excel con el kit común. `drivers.csv.CANAL`, `drivers.sire.CANAL` y
  `drivers.sire.txt.columnas_igv_compras`, que vivía en `formato`.

- **En ventas, dos comprobantes con el mismo tipo, serie y número son el mismo aunque el cliente difiera**:
  `validar.revisar` los marca como duplicados, también contra las claves previas. Es la identidad del hito 0.0; en
  compras no cambia nada. `validar.marcar_duplicados` recibe `sin_contraparte` para decidirlo y por defecto hace lo de
  siempre.

- **`generar_asiento` exige lo del destino**: es `exportar` sin escribir el archivo. Deja fuera los excluidos, los
  duplicados y lo que ese destino no lleva, y se niega por lo que su driver exige —en CONCAR, el centro de costo donde
  la cuenta lo lleva y una moneda con código— y por lo que no cabe en su formato. Mirar sin exigir es `diagnosticar`, o
  `generar_asiento` hacia el CSV. El desborde de un sub-diario no se lanza: queda en `_asiento.sub_diarios`.

- **El tipo de cambio y la tasa de la detracción viajan como texto exacto en la línea neutral** (hito 0.6):
  `"3.550"` y `"4"` en vez de `3.55` y `4.0`, y `float` solo al escribir la celda. El Excel de CONCAR no cambia. Cambian,
  y es a propósito, la huella de las tandas en dólares o con detracción —una huella guardada con la 0.10 para esas
  tandas no coincide con la nueva; la de soles, sí— y cómo se escriben esas dos columnas en el CSV. El camino inverso
  (`drivers.concar.a_lineas`) también devuelve texto.

- **`diagnosticar` cuenta igual lo que saldría** (hito 0.8): `totales.saldrian` es el largo de la lista `saldrian`;
  hasta ahora contaba también los comprobantes que bloquean.
- **`diagnosticar` no suma soles con dólares** en `resumen_por_contraparte` (hito 0.8): cada contraparte trae
  `por_moneda`, con un total por moneda, y `total` y `moneda` son los de la primera moneda en que aparece. El
  serie-número sigue escribiéndose como en el documento, con sus ceros: igualarlo al de la línea queda por confirmar.

- **Un PDF o una foto enviados a `leer_xml` cuentan como pendientes de leer** (hito 0.7): `_lectura.pendientes_de_leer`
  sube en uno y no aparece un «XML inválido». El motor reconoce el PDF, el JPEG, el PNG y el WEBP por sus primeros
  bytes, porque lo que llega por un protocolo no trae nombre de archivo.

- **El CSV lleva tres columnas más al final** (B5): `rol`, `doc_tipo_cp` y `ref_tipo_cp`, lo que un driver necesita
  para traducir sin adivinar. Las columnas de siempre no se mueven.

- `estandar/LEEME.md`, «La detracción, que ocurre en dos tiempos» (hito 0.3): ya no dice que el asiento «puede
  regenerarse» con el número de la constancia. En un destino que suma lo importado, regenerarlo duplica; el segundo
  tiempo es una decisión contable que entrará con su fuente y un archivo real.

- **El TXT del SIRE no usa `assert`.** Una nota de crédito cuyo descuento cambiaría de signo el campo 15 o el 17 del
  RVIE se niega con `CampoCambiaDeSigno`, un `NoExportable` que trae la nota, en vez de un `AssertionError` que
  `python -O` se saltaba. Un test impide `assert` en todo el paquete.

- El extra `mcp` pide `mcp>=1.30`, la versión más antigua con la que se probó el servidor (el `>=1.2` de antes no
  tenía las anotaciones ni la defensa del Host que ya usaba). Un trabajo de CI, `minimos`, instala ese mínimo tal cual.

- La imagen de Docker instala también la puerta HTTP y expone el 8080; su `CMD` sigue siendo `contaperu-mcp`.

- **Versión 1.0.0** (antes, la candidata 1.0.0rc1) y `Development Status :: 5 - Production/Stable`. `README.md`, `ARQUITECTURA.md` (las capas, el
  pipeline, el contrato v1 con sus canales, «STARSOFT: qué se sabe y qué falta» y lo que queda preparado),
  `CONTRIBUTING.md`, `CLAUDE.md`, `SECURITY.md` (la política de la 1.x) y la hoja de ruta, con sus hitos cumplidos,
  describen la 1.0.

### Obsoleto
- `comparar_sire.leer(ruta)`, `pcge.cargar_equivalencias(ruta)` y `pcge.adaptar(lineas, ruta)`: siguen funcionando y
  avisan; se pasan los bytes o el diccionario. `asiento.motor.Opciones` y `asiento.motor.formatear_numero` siguen
  resolviendo desde ahí, con aviso.
- **`contaperu.operaciones`** (todo el módulo): sigue funcionando con las firmas y los valores por defecto de la 0.10 y
  avisa con la ruta nueva, `contaperu.api`. `contaperu.generar`: `api.exportar_archivo`, `api.Exportado` y
  `api.ErroresBloqueantes`. `contaperu.cli` y `contaperu.servidor_mcp`: `contaperu.puertas.cli` y
  `contaperu.puertas.servidor_mcp`. Son el mismo objeto por las dos rutas (`generar.Exportado is api.Exportado`).
- **`drivers.concar.construir`** (y `drivers.concar.xlsx.construir`): da las mismas celdas y el mismo resumen y avisa;
  el Excel de CONCAR se pide a `api.exportar_archivo`. **`contaperu.formato`** entero: `contaperu.drivers.kit`.
  La forma `construir` de un driver de terceros se retira en la 2.0.

### Cómo migrar desde la 0.10

Nada deja de funcionar: cada ruta de la 0.10 resuelve al mismo objeto, con su firma, y avisa con `RutaObsoleta` qué usar.
Para silenciar el aviso mientras se migra: `warnings.filterwarnings("ignore", category=contaperu.RutaObsoleta)`.

| En la 0.10 | En la 1.0 |
|---|---|
| `from contaperu import operaciones as op` | `from contaperu import api` |
| `op.exportar(doc, "concar", config, correlativos)` | `api.exportar(doc, driver="concar", configuracion=config, correlativos=correlativos)` |
| `op.generar_asiento(doc, config, None, False, imputacion, "csv")` | `api.generar_asiento(doc, driver="csv", configuracion=config, imputacion=imputacion)` |
| `op.diagnosticar(doc, config, driver="concar")` | `api.diagnosticar(doc, driver="concar", configuracion=config)` |
| `op.revisar(doc, config)` · `op.leer_xml(contenido, libro, True)` | `api.revisar(doc, configuracion=config)` · `api.leer_xml(contenido, libro, es_base64=True)` |
| `op.documento(libro, comprobantes)` | `api.documento_de(libro, comprobantes)` |
| `op.config_aplicada`, `op.con_imputacion`, `op.libro_de`, `op.comprobantes_de` | dentro de cada operación; el paso suelto está en `contaperu.pipeline.preparacion`, que es interno |
| `generar.generar(libro, comprobantes, "concar", config=..., correlativos=...)` | `api.exportar_archivo(documento, driver="concar", configuracion=...)` |
| `generar.Exportado`, `generar.ErroresBloqueantes`, `op.DocumentoInvalido` | `api.Exportado`, `api.ErroresBloqueantes`, `api.DocumentoInvalido` |
| `drivers.concar.construir(...)` | `api.exportar_archivo`; un driver nuevo, `desde_lineas` |
| `from contaperu.formato import Opciones` | `from contaperu.drivers.kit import Opciones` |
| `contaperu.cli`, `contaperu.servidor_mcp` | `contaperu.puertas.cli`, `contaperu.puertas.servidor_mcp`; los comandos no cambian |
| `comparar_sire.leer(ruta)` · `pcge.cargar_equivalencias(ruta)` | `comparar_sire.leer_bytes(datos)` · `pcge.cargar_equivalencias(datos)` |

No cambian de sitio ni avisan: `asiento.*`, `drivers.concar.filas_de_comprobante`, `igv.aplicar_igv`,
`igv.aplicar_total`, `detracciones.normalizar`, `detracciones.monto_detraccion`, `validar.marcar_duplicados`,
`validar.revisar` y `modelo.clave_de`. El `resumen` de cada exportación conserva sus claves.

Lo que sí cambia de comportamiento está arriba en negrita. Lo que no se aplicó y queda por decidir: descartar al
exportar las detracciones que la tabla del contribuyente no reconoce (movería de sub-diario una factura y cambiaría el
Excel de CONCAR validado), e igualar el serie-número de `diagnosticar` al de la línea.

## [0.10.0] — 2026-09-13

**CONTASIS entra como driver de serie**, con lo que hizo falta para que un segundo sistema contable salga del mismo
documento que CONCAR. CONTASIS importa su registro de compras y de ventas —una fila por comprobante, con la cuenta
de la base y la del total— y arma el asiento él mismo: cada columna sale de la misma función del núcleo que usa el
asiento de CONCAR, y ningún driver decide una cuenta.

**El documento lleva los hechos; las cuentas llegan aparte.** Decisión de John (12-sep-2026) al integrar CONTASIS:
el JSON universal `open-accounting` es el riel que recibe cualquier input, y las cuentas contables viven en la
aplicación —en la configuración de cada entorno y en lo que el contador decide en su Revisión—. El motor recibe
tres piezas: el documento, la imputación de cada documento y la configuración. **El Excel de CONCAR no cambia**:
los casos de `tests/test_snapshot_concar.py` salen idénticos celda a celda. El estándar pasa a la `0.3` y se llama
`open-accounting`.

**La configuración se declara, va por secciones y la valida el motor.** Decisión de John (13-sep-2026): el dato se
guarda una vez, la contabilidad general también, y lo propio de cada sistema contable —sus códigos y en qué columnas
de su archivo va cada dato— vive en su sección: `{"cuentas": …, "concar": {"tipos": …, "columnas": …}, "contasis":
{"medio_pago": …}}`. El motor es de cualquier aplicación que se construya encima: cada driver declara lo que se
configura en su sección, el motor lo valida antes de generar y se lo describe a quien pinte la pantalla.

### Añadido
- **El driver `contasis`** (`drivers/contasis/`): el Excel de «FORMATO REGISTRO DE COMPRAS» y «FORMATO REGISTRO DE
  VENTAS» del Sistema Experto Contable 26.00 (NewContaSis), con sus 50 y 44 columnas transcritas de la plantilla
  oficial, sin sus filas de notas y con su pestaña. Las reglas de formato las revisó John contra un registro que
  CONTASIS importó (12-sep-2026):
  - textos rellenos con espacios hasta su largo, la serie tal como la trae el comprobante y el número sin ceros a
    la izquierda;
  - importes en soles: en dólares, cada columna × T.C. y el total en «equivalente en dólares»;
  - la nota de crédito en negativo, el % IGV legal y la glosa cortada a 60;
  - la boleta de compras, entera en no gravadas, y la detracción vacía;
  - el recibo por honorarios queda fuera del archivo (`EXCLUYE_TIPOS`);
  - una cuenta por documento (`cuenta_unica`), el medio de pago del entorno y las cuentas de otros tributos e ICBPER,
    que se configuran como el resto: su sección declara `medio_pago` (`001`), y lo general, `cuentas.otros_tributos` y
    `cuentas.icbper` (vacías);
  - el centro de costo también en su segunda columna de centro de costos, si su sección la elige (`columnas`);
  - anchos de columna para que el archivo se lea al abrirlo: los de la plantilla, los que ensanchó John al revisar
    el primer archivo generado, y ninguna fecha por debajo de lo que la deja ver.

  Lo que no cabe —otra moneda, dólares sin T.C., un rango de boletas, IVAP, un código más largo que su columna— lo
  dice `no_caben`. `tests/test_snapshot_contasis.py` congela las filas celda a celda, y
  `tests/test_plantilla_contasis.py` compara columnas y celdas con la plantilla y el registro validado cuando están
  en `tests/fixtures/privado/contasis/` (fuera de Git).

  Su formato es `contasis_xlsx`, en compras y en ventas (`FORMATOS`). **Aceptado el 13-sep-2026:** CONTASIS importó
  los dos Excel que genera el driver, el registro de compras y el de ventas de un mes real, con los anchos ya
  fijados. Los del 12-sep-2026 eran registros que CONTASIS ya había importado; estos los generó el driver.
- **`condicion_pago`** (`contado` | `credito`) en el comprobante: lo que declara el documento sobre su pago. En la
  factura electrónica es obligatorio (`PaymentTerms FormaPago`), y el lector de XML ya lo leía y lo dejaba en
  `datos_raw.forma_pago`; ahora es campo, y una factura con cuotas es a crédito. Vacío no es contado: es que el
  documento no lo dice. «Crédito» o «CONTADO» se normalizan; otro valor se rechaza.
- **`id_externo`** en el comprobante (era un nombre reservado): el id con el que la aplicación conoce el
  documento, y la llave de su imputación.
- **La imputación** (`asiento.Imputacion`): la cuenta, el centro de costo, la cuenta del total y el **reparto** de
  un documento, que llegan aparte y por `id_externo`: en la fachada, el argumento `imputacion` de `exportar`,
  `diagnosticar` y `generar_asiento`. En la configuración guardada, `imputaciones` es un error; la fachada se la
  entrega al núcleo dentro de la configuración aplicada (`operaciones.con_imputacion`). El
  reparto divide solo la base —el caso: una factura con una parte de sistemas y otra de
  desarrollo; la plantilla de CONTASIS admite varias filas por documento—, y el asiento lleva una línea de gasto o
  ingreso por parte. Un reparto con cuenta o centro al lado, o la imputación de un `id_externo` que no está, se
  rechazan en la puerta.
- **`reparto_que_no_cuadra`** (en `diagnosticar` y `faltantes_para`) y **`asiento.RepartoNoCuadra`**: las partes
  suman la base del asiento, sin tolerancia; si no, el mes no está listo y `lineas_del_comprobante` no arma ese
  asiento.
- **`asiento.partes_de` y `asiento.cuenta_tercero`**: resuelven la cuenta de la base y la del total una sola vez
  para todos los drivers. La del total vivía dentro de `lineas_del_comprobante`; se sacó primero sin cambiar nada.
- **`igv.base_imputable` e `igv.igv_del_asiento`**: la regla de que en compras la boleta y el recibo por
  honorarios no dan crédito fiscal salió de `lineas_del_comprobante`, porque la comprobación del reparto la necesita
  igual.
- `estandar/LEEME.md`: **documento, imputación y configuración**, con la forma de la imputación, y **las dos
  familias de salida** (registro y asiento). Y los nombres reservados que pide CONTASIS: `medio_pago`,
  `retencion_igv`, `percepcion` y `no_domiciliado`.
- **La familia registro en el contrato de drivers: la forma `desde_comprobantes(libro, comprobantes, config,
  opciones)`**, para un sistema contable que importa su registro de compras o de ventas y arma el asiento él mismo
  (CONTASIS). El driver recibe los comprobantes y la configuración, con la imputación dentro,
  y lee cada cuenta de `asiento.partes_de` y `asiento.cuenta_tercero`: no decide ninguna. El núcleo no le arma
  asiento ni le numera nada, y le exige la cuenta antes de llamarlo (`contrato.EXIGE_NUCLEO_REGISTRO`); puede
  exigir además el centro de costo (`EXIGE_POSIBLES_REGISTRO`). La equivalencia del tipo y el código de la
  moneda son de la configuración del asiento y no le aplican. `diagnosticar` le cuenta la cuenta, el reparto y
  el centro, sin sub-diarios.
- **`contrato.familia(modulo)`** (`registro` | `asiento`) y **`contrato.lleva_cuentas(modulo)`**: la configuración
  la pide todo driver que lleva cuentas; los correlativos, solo el que arma asientos (`arma_asientos`). El recurso `contaperu://drivers` del MCP dice la familia de cada driver.
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
  18 aunque base e IGV, redondeados ítem a ítem, den 17.98. `igv.tasa_calculada` no cambia, ni la tasa entera de CONCAR.
- **`cuenta_unica`**, un requisito que puede declarar un driver de registro: su destino lleva una cuenta por
  documento y no admite un reparto de la base (CONTASIS arma un asiento por fila, John 12-sep-2026).
  `diagnosticar` lo dice como `reparto_no_admitido` —a quién pedirlo: al contador— y el núcleo se niega con
  `asiento.RepartoNoAdmitido`. A quien no lo declara no le aparece.
- **`no_caben(libro, comprobantes, config)`**, opcional en el contrato de drivers: lo que un formato no puede
  llevar aunque la contabilidad esté completa (una moneda que no tiene, un código más largo que su columna).
  `diagnosticar` lo lista en `faltantes.no_cabe`, por motivo, y deja el mes «no listo»; el núcleo se niega con
  `drivers.contrato.NoCabe` antes de llamar a un driver `desde_comprobantes`, y la CLI lo dice sin traceback.
- **`asiento.FALTAS`**, la única tabla de lo que impide exportar (clave, requisito, excepción, texto, a quién pedirla
  y título de la CLI), y **`asiento.NoExportable`**, la base de sus excepciones y de `contrato.NoCabe` y
  `concar.CorrelativoDesborda`: quien exporta atrapa una sola y lee su `clave`, la de su fila de `FALTAS` o la propia
  de un driver (`CorrelativoDesborda` lleva `sub_diario_desborda`: un sub-diario que pasaría de 9999).
  **`asiento.correlativos_de_partida`**, el correlativo de partida de cada sub-diario. Y en `modelo`, **`CENTIMO`**,
  **`a_decimal`**, **`texto_tasa`** y **`serie_y_numero`**: cada uno es la única copia de lo que se repetía.
- **La configuración declarada** (`contaperu/configuracion.py`): `Campo` (clave, tipo, valor por defecto, patrón,
  título, ayuda) y `Columna` (en qué columna de un archivo puede ir un dato, con su letra en compras y ventas, fija o
  marcada), con `validar`, `por_defecto`, `describir` y `ConfiguracionInvalida`, que trae todos los errores con su
  ruta. Se declara en tres sitios: lo general en `CONFIGURACION_GENERAL`, lo que lee el asiento en
  `asiento.CONFIGURACION_DEL_ASIENTO` y lo propio de cada sistema en su driver (`CONFIGURACION` y
  `COLUMNAS_ELEGIBLES`). El contrato gana `configuracion`, `columnas_elegibles`, `seccion_por_defecto`, `describir`,
  `centro_en_anexo` y `DATOS_CON_COLUMNAS`, e `incumplimientos` examina lo declarado.
- **`columnas`: en qué columnas va el centro de costo**, elegidas en la sección de cada sistema. En CONCAR, la M,
  fija; la X de la línea del gasto como referencia, y la X del tercero, marcada de fábrica. En CONTASIS, su columna de
  centro de costos, fija, y la segunda. Una aplicación guarda el centro una vez y elige dónde sale.
- **En la fachada:** `operaciones.errores_de_configuracion`, `configuracion_por_defecto` (la forma guardada, con los
  valores por defecto de cada sección) y `describir_configuracion` (lo que se configura, para pintar una pantalla).
  `diagnosticar` dice `errores_de_configuracion` y el motivo `configuracion_invalida` en vez de lanzar, y
  `generar_asiento` recibe `driver`.
- **En las puertas:** el recurso `contaperu://configuracion` y la clave `configurable` en `contaperu://drivers` del
  MCP, el `driver` de su `generar_asiento`, y `contaperu configuracion [--driver] [--por-defecto]` en la CLI.
- **Los vigilantes de la configuración:** una configuración espía comprueba, por driver, que lo que se lee está
  declarado y lo declarado se lee; dos pruebas leen el código para que ni un driver ni el núcleo pidan por su nombre
  una clave que no les toca; y `test_frontera` comprueba que el motor no nombra ninguna aplicación.

### Cambiado (rompe)
Sin alias ni compatibilidad hacia atrás (John, 12-sep-2026: era el momento de rebajar la deuda de nombres, con la
arquitectura recién cambiada y contab-core sin usuarios activos, que se ajusta a la vez). Los tres snapshots
—el Excel de CONCAR, el registro de CONTASIS y las líneas neutrales— no cambian ni una celda, y julio rehecho desde
los registros que CONTASIS importó sale igual que antes de los renombres. Con la configuración por secciones
(13-sep-2026) solo cambió la entrada de un caso: el área de la detracción de `detraccion_area_y_tipo_doc` era `9001`, y
la sección de CONCAR rechaza un área de más de sus 3 caracteres.

- **La configuración va por secciones y se valida entera**: lo general en la raíz y lo de cada sistema en su sección.
  Una clave de un sistema en la raíz —la forma plana de antes—, una retirada o una desconocida detienen la generación
  con `ConfiguracionInvalida` y un mensaje que dice adónde va (`CLAVES_RETIRADAS`). `generar` también la comprueba,
  para quien lo llama directamente.
- **La tabla de detracciones que se reconocen** son las claves de `detraccion_tasas`, que es general (`null`: se
  reconoce sin tasa); `detraccion_codigos` queda para el código interno de CONCAR.

- **El estándar se llama `open-accounting`** (antes `pe-ledger`) y pasa a la `0.3`: la clave del documento es
  `open_accounting`, el esquema `estandar/open-accounting.schema.json`, la constante `OPEN_ACCOUNTING` y el recurso
  del MCP `contaperu://estandar/open-accounting`. `datos_raw` pasa a `datos_originales`. Rompe a quien lea los
  nombres viejos; contab-core se ajusta a la vez.
- **CONCAR sale del núcleo**, con el mismo reparto que CONTASIS (`drivers/concar/datos.py`, `proyeccion.py` y
  `xlsx.py`): el núcleo ya no importa ningún driver.
- `contrato.incumplimientos` explica de otra manera por qué un driver de la forma `linea` no declara `EXIGE`
  («no lleva cuentas»): ya no es cosa solo de los de asientos, porque uno de registro también lo declara.

Los nombres del núcleo:

| Antes | Después |
|---|---|
| `asiento/datos.py`, `DEFAULTS` | lo general en `contaperu/configuracion.py` (`CONFIG_POR_DEFECTO`, sin lo de ningún sistema), lo del asiento en `asiento/configuracion.py` (`CONFIGURACION_DEL_ASIENTO`) y lo de cada sistema en su driver; los datos del Excel, en `drivers/concar/datos.py` |
| `EXCEL_HEADERS` (`row1`, `row2`, `row3`), `FLAG_CONVERSION` | `drivers.concar.datos.CABECERAS` (`titulos`, `notas`, `formatos`), `MARCA_CONVERSION` |
| `asiento.asiento`, `asiento.tasa_igv`, `asiento.nombre`, `asiento.CorrelativoDesborda` | `drivers.concar.filas_de_comprobante`, `tasa_igv_entera`, `nombre`, `CorrelativoDesborda` |
| `asiento.desde_fila`, `asiento.a_lineas`, `ETIQUETAS_SUB_DIARIO` | `drivers.concar.desde_fila` y `a_lineas`; la tabla sin uso, fuera (queda `etiquetas_sub_diario`) |
| la configuración bajo la clave `concar`; `tipos.NN.concar`, `cc_referencia_en_x`, `cc_en_anexo_auxiliar` | lo general en la raíz y lo de cada sistema en su sección; `concar.tipos.NN.sigla`; el centro en la X, con las columnas `anexo_auxiliar` y `anexo_auxiliar_del_tercero` de `concar.columnas.centro_costo` |
| `tipo_concar`, `_mapa` | `sigla_documento`, `equivalencia_tipo` |
| `asiento/construir.py` | `asiento/resolucion.py` |
| `merge_config`, `resolve_cxp_account`, `resolve_cxp_detraccion_account` | `fundir_config`, `cuenta_por_pagar`, `cuenta_por_pagar_detraccion` |
| `build_xlsx`, `DRIVER_DEFAULT` | `escribir_xlsx`, `DRIVER_POR_DEFECTO` |
| `fmt_fecha`, `fmt_monto`, `fmt_tc`, `fmt_numero` | `formatear_fecha`, `formatear_monto`, `formatear_cambio`, `formatear_numero` |
| `filas_sin_cuenta`, `filas_sin_centro`, `tipos_sin_mapa` | `comprobantes_sin_cuenta`, `comprobantes_sin_centro`, `tipos_sin_sigla` |
| `cuenta_gasto`, `cuenta_venta`, `cuenta_de_fila` | fuera: la cuenta de la base la resuelve `partes_de` |
| `asiento_neutral(c, contab, mes, numero_comprobante, op, venta)`, `mes_del_libro` | `lineas_del_comprobante(c, config, limites, correlativo, opciones, es_venta)`, `limites_del_periodo` |
| `contrato.necesita_config`, `necesita_asiento`, `EXIGE_POSIBLES`, `EXIGE_NUCLEO` | `lleva_cuentas`, `arma_asientos`, `EXIGE_POSIBLES_ASIENTO`, `EXIGE_NUCLEO_ASIENTO` |
| `DriverTexto`, `DriverRegistro`, `DriverArchivo`, `DriverAsientos` | `DriverRegistroTexto`, `DriverRegistroArchivo`, `DriverAsientoComprobantes`, `DriverAsientoLineas` |
| `generar(…, **params)` con `contab`; `generar.lineas` | `generar(…, config=…, correlativos=…)`; `lineas_de_texto` |
| `Exportado.txt`, `.zip`, `.nombre_zip`, `.n_filas` | `.texto`, `.comprimido`, `.nombre_comprimido`, `.comprobantes` |
| `igv.tasa`, `detracciones.monto`, `detracciones.tasa`, `drivers.formato` | `tasa_calculada`, `monto_detraccion`, `tasa_detraccion`, `formato_de` |
| `asiento.config_de(config_cliente, config_cuenta)` con sus tres capas; `operaciones.configuracion`, que aceptaba la forma anidada | `operaciones.config_aplicada(configuracion, driver)`: lo general con sus valores por defecto y encima la sección del destino con los suyos, plana; validada entera |
| los parámetros `contab` y `conf`, `op`, `mod`, `venta` | `config`, `opciones`, `modulo`, `es_venta` |
| `xml_ubl.parsear(data, tipo_libro)` | `parsear(datos, libro)`, como el lector del SIRE |
| `lectores.archivos.Resultado`, `partida_doble.Resultado`, `pcge.cargar`, `pcge.catalogo.cargar` | `ResultadoLectura`, `Cuadre`, `cargar_equivalencias`, `cargar_catalogo` |
| `asiento.REQUISITO_DE`, `operaciones.TEXTO_FALTANTE` | `asiento.FALTAS` (y `asiento.FALTA`, por clave) |
| `TipoSinMapa`, `CorrelativoFaltante`, `MonedaSinCodigo` | `SinSigla`, `SinCorrelativo`, `SinCodigoDeMoneda` |
| `RepartoNoCuadra` y `RepartoNoAdmitido` heredan de `SinCuenta` | todas las excepciones de exportar heredan de `NoExportable` |
| `asiento.D2` | `modelo.CENTIMO` |
| `lineas_del_comprobante` y `lineas_del_libro` leían `centro_como_referencia` y `centro_en_anexo_del_tercero` | el parámetro `centro_en_anexo` (`principal`, `tercero`), que calcula `contrato.centro_en_anexo` desde las columnas elegidas |
| el parámetro `config` de `exportar`, `diagnosticar`, `generar_asiento` y `revisar` | `configuracion`, la forma guardada (`config` queda para la aplicada) |

Las respuestas de la fachada, el MCP y la CLI (las herramientas, sus parámetros y las opciones no cambian):

| Antes | Después |
|---|---|
| `faltantes`: `sin_centro_de_costo`, `tipos_sin_equivalencia`, `monedas_sin_codigo`, `sub_diarios_sin_correlativo`, `reparto_no_cuadra`, `no_caben` | con `sin_*`, como el modal de contab-core: `sin_centro`, `sin_sigla`, `sin_codigo_de_moneda`, `sin_correlativo`, `reparto_que_no_cuadra`, `no_cabe` (también en `que_falta[].motivo`) |
| `exportar.filas` | `exportar.comprobantes` |
| `fuera_del_registro`, en el resumen y en `diagnosticar.totales` | `fuera_del_destino` |
| `con_avisos`, `con_errores` en el resumen | `con_aviso`, `con_error`, como en `diagnosticar` |
| `_revision.total`, `_revision.bloquean_la_exportacion` | `_revision.comprobantes`, `_revision.bloqueantes` |
| el resumen de CONCAR `filas_excel`; por sub-diario `n`, `desde_cod`, `hasta_cod` | `filas`; `comprobantes`, `desde_codigo`, `hasta_codigo` |
| la herramienta `configuracion_por_defecto` devolvía la configuración plana | la forma por secciones, que se puede volver a pasar |

`por_que_no` y la lista de la CLI siguen el orden de `asiento.FALTAS`: sigla, código de moneda, reparto no admitido,
cuenta, reparto que no cuadra y centro.

### Retirado
- `Opciones.correlativo` (el campo 3 del PLE), `formato.fmt_fecha_libre` y `drivers.csv.construir`, que además se
  saltaba los requisitos del destino: no los usaba nadie.
- `asiento.config_aplicada` (queda `operaciones.config_aplicada`, que conoce los drivers) y, en la configuración,
  `centro_como_referencia` y `centro_en_anexo_del_tercero`: los reemplazan las columnas del centro de CONCAR.
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

[Sin publicar]: https://github.com/contaperu/contaperu/compare/v2.3.0...HEAD
[2.3.0]: https://github.com/contaperu/contaperu/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/contaperu/contaperu/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/contaperu/contaperu/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/contaperu/contaperu/compare/v1.4.0...v2.0.0
[1.4.0]: https://github.com/contaperu/contaperu/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/contaperu/contaperu/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/contaperu/contaperu/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/contaperu/contaperu/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/contaperu/contaperu/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/contaperu/contaperu/compare/v0.10.0...v1.0.0
[0.2.0]: https://github.com/contaperu/contaperu/releases/tag/v0.2.0
