"""Los DATOS del driver STARSOFT: su identidad en el contrato, sus columnas y lo que se configura.

**De dónde sale cada cosa.** La fuente es **la documentación oficial de STARSOFT** desde el 22-sep-2026 —la tabla
de campos de compras y de ventas, con ejemplos de TXT sacados del propio sistema—, y de ahí salen las columnas, las
dos fechas y las cuentas que constan. Lo anterior a ella se levantó de dos vídeos del canal *ArchivoExcel*
—«Importar asientos contables de compras al Star Soft» (`watch?v=1HMTMsuQJAA`, 22:25) y su gemelo de ventas
(`watch?v=iOq8Zh6avj8`, 20:16), leídos el 20-sep-2026— y de las capturas de la hoja `PARAMETROS`; sigue vigente
donde el manual no dice nada, y **el manual gana donde los dos hablan**. De ahí vienen los minutos que se citan más
abajo: «compras 7:34» es el primero de los dos vídeos.

**El manual no entra al repositorio y su tabla sí**, que es la única manera de cumplir la regla de que ninguna
regla viva sin su fuente. `CONT_COMPRAS` y `CONT_VENTAS` son del fabricante, así que `.gitignore` los bloquea y
promete en su lugar que «lo que entra aquí son LOS DATOS»: eso es `CAMPOS_DEL_MANUAL`, abajo, con los 39 ítems de
compras y los 34 de ventas, cada uno con su longitud, su obligatoriedad y la condición que el manual le pone.

**Lo que NO consta se queda vacío**, y eso incluye la mitad de la tabla de siglas. Un tipo de comprobante sin
equivalente detiene la exportación con `SinSigla`, que es la regla que no se negocia: es preferible que el
contador vea «no sé cómo llama tu sistema a la nota de débito» a que el archivo salga con una sigla inventada y
STARSOFT lo rechace —o peor, lo acepte mal—.

Aquí no hay lógica: si STARSOFT cambia una columna, se toca este archivo y nada más.
"""
from __future__ import annotations

from dataclasses import replace

from ...asiento.configuracion import CONFIGURACION_DEL_ASIENTO
from ...configuracion import Campo, Columna
from ..kit import OpcionesArchivo

NOMBRE = "starsoft"
# Un sistema contable instalado que importa un archivo (`drivers.contrato.CANALES`).
CANAL = "legacy"

# La salida es el TXT de palotes que importa STARSOFT. Las fechas van como las escribe su hoja, `DD/MM/AAAA`, y
# no en el ISO del estándar: hasta la 2.2 salían en ISO porque `OpcionesArchivo` no tenía dónde decirlo. Hasta
# entonces la salida fue un CSV, provisional, para poder revisarlo columna por columna mientras no se conocía la
# plantilla.
#
# **El TXT va suelto, no dentro de un ZIP** (John, 7-oct-2026): «lo que STARSOFT acepta es el TXT». De la 2.3 a
# la 5.3 se envolvió en un ZIP —se eligió por parecido con el SIRE, sin un caso que lo pidiera— y su pantalla de
# importación no lo abre: pide el archivo de texto. Es la otra mitad de lo que destapó el mes real del
# 7-oct-2026, con el nombre (`salida.nombre`). Por eso `CONTENT_TYPE` es de texto: así `pipeline.respuesta` lo
# devuelve legible además de en base64, como el CSV y los dos Excel.
OPCIONES = OpcionesArchivo(extension=".txt", fecha="DD/MM/AAAA")
FORMATOS = {"compra": "starsoft_txt", "venta": "starsoft_txt"}
CONTENT_TYPE = "text/plain"

# Lo que STARSOFT necesita para no rechazar el archivo, además de lo que el núcleo exige a todo driver de asientos
# (`cuenta_contable` y `tipo_cp`). **Vacío a propósito**, y las dos ausencias son decisiones:
#
# - `centro_costo` NO: en el vídeo de compras la columna va vacía y el narrador dice «de ser necesario… de lo
#   contrario, obviarlo». Exigirlo haría que `diagnosticar` diera por no listo un mes que STARSOFT sí importa.
# - `moneda` NO: exigirla obliga a declarar `monedas_codigo` (`drivers/contrato.py`), y no consta cómo llama
#   STARSOFT a los soles y a los dólares. CONCAR usa MN y US; suponer que STARSOFT hace lo mismo sería inventar.
#
# Las dos se amplían sin romper nada el día que la plantilla lo diga.
# `detraccion` (4.1): escribe la línea de la detracción, así que sin el código del Catálogo 54 la omitiría en silencio.
EXIGE: frozenset[str] = frozenset({"detraccion"})

