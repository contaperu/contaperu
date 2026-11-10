"""Leer la PROPUESTA del SIRE: el TXT que SUNAT entrega al exportar un periodo.

Por qué existe: el archivo que un estudio contable siempre tiene a mano no son los
XML de su cliente —esos los tiene el cliente— sino lo que SUNAT ya registró. Se baja
del SIRE (Exportar → ticket → ZIP con un TXT) y con eso se puede trabajar el mes
entero, sin un solo XML, hasta el Excel para el sistema contable.

Entran los dos formatos, porque comparten el orden de los campos informados:

- **La exportación**: fila de cabecera, 40 columnas en ventas, el CAR lleno y las
  que completa la Administración al final. De esas se leen dos, el motivo de la nota
  y el estado del comprobante, y se ignoran las demás (FOB, gratuitas, tipo de
  operación, DAM, CLU): son referenciales y nunca vuelven a SUNAT, así que del estado
  y del motivo lo que se hace es transportarlos, no decidir con ellos.
- **El de "reemplazar propuesta"**: 33 campos en ventas (37 en compras) y palote
  final, sin cabecera. Es el que genera este mismo portal, así que un archivo puede
  salir y volver a entrar.

**Y lo DECLARADO entra por aquí sin cambiar nada** (medido el 01-nov-2026). El registro que se generó en SOL, que se
baja con `registro_pedir` (`sunat/`), llega en el formato de la exportación: en compras, cabecera y las 41 columnas
de siempre más las 39 de libre utilización (CLU1 a CLU39), que se ignoran como en la propuesta. Un mes real de 1 326
comprobantes se leyó entero, sin un error. Lo que sí trae distinto es un **segundo TXT en el mismo ZIP**, el registro
de no domiciliados, y de ahí que dentro de un ZIP se busque el TXT que tiene la forma del SIRE, y no el primero de la
lista.

**Y ese segundo TXT también se lee** (15.3.0). Es el registro de compras de no domiciliados (Anexo 9 de la RS
040-2022, §8.5): tiene su propio formato —el periodo delante, ni RUC del proveedor ni columnas de IGV, y detrás el
país, la renta y la retención— y entra por `parsear` igual que el otro, con su mapa (`POS_NO_DOMICILIADO`). De la
15.1 a la 15.2 se reconocía y se decía en `no_leidos`: diez compras del mes real se quedaban fuera de la tabla.
**En ventas llega sin cabecera**: 38 campos y palote, en el orden de la exportación (15.2.1, un mes real de 14
comprobantes). Es una tercera forma de las mismas columnas, y entra por la misma regla que el reemplazo: una fila que
empieza por el RUC y el periodo.

Lo que la propuesta NO trae, y por eso no se inventa aquí: el concepto del
comprobante, la cuenta contable, el centro de costo y el detalle de la detracción. Son
datos del comprobante, no del registro; `validar.py` lo avisa con `SIRE_SIN_DETALLE`.

De la detracción conviene precisar qué calla SUNAT y qué no, porque no es lo mismo: el RCE **sí marca si una
fila está sujeta al SPOT** —el campo 38 del Anexo 8, con una `D`; en un RCE real de un mes, 221 filas de 3018—,
pero **no dice cuál**: ni código del Catálogo 54, ni tasa, ni monto, ni cuenta, ni constancia. Desde la 4.1 esa
marca **se lee** y entra como anotación (`detraccion._marca_sire`), sin código, y el motor se niega a exportar
esos comprobantes hasta que quien integra mande el `detraccion_codigo` en su imputación (enmienda 0020). Antes
salían sin su línea de detracción y en silencio. Para quien integra, el circuito está en `INTEGRAR.md` §«El SIRE,
de punta a punta», punto 9.
El **concepto se queda VACÍO a propósito** (regla de contabilidad): copiarle el nombre de
la contraparte repetía en la columna un dato que ya está en la suya, y no ganaba nada
—`asiento.glosa_de` ya cae al nombre de la contraparte cuando el concepto está vacío, así
que el Excel sale idéntico— mientras que la celda llena aparentaba un dato que el
archivo no da y estorbaba para escribir el de verdad.
"""
from __future__ import annotations

import io
import posixpath
import re
import zipfile
from decimal import ROUND_HALF_UP, Decimal

from . import _zip
from ..tributos import detracciones as _detracciones
from ..errores import ErrorContaperu
from ..modelo.libro import Libro
from .comprobante import Comprobante

ORIGEN = "sire"


class SireInvalido(ErrorContaperu, ValueError):
    """El archivo no es una propuesta del SIRE, o no es la de este proceso."""


