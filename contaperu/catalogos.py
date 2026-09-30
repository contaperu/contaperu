"""Catálogos de SUNAT que usa el motor (los que hacen falta, no todos).

Fuentes: Anexo 1 de la RS 112-2021 (documentos de identidad, monedas y tipos de
comprobante del RVIE), Anexo 1 de la RS 040-2022 (tipos de comprobante del RCE) y
Anexo 3 de la RS 169-2015 (tipos de medio de pago). Los códigos de tributo (1000,
9997…) son el Catálogo 05 de la factura electrónica (UBL 2.1).

**Un catálogo se nombra por lo que ES, nunca por su número de tabla.** Cada anexo de SUNAT numera las suyas
empezando por 1, así que hay una «Tabla 1» de documentos de identidad (Anexo 1 de la RS 112-2021) y otra de medios de
pago (Anexo 3 de la RS 169-2015), y el número suelto no identifica nada: solo vale dentro de su cita, que es donde
vive, en `fuente`. Y el número puede cambiar con la siguiente resolución; lo que el catálogo es, no.

**Los catálogos viven en datos, con su fuente** (1.1, primer paso del hito C1 de la hoja de ruta): los tipos de
comprobante, los documentos de identidad, las monedas y los medios de pago se leen de `datos/sunat/catalogos.json`, y
`FUENTES` dice de dónde sale cada uno. Los nombres y los tipos de siempre no cambian. Lo demás de este módulo son
reglas del motor sobre esos códigos, con su porqué al lado.
"""
from __future__ import annotations

from decimal import Decimal

from . import _datos

_CATALOGOS = _datos.leer_json("datos/sunat/catalogos.json")
if not _CATALOGOS:
    raise FileNotFoundError("No encuentro los catálogos de SUNAT (datos/sunat/catalogos.json)")
# De dónde sale cada catálogo, por su nombre: ninguno entra sin fuente.
FUENTES: dict[str, str] = {nombre: tabla["fuente"] for nombre, tabla in _CATALOGOS.items()}

# ── El canal: la API del SIRE, descrita (no ejecutada) ───────────────────────
# El motor NO sale a la red y no va a salir: `tests/test_frontera.py` prohíbe importar httpx o
# socket, y `conftest.py` mata cualquier conexión. Esto no es un cliente: es la DESCRIPCIÓN de una
# API ajena —rutas, parámetros obligatorios, estados de ticket y códigos de retorno— para que quien
# escriba su propio conector no tenga que reunirla otra vez desde dos PDF que se contradicen.
#
# Es el mismo papel que ya cumplen los formatos de CONCAR, CONTASIS y STARSOFT: describir un sistema
# ajeno columna a columna sin hablar con él. Y responde al criterio del hito D7 de la hoja de ruta:
# «si la normalización se separa del transporte, la lectura de bytes puede entrar al motor y solo el
# transporte queda fuera». El transporte, las credenciales y el estado siguen fuera, y para siempre.
_API_SIRE = _datos.leer_json("datos/sunat/sire_api.json")


def api_sire() -> dict:
    """El canal del SIRE como datos: hosts, los dos grants, rutas por libro, la metadata de
    TUS, los estados del ticket y los códigos de retorno, cada bloque con su fuente.

    Quien lo use pone el transporte. Aquí no hay ni una petición."""
    return dict(_API_SIRE)