# Los roles del asiento que STARSOFT **no escribe como fila** (2.5). Su formato no asienta la detracción: la lleva
# en campos de la fila del proveedor (24 afecto, 25 número, 26 fecha, 31 código, 34 tasa, 35 importe), así que el
# traslado a la cuenta de detracciones —que en CONCAR son dos líneas más— no va al archivo, y una compra con
# detracción sale con las mismas TRES filas que una sin ella. Lo confirmó John contra el manual (22-sep-2026): los
# seis ejemplos oficiales llevan tres filas por comprobante y ninguno de ellos tiene detracción.
#
# Las líneas siguen existiendo en el asiento del motor, que es el mismo para todos los destinos; lo que cambia es
# lo que este driver proyecta. Por eso se declaran aquí y no se tocan en el núcleo.
ROLES_DE_LA_DETRACCION = ("detraccion", "recorte")

# En qué ORDEN salen las filas de cada libro, según sus treinta ejemplos oficiales (John, 22-sep-2026): una COMPRA
# va IGV, proveedor, gasto; una VENTA va cliente, IGV, ingreso. No es el del asiento del motor, que en compras saca
# el gasto primero y que en una nota de crédito de ventas invierte el orden al invertirse los sentidos.
#
# Se ordena aquí y no en el núcleo a propósito: **el orden entra en la huella del asiento**, así que moverlo allá
# cambiaría la de CONCAR, la del CSV y la de todos los destinos por un detalle de este formato.
#
# Lo que no case con un rol de estos va al final y conserva su orden relativo, que es lo que hace el segundo
# ejemplo del manual: una compra con dos cuentas de gasto las escribe seguidas, detrás del proveedor.
ORDEN_DE_LAS_FILAS = {"compra": ("impuesto", "tercero"), "venta": ("tercero", "impuesto")}

# --- con qué cuentas nace una empresa que lleva STARSOFT ------------------------------

# STARSOFT numera a OCHO dígitos, y las de fábrica del motor son las del PCGE a seis (`configuracion.py`), que es
# como numeran CONCAR y CONTASIS. Sin esto, un contribuyente de STARSOFT que no hubiera abierto la pantalla de
# configuración exportaba su asiento con el `421201` de CONCAR: no fallaba en ninguna parte, y el archivo lo
# rechazaba su sistema. Se declaran SOLO las que se apartan de lo general (`drivers/contrato.py`).
#
# **Cuatro salen del manual**, de los asientos de ejemplo de compras y de ventas —cuentas que STARSOFT escribe en
# su propia documentación—: facturas por pagar en soles, IGV, clientes en soles e ingresos. **Las otras siete se
# DEDUCEN de su patrón**, y van marcadas una a una: son un punto de partida configurable, igual que las cinco
# siglas heredadas de CONCAR, no un hecho comprobado.
#
# El patrón es el que enseñan las cuatro del manual: **la subcuenta del PCGE de cuatro dígitos más un correlativo
# de cuatro** (4212 → 42120001); las de raíz de cinco —el IGV y la renta de 4ta, que en el PCGE son 40111 y
# 40172— completan con tres (40111 → 40111000). Cada deducida es la misma cuenta de lo general reescrita con ese
# patrón, así que si el contador ve otra en su sistema la cambia desde su pantalla, sin tocar código.
#
# **El bloque va ENTERO y visible** (John, 23-sep-2026), aunque repita lo de fábrica: un driver se lee de un vistazo
# y no obliga a ir a buscar qué hereda. Lo vigila `tests/test_cuentas_del_sistema.py`, que compara con lo general lo
# que tiene que coincidir y se pone rojo si se separan sin que nadie lo haya decidido.
#
# **`compras` y `ventas` no son configuración**: son la cuenta con la que este sistema registra habitualmente una
# compra y una venta, y de ellas **nace el plan de cuentas** de la empresa, para elegirlas comprobante a comprobante
# (`drivers.contrato.plan_base`). **No imputan solas**: hasta la 3.0 una cuenta de gasto o de ingreso por defecto
# suplía a la que nadie puso, y entonces el mes salía «listo para exportar» imputado a un comodín que nadie eligió.
#
# **`compras` es `60110100`** (John, 23-sep-2026, de una instalación real): mercaderías, PCGE 6011. Antes aquí no
# había ninguna y la sembraba la aplicación como comodín — el `62010001` del manual—, que es justo lo que se retiró:
# de respaldo imputaba a mercaderías, en silencio, toda compra a la que nadie le puso cuenta.
CUENTAS_POR_DEFECTO: dict = {
    "cxp": {"PEN": "42120001",                              # del manual
            "USD": "42120002"},                             # deducida
    # Esta NO se escribe en el archivo —STARSOFT no asienta la detracción, ver `ROLES_DE_LA_DETRACCION`—, pero el
    # asiento del motor sí la usa, y es el mismo para todos los destinos. Sin ella ese asiento mostraría la cuenta
    # de seis dígitos de CONCAR en un libro de STARSOFT, que es justo lo que este bloque viene a evitar.
    "cxp_detraccion": {"PEN": "42120003",                   # deducida
                       "USD": "42120003"},                  # deducida (la misma en las dos, como en lo general)
    "honorarios": {"PEN": "42410001",                       # deducida
                   "USD": "42410002"},                      # deducida
    "retencion_4ta": "40172100",                            # deducida
    "igv": "40111000",                                      # del manual
    "clientes": {"PEN": "12120001",                         # del manual
                 "USD": "12120002"},                        # deducida
    "compras": "60110100",                                  # John, 23-sep-2026
    # Del manual, y OJO que la instalación real no la escribe igual: las capturas de John (21-sep-2026) traen
    # `70410100`, un dígito distinto en la divisionaria. Las dos son PCGE 7041 —mercaderías—, así que el plan base
    # sirve para elegir, que es para lo que está. Y la cuenta de ingreso **cambia con el tipo de venta**: la
    # exonerada va a `70610100` y la mixta a `70510100`, que es otra razón para no imputar sola.
    "ventas": "70410001",                                   # del manual (la instalación real: `70410100`)
}