# Orden de los campos informados. El mismo en la exportación y en el reemplazo: se
# comprobó columna a columna contra la exportación real de agosto (26-ago-2026).
# Ventas = Anexo 3 (RS 112-2021); compras = Anexo 11 (RS 040-2022).
#
# Los índices son 0-based, o sea el número de campo del anexo menos uno. **Los dos últimos de cada mapa son los que
# completa la Administración**, y se leen desde la 3.5.0: el motivo de la nota y lo que SUNAT dice del comprobante.
# Sus números NO son los mismos en los dos registros, y de ahí que cada mapa los tenga por separado — ventas los pone
# en los campos 34 y 35 (Anexo N.° 2 de la RS 112-2021) y compras en el 39 y el 40 (Anexo 8 de la RS 040-2022, §8.4,
# donde el 38 es la marca de detracción y el 41 las inconsistencias). Los anexos ni siquiera les dan el mismo formato:
# el estado es «longitud 2, alfanumérico» en ventas y «longitud 1, numérico» en compras, así que ninguno de los dos
# campos se normaliza al leerlo.
#
# El formato de «reemplazar propuesta» no las trae —33 campos y palote en ventas, 37 en compras—: ahí quedan vacías
# y el comprobante entra igual, que es lo que hace segura la ida y vuelta.
POS_VENTA = {
    "fecha_emision": 4, "fecha_vencimiento": 5, "tipo_cp": 6, "serie": 7, "numero": 8, "numero_final": 9,
    "contraparte_tipo_doc": 10, "contraparte_doc": 11, "contraparte_nombre": 12,
    "exportacion": 13, "base_gravada": 14, "dscto_base": 15, "igv": 16, "dscto_igv": 17,
    "exonerado": 18, "inafecto": 19, "isc": 20, "base_ivap": 21, "ivap": 22, "icbper": 23,
    "otros": 24, "total": 25, "moneda": 26, "tipo_cambio": 27,
    "ref_fecha": 28, "ref_tipo_cp": 29, "ref_serie": 30, "ref_numero": 31, "id_contrato": 32,
    "tipo_nota": 33, "estado_sunat": 34,
}
POS_COMPRA = {
    "fecha_emision": 4, "fecha_vencimiento": 5, "tipo_cp": 6, "serie": 7, "anio_dua": 8,
    "numero": 9, "numero_final": 10, "contraparte_tipo_doc": 11, "contraparte_doc": 12,
    "contraparte_nombre": 13,
    # 14-19: las tres parejas base/IGV según el destino de la adquisición
    "isc": 21, "icbper": 22, "otros": 23, "total": 24, "moneda": 25, "tipo_cambio": 26,
    "ref_fecha": 27, "ref_tipo_cp": 28, "ref_serie": 29, "cod_dep_aduanera": 30, "ref_numero": 31,
    "clasif_bienes": 32, "id_contrato": 33,
    # 34-36: % de participación, IMB y el CAR del CP a modificar; 37: la marca de detracción, que no se lee.
    # Estos índices y los de arriba, con el nombre de SUNAT de cada columna y el motivo de cada hueco, están
    # publicados en `datos/sunat/sire_campos.json`, y `tests/test_sire_campos.py` no los deja separarse.
    "tipo_nota": 38, "estado_sunat": 39,
}
IGV_COMPRAS = {"DG": (14, 15), "DGNG": (16, 17), "DNG": (18, 19)}
VALOR_NO_GRAVADO = 20
# La columna «Detracción» del RCE: campo 38 del Anexo 8 de la RS 040-2022 (§8.4). SUNAT escribe una `D` en las filas
# sujetas al SPOT y la deja vacía en las demás — en un RCE real de un mes, 221 de 3018 (set-2026). **Es lo único que
# la propuesta dice del SPOT**: afirma QUE hay detracción y no dice CUÁL, porque el código del Catálogo 54, la tasa y
# el monto son del comprobante y no del registro. El RVIE no tiene esta columna: solo compras.
MARCA_DETRACCION = 37
# Lo que SUNAT escribe en esa columna cuando la operación está sujeta. Se guarda el valor literal, no un booleano: es
# el dato del archivo, y si algún día el anexo admite otra letra, aquí se verá en vez de perderse en un `True`.
MARCA_DETRACCION_SI = "D"
MONTOS = {"exportacion", "base_gravada", "dscto_base", "igv", "dscto_igv", "exonerado", "inafecto",
          "isc", "base_ivap", "ivap", "icbper", "otros", "dscto_otros", "total"}
FECHAS = {"fecha_emision", "fecha_vencimiento", "ref_fecha"}
MINIMO_CAMPOS = 30

# Los libros electrónicos que SUNAT entrega o recibe llevan el código del libro EN EL NOMBRE (`LE` + RUC + periodo +
# … + código de seis dígitos: `drivers/kit/nombres.py`). Los del SIRE no son los del PLE. Este lector lee los tres: el
# tercero es el registro de compras de **no domiciliados**, que viaja con lo declarado en el mismo ZIP y tiene su
# propio formato —ni RUC del proveedor ni las columnas del IGV: país, renta bruta, tasa y retención—. El código se
# comprobó en dos archivos reales del 01-nov-2026: el que bajó `registro_pedir` y el que se presentó.
CODIGOS_DEL_SIRE = {"080400": "el registro de compras", "140400": "el registro de ventas",
                    "080500": "el registro de compras de no domiciliados"}
NO_DOMICILIADOS = "080500"
# Su exportación empieza así, y no por «RUC»: el periodo va primero porque el titular está en el nombre del archivo.
CABECERA_NO_DOMICILIADOS = ("periodo", "car sunat")