# ── El formato: las columnas del SIRE, y dónde cae cada una ──────────────────
# El mapa columna a columna del RVIE y del RCE: de cada campo del anexo, a qué campo del documento
# va o por qué no va, y si el TXT de reemplazo lo devuelve. Existe porque el mismo conocimiento
# estaba repartido en tres sitios que nada obligaba a concordar —`POS_VENTA`/`POS_COMPRA` del
# lector, estos nombres y el escritor del driver `sire`—, y porque tres de las cuatro versiones
# anteriores fueron columnas del SIRE mal leídas o ignoradas: el 26-sep-2026 `tipo_nota` y
# `estado_sunat` estaban en la lista de «referenciales que se ignoran» y resultó que importaban.
# `tests/test_sire_campos.py` lo confronta con el lector y con el escritor, así que ahora no se
# pueden separar sin que la batería lo diga.
_CAMPOS_SIRE = _datos.leer_json("datos/sunat/sire_campos.json")
if not _CAMPOS_SIRE:
    raise FileNotFoundError("No encuentro el mapa de campos del SIRE (datos/sunat/sire_campos.json)")
# El nombre del libro de SUNAT según el registro que se trabaja: el mismo par de siglas que usa el canal.
REGISTRO_SIRE = {True: "rvie", False: "rce"}


def campos_del_sire() -> dict:
    """El formato del SIRE columna a columna, con su fuente: por cada campo del anexo, su número, su
    nombre, el campo del documento donde cae —o el motivo por el que no cae— y si el TXT de reemplazo
    lo devuelve.

    Una columna que el motor no lee NO se pierde: la fila entera viaja en `datos_originales["sire"]`."""
    return dict(_CAMPOS_SIRE)


def columnas_del_sire(es_venta: bool) -> list[dict]:
    """Las columnas de un registro, en el orden del anexo."""
    return list(_CAMPOS_SIRE["libros"][REGISTRO_SIRE[es_venta]]["campos"])


def nombres_del_sire(es_venta: bool) -> list[str]:
    """Los nombres de SUNAT de los campos INFORMADOS de un registro, para que un informe diga «IGV» y
    no «campo 17». Viven aquí una sola vez: el mapa es la fuente."""
    libro = _CAMPOS_SIRE["libros"][REGISTRO_SIRE[es_venta]]
    return [c["nombre"] for c in libro["campos"] if c["n"] <= libro["campos_informados"]]


# Tipo de comprobante (2 dígitos). Se listan los que un estudio contable ve de verdad.
TIPOS_CP: dict[str, str] = dict(_CATALOGOS["tipos_comprobante"]["codigos"])

# Comprobantes en los que SUNAT exige fecha de vencimiento o de pago (RCE campo 6).
EXIGEN_VENCIMIENTO = frozenset({"14", "46", "50", "51", "52", "53", "54"})
# Comprobantes en los que el ICBPER va con 0.00 aunque no aplique (nunca vacío).
# Notas: llevan documento modificado obligatorio. Se separan en crédito y débito porque su catálogo de motivos es
# distinto —el 09 y el 10— y porque el «01» significa cosas opuestas en cada uno; `NOTAS` se DERIVA de los dos, así
# que aquí no se pueden desacordar. Los mismos cuatro códigos viven en `modelo.NOTAS_CREDITO`/`NOTAS_DEBITO`: los dos
# módulos son hojas y no se importan entre sí, así que lo que impide que se separen es un test
# (`test_catalogos.py::test_las_dos_listas_de_notas_dicen_lo_mismo`), no la buena voluntad.
NOTAS_CREDITO = frozenset({"07", "87"})     # 07 domiciliado · 87 no domiciliado
NOTAS_DEBITO = frozenset({"08", "88"})      # las hermanas que suman
NOTAS = NOTAS_CREDITO | NOTAS_DEBITO
# Comprobantes aduaneros: llevan año de la DUA y código de dependencia.
ADUANEROS = frozenset({"50", "51", "52", "53", "54"})
# Comprobantes que pueden ir sin documento de la contraparte (consumidor final).
SIN_CONTRAPARTE_OK = frozenset({"03", "12", "13", "16", "36", "00"})
# Comprobantes que NO se anotan en el registro que se declara a SUNAT (el SIRE):
# el recibo por honorarios (02) — regla de contabilidad. SÍ entran
# al asiento contable (Excel de CONCAR, sub-diario 15): son gasto de la empresa.
# Se filtran en `generar()` según lo que declare cada driver (`EXCLUYE_TIPOS`).
FUERA_DEL_REGISTRO_SUNAT = frozenset({"02"})