# --- lo que se configura en la sección `starsoft` ------------------------------------

# Los sub-diarios de STARSOFT, que NO son los de CONCAR: compras es `04` y no 11 («el subdiario por defecto
# para compras es cuatro según el sistema contable», vídeo de compras 6:08), y ventas es `03` y no 05
# (John, 20-sep-2026). El de detracción no consta y se queda en el del núcleo hasta que se sepa.
#
# **Van a DOS dígitos, con el cero delante** (John, 21-sep-2026): el vídeo dice «cuatro» y de ahí salió un
# `4` a secas, pero el formato de STARSOFT es `04`, como su `03` de ventas —que sí se escribió bien desde
# el principio y venía delatando la inconsistencia—. Por eso el campo es TEXTO y su patrón admite el cero
# a la izquierda: un sub-diario no es un número, es un código.
#
# Se cambia el VALOR POR DEFECTO del campo que ya declara el asiento, no se declara otro campo: la clave es la
# misma (`sub_diario_compras`) y el núcleo la lee de ahí. Declarar una clave propia sería tener el mismo dato dos
# veces y romper la comprobación de que todo lo que se lee está declarado.
# Las siglas de STARSOFT. Coinciden con las de CONCAR donde menos se espera y divergen donde más duele: `FT` y
# `BV` son iguales, pero la nota de crédito es **`CC`** y no `NC` (vídeo de ventas 14:05). Dejar la tabla del
# asiento sin tocar sacaría un archivo con `NC` dentro, que STARSOFT importaría clasificando la nota de crédito
# como otra cosa: no daría error, daría contabilidad equivocada.
#
# **De las ocho, solo tres constan** —`01`, `03` y `07`— y las otras cinco se heredan de CONCAR como punto de
# partida, no como hecho. Se decidió así, y no dejándolas vacías, por lo que pasa si se dejan: el golden de
# compras del repositorio lleva un recibo de servicios públicos (tipo `14`) y un recibo por honorarios (`02`), así
# que un mes corriente no se exportaría entero. Un driver que se planta ante el comprobante más común de una
# empresa no sirve para probar nada.
#
# El precio es que cinco valores son una suposición, y por eso van marcados aquí, que es donde hay que mirarlos.
# La diferencia con inventar está en que son un DEFECTO configurable, no una regla: el contribuyente los cambia
# desde su sección sin tocar código, y `configuracion_por_defecto` ya advierte de que es «un punto de partida
# razonable, no la verdad de ningún contribuyente». Se confirman con el manual de STARSOFT o con un mes real
# importado, y hasta entonces son lo único de este driver que no se puede afirmar.
TIPOS = {
    "01": {"sigla": "FT"},     # CONSTA: «tipo de documento FT que son las iniciales de factura» (compras 7:34)
    "03": {"sigla": "BV"},     # CONSTA (John, 20-sep-2026)
    "07": {"sigla": "CC"},     # CONSTA: «la sigla para la nota de crédito en este sistema contable es CC» (14:05),
                               # y los tres ejemplos de nota de crédito del manual de VENTAS la traen
    # CONSTA desde el manual (22-sep-2026): sus dos ejemplos de nota de DÉBITO —una penalidad por daños, con el
    # proveedor al haber y referencia a una FT— la escriben `CD`. Hasta hoy iba `ND`, heredada de CONCAR y marcada
    # «[por confirmar] — y es el que más sospecha da, por ser el hermano del 07». La sospecha era buena: es el
    # mismo error que `NC` en vez de `CC`, del que no avisa nadie porque el archivo entra igual.
    "08": {"sigla": "CD"},
    "12": {"sigla": "TK"},     # CONSTA: tres ejemplos de compras (un ticket de combustible)
    "14": {"sigla": "RC"},     # CONSTA: tres ejemplos de compras (un recibo de Claro)
    # Las dos que siguen SIN constar. No aparecen en ningún ejemplo ni en la tabla de campos, y el manual dice que
    # el tipo es «el que tiene registrado TU sistema», o sea de cada instalación: se cotejan con el maestro de
    # cada contribuyente, no se fijan aquí.
    # Las dos salen de la tabla de equivalencias con CONCAR, que es de donde se heredaron las cinco: el `02` es
    # el recibo por honorarios, que en CONCAR tiene además su propio sub-diario (el 15) y aquí no consta ninguno,
    # y el `05` es la boleta de anticipo. **Lo que las cerraría es el maestro de tipos de documento de una
    # instalación real**: un `SELECT` de su tabla de tipos, o un TXT que esa instalación haya importado con un
    # recibo por honorarios dentro. No hace falta esperar a un mes entero.
    "02": {"sigla": "RH"},     # [por confirmar] — de CONCAR, sin su sub-diario propio, que tampoco consta
    "05": {"sigla": "BA"},     # [por confirmar] — de CONCAR
}