# ── El registro de compras de NO DOMICILIADOS (15.3.0) ──────────────────────────────────────────────────────────────
# Anexo 9 de la RS 040-2022, «8.5 Registro de Compras – operaciones con sujetos no domiciliados»: 35 campos, en este
# orden en las dos formas que se han visto —la exportación de lo declarado, con cabecera y diez columnas libres
# (CLU1 a CLU10) detrás, y la que se presenta, sin cabecera, con un campo 36 vacío y palote—. Índices 0-based, o sea
# el número de campo del anexo menos uno, como los de arriba.
#
# Lo que el comprobante tenía donde ponerlo desde la 15.3.0 (John, 01-nov-2026: «lo básico ahora»): fecha, tipo,
# serie, número, importes, moneda y el proveedor (`POS_NO_DOMICILIADO`). **Y desde la 15.6.0, lo demás**: el país, el
# beneficiario, la renta, la tasa, el impuesto retenido, el IGV de utilización, el convenio, el tipo de renta, la
# modalidad y el documento que sustenta el crédito van al bloque `no_domiciliado` del comprobante (enmienda 0007,
# open-accounting 4.1; `POS_DEL_BLOQUE_NO_DOMICILIADO`). La fila cruda sigue viajando en `datos_originales["sire"]`:
# el CAR no tiene sitio, y quien quiera comparar con lo que SUNAT vio lo tiene ahí.
#
# Cada índice se ancla al rótulo de su columna en la cabecera de SUNAT: `tests/test_sire_txt.py` los compara.
POS_NO_DOMICILIADO = {
    "fecha_emision": 2, "tipo_cp": 3, "serie": 4, "numero": 5, "otros": 7, "total": 8,
    "moneda": 14, "tipo_cambio": 15, "contraparte_nombre": 17, "contraparte_doc": 19,
}
# El bloque del no domiciliado, campo a campo (Anexo 9, §8.5; índice = número de campo menos uno). **Sus importes se
# copian TAL CUAL, en soles** —la moneda de la contabilidad—, sin devolverlos a la del comprobante como los de arriba:
# así los define el bloque, y el impuesto retenido no vuelve igual si se convierte (medido en el registro real).
POS_DEL_BLOQUE_NO_DOMICILIADO = {
    "sustento_tipo_cp": 9, "sustento_serie": 10, "sustento_anio_dua": 11, "sustento_numero": 12,
    "igv_utilizacion": 13, "pais": 16, "domicilio": 18,
    "beneficiario_doc": 20, "beneficiario_nombre": 21, "beneficiario_pais": 22, "vinculo": 23,
    "renta_bruta": 24, "deduccion": 25, "renta_neta": 26, "porcentaje": 27, "impuesto_retenido": 28,
    "convenio": 29, "exoneracion": 30, "tipo_renta": 31, "modalidad": 32, "art_76": 33,
}
# El campo 7, «Valor de las adquisiciones»: lo que se compró, que el documento del exterior no grava. Va a
# `valor_no_gravado` —«valor de las adquisiciones no gravadas», la columna con la que el otro registro dice lo mismo—
# y por eso aparte del mapa: solo se declara cuando trae importe, con el mismo idioma que `VALOR_NO_GRAVADO`.
VALOR_DE_ADQUISICIONES = 6
CAMPOS_NO_DOMICILIADO = 35
# El documento del proveedor del exterior no es un RUC ni un DNI: es el que le da su país —en el mes real, un código
# interno, un PAN de la India de diez caracteres y hasta un RUC peruano—, y el registro no trae columna de tipo. El
# «0» del Catálogo 06 es el documento tributario del no domiciliado sin RUC; aquí el número se guarda **tal cual, con
# sus letras**, y por eso `validar` no lo pasa por `solo_digitos` (solo lo hace con los tipos 1 y 6).
TIPO_DOC_NO_DOMICILIADO = "0"
# **Los importes de este registro van en la moneda de la CONTABILIDAD, no en la del comprobante** (15.3.1). Lo dice la
# regla 5 del campo 16 del Anexo 9: el tipo de cambio es «el utilizado para la conversión a soles en caso lleve su
# contabilidad en soles» —y en dólares, el de soles a dólares—. Y lo dice el nombre del archivo, cuya tercera bandera
# es la moneda en que se lleva (1 soles, 2 dólares; `drivers/kit/nombres.py`). La 15.3.0 los leyó como si fueran de
# la moneda del comprobante, y una suscripción de 20 dólares salió de 67.24 «USD», que es 20 × 3.362 en soles: lo vio
# John en la pantalla el mismo día. Las diez filas del mes real cumplen la cuenta al céntimo.
MONEDA_DE_LA_CONTABILIDAD = {"1": "PEN", "2": "USD"}
# `LE` + RUC + AAAAMM + día + código + oportunidad + las cuatro banderas, sin la extensión; la de la moneda es la
# tercera de las cuatro.
_LARGO_DEL_NOMBRE = 33
_BANDERA_DE_MONEDA = 31


def _texto(datos: bytes) -> str:
    return datos.decode("utf-8-sig", errors="replace")


def _tiene_la_forma(texto: str) -> bool:
    """¿Este texto es una propuesta (o un registro) del SIRE? Por su primera línea con algo."""
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        campos = linea.split("|")
        if campos[0].strip().lower() == "ruc" and len(campos) >= MINIMO_CAMPOS:
            return True            # la cabecera de la exportación
        # Una fila: RUC de 11 dígitos, periodo AAAAMM y bastantes columnas.
        return (len(campos) >= MINIMO_CAMPOS and campos[0].strip().isdigit()
                and len(campos[0].strip()) == 11 and campos[2].strip().isdigit() and len(campos[2].strip()) == 6)
    return False


def _txts_del_zip(datos: bytes) -> list[tuple[str, bytes]]:
    """Los TXT de un ZIP, con su nombre y en el orden en que vienen. Lo declarado trae dos: el registro y el de no
    domiciliados, y el orden en que SUNAT los mete no está escrito en ninguna parte."""
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        nombres = [n for n in z.namelist() if n.lower().endswith(".txt")]
        if not nombres:
            raise SireInvalido("El ZIP no trae ningún TXT dentro")
        txts = []
        for nombre in nombres:
            try:
                txts.append((nombre, _zip.leer(z, z.getinfo(nombre))))
            except _zip.Desmedido as e:
                raise SireInvalido(str(e)) from None
        return txts


