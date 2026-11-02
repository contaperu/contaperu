"""Leer lo que SUNAT contesta cuando se le pregunta qué ve de un periodo: las inconsistencias por comprobante y el
reporte de las casillas del 621.

Los dos se escribieron **después de medir** (01-nov-2026, con un RUC real, en un mes sin presentar y en uno
presentado), y cada decisión de abajo sale de lo que se vio y no del manual —que en los dos se equivoca—. Lo medido,
con sus cifras, está en las notas de cada operación en `datos/sunat/sire_api.json`. Las pruebas usan archivos
sintéticos con la forma real: lo de un contribuyente no entra en este repositorio.

Lo que NO tiene lector aquí, y por qué: los **excluidos** y los **no incluidos** llegan con el formato de la
exportación de la propuesta, que `comprobantes.sire_txt` ya lee; y el **resumen de inconsistencias** es un JSON de dos
niveles que se usa tal cual llega.

Los dos lectores reciben los bytes de la respuesta —o el ZIP que la trae, como lo baja `ticket_archivo`— y no abren
archivos ni salen a la red: son núcleo.
"""
from __future__ import annotations

import collections
import io
import re
import unicodedata
import zipfile
from decimal import Decimal, InvalidOperation
from typing import Any

from ..comprobantes import _zip
from ..comprobantes.comprobante import clave_de
from ..comprobantes.sire_txt import SireInvalido

__all__ = ["leer_casillas", "leer_inconsistencias"]