# El sub-diario de la detracción va VACÍO, y no es un olvido: en CONCAR las compras con detracción tienen su
# propio registro (el 10) y en STARSOFT no consta que exista. Vacío, el motor las manda al de compras
# (`resolucion.sub_diario`), que es lo que hace cualquier sistema que no los separa. Si STARSOFT tuviera el
# suyo, se pone aquí y las compras con detracción se van solas a él.
POR_DEFECTO = {"sub_diario_compras": "04", "sub_diario_ventas": "03", "sub_diario_detraccion": "", "tipos": TIPOS}

CONFIGURACION = (
    *(replace(campo, por_defecto=POR_DEFECTO[campo.clave]) if campo.clave in POR_DEFECTO else campo
      for campo in CONFIGURACION_DEL_ASIENTO),
    # El tipo de anexo del maestro de STARSOFT, la columna F de los dos libros. Es un código del contribuyente y
    # NO el tipo de documento de SUNAT (que para un RUC es `6`), así que va configurado y no deducido.
    #
    # **Son dos y no uno** (John, 21-sep-2026): el maestro de proveedores y el de clientes son distintos en
    # STARSOFT, así que compras lleva `03` y ventas `02`. Hasta la 2.1 había una sola clave `tipo_anexo`, vacía
    # por defecto, que se escribía igual en los dos libros: eso obligaba a elegir cuál de los dos maestros salía
    # bien. El `03` consta en el vídeo de compras; el `02` de ventas lo pone John.
    Campo("tipo_anexo_proveedor", "texto", "03", titulo="Tipo de anexo del proveedor", grupo="registro",
          patron=r"^[0-9]{0,3}$",
          ayuda="El código de tipo de anexo de tu STARSOFT para PROVEEDORES, en compras (en el ejemplo, 03). "
                "Vacío, la columna se deja en blanco."),
    Campo("tipo_anexo_cliente", "texto", "02", titulo="Tipo de anexo del cliente", grupo="registro",
          patron=r"^[0-9]{0,3}$",
          ayuda="El código de tipo de anexo de tu STARSOFT para CLIENTES, en ventas (en el ejemplo, 02). "
                "Vacío, la columna se deja en blanco."),
    # La columna CONV. En los dos vídeos vale VTA en todas las filas, también en compras.
    Campo("tipo_conversion", "texto", "VTA", titulo="Tipo de conversión", grupo="monedas", patron=r"^[A-Z]{0,5}$",
          ayuda="Cómo llama tu STARSOFT al tipo de conversión de moneda. En los ejemplos, VTA."),
)

# --- la plantilla -------------------------------------------------------------------

# ── Las columnas ────────────────────────────────────────────────────────────────────────────────────
#
# **LA FUENTE CAMBIÓ EL 22-sep-2026.** Hasta entonces estas dos tablas se calcaron de capturas de la hoja
# `PLANTILLA` de Excel y de la narración de dos vídeos. Ahora existe la documentación de STARSOFT
# —`CONT_COMPRAS` y `CONT_VENTAS`, «Sistema de Contabilidad · Documentación»—, con la tabla de campos
# (longitud, obligatoriedad, formato y condiciones) y **ejemplos de TXT sacados del propio sistema**.
# Los PDF no están en el repositorio —son de otra empresa y esto es público—: lo que dicen está volcado
# en `CAMPOS_DEL_MANUAL`, al final de este fichero.
#
# **Y trajeron la regla que la plantilla de Excel escondía: el número del ítem en el manual NO es su
# posición en la línea.** Varias columnas dependen de un «concepto general» de cada instalación, y el
# manual dice literal: «Para las columnas que se habilitan con un concepto general: si el concepto está
# en falso, no incluir la columna». O sea que no ocupan sitio. La hoja de Excel las tiene todas —por eso
# las capturas las mostraban— pero el TXT no.
#
# Escribiéndolas salían **38 campos en compras y 34 en ventas**; los ejemplos oficiales traen **35 y 27**,
# que es lo que hay aquí. Las condicionales quedan listadas abajo, con el concepto del que depende cada
# una: no se inventan, se sabe que existen y por qué no se escriben.
#
# Para un TXT la LETRA es la posición en la línea (A = campo 1), no la columna de una hoja de cálculo.