def _del_zip(datos: bytes) -> bytes:
    """El registro del SIRE que va dentro de un ZIP: **el primero que tenga su forma**, no el primero de la lista.

    Tomar el primero dependía del orden en que SUNAT metiera los dos TXT de lo declarado. Si ninguno tiene la forma,
    se devuelve el primero, para que quien lee falle con su motivo de siempre. El de no domiciliados no se busca aquí:
    lo lee `parsear` aparte, con su propio mapa.
    """
    txts = _txts_del_zip(datos)
    return next((c for _, c in txts if _tiene_la_forma(_texto(c[:4096]))), txts[0][1])


def leer_lineas(datos: bytes) -> list[list[str]]:
    """Filas del TXT (o del TXT del SIRE que va dentro del ZIP), sin la cabecera si la trae."""
    if zipfile.is_zipfile(io.BytesIO(datos)):
        datos = _del_zip(datos)
    filas = [l.split("|") for l in _texto(datos).splitlines() if l.strip()]
    if filas and filas[0][0].strip().lower() == "ruc":
        filas = filas[1:]          # la exportación trae cabecera; el reemplazo no
    return filas


def _se_lee(datos: bytes) -> bool:
    return _tiene_la_forma(_texto(datos[:4096])) or es_no_domiciliados(datos)


def es_sire(datos: bytes) -> bool:
    """¿Esto es un archivo del SIRE que este lector lee? Se mira el contenido, no el nombre.

    Lo es el registro de compras o de ventas —la propuesta, el reemplazo o lo declarado— y, desde la 15.3.0, el de
    compras de no domiciliados. Acepta el TXT suelto y el ZIP tal cual lo entrega SUNAT (dentro de la aplicación que
    lo use los ZIP ya vienen abiertos, pero desde la CLI o los tests entra el ZIP entero).
    """
    try:
        if zipfile.is_zipfile(io.BytesIO(datos)):
            return any(_se_lee(c) for _, c in _txts_del_zip(datos))
        return _se_lee(datos)
    except Exception:  # noqa: BLE001
        return False


# La fecha de emisión tal como la escribe el registro de no domiciliados: es lo que separa una de sus filas de una del
# otro registro, que empieza por el RUC.
_FECHA_DEL_REGISTRO = re.compile(r"\d{2}/\d{2}/\d{4}")


def es_no_domiciliados(datos: bytes) -> bool:
    """¿Es el registro de compras de no domiciliados? Por su primera línea con algo, en las dos formas que se han visto.

    La exportación de lo declarado trae una cabecera que empieza por el periodo; la que se PRESENTA no trae cabecera
    —diez filas de 36 campos y palote, en el caso real—, y se reconoce por la forma de su fila: el periodo, el CAR y
    la fecha de emisión, con al menos los 35 campos del anexo. Las dos se separan del otro registro por lo mismo: el
    titular está en el nombre del archivo, así que la fila no empieza por un RUC sino por el periodo.

    El código del nombre (`080500`) también lo delata, pero eso lo mira quien tiene el nombre (`parsear`): aquí solo
    hay bytes."""
    for linea in _texto(datos[:4096]).splitlines():
        if not linea.strip():
            continue
        campos = [c.strip() for c in linea.split("|")]
        if tuple(c.lower() for c in campos[:2]) == CABECERA_NO_DOMICILIADOS:
            return True
        return (len(campos) >= CAMPOS_NO_DOMICILIADO and len(campos[0]) == 6 and campos[0].isdigit()
                and _FECHA_DEL_REGISTRO.fullmatch(campos[2]) is not None)
    return False


def _codigo_del_nombre(nombre: str) -> str:
    """El código del libro que dice el nombre de un libro electrónico, o `""` si no lo dice.

    Se busca DESPUÉS del RUC: un RUC puede contener «140400» y se leería como el registro de ventas."""
    base = posixpath.basename(nombre)
    return next((c for c in CODIGOS_DEL_SIRE if es_libro_electronico(base) and c in base[13:]), "")


def _de_no_domiciliados(datos: bytes, nombre: str) -> bool:
    return es_no_domiciliados(datos) or _codigo_del_nombre(nombre) == NO_DOMICILIADOS


def es_libro_electronico(nombre: str) -> bool:
    """¿El nombre es el que SUNAT impone a un libro electrónico? `LE` y el RUC de once dígitos, al principio."""
    base = posixpath.basename(nombre)
    return len(base) > 13 and base[:2].upper() == "LE" and base[2:13].isdigit()