# Tipos con un tratamiento propio en el asiento: el recibo por honorarios (su cuenta y su retención de 4ta), la boleta
# (su registro), la nota de crédito (invierte el asiento) y las notas (llevan el documento que modifican).
TIPO_HONORARIOS, TIPO_BOLETA, TIPOS_INVIERTEN, TIPOS_NOTA = "02", "03", ("07",), ("07", "08")

# Tipo de documento de identidad (Anexo 1 de la RS 112-2021).
TIPOS_DOC_IDENTIDAD: dict[str, str] = dict(_CATALOGOS["tipos_documento_identidad"]["codigos"])

# Monedas, ISO 4217 (Anexo 1 de la RS 112-2021). Se deja pasar cualquier código de 3 letras; estos son los
# habituales.
MONEDAS = frozenset(_CATALOGOS["monedas"]["codigos"])

# Tipo de medio de pago (Anexo 3 de la RS 169-2015): los 22 códigos con los que se paga una operación, `001`
# depósito en cuenta … `999` otros. Son los medios del artículo 5 de la Ley 28194, la de bancarización.
#
# El motor no decide con ella: es vocabulario. Da significado al código que un sistema contable exige —CONTASIS lo
# pide en su registro de ventas— y permite avisar de uno que no existe. Un código que no esté aquí **no bloquea**
# (`validar.MEDIO_PAGO_DESCONOCIDO` es aviso): el día que SUNAT añada uno, nadie se queda sin exportar su mes.
MEDIOS_PAGO: dict[str, str] = dict(_CATALOGOS["medios_pago"]["codigos"])

# Por qué se emitió una nota: el Catálogo 09 para las de crédito (13 motivos, «01 anulación de la operación» …
# «09 disminución en el valor») y el 10 para las de débito (3: mora, aumento de valor, penalidades).
#
# **Son dos tablas y no una porque los códigos colisionan**: el `01` es «anulación de la operación» en el de crédito
# e «intereses por mora» en el de débito. Juntarlas obligaría a inventar un prefijo, y un catálogo con códigos
# inventados deja de ser el de SUNAT.
#
# No son del SIRE: son de la factura electrónica (el `cbc:ResponseCode` del XML), y el SIRE los CITA —campo 34 del
# Anexo N.° 2 de la RS 112-2021 en ventas, campo 39 del Anexo 8 de la RS 040-2022 en compras—. Como los medios de
# pago, esto es vocabulario y el motor no decide con él: un código que no esté aquí **no bloquea**
# (`validar.TIPO_NOTA_DESCONOCIDO` es aviso), porque SUNAT ya le añadió cuatro códigos al 09 en 2020.
#
# Y OJO con lo que NO dice el `01` del Catálogo 09: dice que la nota **anula el comprobante que referencia**, no que
# la nota esté anulada. En el mes real con el que se hizo esto, las cinco notas con motivo `01` estaban vivas y con
# importes, y las dos que SUNAT daba de baja llevaban motivo `09`. Ninguna regla del motor lee el motivo para hablar
# de anulación.
MOTIVOS_NOTA_CREDITO: dict[str, str] = dict(_CATALOGOS["motivos_nota_credito"]["codigos"])
MOTIVOS_NOTA_DEBITO: dict[str, str] = dict(_CATALOGOS["motivos_nota_debito"]["codigos"])


def motivos_de_nota(tipo_cp: str) -> dict[str, str]:
    """El catálogo de motivos que le toca a ese comprobante, y `{}` si no es una nota.

    Aquí vive, **una sola vez**, el reparto entre los dos catálogos, y se apoya en los conjuntos completos: mirar
    solo `("07", "08")` dejaría al 87 y al 88 sin catálogo **en silencio**, que es exactamente la forma del fallo que
    `resumen.py` cuenta en su cabecera (una nota de crédito de no domiciliado tratada como si no lo fuera)."""
    codigo = str(tipo_cp or "").strip()
    if codigo in NOTAS_CREDITO:
        return MOTIVOS_NOTA_CREDITO
    if codigo in NOTAS_DEBITO:
        return MOTIVOS_NOTA_DEBITO
    return {}