def _normal(rotulo: str) -> str:
    """Un rótulo de SUNAT sin tildes, sin mayúsculas y sin puntuación: «Número Doc. Emisor» → «numero doc emisor».
    Así un acento o un punto de más no rompen la lectura."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", rotulo) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", sin_tildes.lower()).split())


def _texto(datos: bytes | str) -> str:
    """El texto de la respuesta. Acepta el texto, sus bytes o el ZIP que lo trae (el primer TXT de dentro, o su único
    archivo). UTF-8 —con o sin BOM—, que es lo que se midió; si no lo es, latin-1, que no falla nunca."""
    if isinstance(datos, str):
        return datos
    if datos[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(datos)) as z:
                nombres = [n for n in z.namelist() if not n.endswith("/")]
                txts = [n for n in nombres if n.lower().endswith(".txt")] or nombres
                if not txts:
                    raise SireInvalido("El ZIP no trae ningún archivo dentro")
                datos = _zip.leer(z, z.getinfo(txts[0]))
        except zipfile.BadZipFile:
            raise SireInvalido("Empieza como un ZIP y no se puede abrir") from None
        except _zip.Desmedido as e:
            raise SireInvalido(str(e)) from None
    try:
        return datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        return datos.decode("latin-1")


def _importe(texto: str, *, donde: str) -> Decimal | None:
    """Un importe de SUNAT, con su signo: `1,234.56`, `-1,234.56` o `0.00`. Vacío es «no aplica» y vuelve `None`, no
    cero: en el reporte de casillas una celda vacía es una columna que esa casilla no tiene."""
    texto = texto.strip().replace(",", "")
    if not texto:
        return None
    try:
        return Decimal(texto)
    except InvalidOperation:
        raise SireInvalido(f"{donde}: «{texto}» no es un importe") from None


def _campos(linea: str) -> list[str]:
    """Los campos de una línea separada por `|`. Lo medido no trae palote al final; si un día lo trae, no cuenta como
    un campo vacío de más."""
    linea = linea.rstrip("\r\n")
    return linea[:-1].split("|") if linea.endswith("|") else linea.split("|")


# ── Las inconsistencias por comprobante ──────────────────────────────────────────────────────────────────────────

# Rótulo (normalizado) → lo que se lee. Lo demás de la fila —importes, razón social, fechas, el número de operación—
# no se lee: quien integra ya tiene el comprobante, y lo que le falta es qué ve SUNAT en él.
_DE_LA_INCONSISTENCIA = {
    "tipo cp": "tipo",
    "serie de cp": "serie",
    "numero de cp": "numero",
    "numero doc emisor": "doc",
    "campo de registro": "campo",
    "codigo de inconsistencia": "codigo",
    "descripcion de la inconsistencia": "descripcion",
    "semaforo": "semaforo",
    "monto de la inconsistencia": "monto",
}
# El rótulo que la cabecera trae y las filas no: medido en los dos meses, con dos cabeceras distintas.
_SOLO_EN_LA_CABECERA = "tipo doc emisor"


def leer_inconsistencias(datos: bytes | str) -> dict[str, list[dict[str, Any]]]:
    """El archivo de `inconsistencias_comprobante`, leído: qué inconsistencia ve SUNAT en cada comprobante.

    Devuelve `{"por_comprobante": [...], "del_archivo": [...]}`. Cada entrada de `por_comprobante` es
    `{clave, codigo, descripcion, semaforo, campo, monto}`: `clave` es la de `clave_de` —tipo, serie, número sin ceros
    y documento del emisor—, la misma con la que una aplicación sabe si ya tiene ese comprobante; `monto` es un
    `Decimal` con su signo. Un comprobante con el mismo código en varios campos trae una entrada por campo, cada una
    con su monto. `del_archivo` son las que no nombran comprobante —la cantidad o los montos totales del archivo
    distintos de la propuesta—, con las mismas claves menos `clave`.

    Tres cosas medidas que este lector resuelve, y que un lector que se fiara de la cabecera no:

    - **A las filas les falta «Tipo Doc. Emisor»**, que la cabecera sí trae: desde ahí la fila va corrida un lugar. Se
      lee con la cabecera sin ese rótulo. Si un día SUNAT lo arregla y la fila trae tantos campos como la cabecera, se
      lee con la cabecera entera, sin tocar nada.
    - **La cabecera cambia de un mes a otro** —la de un mes sin presentar empieza por «Archivo cargado»—, así que cada
      dato se busca por su rótulo y no por su posición.
    - **Cada fila puede venir dos veces**, idéntica: se queda una.

    Una forma que no es esta —un rótulo que falta, o filas de otro largo— es un `SireInvalido` con su motivo, nunca
    una lista a medias.
    """
    lineas = [x for x in _texto(datos).splitlines() if x.strip()]
    if not lineas:
        raise SireInvalido("El archivo de inconsistencias está vacío: ni siquiera trae la cabecera")
    cabecera = [_normal(r) for r in _campos(lineas[0])]
    filas = [(n, _campos(x)) for n, x in enumerate(lineas[1:], start=2)]
    if not filas:
        return {"por_comprobante": [], "del_archivo": []}

    largo = collections.Counter(len(f) for _n, f in filas).most_common(1)[0][0]
    if largo == len(cabecera) - 1 and _SOLO_EN_LA_CABECERA in cabecera:
        cabecera.remove(_SOLO_EN_LA_CABECERA)
    elif largo != len(cabecera):
        raise SireInvalido(f"La cabecera de las inconsistencias trae {len(cabecera)} rótulos y las filas {largo} campos: "
                           "no se sabe a qué columna va cada dato")
    faltan = [r for r in _DE_LA_INCONSISTENCIA if r not in cabecera]
    if faltan:
        raise SireInvalido(f"Al archivo de inconsistencias le falta {', '.join(faltan)}: no es la forma que se midió")
    donde = {campo: cabecera.index(rotulo) for rotulo, campo in _DE_LA_INCONSISTENCIA.items()}

    por_comprobante: list[dict[str, Any]] = []
    del_archivo: list[dict[str, Any]] = []
    vistas: set[tuple[str, ...]] = set()
    for n, fila in filas:
        if len(fila) != largo:
            raise SireInvalido(f"La línea {n} de las inconsistencias trae {len(fila)} campos y las demás {largo}")
        if tuple(fila) in vistas:
            continue
        vistas.add(tuple(fila))
        valor = {campo: fila[i].strip() for campo, i in donde.items()}
        entrada: dict[str, Any] = {"codigo": valor["codigo"], "descripcion": valor["descripcion"],
                                   "semaforo": valor["semaforo"], "campo": valor["campo"],
                                   "monto": _importe(valor["monto"], donde=f"La línea {n} de las inconsistencias")}
        if valor["tipo"]:
            por_comprobante.append({"clave": clave_de(valor["tipo"], valor["serie"], valor["numero"], valor["doc"]),
                                    **entrada})
        else:
            del_archivo.append(entrada)
    return {"por_comprobante": por_comprobante, "del_archivo": del_archivo}


# ── El reporte de las casillas del 621 ───────────────────────────────────────────────────────────────────────────

_BLOQUES = ("ventas", "compras")


def _columna_de_casillas(rotulo: str, posicion: int) -> str:
    """Qué es cada columna de un bloque de casillas, por su rótulo. La primera es el concepto, y su rótulo es el nombre
    del bloque; la de lo del contribuyente se llama distinto en ventas y en compras."""
    if posicion == 0:
        return "concepto"
    if rotulo == "casilla":
        return "casilla"
    if "contribuyente" in rotulo:
        return "registro"
    if rotulo == "inconsistencias en registros":
        return "inconsistencias"
    if rotulo == "propuesta sunat":
        return "propuesta"
    if rotulo.startswith("ddjj"):
        return "declarado"
    if rotulo.startswith("diferencia"):
        return "diferencia"
    return ""


# En el orden en que se devuelven.
_COLUMNAS_DE_CASILLAS = ("casilla", "concepto", "registro", "inconsistencias", "propuesta", "declarado", "diferencia")


def leer_casillas(datos: bytes | str) -> dict[str, Any]:
    """El reporte de `casillas`, leído: cada concepto del 621 con su casilla y lo que dice cada fuente.

    Devuelve `{"numero_de_orden", "ventas", "compras"}`. `ventas` y `compras` son listas, una fila por concepto en el
    orden del reporte, cada una `{casilla, concepto, registro, inconsistencias, propuesta, declarado, diferencia}`:
    `casilla` es el número del 621 —vacío en las filas de desglose al 18 % y al 10 %, que van debajo de la suya—;
    `registro` es lo de los registros del contribuyente; `propuesta`, lo de SUNAT; `declarado`, lo de la declaración
    jurada; y `diferencia`, la de la propuesta contra lo declarado. Los importes son `Decimal` con su signo, y `None`
    donde la columna no aplica: vacío no es cero. `numero_de_orden` es el de la declaración jurada, de la cabecera
    («DDJJ N° …»), o `""` si no trae ninguno distinto de 0.

    Lo medido (comparada, setiembre de 2026, ya presentado): un texto separado por `|` en dos bloques, ventas y luego
    compras, cada uno con su línea de rótulos y otra de guiones; los importes con coma de miles. Una forma que no es
    esta es un `SireInvalido`.
    """
    resultado: dict[str, Any] = {"numero_de_orden": "", "ventas": [], "compras": []}
    bloque = ""
    columnas: list[str] = []
    vistos: set[str] = set()
    for n, linea in enumerate(_texto(datos).splitlines(), start=1):
        campos = _campos(linea)
        if len(campos) == 1:
            continue            # una línea vacía o de guiones
        rotulos = [_normal(c) for c in campos]
        if len(rotulos) > 1 and rotulos[1] == "casilla":
            bloque = rotulos[0]
            if bloque not in _BLOQUES:
                raise SireInvalido(f"La línea {n} del reporte de casillas abre un bloque «{campos[0].strip()}», y solo "
                                   "se conocen Ventas y Compras")
            columnas = [_columna_de_casillas(r, i) for i, r in enumerate(rotulos)]
            if sorted(columnas) != sorted(_COLUMNAS_DE_CASILLAS):
                raise SireInvalido(f"Los rótulos del bloque de {bloque} del reporte de casillas no son los que se "
                                   f"midieron: {', '.join(c.strip() for c in campos)}")
            orden = re.search(r"(\d+)", campos[columnas.index("declarado")])
            if orden and int(orden.group(1)) and not resultado["numero_de_orden"]:
                resultado["numero_de_orden"] = orden.group(1)
            vistos.add(bloque)
            continue
        if not bloque:
            raise SireInvalido(f"La línea {n} del reporte de casillas trae datos antes de la cabecera de un bloque")
        if len(campos) != len(columnas):
            raise SireInvalido(f"La línea {n} del reporte de casillas trae {len(campos)} campos y su cabecera "
                               f"{len(columnas)}")
        donde = f"La línea {n} del reporte de casillas"
        fila: dict[str, Any] = {"casilla": "", "concepto": ""}
        for columna, valor in zip(columnas, campos):
            fila[columna] = valor.strip() if columna in ("casilla", "concepto") else _importe(valor, donde=donde)
        resultado[bloque].append({c: fila[c] for c in _COLUMNAS_DE_CASILLAS})
    if not vistos:
        raise SireInvalido("No es un reporte de casillas: no trae el bloque de ventas ni el de compras")
    return resultado
