"""Entrada de archivos: desarmar ZIP, clasificar por tipo, convertir XML.

La subida puede traer el ZIP tal cual lo entrega el facturador (XML + CDR
`R-….xml` + PDF), ZIP de un mes entero o archivos sueltos. Reglas:
- tope de archivos por lote (50): lo que pase del tope se reporta, no se procesa;
- ZIP anidados no se abren (se reportan);
- el CDR se detecta por su raíz XML, no por el nombre.
"""
from __future__ import annotations

import io
import posixpath
import zipfile
from dataclasses import dataclass, field
from datetime import date

from . import sire_txt, xml_ubl
from ..modelo import Comprobante, Libro

TOPE_ARCHIVOS = 50
EXT_XML = (".xml",)
EXT_PDF = (".pdf",)
EXT_IMAGEN = (".jpg", ".jpeg", ".png", ".webp")
EXT_ZIP = (".zip",)
# Archivos de presentación que los facturadores meten en el mismo ZIP (hoja de estilos, CSS…): se ignoran.
EXT_AUXILIAR = (".xsl", ".xslt", ".css", ".htm", ".html", ".txt", ".json", ".js")
EXT_TEXTO = (".txt",)   # donde puede venir la propuesta del SIRE


@dataclass
class Entrada:
    nombre: str
    datos: bytes

    @property
    def extension(self) -> str:
        return posixpath.splitext(self.nombre.lower())[1]

    @property
    def es_auxiliar(self) -> bool:
        # El TXT de la propuesta del SIRE es un comprobante más, no un acompañante:
        # antes caía aquí y el proceso decía "no había ningún comprobante dentro".
        return self.extension in EXT_AUXILIAR and not self.es_sire

    @property
    def es_sire(self) -> bool:
        """La propuesta que SUNAT entrega al exportar un periodo (se mira el contenido)."""
        return self.extension in EXT_TEXTO and sire_txt.es_sire(self.datos)

    @property
    def es_xml(self) -> bool:
        if self.es_auxiliar:
            return False
        return self.extension in EXT_XML or self.datos.lstrip()[:1] == b"<"

    @property
    def es_zip(self) -> bool:
        return self.extension in EXT_ZIP or self.datos[:4] == b"PK\x03\x04"

    @property
    def es_pdf(self) -> bool:
        return self.extension in EXT_PDF or self.datos[:5] == b"%PDF-"

    @property
    def es_imagen(self) -> bool:
        return self.extension in EXT_IMAGEN


@dataclass
class Lote:
    entradas: list[Entrada] = field(default_factory=list)
    errores: list[dict] = field(default_factory=list)   # [{archivo, motivo}]

    def error(self, archivo: str, motivo: str) -> None:
        self.errores.append({"archivo": archivo, "motivo": motivo})


def expandir(nombre: str, datos: bytes, tope: int = TOPE_ARCHIVOS, lote: Lote | None = None) -> Lote:
    """Un archivo (o ZIP) → entradas planas. Se puede llamar varias veces con
    el mismo `lote` para acumular varios archivos subidos."""
    lote = lote or Lote()
    entrada = Entrada(nombre, datos)
    if not entrada.es_zip:
        if len(lote.entradas) >= tope:
            lote.error(nombre, f"Supera el tope de {tope} archivos por tanda")
        else:
            lote.entradas.append(entrada)
        return lote
    try:
        z = zipfile.ZipFile(io.BytesIO(datos))
    except zipfile.BadZipFile:
        lote.error(nombre, "El ZIP está dañado o no es un ZIP")
        return lote
    with z:
        for info in z.infolist():
            base = posixpath.basename(info.filename)
            if info.is_dir() or not base or base.startswith(".") or "__MACOSX" in info.filename:
                continue
            etiqueta = f"{nombre}/{base}"
            if base.lower().endswith(EXT_ZIP):
                lote.error(etiqueta, "ZIP dentro de un ZIP: descomprímelo antes de subirlo")
                continue
            if len(lote.entradas) >= tope:
                lote.error(etiqueta, f"Supera el tope de {tope} archivos por tanda")
                continue
            try:
                lote.entradas.append(Entrada(etiqueta, z.read(info)))
            except Exception as e:  # entrada corrupta o cifrada
                lote.error(etiqueta, f"No se pudo leer dentro del ZIP: {e}")
    return lote


@dataclass
class Resultado:
    comprobantes: list[Comprobante] = field(default_factory=list)
    errores: list[dict] = field(default_factory=list)
    ignorados: list[str] = field(default_factory=list)   # CDR y similares
    pendientes_ia: list[Entrada] = field(default_factory=list)  # PDF/foto: los lee la IA (Parte 6)


def convertir_xml(lote: Lote, libro: Libro) -> Resultado:
    """Convierte las entradas XML de un lote. Los PDF/imágenes quedan en
    `pendientes_ia`; el resto se reporta."""
    r = Resultado(errores=list(lote.errores))
    for e in lote.entradas:
        if e.es_auxiliar:
            r.ignorados.append(e.nombre)
        elif e.es_xml:
            try:
                r.comprobantes.append(xml_ubl.parsear(e.datos, libro.tipo, archivo_nombre=e.nombre))
            except xml_ubl.EsCdr:
                r.ignorados.append(e.nombre)
            except xml_ubl.XmlInvalido as ex:
                r.errores.append({"archivo": e.nombre, "motivo": str(ex)})
        elif e.es_sire:
            try:
                r.comprobantes.extend(sire_txt.parsear(e.datos, libro, archivo_nombre=e.nombre))
            except sire_txt.SireInvalido as ex:
                r.errores.append({"archivo": e.nombre, "motivo": str(ex)})
        elif e.es_pdf or e.es_imagen:
            r.pendientes_ia.append(e)
        else:
            r.errores.append({"archivo": e.nombre, "motivo": "Formato no reconocido (se aceptan XML, PDF, JPG, PNG y ZIP)"})
    return r


def clave_orden(c: Comprobante):
    """Orden natural del registro: fecha, tipo, serie y número (numérico si se puede)."""
    n = c.numero.lstrip("0") or "0"
    # El XML antes que la lectura por IA del mismo comprobante: así el duplicado es el PDF, no el XML.
    return (c.fecha_emision or date.min, c.tipo_cp, c.serie, (0, int(n)) if n.isdigit() else (1, n), 0 if c.origen == "xml" else 1)


def ordenar(comprobantes: list[Comprobante]) -> list[Comprobante]:
    return sorted(comprobantes, key=clave_orden)