def libro_sin_leer(nombre: str, datos: bytes) -> dict:
    """Un libro electrónico de SUNAT que este lector no lee, dicho en vez de callado.

    Devuelve `{archivo, codigo, filas, motivo}`: `codigo` es el del libro en la tabla de SUNAT, si el nombre o la
    cabecera lo dicen, y `filas` cuenta las que empiezan por un número —un RUC o un periodo—, que es lo que separa una
    fila de una cabecera en todos los libros que se han visto.

    **Existe por el silencio que había antes**: un TXT que no tenía la forma del SIRE se trataba como un acompañante
    —como la hoja de estilos que meten los facturadores en su ZIP— y se ignoraba sin decir nada. Así se perdían las
    compras de no domiciliados de lo declarado, y así se perdería el registro entero el día que SUNAT le cambiara la
    forma: una tabla vacía donde había mil filas, sin un error. Que se diga cuántas filas no se leyeron deja la
    decisión a quien integra.

    El de no domiciliados tuvo aquí su rama propia de la 15.1 a la 15.2 («tiene su propio formato y este lector
    todavía no lo lee»). Desde la 15.3.0 se lee, así que solo llega aquí si su nombre lo dice y su contenido no tiene
    ninguna de las dos formas conocidas: es el caso de abajo, el de cualquier registro que SUNAT haya cambiado.
    """
    filas = sum(1 for linea in _texto(datos).splitlines() if linea.split("|")[0].strip().isdigit())
    codigo = _codigo_del_nombre(nombre)
    if codigo:
        return {"archivo": nombre, "codigo": codigo, "filas": filas,
                "motivo": f"Su nombre dice que es {CODIGOS_DEL_SIRE[codigo]} del SIRE y no tiene la forma que este "
                          "lector conoce: puede que SUNAT la haya cambiado"}
    return {"archivo": nombre, "codigo": "", "filas": filas,
            "motivo": "Es un libro electrónico de SUNAT que este lector no reconoce"}


def _valor(campos: list[str], i: int) -> str:
    return campos[i].strip() if i < len(campos) else ""


def _con_signo(v: str) -> Decimal:
    return Decimal((v or "0").replace(",", ""))


def _una(campos: list[str], libro: Libro, archivo_nombre: str) -> Comprobante:
    pos = POS_VENTA if libro.es_venta else POS_COMPRA
    datos = {k: _valor(campos, i) for k, i in pos.items()}
    # «Otros conceptos, tributos y cargos» (RCE campo 24, RVIE campo 25) es un NETO CON SIGNO, y un negativo
    # ahí es un descuento global: caso real, una factura de grifo con 96.00 no gravado y −13.40, total 82.60.
    # `monto()` devuelve el valor absoluto —el signo no es parte del dato— así que sin esto el total salía
    # 109.40 y el comprobante avisaba «no cuadra» por algo que estaba bien.
    #
    # Se mira el signo CONTRARIO AL DEL TOTAL, no el signo a secas: en una nota de crédito TODOS los campos
    # vienen negativos porque lo es la operación entera, y ese signo ya lo pone el driver al escribir
    # (`negativo(c)`). Tomarlo por descuento invertiría la nota. Comprobado en un RCE real de 1116 filas: las
    # dos notas de crédito traen este campo en 0.00 y las seis facturas con descuento lo traen contrario.
    bruto_otros = _con_signo(datos.get("otros") or "0")
    if bruto_otros < 0 and _con_signo(datos.get("total") or "0") >= 0:
        datos["otros"], datos["dscto_otros"] = "0", str(-bruto_otros)
    for k in MONTOS:
        if k in datos:
            datos[k] = datos[k] or "0"
    for k in FECHAS:
        datos[k] = datos.get(k) or None
    # SUNAT exporta `1.000` cuando la moneda es PEN, pero el registro solo pide el
    # T.C. si la moneda NO es soles — y así lo escribe el driver (`tc_pen=""`).
    # Guardar ese 1.000 sería un dato que el comprobante no tiene y que se
    # contradice con el archivo que este mismo motor genera (regla de contabilidad).
    if datos.get("moneda", "").strip().upper() in ("", "PEN"):
        datos["tipo_cambio"] = ""
    if not libro.es_venta:
        # Las seis columnas de base/IGV dicen el destino de la adquisición: se toma
        # la pareja que trae importe, y si no hay ninguna se queda en DG.
        for destino, (i_base, i_igv) in IGV_COMPRAS.items():
            base, igv = _valor(campos, i_base), _valor(campos, i_igv)
            if (base and base.strip("0.-")) or (igv and igv.strip("0.-")):
                datos.update(destino_igv=destino, base_gravada=base or "0", igv=igv or "0")
                break
        else:
            datos.update(destino_igv="DG", base_gravada="0", igv="0")
        # El campo 21 solo se DECLARA cuando trae importe, y el `strip("0.-")` no es adorno: la columna
        # llega como "0" o "0.00" en las compras gravadas, y la cadena "0" es verdadera. Declararlo en cero
        # significa «lo no gravado de este comprobante es cero», y eso **gana** sobre `exonerado + inafecto`
        # en `adquisiciones_no_gravadas`. Mientras el lector fuera el unico que escribia el campo daba igual
        # —en el RCE esos dos siempre son 0—, pero desde que `validar` usa la propiedad (3.5.1) un cero
        # declarado se llevaria por delante el desglose que alguien escriba luego en la pantalla. Es el mismo
        # idioma con el que arriba se decide si una pareja base/IGV trae algo.
        no_gravado = _valor(campos, VALOR_NO_GRAVADO)
        if no_gravado and no_gravado.strip("0.-"):
            datos["valor_no_gravado"] = no_gravado
        # La marca de detracción, lo único que la propuesta dice del SPOT. Entra como ANOTACIÓN en un bloque de
        # detracción que, a propósito, **no lleva código**: la propuesta no lo trae y no se inventa (si se inventara,
        # CONCAR recibiría un código interno falso y el asiento una tasa falsa). Lo que hace esta marca es que el
        # motor sepa a QUIÉN le falta: `validar` se niega a exportar esos comprobantes hasta que el contador ponga el
        # código, en vez de exportarlos sin su línea de detracción y en silencio, que es lo que pasaba hasta la 4.0.
        if _valor(campos, MARCA_DETRACCION).strip().upper() == MARCA_DETRACCION_SI:
            datos["detraccion"] = {_detracciones.MARCA_SIRE: MARCA_DETRACCION_SI}
    if libro.es_venta:
        # Base e IGV netos, descuentos aparte (estandar/LEEME.md). SUNAT escribe cada campo con su signo y el
        # total es la suma de todos: en las diez filas de la exportación real de agosto, el campo 26 es
        # exactamente la suma con signo de los campos 14 a 25 (11-sep-2026). Por eso la base neta es 15 + 16 y
        # el IGV neto 17 + 18 —una NC de descuento (15 = 0, 16 = −9985.36) tiene base 9985.36—, y hay que
        # leerlos CON signo: `Comprobante` los guarda en positivo y se perdería de qué lado estaba cada uno.
        b15, d16, i17, d18 = (_con_signo(datos[k]) for k in ("base_gravada", "dscto_base", "igv", "dscto_igv"))
        if d16 > 0 or d18 > 0:
            raise ValueError("los descuentos (campos 16 y 18) vienen en positivo y SUNAT los escribe en negativo")
        datos.update(base_gravada=str(abs(b15 + d16)), dscto_base=str(abs(d16)),
                     igv=str(abs(i17 + d18)), dscto_igv=str(abs(d18)))
    return Comprobante(
        **datos,
        # `concepto` se queda vacío: la propuesta no lo trae y el Excel de CONCAR ya
        # cae al nombre de la contraparte por su cuenta (`asiento.glosa_de`).
        origen=ORIGEN,
        confianza=Decimal("1.00"),      # es el dato de SUNAT, no la lectura de una IA
        archivo_nombre=archivo_nombre,
        datos_originales={"sire": campos},     # la fila cruda, para rastrear de dónde salió cada valor
    )