COMPRAS = (
    ("A", "CTA CONTABLE", "texto"),
    ("B", "AÑO Y MES PROCESO", "texto"),
    ("C", "SUBDIARIO", "texto"),
    ("D", "COMPROBANTE", "texto"),
    ("E", "FECHA DOCUMENTO", "fecha"),
    ("F", "TIPO ANEXO", "texto"),
    ("G", "CODIGO PROVEEDOR", "texto"),
    ("H", "TIPO DOCUMENTO", "texto"),
    ("I", "NRO DOCUMENTO", "texto"),
    ("J", "FECHA VENCIMIENTO", "fecha"),
    ("K", "IGV", "importe"),
    ("L", "TASA IGV", "numero"),
    ("M", "IMPORTE", "importe"),
    ("N", "CONV", "texto"),
    ("O", "FECHA REGISTRO", "fecha"),
    ("P", "TIPO CAMBIO", "numero"),
    ("Q", "GLOSA", "texto"),
    ("R", "DESTINO", "texto"),
    ("S", "PORC OPE MIXTA", "numero"),
    ("T", "VALOR CIF", "importe"),
    ("U", "TIPO DOC REF", "texto"),
    ("V", "NRO DOC REF", "texto"),
    ("W", "CENTRO DE COSTOS", "texto"),
    ("X", "DETRACCION", "texto"),
    ("Y", "NRO DOC DETRACCION", "texto"),
    ("Z", "FECHA DETRACCION", "fecha"),
    ("AA", "FECHA DOC REF", "fecha"),
    ("AB", "GLOSA MOVIMIENTO", "texto"),
    ("AC", "DOCUMENTO ANULADO", "texto"),
    ("AD", "IGV POR APLICAR", "texto"),
    ("AE", "CODIGO DETRACCION", "texto"),
    ("AF", "IMPORTACION", "texto"),
    ("AG", "DEBE / HABER", "texto"),
    ("AH", "TASA DETRACCION", "numero"),
    ("AI", "IMPORTE DETRACCION", "importe"),
)

# Las que el manual llama condicionales y NO se escriben (ver `CONDICIONALES` abajo): en compras son los
# items 36 `NRO. DE FILE`, 37 `OTROS TRIBUTOS`, 38 `IMP. A LA BOLSA DE PLASTICO` y 39 `TIPO OPERACION DE
# DETRACCION`. Hasta la 2.3 las tres primeras se escribian siempre, y por eso la linea salia con 38 campos
# donde el sistema espera 35.

# Ventas no comparte juego de columnas con compras: lleva el RUC y la razón social del cliente donde compras
# lleva el código del proveedor, y no lleva DESTINO —que es del crédito fiscal de una adquisición—. Y coloca
# las dos fechas AL REVÉS: aquí el campo 5 es la de registro y el 11 la de emisión; en compras, al contrario.
#
# 27 campos, los de los ejemplos del manual. Fuera quedan siete condicionales (ver `CONDICIONALES`).

VENTAS = (
    ("A", "CTA CONTABLE", "texto"),
    ("B", "AÑO Y MES PROCESO", "texto"),
    ("C", "SUBDIARIO", "texto"),
    ("D", "COMPROBANTE", "texto"),
    ("E", "FECHA REGISTRO", "fecha"),
    ("F", "TIPO ANEXO", "texto"),
    ("G", "CODIGO CLIENTE", "texto"),
    ("H", "TIPO DOCUMENTO", "texto"),
    ("I", "NRO DOCUMENTO", "texto"),
    ("J", "FECHA EMISION", "fecha"),
    ("K", "DOC REFERENCIA", "texto"),
    ("L", "NRO DOC REF", "texto"),
    ("M", "IGV", "importe"),
    ("N", "TASA IGV", "numero"),
    ("O", "IMPORTE", "importe"),
    ("P", "CONV", "texto"),
    ("Q", "TIPO CAMBIO", "numero"),
    ("R", "GLOSA", "texto"),
    ("S", "GLOSA MOVIMIENTO", "texto"),
    ("T", "DOCUMENTO ANULADO", "texto"),
    ("U", "DEBE / HABER", "texto"),
    ("V", "RUC CLIENTE", "texto"),
    ("W", "RAZON SOCIAL", "texto"),
    ("X", "CENTRO DE COSTOS", "texto"),
    ("Y", "FECHA VENCIMIENTO", "fecha"),
    ("Z", "FECHA DOC REFERENCIA", "fecha"),
    ("AA", "EXPORTACION", "texto"),
)

