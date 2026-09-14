"""Leer: de los archivos que entrega SUNAT —el XML UBL de cada comprobante, un ZIP con varios, la propuesta del SIRE— a
un documento `open-accounting` ya revisado.

Lo que llega son bytes o texto: quien los leyó del disco o los recibió por un protocolo es la puerta, no esto.
"""
from __future__ import annotations

from typing import Iterable

from .. import validar
from ..lectores import archivos as lectura_archivos
from ..lectores import sire_txt
from .preparacion import bytes_de, documento, libro_de


# Los bytes con que empieza un PDF o una imagen: lo que llega por un protocolo no trae nombre de archivo.
_FIRMAS = ((b"%PDF-", "comprobante.pdf"), (b"\xff\xd8\xff", "comprobante.jpg"), (b"\x89PNG\r\n\x1a\n", "comprobante.png"))


def _nombre_de(datos: bytes) -> str:
    """Un nombre coherente con lo que los bytes dicen que es. Lo que llega por un protocolo no
    tiene nombre de archivo, y el lector clasifica por extension o por bytes magicos. Un PDF o una foto se nombran
    como lo que son (hito 0.7): así cuentan como pendientes de leer y no como un XML inválido."""
    for firma, nombre in _FIRMAS:
        if datos.startswith(firma):
            return nombre
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "comprobante.webp"
    return "entrada.zip" if datos[:4] == b"PK" else "comprobante.xml"


def leer_xml(contenido: str, libro: dict, es_base64: bool = False) -> dict:
    """XML UBL 2.1 de SUNAT (uno, o un ZIP con varios) -> documento `open-accounting`."""
    lib = libro_de({"libro": libro})
    datos = bytes_de(contenido, es_base64)
    lote = lectura_archivos.Lote()
    # El nombre NO decide si es un ZIP: lo deciden los bytes. Llamarlo ".zip" hacia que un
    # XML suelto en base64 —lo natural desde un agente— se rechazara como "ZIP danado".
    lectura_archivos.expandir(_nombre_de(datos), datos, lote=lote)
    res = lectura_archivos.convertir_xml(lote, lib)
    comprobantes = lectura_archivos.ordenar(res.comprobantes)
    validar.revisar(comprobantes, lib)
    return documento(lib, comprobantes,
                     _lectura={"ignorados": len(res.ignorados), "errores": res.errores,
                               "pendientes_de_leer": len(res.pendientes_ia)})


def leer_archivos(archivos: Iterable[tuple[str, bytes | None]], libro: dict) -> dict:
    """Varios archivos con su nombre —XML, ZIP, y lo que no se lee aquí: CDR, PDF, fotos— -> documento `open-accounting`.

    Es la lectura de quien tiene los archivos en la mano, como la línea de comandos: el nombre de cada uno queda como
    procedencia (`archivo_nombre`). Un archivo que no se pudo abrir llega con `None` en vez de bytes y se anota como
    error, en su orden. `_lectura` dice cuántos se leyeron, cuántos se ignoraron, cuáles fallaron y cuántos PDF o
    imágenes quedan pendientes de leer."""
    lib = libro_de({"libro": libro})
    lote = lectura_archivos.Lote()
    for nombre, datos in archivos:
        if datos is None:
            lote.error(nombre, "No existe")
            continue
        lectura_archivos.expandir(nombre, datos, lote=lote)
    res = lectura_archivos.convertir_xml(lote, lib)
    comprobantes = lectura_archivos.ordenar(res.comprobantes)
    validar.revisar(comprobantes, lib)
    return documento(lib, comprobantes,
                     _lectura={"archivos": len(lote.entradas), "ignorados": len(res.ignorados),
                               "errores": res.errores, "pendientes_de_leer": len(res.pendientes_ia)})


def leer_propuesta_sire(contenido: str, libro: dict, es_base64: bool = False) -> dict:
    """El TXT (o el ZIP) de la propuesta que entrega SUNAT -> documento `open-accounting`."""
    lib = libro_de({"libro": libro})
    comprobantes = sire_txt.parsear(bytes_de(contenido, es_base64), lib)
    comprobantes = lectura_archivos.ordenar(comprobantes)
    validar.revisar(comprobantes, lib)
    return documento(lib, comprobantes)
