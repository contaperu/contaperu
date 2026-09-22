"""Los DATOS del driver STARSOFT: su identidad en el contrato, sus columnas y lo que se configura.

**De dónde sale cada cosa.** La fuente es **la documentación oficial de STARSOFT** desde el 22-sep-2026 —la tabla
de campos de compras y de ventas, con ejemplos de TXT sacados del propio sistema—, y de ahí salen las columnas, las
dos fechas y las cuentas que constan. Lo anterior a ella se levantó de dos vídeos del canal *ArchivoExcel*
—«Importar asientos contables de compras al Star Soft» y su gemelo de ventas— y de las capturas de la hoja
`PARAMETROS`; sigue vigente donde el manual no dice nada, y **el manual gana donde los dos hablan**. Está todo en
`STARSOFT-INTEGRACION.md`, columna por columna, cada cosa con su fuente.

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

# La salida es el TXT de palotes que importa STARSOFT, envuelto en un ZIP (John, 22-sep-2026). Las fechas van
# como las escribe su hoja, `DD/MM/AAAA`, y no en el ISO del estándar: hasta la 2.2 salían en ISO porque
# `OpcionesArchivo` no tenía dónde decirlo. Hasta entonces la salida fue un CSV, provisional, para poder
# revisarlo columna por columna mientras no se conocía la plantilla.
OPCIONES = OpcionesArchivo(extension=".txt", fecha="DD/MM/AAAA", comprimir=True)
FORMATOS = {"compra": "starsoft_txt", "venta": "starsoft_txt"}
CONTENT_TYPE = "application/zip"

# Lo que STARSOFT necesita para no rechazar el archivo, además de lo que el núcleo exige a todo driver de asientos
# (`cuenta_contable` y `tipo_cp`). **Vacío a propósito**, y las dos ausencias son decisiones:
#
# - `centro_costo` NO: en el vídeo de compras la columna va vacía y el narrador dice «de ser necesario… de lo
#   contrario, obviarlo». Exigirlo haría que `diagnosticar` diera por no listo un mes que STARSOFT sí importa.
# - `moneda` NO: exigirla obliga a declarar `monedas_codigo` (`drivers/contrato.py`), y no consta cómo llama
#   STARSOFT a los soles y a los dólares. CONCAR usa MN y US; suponer que STARSOFT hace lo mismo sería inventar.
#
# Las dos se amplían sin romper nada el día que la plantilla lo diga.
EXIGE: frozenset[str] = frozenset()

# Los roles del asiento que STARSOFT **no escribe como fila** (2.5). Su formato no asienta la detracción: la lleva
# en campos de la fila del proveedor (24 afecto, 25 número, 26 fecha, 31 código, 34 tasa, 35 importe), así que el
# traslado a la cuenta de detracciones —que en CONCAR son dos líneas más— no va al archivo, y una compra con
# detracción sale con las mismas TRES filas que una sin ella. Lo confirmó John contra el manual (22-sep-2026): los
# seis ejemplos oficiales llevan tres filas por comprobante y ninguno de ellos tiene detracción.
#
# Las líneas siguen existiendo en el asiento del motor, que es el mismo para todos los destinos; lo que cambia es
# lo que este driver proyecta. Por eso se declaran aquí y no se tocan en el núcleo.
ROLES_DE_LA_DETRACCION = ("detraccion", "detraccion_tercero")

# En qué ORDEN salen las filas de una COMPRA: primero el IGV, luego el proveedor y al final el gasto (John,
# 22-sep-2026). Es el de los dieciocho ejemplos oficiales, y el contrario al del asiento del motor, que saca el
# gasto primero. Se ordena aquí y no en el núcleo a propósito: **el orden entra en la huella del asiento**, así
# que moverlo allá cambiaría la de todos los destinos por un detalle de este formato. En VENTAS no hace falta —
# sus ejemplos van cliente, IGV, ingreso, que ya es el orden del núcleo desde la 2.2—.
#
# Lo que no case con un rol de estos va al final y conserva su orden relativo, que es lo que hace el segundo
# ejemplo del manual: una compra con dos cuentas de gasto las escribe seguidas, detrás del proveedor.
ORDEN_DE_LA_COMPRA = ("igv", "tercero")

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
# **`gasto` NO se declara, y es una decisión.** En lo general va vacía a propósito —es el comodín «63/65», que no
# es una cuenta— y lo que trae el manual (`62010001`) es una cuenta de gasto REAL, mercaderías. De respaldo
# imputaría a mercaderías, en silencio, toda compra a la que nadie le puso cuenta. El comodín que evita que la
# exportación se bloquee es de la aplicación, que lo SIEMBRA y el contador lo ve en su pantalla; un respaldo del
# motor actúa sin que nadie lo haya escrito. Es la misma regla que la sigla que no se inventa.
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
    "ventas": "70410001",                                   # del manual
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
# El precio es que cinco valores son una suposición, y por eso van marcados aquí y en `STARSOFT-INTEGRACION.md`.
# La diferencia con inventar está en que son un DEFECTO configurable, no una regla: el contribuyente los cambia
# desde su sección sin tocar código, y `configuracion_por_defecto` ya advierte de que es «un punto de partida
# razonable, no la verdad de ningún contribuyente». Se confirman con el manual de STARSOFT o con un mes real
# importado, y hasta entonces son lo único de este driver que no se puede afirmar.
TIPOS = {
    "01": {"sigla": "FT"},     # CONSTA: «tipo de documento FT que son las iniciales de factura» (compras 7:34)
    "03": {"sigla": "BV"},     # CONSTA (John, 20-sep-2026)
    "07": {"sigla": "CC"},     # CONSTA: «la sigla para la nota de crédito en este sistema contable es CC» (14:05)
    "02": {"sigla": "RH"},     # [por confirmar] — de CONCAR, sin su sub-diario propio, que tampoco consta
    "05": {"sigla": "BA"},     # [por confirmar]
    "08": {"sigla": "ND"},     # [por confirmar] — y es el que más sospecha da, por ser el hermano del 07
    "12": {"sigla": "TK"},     # [por confirmar]
    "14": {"sigla": "RC"},     # [por confirmar]
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
# en `STARSOFT-INTEGRACION.md`.
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

# La columna del documento anulado (`Y` en compras, `S` en ventas). Sale `0` y no en blanco (John,
# 21-sep-2026): un comprobante que está entrando al registro no está anulado, y decirlo es más claro que
# callarlo. La hoja de compras del vídeo admite las dos formas —«Blanco o `0` por defecto»,
# `STARSOFT-INTEGRACION.md`— y entre las dos se elige la que afirma.
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

# Lo que no cabe en el formato. El largo de la glosa está escrito en la cabecera de la propia hoja `PARAMETROS`
# («GLOSA DEL MOVIMIENTO · Máximo 60 caracteres»), así que es un hecho y no una deducción.
LARGO_GLOSA = 60
MOTIVOS = {
    "glosa": f"con una glosa de más de {LARGO_GLOSA} caracteres, que es lo que admite la plantilla de STARSOFT",
}