# Las columnas que el manual declara pero que NO se escriben, con el concepto general del que depende cada
# una. Se listan para que consten: si una instalación las tiene en verdadero, su archivo lleva esas columnas
# de más y este driver no las pone. El día que haga falta, se sabe cuáles son y en qué posición van.
#
# «Para las columnas que se habilitan con un concepto general: si el concepto está en falso, no incluir la
# columna» (CONT_COMPRAS y CONT_VENTAS, «Datos generales»).
CONDICIONALES = {
    "compra": (
        (36, "NRO. DE FILE", "PERS_SETOURS"),
        (37, "OTROS TRIBUTOS", "DATOS_ADIC_COM_TXT"),
        (38, "IMP. A LA BOLSA DE PLASTICO", "el check de impuesto a la bolsa"),
        (39, "TIPO OPERACION DE DETRACCION", "IMPDX_TIPOPE_DETRAC"),
    ),
    "venta": (
        (10, "NUM. DE DOC. FINAL", "DATOS_ADIC_VTAS_TXT"),
        (15, "VALOR ISC", "MIGRA_ISC_TXT"),
        (16, "OTROS TRIBUTOS", "DATOS_ADIC_VTAS_TXT"),
        (31, "NRO. DE FILE", "PERS_SETOURS"),
        (32, "EXONERADO", "EXONERADO_TXT"),
        (33, "OTROS CARGOS", "OTROS_CARGOS_VTA"),
        (34, "IMP. A LA BOLSA DE PLASTICO", "el check de impuesto a la bolsa"),
    ),
}

COLUMNAS = {"compra": COMPRAS, "venta": VENTAS}

# La columna del centro de costo, para que el contribuyente elija dónde va (`COLUMNAS_ELEGIBLES` del contrato).
COLUMNAS_ELEGIBLES = {"centro_costo": (
    Columna("centro_costo", "CENTRO DE COSTOS", {"compra": "W", "venta": "X"}, fija=True,
            ayuda="En la línea del gasto o del ingreso, cuando su cuenta lleva centro de costo.",
            rol="principal", campo="centro_costo"),
)}

# --- los valores propios de STARSOFT ------------------------------------------------

# El destino de la adquisición, la columna R. Los cinco valores salen de la narración del vídeo de compras
# (8:46-9:10), y los tres primeros mapean 1:1 con `destino_igv` del estándar (Anexo 11 del SIRE, campos 15-20).
#
# ⚠️ El 004 y el 005 **no** salen de `destino_igv`: se deducen del comprobante, y la precedencia entre ellos está
# `[por confirmar]` —un comprobante con DUA y destino mixto a la vez hoy sale como 005—.
DESTINO = {"DG": "001", "DGNG": "002", "DNG": "003"}
DESTINO_NO_GRAVADA = "004"
DESTINO_IMPORTACION = "005"

# La columna del documento anulado (`AC` en compras, `T` en ventas; el campo 29 y el 23 del manual). Sale `0`
# y no en blanco (John, 21-sep-2026): un comprobante que está entrando al registro no está anulado, y decirlo es
# más claro que callarlo. Las dos formas valen: el manual dice «Poner 0 o dejarlo en blanco» y la hoja del vídeo
# de compras lo rotula «Blanco o `0` por defecto» (10:49). Entre las dos se elige la que afirma.
#
# **El motor no sabe anular**: no hay un comprobante anulado que llegue hasta aquí, porque un comprobante
# excluido no entra en el archivo. Si algún día el estándar lo trae, esta constante deja de ser el único
# valor posible y pasa a ser el valor por defecto de verdad.
NO_ANULADO = "0"

# La columna `IGV POR APLICAR` de compras (`AD`). Su hoja dice «`0` o `1`, donde `1` es que el IGV está
# PENDIENTE de aplicación», y la captura de la hoja real la muestra con `0` en todas las filas, así que el
# defecto es afirmar que no está pendiente (John, 21-sep-2026, tras ver la captura).
#
# **El motor no sabe diferir el crédito fiscal**: no hay hoy un comprobante que llegue aquí con el IGV
# pendiente. El día que el estándar lo traiga, esta constante deja de ser el único valor posible.
IGV_NO_PENDIENTE = "0"

# A cuánto se CORTA la glosa al escribirla. Está en la cabecera de la propia hoja `PARAMETROS` («GLOSA DEL
# MOVIMIENTO · Máximo 60 caracteres»), así que es un hecho y no una deducción.
#
# Hasta la 2.6 esto no cortaba: medía, y un comprobante que se pasara **detenía la exportación del mes entero**
# con un `no_caben`. Lo quitó John el 22-sep-2026 al encontrarse cuatro facturas parándole el archivo, y tenía
# razón: la glosa es texto libre, cortada sigue diciendo lo que decía, y los otros dos drivers la cortaban desde
# siempre. Lo que no se corta es un CÓDIGO —una cuenta o una serie cortadas serían otra cuenta y otra serie—.
LARGO_GLOSA = 60


