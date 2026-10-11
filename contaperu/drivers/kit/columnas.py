"""Un formato de archivo declarado como tabla: cada columna, el campo de la línea del comprobante que la llena y su fuente (1.1).

Para un sistema que importa sus asientos en columnas simples —un CSV, un TXT de campos separados— el driver no necesita
código de proyección: declara `COLUMNAS_DE_LINEA`, una tupla de `ColumnaDeLinea`, y su `desde_lineas` escribe con
`escribir_csv`. Quien conoce el formato de su sistema describe sus columnas con la plantilla al lado, y `contaperu
verificar-driver` le dice si la tabla cumple. La fuente es obligatoria en cada columna: ninguna regla entra sin fuente,
tampoco la de qué dato va en qué columna.

El driver CSV de serie está escrito así. CONCAR y CONTASIS siguen en código: sus columnas mezclan la cabecera del
comprobante, cortes y reglas que una tabla no dice, y sus snapshots los vigilan celda a celda.
"""
from __future__ import annotations

import csv as _csv
import io
from dataclasses import dataclass, fields
from typing import Any, Iterable

from ...asiento.lineas import LineaDiario
from . import rol as _rol

# Lo que puede llenar una columna: un campo de la línea del comprobante o, con punto, un campo de uno de sus bloques.
BLOQUES: dict[str, tuple[str, ...]] = {
    "documento": ("tipo", "tipo_cp", "serie_numero", "id_externo", "fecha_emision", "fecha_vencimiento"),
    "referencia": ("tipo", "tipo_cp", "serie_numero", "fecha"),
    # `codigo_interno` salió en la 4.0: ninguna línea lo lleva ya —el código interno es de la tabla de cada ERP y lo
    # pone su driver—, así que una columna que lo declarara saldría vacía en silencio, que es justo lo que esta tabla
    # existe para impedir.
    "detraccion": ("codigo", "tasa", "base", "nro_constancia", "fecha_constancia"),
}
# Rutas que NO son un campo de la línea: se **derivan** de lo que la línea trae. Hoy solo el `rol`, que dejó de
# viajar en la línea con el estándar 2.0 —era una etiqueta para los destinos y nadie decidía por ella— y que un
# driver sigue queriendo en su columna para que quien lea su archivo no tenga que adivinar (la decisión es de la
# 1.0). Derivarlo necesita el libro, porque el lado al que va la contraparte lo dice el libro: una columna derivada
# sale VACÍA si quien escribe no lo pasa, y eso es lo que un driver no debe hacer.
DERIVADAS: tuple[str, ...] = ("rol",)
# Qué es el dato de una columna, para quien lo escriba en un formato que distingue (una celda, un ancho fijo).
# Ojo: no es la `clase` de una línea del asiento (activo, pasivo…), que vive en `contaperu/vocabulario.py`.
CLASES = ("texto", "importe", "fecha", "numero")


@dataclass(frozen=True)
class ColumnaDeLinea:
    """Una columna del archivo: su `cabecera`, la `ruta` del campo de la línea que la llena (`cuenta`,
    `documento.serie_numero`), de dónde sale que vaya ahí (`fuente`: la plantilla o el manual del sistema) y su
    `clase`."""

    cabecera: str
    ruta: str
    fuente: str
    clase: str = "texto"


def rutas() -> frozenset[str]:
    """Todas las rutas que una columna puede llenar: los campos de la línea, los de sus bloques y las derivadas."""
    simples = {campo.name for campo in fields(LineaDiario)} - set(BLOQUES)
    return frozenset(simples | set(DERIVADAS)
                     | {f"{bloque}.{campo}" for bloque, campos in BLOQUES.items() for campo in campos})


def valor(linea: dict, ruta: str, libro: Any = None) -> Any:
    """El valor de una ruta en una línea ya en diccionario (`LineaDiario.a_dict()`); vacío si no lo lleva.

    Una ruta de `DERIVADAS` no está en la línea y se calcula; sin `libro` no se puede, y devuelve vacío en vez de
    inventarse un papel."""
    if ruta in DERIVADAS:
        return _rol.rol_de(linea, libro) if libro is not None else ""
    if "." not in ruta:
        return linea.get(ruta, "")
    bloque, campo = ruta.split(".", 1)
    return (linea.get(bloque) or {}).get(campo, "")


def problemas(columnas: Any) -> list[str]:
    """Lo que no cumple una tabla de columnas; lista vacía = se puede escribir con ella."""
    if (isinstance(columnas, (str, bytes, dict)) or not columnas
            or not all(isinstance(columna, ColumnaDeLinea) for columna in columnas)):
        return ["COLUMNAS_DE_LINEA es una tupla de kit.columnas.ColumnaDeLinea"]
    salida: list[str] = []
    validas = rutas()
    cabeceras = [columna.cabecera for columna in columnas]
    repetidas = sorted({cabecera for cabecera in cabeceras if cabeceras.count(cabecera) > 1})
    if repetidas:
        salida.append(f"COLUMNAS_DE_LINEA repite cabeceras: {', '.join(repetidas)}")
    for columna in columnas:
        if not str(columna.cabecera).strip():
            salida.append(f"la columna que lee {columna.ruta!r} no tiene cabecera")
        if columna.ruta not in validas:
            salida.append(f"la columna {columna.cabecera!r} lee {columna.ruta!r}, que no es un campo de la línea del comprobante")
        if not str(columna.fuente).strip():
            salida.append(f"la columna {columna.cabecera!r} no dice su fuente: ninguna columna entra sin ella")
        if columna.clase not in CLASES:
            salida.append(f"la columna {columna.cabecera!r} es de clase {columna.clase!r}; las que hay: "
                          f"{', '.join(CLASES)}")
    return salida


def filas(lineas: Iterable[LineaDiario], columnas: Iterable[ColumnaDeLinea],
          libro: Any = None) -> list[list[Any]]:
    """Una fila por línea, con el valor de cada columna en su orden. El `libro` hace falta para las `DERIVADAS`."""
    columnas = tuple(columnas)
    return [[valor(linea, columna.ruta, libro) for columna in columnas]
            for linea in (ln.a_dict() if hasattr(ln, "a_dict") else dict(ln) for ln in lineas)]


def escribir_csv(lineas: Iterable[LineaDiario], columnas: Iterable[ColumnaDeLinea], separador: str = ";",
                 bom: bool = True, libro: Any = None) -> bytes:
    """Las líneas → un CSV con la cabecera de cada columna, filas terminadas en CRLF y comillas solo donde hacen falta.
    `bom` antepone la marca UTF-8 con que Excel en español abre bien las tildes. El `libro` hace falta para las
    columnas `DERIVADAS`; sin él salen vacías."""
    columnas = tuple(columnas)
    buf = io.StringIO(newline="")
    escritor = _csv.writer(buf, delimiter=separador, lineterminator="\r\n", quoting=_csv.QUOTE_MINIMAL)
    escritor.writerow([columna.cabecera for columna in columnas])
    escritor.writerows(filas(lineas, columnas, libro))
    texto = buf.getvalue()
    return ("﻿" + texto if bom else texto).encode("utf-8")