def _moneda_de_la_contabilidad(nombre: str) -> str:
    """La moneda en que el contribuyente lleva su contabilidad, por la tercera bandera del nombre del archivo.

    Soles si el nombre no la dice —un archivo renombrado, o uno cuyo nombre no tiene el largo de un libro
    electrónico—: es lo que lleva casi todo contribuyente, lo que dice el mes real y lo que escribe el driver `sire`
    de este mismo motor (`BANDERAS`)."""
    raiz = posixpath.basename(nombre).rsplit(".", 1)[0]
    if es_libro_electronico(raiz) and len(raiz) == _LARGO_DEL_NOMBRE:
        return MONEDA_DE_LA_CONTABILIDAD.get(raiz[_BANDERA_DE_MONEDA], "PEN")
    return "PEN"


def _en_la_moneda_del_comprobante(importe: str, tipo_cambio: Decimal) -> str:
    """Un importe del registro, de soles a la moneda del comprobante: dividido por su tipo de cambio y al céntimo."""
    return str((_con_signo(importe) / tipo_cambio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _un_no_domiciliado(campos: list[str], archivo_nombre: str, contabilidad: str = "PEN") -> Comprobante:
    """Una fila del registro de no domiciliados → el comprobante, con lo que tiene donde ponerlo (`POS_NO_DOMICILIADO`).

    `contabilidad` es la moneda en que vienen los IMPORTES de la fila (`MONEDA_DE_LA_CONTABILIDAD`), que no es la del
    comprobante: un comprobante en dólares de quien lleva su contabilidad en soles trae sus importes en soles y su tipo
    de cambio, y aquí se pasan a dólares para que el comprobante diga lo que dice el papel."""
    datos: dict[str, object] = {k: _valor(campos, i) for k, i in POS_NO_DOMICILIADO.items()}
    moneda = str(datos["moneda"] or "").strip().upper()
    # «Otros conceptos» con signo, con la misma regla que el otro registro (`_una`): un negativo contrario al total es
    # un descuento global; en una nota, todo viene negativo porque lo es la operación entera.
    bruto_otros = _con_signo(str(datos["otros"] or "0"))
    if bruto_otros < 0 and _con_signo(str(datos["total"] or "0")) >= 0:
        datos["otros"], datos["dscto_otros"] = "0", str(-bruto_otros)
    datos["otros"] = datos["otros"] or "0"
    datos["total"] = datos["total"] or "0"
    datos["fecha_emision"] = datos["fecha_emision"] or None
    # El tipo de cambio solo cuando la moneda no es soles, como en el otro registro y en el TXT que escribe el driver.
    if moneda in ("", "PEN"):
        datos["tipo_cambio"] = ""
    valor = _valor(campos, VALOR_DE_ADQUISICIONES)
    if valor and valor.strip("0.-"):
        datos["valor_no_gravado"] = valor
    # **Los importes, de la moneda de la contabilidad a la del comprobante** (15.3.1). En dólares, de quien lleva su
    # contabilidad en soles: se dividen por el tipo de cambio de la fila, que es el que se usó para llevarlos a soles.
    # Sin él no hay forma de devolverlos, y el anexo lo exige, así que la fila no se lee. Quien lleva su contabilidad en
    # dólares y anota un comprobante en otra moneda pasó por soles antes (regla 5 del campo 16): esa vuelta no se ha
    # visto en un archivo real y no se adivina.
    if moneda and moneda != contabilidad:
        if contabilidad != "PEN":
            raise ValueError(f"lleva su contabilidad en {contabilidad} y el comprobante es de {moneda}: este lector "
                             "solo sabe devolver a su moneda los importes de una contabilidad en soles")
        tipo_cambio = _con_signo(str(datos["tipo_cambio"] or "0"))
        if tipo_cambio <= 0:
            raise ValueError(f"está en {moneda} sin tipo de cambio, y sus importes vienen en soles: no se pueden "
                             f"devolver a {moneda}")
        for campo in ("otros", "dscto_otros", "total", "valor_no_gravado"):
            if campo in datos:
                datos[campo] = _en_la_moneda_del_comprobante(str(datos[campo]), tipo_cambio)
    return Comprobante(
        **datos,  # type: ignore[arg-type]
        contraparte_tipo_doc=TIPO_DOC_NO_DOMICILIADO,
        origen=ORIGEN,
        confianza=Decimal("1.00"),      # es el dato de SUNAT, no la lectura de una IA
        archivo_nombre=archivo_nombre,
        no_domiciliado=bloque_de_la_fila(campos),
        datos_originales={"sire": campos},     # la fila entera: el CAR no tiene sitio, y viaja aquí
    )


# Los importes del bloque. Van en positivo como todo importe del estándar: en una nota del no domiciliado (97, 98) la
# fila los trae negativos porque lo es la operación entera, y el signo lo pone el tipo.
_IMPORTES_DEL_BLOQUE = ("igv_utilizacion", "renta_bruta", "deduccion", "renta_neta", "impuesto_retenido")

# Las claves del bloque donde un «0» de SUNAT es «sin dato» (15.6.1): ver `bloque_de_la_fila`.
CERO_ES_VACIO = frozenset({"exoneracion", "art_76", "sustento_anio_dua"})


def bloque_de_la_fila(campos: list[str]) -> dict[str, str]:
    """Lo del no domiciliado de una fila del 080500, al bloque del comprobante: tal cual, con sus importes EN SOLES y en
    positivo.

    **Pública desde la 15.6.1** (se llamaba `_bloque_no_domiciliado`): una aplicación que guardó la fila cruda
    —`datos_originales["sire"]`, que viaja con cada comprobante leído de este registro— reconstruye el bloque con
    ella sin volver a pedirle nada a SUNAT y sin copiar las posiciones de las columnas, que son de este módulo.
    Lo vacío no entra —es «la fila no lo dice»—, y lo valida después `validar` contra los catálogos, no aquí: un
    código que no está en una tabla es un aviso, no una fila que no se lee.

    **Y un «0» en `CERO_ES_VACIO` también es vacío** (15.6.1). Medido el 04-nov-2026 con el mismo mes en las dos formas
    en que SUNAT lo da: lo declarado (5.51) deja vacías la exoneración, el art. 76 y el año de la DUA, y el preliminar de
    no domiciliados (5.39) escribe ahí un 0. Ninguno de los tres es un código —la Tabla 21 empieza en 1, y un año no es
    0—, así que leerlos tal cual daba en las diez filas de ese mes dos avisos que lo declarado no da."""
    bloque: dict[str, str] = {}
    for clave, indice in POS_DEL_BLOQUE_NO_DOMICILIADO.items():
        valor = _valor(campos, indice).strip()
        if not valor or (clave in CERO_ES_VACIO and valor == "0"):
            continue
        bloque[clave] = str(abs(_con_signo(valor))) if clave in _IMPORTES_DEL_BLOQUE else valor
    return bloque


# Dónde va el CAR en una fila del 080500: la segunda columna, «CAR SUNAT» (`CABECERA_NO_DOMICILIADOS`).
POS_CAR = 1
# **El CAR medido son 27 letras y dígitos** (el preliminar de setiembre de 2026, 04-nov-2026). El manual de la 5.38 dice
# «solo dato numérico de 27 dígitos» (error 1136) y se equivoca: de los CAR reales que se miraron, ninguno era solo de
# dígitos.
_CAR = re.compile(r"^[A-Za-z0-9]{27}$")


def car_de(c: Comprobante) -> str:
    """El CAR que SUNAT le puso a un comprobante del registro de no domiciliados al cargarlo, o `""` si no lo tiene.

    Lo necesita quien quiera quitar un comprobante del preliminar (`no_domiciliados_eliminar_comprobante`, cuyo cuerpo
    arma `sunat.cuerpo_para_quitar_no_domiciliados`): el CAR no tiene sitio en el comprobante y viaja en la fila cruda,
    `datos_originales["sire"]`. Solo en lo leído del 080500 —un comprobante con su bloque `no_domiciliado`—, porque en
    la fila del otro registro esa columna es la razón social. Lo DECLARADO lo trae vacío (medido): el CAR sale del
    preliminar (`no_domiciliados_exportar_preliminar`). Uno que no tiene la forma medida no se devuelve: mandarle a SUNAT
    un CAR a medias quitaría otro comprobante o ninguno, y no lo diría."""
    if not c.no_domiciliado:
        return ""
    fila = (c.datos_originales or {}).get("sire")
    if not isinstance(fila, (list, tuple)) or len(fila) <= POS_CAR:
        return ""
    car = str(fila[POS_CAR] or "").strip()
    return car if _CAR.match(car) else ""


def _parsear_no_domiciliados(datos: bytes, libro: Libro, archivo_nombre: str, nombre_del_txt: str) -> list[Comprobante]:
    """El registro de compras de no domiciliados → comprobantes del libro de compras, con las mismas negativas que el
    otro registro: otro RUC, otro periodo o una fila que no es de este anexo."""
    if libro.es_venta:
        raise SireInvalido("Es el registro de compras de no domiciliados: va en el libro de compras, no en el de ventas")
    filas = [linea.split("|") for linea in _texto(datos).splitlines() if linea.strip()]
    if filas and tuple(c.strip().lower() for c in filas[0][:2]) == CABECERA_NO_DOMICILIADOS:
        filas = filas[1:]          # la exportación trae cabecera; lo que se presenta, no
    if not filas:
        raise SireInvalido("El registro de no domiciliados no tiene ninguna fila")
    # El titular no va en la fila: va en el nombre del archivo, cuando lo trae.
    base = posixpath.basename(nombre_del_txt)
    ruc = base[2:13] if es_libro_electronico(base) else ""
    if ruc and ruc != libro.ruc:
        raise SireInvalido(f"El archivo es del RUC {ruc} y este cliente es {libro.ruc}")
    periodos = {f[0].strip() for f in filas if f[0].strip()}
    if periodos and libro.periodo not in periodos:
        raise SireInvalido(f"El archivo es del periodo {sorted(periodos)[0]} y este proceso es de {libro.periodo}")

    comprobantes = []
    contabilidad = _moneda_de_la_contabilidad(nombre_del_txt)
    for i, campos in enumerate(filas, 1):
        if len(campos) < CAMPOS_NO_DOMICILIADO:
            raise SireInvalido(f"La fila {i} del registro de no domiciliados tiene {len(campos)} campos y su anexo "
                               f"tiene {CAMPOS_NO_DOMICILIADO}")
        try:
            c = _un_no_domiciliado(campos, archivo_nombre, contabilidad)
        except ValueError as e:
            raise SireInvalido(f"La fila {i} del registro de no domiciliados no se pudo leer ({e})") from e
        if not c.fecha_emision or not c.tipo_cp.strip():
            raise SireInvalido(f"La fila {i} del registro de no domiciliados no trae fecha de emisión o tipo de "
                               "comprobante")
        comprobantes.append(c)
    return comprobantes


def parsear(datos: bytes, libro: Libro, archivo_nombre: str = "") -> list[Comprobante]:
    """TXT (o ZIP) del SIRE → comprobantes del libro que se está trabajando.

    Lee el registro de compras o de ventas y, desde la 15.3.0, el de compras de no domiciliados: suelto —se reconoce
    por su contenido o por el código de su nombre— o dentro del ZIP de lo declarado, junto al otro. Falla con un
    motivo concreto —RUC, periodo o tipo de registro— en vez de cargar comprobantes que no son de este proceso.
    """
    if zipfile.is_zipfile(io.BytesIO(datos)):
        txts = _txts_del_zip(datos)
        de_no_domiciliados = [(n, c) for n, c in txts if _de_no_domiciliados(c, n)]
        resto = [c for n, c in txts if not _de_no_domiciliados(c, n)]
        comprobantes = []
        registro = next((c for c in resto if _tiene_la_forma(_texto(c[:4096]))), None)
        if registro is not None:
            comprobantes = _parsear_registro(registro, libro, archivo_nombre)
        elif not de_no_domiciliados:
            # Ninguno tiene ninguna de las formas: se lee el primero para fallar con su motivo de siempre.
            comprobantes = _parsear_registro(resto[0], libro, archivo_nombre)
        for nombre, contenido in de_no_domiciliados:
            comprobantes.extend(_parsear_no_domiciliados(contenido, libro, archivo_nombre, nombre))
        return comprobantes
    if _de_no_domiciliados(datos, archivo_nombre):
        return _parsear_no_domiciliados(datos, libro, archivo_nombre, archivo_nombre)
    return _parsear_registro(datos, libro, archivo_nombre)


def _parsear_registro(datos: bytes, libro: Libro, archivo_nombre: str) -> list[Comprobante]:
    """El registro de compras o de ventas (un TXT, ya fuera de su ZIP) → comprobantes."""
    filas = leer_lineas(datos)
    if not filas:
        raise SireInvalido("El archivo del SIRE no tiene ninguna fila")

    rucs = {f[0].strip() for f in filas if f and f[0].strip()}
    if rucs and libro.ruc not in rucs:
        raise SireInvalido(f"El archivo es del RUC {sorted(rucs)[0]} y este cliente es {libro.ruc}")
    periodos = {f[2].strip() for f in filas if len(f) > 2 and f[2].strip()}
    if periodos and libro.periodo not in periodos:
        raise SireInvalido(f"El archivo es del periodo {sorted(periodos)[0]} y este proceso es de {libro.periodo}")

    comprobantes = []
    for i, campos in enumerate(filas, 1):
        if len(campos) < MINIMO_CAMPOS:
            raise SireInvalido(f"La fila {i} tiene {len(campos)} campos: no parece un archivo del SIRE")
        try:
            c = _una(campos, libro, archivo_nombre)
        except ValueError as e:
            raise SireInvalido(f"La fila {i} no se pudo leer ({e}). "
                               f"¿Es el registro de {'ventas' if libro.es_venta else 'compras'}?") from e
        if not c.fecha_emision or not c.tipo_cp.strip():
            raise SireInvalido(f"La fila {i} no trae fecha de emisión o tipo de comprobante: "
                               f"¿es el registro de {'ventas' if libro.es_venta else 'compras'}?")
        comprobantes.append(c)
    return comprobantes