# ── La tabla de campos del manual ───────────────────────────────────────────────────────────────────
#
# **Esto es la fuente, no una validación.** Es lo que dicen `CONT_COMPRAS` y `CONT_VENTAS` del fabricante, leídos
# el 22-sep-2026 y volcados aquí porque los PDF no pueden entrar a un repositorio público: 39 ítems en compras y 34
# en ventas, con su longitud, su obligatoriedad y la condición que el manual les pone. **Nada de esto se comprueba
# todavía** —`proyeccion.no_caben()` devuelve `{}` a propósito—, y activarlo pide lo único que lo probaría: un
# archivo que STARSOFT haya rechazado por longitud. Está anotado en el §8 de la hoja de ruta.
#
# El número es el del MANUAL y no la posición en la línea: las columnas que dependen de un concepto general no se
# escriben y no ocupan sitio (`CONDICIONALES`, arriba). La longitud se escribe como la distingue el manual: `≤18`
# donde dice «Hasta 18», y `6` donde dice 6 a secas, que es exacto. `18,2` es dieciocho con dos decimales.
CAMPOS_DEL_MANUAL = {
    "compra": (
        ( 1, "CUENTA CONTABLE",                     "≤18",  True,
             "A ultimo nivel. Ejemplos del manual: 42120001, 40111000, 62010001"),
        ( 2, "ANO Y MES DE PROCESO",                "6",    True,  "AAAAMM. Todos los registros, del mismo periodo"),
        ( 3, "SUBDIARIO",                           "≤2",   True,  "Del mantenimiento de Subdiarios de Contabilidad"),
        ( 4, "COMPROBANTE",                         "4",    True,
             "Correlativo de 4 digitos, rellenando con ceros a la izquierda"),
        ( 5, "FECHA DEL DOCUMENTO",                 "≤10",  True,
             "Menor o igual al campo 15 y debe corresponder al periodo"),
        ( 6, "TIPO DE ANEXO",                       "≤2",   False,
             "Obligatorio si la cuenta tiene Tipo de Anexo. Proveedores: 03"),
        ( 7, "CODIGO DEL PROVEEDOR",                "≤11",  False,
             "Obligatorio si la cuenta tiene Tipo de Anexo y el anexo existe"),
        ( 8, "TIPO DE DOCUMENTO",                   "≤2",   True,
             "El que tiene registrado TU sistema (FT, BV, NC...)"),
        ( 9, "SERIE Y NUMERO DEL DOCUMENTO",        "≤21",  True,
             "Los 4 primeros son la serie; si es de 3, un espacio en blanco y el numero desde la quinta"),
        (10, "FECHA DE VENCIMIENTO",                "≤10",  False, "Si viene, mayor o igual al campo 5"),
        (11, "IGV",                                 "≤18,2",True,  "Solo si el campo 1 es una cuenta de Proveedores"),
        (12, "TASA IGV",                            "≤10,2",True,  "Valor fijo del IGV vigente (18)"),
        (13, "IMPORTE TOTAL DEL DOCUMENTO",         "≤18,2",True,
             "En la cuenta de Proveedores, el total; en las demas, el importe de la cuenta"),
        (14, "TIPO DE CONVERSION DEL TIPO DE CAMBIO","3",    True,  "Puede ser VTA o ESP. Sin distinguir por cuenta"),
        (15, "FECHA DE REGISTRO",                   "≤10",  True,  "Debe corresponder al periodo informado"),
        (16, "TIPO DE CAMBIO",                      "≤10,3",True,  "Obligatorio si el campo 14 es ESP"),
        (17, "GLOSA",                               "≤60",  False, "Hasta 60 caracteres"),
        (18, "TIPO DE DESTINO DE LA COMPRA",        "3",    True,
             "001 gravada . 002 mixta . 003 no gravada . 004 no gravadas . 005 importacion"),
        (19, "PORCENTAJE PARA OPERACIONES MIXTAS",  "≤18,2",False, "Solo con destino 002"),
        (20, "VALOR CIF",                           "≤18,2",False, "Solo con destino 005"),
        (21, "TIPO DE DOCUMENTO DE REFERENCIA",     "≤2",   False,
             "Obligatorio si el campo 8 es nota de credito o debito"),
        (22, "SERIE Y NUMERO DEL DOC. DE REFERENCIA","≤21",  False, "Misma regla de serie que el campo 9"),
        (23, "CENTRO DE COSTO",                     "≤10",  False, "Obligatorio si la cuenta lo tiene configurado"),
        (24, "AFECTO A DETRACCION",                 "1",    False, "1 si lo es; si no, 0 o en blanco"),
        (25, "NUMERO DE DETRACCION",                "≤17",  False, "Solo si esta afecto a detraccion"),
        (26, "FECHA DE DETRACCION",                 "≤10",  False, "Solo si esta afecto a detraccion"),
        (27, "FECHA DEL DOC. DE REFERENCIA",        "≤10",  False,
             "Obligatorio si el campo 8 es nota de credito o debito"),
        (28, "GLOSA DEL MOVIMIENTO",                "≤60",  False, ""),
        (29, "DOC. ANULADO",                        "1",    True,  "Poner 0 o dejarlo en blanco"),
        (30, "IGV POR APLICAR",                     "1",    False, "0 o 1"),
        (31, "CODIGO DE LA DETRACCION",             "5",    False, "Solo si esta afecto a detraccion"),
        (32, "IMPORTACION",                         "1",    False, "0 o 1"),
        (33, "DEBE O HABER",                        "1",    True,  "D o H"),
        (34, "TASA DE DETRACCION",                  "≤18,2",False, "Solo si esta afecto a detraccion"),
        (35, "IMPORTE DE DETRACCION",               "≤18,2",False, "Solo si esta afecto a detraccion"),
        (36, "NRO. DE FILE",                        "≤12",  False,
             "solo si el concepto general `PERS_SETOURS` es verdadero"),
        (37, "OTROS TRIBUTOS",                      "≤18,2",False, "solo si `DATOS_ADIC_COM_TXT` es verdadero"),
        (38, "IMP. A LA BOLSA DE PLASTICO",         "≤18,2",False,
             "solo con el check de impuesto a la bolsa. Y solo en la fila de la cuenta de proveedores (42)"),
        (39, "TIPO OPERACION DE DETRACCION",        "2",    False, "solo si `IMPDX_TIPOPE_DETRAC` es verdadero"),
    ),
    "venta": (
        ( 1, "CUENTA CONTABLE",              "≤18",  True,
             "A ultimo nivel. Ejemplos del manual: 12120001, 40111000, 70410001"),
        ( 2, "ANO Y MES PROCESO",            "6",    True,  "AAAAMM"),
        ( 3, "SUBDIARIO",                    "≤2",   True,  ""),
        ( 4, "COMPROBANTE",                  "4",    True,  "Correlativo de 4 digitos con ceros a la izquierda"),
        ( 5, "FECHA DE REGISTRO",            "≤10",  True,  "Debe corresponder al periodo informado"),
        ( 6, "TIPO ANEXO",                   "≤2",   False, "Clientes: 02"),
        ( 7, "CODIGO CLIENTE",               "≤11",  False, ""),
        ( 8, "TIPO DE DOCUMENTO",            "≤2",   True,  "El que tiene registrado TU sistema"),
        ( 9, "NUMERO DE DOCUMENTO",          "≤21",  True,
             "4 primeros la serie; si tiene 3, un espacio; sin serie, cuatro espacios"),
        (10, "NUM. DE DOC. FINAL",           "≤21",  False,
             "solo si `DATOS_ADIC_VTAS_TXT` es verdadero. Para BV (03), TK (12) y codigo SUNAT 99"),
        (11, "FECHA DE EMISION DEL DOCUMENTO","≤10",  True,
             "Menor o igual al campo 5 y debe corresponder al periodo"),
        (12, "DOCUMENTO DE REFERENCIA",      "≤2",   False, "Obligatorio en nota de credito o debito"),
        (13, "NUMERO DE DOC. DE REFERENCIA", "≤21",  False, ""),
        (14, "IGV",                          "≤18,2",True,
             "Solo si el campo 1 es una cuenta de Clientes (12); en las demas, en blanco"),
        (15, "VALOR ISC",                    "≤18,2",False, "solo si `MIGRA_ISC_TXT` es verdadero"),
        (16, "OTROS TRIBUTOS",               "≤18,2",False, "solo si `DATOS_ADIC_VTAS_TXT` es verdadero"),
        (17, "TASA DEL IGV",                 "≤10,2",True,  "Solo en la cuenta de Clientes; valor fijo (18)"),
        (18, "IMPORTE",                      "≤18,2",True,
             "En Clientes, el total del documento; en las demas, el de la cuenta"),
        (19, "CONVERSION DE TIPO DE CAMBIO", "3",    True,  "VTA o ESP. En las demas cuentas puede estar en blanco"),
        (20, "TIPO DE CAMBIO",               "≤10,3",True,  "Obligatorio si el campo 19 es ESP"),
        (21, "GLOSA",                        "≤60",  False, "Hasta 60 caracteres"),
        (22, "GLOSA DE MOVIMIENTO",          "≤60",  False, ""),
        (23, "DOCUMENTO ANULADO",            "1",    True,  "0 no anulado . 1 anulado"),
        (24, "DEBE / HABER",                 "1",    True,  "D o H"),
        (25, "RUC DEL CLIENTE",              "11",   False, "Solo si el campo 1 es una cuenta de Clientes"),
        (26, "RAZON SOCIAL DEL CLIENTE",     "≤50",  False, "Idem"),
        (27, "CENTRO DE COSTO",              "≤10",  False, "Si la cuenta lo tiene configurado"),
        (28, "FECHA DE VENCIMIENTO",         "≤10",  False, "Si viene, mayor o igual al campo 11"),
        (29, "FECHA DEL DOC. REFERENCIA",    "≤10",  False, ""),
        (30, "EXPORTACION",                  "1",    True,  "0 local . 1 exportacion"),
        (31, "NRO. DE FILE",                 "≤12",  False, "solo si `PERS_SETOURS` es verdadero"),
        (32, "EXONERADO",                    "≤18,2",False,
             "solo si `EXONERADO_TXT` es verdadero. Y solo en la fila de Clientes"),
        (33, "OTROS CARGOS",                 "≤18,2",False,
             "solo si `OTROS_CARGOS_VTA` es verdadero. Y solo en la fila de Clientes"),
        (34, "IMP. A LA BOLSA DE PLASTICO",  "≤18,2",False,
             "solo con el check de impuesto a la bolsa. Y solo en la fila de Clientes"),
    ),
}