# Catálogo 05 de la factura electrónica: código de tributo en cac:TaxScheme/cbc:ID.
TRIBUTO_IGV = "1000"
TRIBUTO_IVAP = "1016"
TRIBUTO_ISC = "2000"
TRIBUTO_ICBPER = "7152"
TRIBUTO_EXPORTACION = "9995"
TRIBUTO_GRATUITO = "9996"   # operaciones gratuitas: NO entran en el cuadre ni en el registro
TRIBUTO_EXONERADO = "9997"
TRIBUTO_INAFECTO = "9998"
TRIBUTO_OTROS = "9999"

# Cómo se llama en castellano cada clase de `igv.clase_de_igv`, para que la pantalla no las escriba a mano y no haya
# dos vocabularios. **Son dos tablas y no una**, porque los dos libros no informan lo mismo: el RVIE separa lo
# exonerado (campo 19) de lo inafecto (campo 20) y el RCE tiene una sola columna de adquisiciones no gravadas (campo
# 21) que no dice cuál de los dos es. Llamar «Inafecto» a una compra afirmaría algo que el archivo no distingue.
#
# La cadena vacía no está en ninguna de las dos **a propósito**: es lo que devuelve `clase_de_igv` cuando el
# comprobante no tiene ningún importe —así declara SUNAT lo que se da de baja— y entonces no hay clase que enseñar.
# Un comprobante en cero no es gravado ni no gravado.
#
# Ojo con «Mixto», que se parece a otra cosa a dos centímetros: aquí significa «lleva importes con y sin IGV», y en
# `destino_igv` el `DGNG` es «la compra se usa para ventas con y sin IGV». Qué te cobraron y para qué lo usas.
CLASES_IGV_COMPRA = {
    "gravada": "Gravada",
    "no_gravada": "No gravada",
    "importacion": "Importación",
    "mixto": "Mixto",
}
CLASES_IGV_VENTA = {
    "afecto": "Afecto",
    "exonerado": "Exonerado",
    "inafecto": "Inafecto",
    "exportacion": "Exportación",
    "mixto": "Mixto",
}

# Tasas de IGV que la validación reconoce. La general es 18 %; las reducidas
# (restaurantes y hoteles) se aceptan con aviso, no como error.
TASA_IGV = "0.18"
TASAS_IGV_REDUCIDAS = ("0.10", "0.105", "0.08")
# Cuánto puede separarse el IGV escrito del calculado por redondeos del emisor. Vivía en `validar.py` y la leía
# también `igv.py`, que por eso dependía de la validación entera (1.0: las dependencias ocultas se cortan).
TOLERANCIA_IGV = Decimal("0.05")

# schemeID del Catálogo 06 → tipo de documento de identidad (coinciden salvo matices).
SCHEME_A_TIPO_DOC = {"0": "0", "1": "1", "4": "4", "6": "6", "7": "7", "A": "A", "-": "0"}


def ruc_valido(ruc: str) -> bool:
    """Módulo 11 de SUNAT: factores 5,4,3,2,7,6,5,4,3,2 sobre los 10 primeros dígitos."""
    if not (isinstance(ruc, str) and len(ruc) == 11 and ruc.isdigit()):
        return False
    if ruc[:2] not in ("10", "15", "16", "17", "20"):
        return False
    factores = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    suma = sum(int(d) * f for d, f in zip(ruc[:10], factores))
    resto = 11 - (suma % 11)
    verificador = {10: 0, 11: 1}.get(resto, resto)
    return verificador == int(ruc[10])



