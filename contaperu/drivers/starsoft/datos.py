"""Los DATOS del driver STARSOFT: su identidad en el contrato, sus columnas y lo que se configura.

**De dónde sale cada cosa.** Lo levantado el 20-sep-2026 de dos vídeos del canal *ArchivoExcel* —«Importar
asientos contables de compras al Star Soft» y su gemelo de ventas— leyendo sus capturas y su transcripción, más
las capturas de la hoja `PARAMETROS` de los dos aplicativos. Está todo en `STARSOFT-INTEGRACION.md`, columna por
columna y con su minuto.

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

# Mientras no haya plantilla oficial, la salida es un CSV de las filas proyectadas: se puede abrir y revisar
# columna por columna con un contador, que es justo lo que hace falta antes de tener el .xlsx. El día que llegue
# la plantilla cambia esto y el módulo `salida.py`; la proyección no se toca.
OPCIONES = OpcionesArchivo(extension=".csv")
FORMATOS = {"compra": "starsoft_csv", "venta": "starsoft_csv"}
CONTENT_TYPE = "text/csv; charset=utf-8"

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

# Las columnas, leídas de la captura de la hoja `PLANTILLA` de compras. Las letras cuadran desde la M, que en la
# captura está seleccionada con el IGV de la segunda línea (`M3 = 167.3`).
#
# ⚠️ **De la A a la E están INFERIDAS**, no leídas: quedan fuera de cuadro en la captura y salen de la narración,
# que las nombra primero y en ese orden («las cuentas contables, el periodo tributario, el subdiario, el voucher
# o comprobante, la fecha», compras 12:51). Encajan justo en el hueco, pero **hasta que una plantilla oficial lo
# confirme, el orden de esas cinco es una hipótesis**, no un hecho.
# Las 38 columnas de la hoja `PLANTILLA` de compras, **leídas del archivo**: cuatro capturas de la hoja
# abierta en Excel con datos dentro (John, 21-sep-2026), como las de ventas. Corrigieron el mapa que se
# había levantado del vídeo: faltaban las CUATRO columnas de la detracción que van juntas —`DETRACCION`,
# `NRO DOC DETRACCION`, `FECHA DETRACCION`— y `FECHA DOC REF`, así que desde la `X` todo estaba corrido.
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
    ("AJ", "NRO FILE", "texto"),
    ("AK", "OTROS TRIBUTOS", "importe"),
    ("AL", "IMP BOLSA", "importe"),
)

# Ventas no comparte juego de columnas con compras: lleva el RUC y la razón social del cliente donde compras lleva
# el código del proveedor y el tipo de anexo, y no lleva DESTINO —que es del crédito fiscal de una adquisición—.
# Leídas de la cabecera en pantalla del vídeo de ventas (11:46) y de la narración que las recorre (12:24-13:07).
# Las 34 columnas de la hoja `PLANTILLA` de ventas, **leídas del archivo** y no de la narración del vídeo:
# cuatro capturas de la hoja abierta en Excel con datos dentro (John, 21-sep-2026). Es la fuente más
# fuerte que tiene este driver, y corrigió el mapa entero: faltaban `TIPO ANEXO` y `CODIGO CLIENTE`, y
# desde la `G` todo estaba corrido una posición.
#
# Los nombres son los de la plantilla, literales, aunque no coincidan con los de compras (`CTA CONTABLE`
# aquí y `CUENTA` allá): son dos plantillas distintas y cada una se calca de SU fuente. La de compras
# sigue levantada del vídeo y espera su propia captura.
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
    ("J", "NRO DOC FINAL", "texto"),
    ("K", "FECHA EMISION", "fecha"),
    ("L", "DOC REFERENCIA", "texto"),
    ("M", "NRO DOC REF", "texto"),
    ("N", "IGV", "importe"),
    ("O", "VALOR ISC", "importe"),
    ("P", "OTROS TRIB", "importe"),
    ("Q", "TASA IGV", "numero"),
    ("R", "IMPORTE", "importe"),
    ("S", "CONV", "texto"),
    ("T", "TIPO CAMBIO", "numero"),
    ("U", "GLOSA", "texto"),
    ("V", "GLOSA MOVIMIENTO", "texto"),
    ("W", "DOCUMENTO ANULADO", "texto"),
    ("X", "DEBE / HABER", "texto"),
    ("Y", "RUC CLIENTE", "texto"),
    ("Z", "RAZON SOCIAL", "texto"),
    ("AA", "CENTRO DE COSTOS", "texto"),
    ("AB", "FECHA VENCIMIENTO", "fecha"),
    ("AC", "FECHA DOC REFERENCIA", "fecha"),
    ("AD", "EXPORTACION", "texto"),
    ("AE", "NRO FILE", "texto"),
    ("AF", "EXONERADO", "importe"),
    ("AG", "OTROS CARGOS", "importe"),
    ("AH", "IMP BOLSA", "importe"),
)

COLUMNAS = {"compra": COMPRAS, "venta": VENTAS}

# La columna del centro de costo, para que el contribuyente elija dónde va (`COLUMNAS_ELEGIBLES` del contrato).
COLUMNAS_ELEGIBLES = {"centro_costo": (
    Columna("centro_costo", "CENTRO DE COSTOS", {"compra": "W", "venta": "AA"}, fija=True,
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

# Lo que no cabe en el formato. El largo de la glosa está escrito en la cabecera de la propia hoja `PARAMETROS`
# («GLOSA DEL MOVIMIENTO · Máximo 60 caracteres»), así que es un hecho y no una deducción.
LARGO_GLOSA = 60
MOTIVOS = {
    "glosa": f"con una glosa de más de {LARGO_GLOSA} caracteres, que es lo que admite la plantilla de STARSOFT",
}
