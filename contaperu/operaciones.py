"""Operaciones de alto nivel: documento `pe-ledger` entra, documento `pe-ledger` sale.

Es la capa que consume el servidor MCP, y sirve igual a cualquier aplicación que prefiera
hablar con diccionarios en vez de con los objetos del modelo. Todas las funciones de aquí son
**puras**: no leen disco, no salen a la red, no guardan nada. La misma entrada da siempre la
misma salida.

El contrato es sencillo: los documentos son los del estándar (ver `estandar/LEEME.md`), la
configuración contable del contribuyente entra por parámetro, y los archivos binarios salen en
base64 porque un JSON no sabe llevar bytes.
"""
from __future__ import annotations

import base64
from typing import Any

from . import asiento as asi
from . import detracciones, drivers, generar as gen, pcge, partida_doble, validar
from .lectores import archivos as lectura_archivos, sire_txt
from .modelo import Comprobante, Libro

# Ojo: NO se redefine aquí. Era la segunda copia del mismo número.
from ._version import PE_LEDGER  # noqa: E402  (constante, no un módulo)

# Tope de seguridad. Un mes de una PYME son decenas o cientos de comprobantes; muchos miles en
# una sola llamada es casi siempre un error de quien llama, y conviene decirlo en vez de
# quedarse pensando.
MAXIMO_COMPROBANTES = 5000


class DocumentoInvalido(ValueError):
    """El documento no cumple el estándar lo bastante como para poder trabajar con él."""


# --- conversión entre el estándar y el modelo --------------------------------------

def libro_de(doc: dict) -> Libro:
    datos = doc.get("libro")
    if not isinstance(datos, dict):
        raise DocumentoInvalido("Falta el bloque `libro`: sin RUC, periodo y tipo no hay contabilidad.")
    try:
        return Libro(ruc=datos.get("ruc", ""), razon_social=datos.get("razon_social", ""),
                     periodo=datos.get("periodo", ""), tipo=datos.get("tipo", ""))
    except ValueError as e:
        raise DocumentoInvalido(str(e)) from None


def comprobantes_de(doc: dict) -> list[Comprobante]:
    crudos = doc.get("comprobantes") or []
    if not isinstance(crudos, list):
        raise DocumentoInvalido("`comprobantes` tiene que ser una lista.")
    if len(crudos) > MAXIMO_COMPROBANTES:
        raise DocumentoInvalido(
            f"{len(crudos)} comprobantes en una sola llamada; el tope es {MAXIMO_COMPROBANTES}. "
            "Divídelo por periodo o por lote.")
    try:
        return [Comprobante.de_dict(c) for c in crudos]
    except (ValueError, TypeError) as e:
        raise DocumentoInvalido(f"Un comprobante no se pudo leer: {e}") from None


def documento(libro: Libro, comprobantes: list[Comprobante] | None = None,
              lineas: list[dict] | None = None, **extra) -> dict:
    """Arma un documento `pe-ledger` con lo que se le dé."""
    doc: dict[str, Any] = {
        "pe_ledger": PE_LEDGER,
        "libro": {"ruc": libro.ruc, "razon_social": libro.razon_social,
                  "periodo": libro.periodo, "tipo": libro.tipo},
    }
    if comprobantes is not None:
        doc["comprobantes"] = [c.a_dict() for c in comprobantes]
    if lineas is not None:
        doc["asiento"] = lineas
    doc.update(extra)
    return doc


def configuracion(contab: dict | None = None) -> dict:
    """La configuración contable efectiva: los valores por defecto con lo del contribuyente
    encima, fundidos en profundidad. Sin argumentos devuelve los de serie.

    Acepta las dos formas, y esto importa: lo que devuelve esta función **se puede volver a
    pasar tal cual**, que es lo que hace cualquiera —persona o agente— al pedir la
    configuración de partida, cambiarle una cuenta y devolverla. La forma anidada
    (`{"concar": {...}}`) existe porque así la guardan las aplicaciones que separan la
    configuración del estudio de la de cada RUC; para eso está `asiento.config_de`, con sus
    tres capas.
    """
    if not contab:
        return asi.config_de(None)
    encima = contab.get("concar") if "concar" in contab else contab
    return asi.merge_config(asi.config_de(None), encima or {})


# --- lectura -----------------------------------------------------------------------

def _bytes_de(contenido: str, es_base64: bool) -> bytes:
    if es_base64:
        try:
            return base64.b64decode(contenido, validate=True)
        except Exception as e:
            raise DocumentoInvalido(f"El contenido no es base64 válido: {e}") from None
    return contenido.encode("utf-8")


def _nombre_de(datos: bytes) -> str:
    """Un nombre coherente con lo que los bytes dicen que es. Lo que llega por el protocolo no
    tiene nombre de archivo, y el lector clasifica por extension o por bytes magicos."""
    return "entrada.zip" if datos[:4] == b"PK" else "comprobante.xml"


def leer_xml(contenido: str, libro: dict, es_base64: bool = False) -> dict:
    """XML UBL 2.1 de SUNAT (uno, o un ZIP con varios) -> documento `pe-ledger`."""
    lib = libro_de({"libro": libro})
    datos = _bytes_de(contenido, es_base64)
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


def leer_propuesta_sire(contenido: str, libro: dict, es_base64: bool = False) -> dict:
    """El TXT (o el ZIP) de la propuesta que entrega SUNAT -> documento `pe-ledger`."""
    lib = libro_de({"libro": libro})
    comprobantes = sire_txt.parsear(_bytes_de(contenido, es_base64), lib)
    comprobantes = lectura_archivos.ordenar(comprobantes)
    validar.revisar(comprobantes, lib)
    return documento(lib, comprobantes)


# --- validación --------------------------------------------------------------------

def revisar(doc: dict, contab: dict | None = None) -> dict:
    """Aplica las reglas deterministas y devuelve el documento con `estado` y
    `observaciones` puestos, más un resumen de lo que hay que mirar."""
    libro = libro_de(doc)
    comprobantes = comprobantes_de(doc)
    conf = configuracion(contab)
    limpiadas = detracciones.normalizar(comprobantes, conf)
    validar.revisar(comprobantes, libro)
    errores = [c for c in comprobantes if c.tiene_errores]
    avisos = [c for c in comprobantes if c.observaciones and not c.tiene_errores]
    salida = documento(libro, comprobantes)
    salida["_revision"] = {
        "total": len(comprobantes),
        "con_error": len(errores),
        "con_aviso": len(avisos),
        "detracciones_descartadas": len(limpiadas),
        "bloquean_la_exportacion": [
            {"serie_numero": f"{c.serie}-{c.numero}".strip("-"),
             "observaciones": [o.a_dict() for o in c.observaciones if o.nivel == "error"]}
            for c in errores
        ],
    }
    return salida


def cuadrar(lineas: list[dict]) -> dict:
    """¿La suma del Debe es igual a la del Haber?"""
    return partida_doble.cuadra(lineas).a_dict()


# --- asiento y exportación ---------------------------------------------------------

def _preparar(doc: dict, contab: dict | None, incluir_observados: bool):
    libro = libro_de(doc)
    comprobantes = [c for c in comprobantes_de(doc) if not c.excluida]
    if not comprobantes:
        raise DocumentoInvalido("No hay comprobantes que procesar.")
    conf = configuracion(contab)
    validar.revisar(comprobantes, libro)
    if not incluir_observados:
        con_error = [c for c in comprobantes if c.tiene_errores]
        if con_error:
            raise DocumentoInvalido(
                f"{len(con_error)} comprobantes tienen observaciones que bloquean. "
                "Corrígelos, o pide `incluir_observados` si sabes lo que haces.")
    return libro, comprobantes, conf


def generar_asiento(doc: dict, contab: dict | None = None, correlativos: dict | None = None,
                    incluir_observados: bool = False) -> dict:
    """Comprobantes -> líneas de diario del estándar, sin formato de ningún ERP."""
    libro, comprobantes, conf = _preparar(doc, contab, incluir_observados)
    venta = libro.es_venta
    corr = {s: 1 for s in asi.sub_diarios_presentes(comprobantes, conf, venta)}
    corr.update(correlativos or {})
    # Directo a las líneas neutrales: sin pasar por las columnas de ningún ERP.
    neutrales, rangos = asi.lineas_del_libro(libro, comprobantes, conf, corr)
    lineas = [ln.a_dict() for ln in neutrales]
    cuadre = partida_doble.cuadra(lineas)
    salida = documento(libro, lineas=lineas)
    salida["_asiento"] = {"lineas": len(lineas), "sub_diarios": dict(rangos), "cuadre": cuadre.a_dict()}
    return salida


def exportar(doc: dict, driver: str = "concar", contab: dict | None = None,
             correlativos: dict | None = None, incluir_observados: bool = False) -> dict:
    """Genera el archivo que pide un sistema contable.

    El resultado trae `texto` cuando la salida es legible (el TXT del SIRE, el CSV) y
    `contenido_base64` cuando son bytes (el Excel de CONCAR). Siempre trae el nombre de archivo
    que el destino espera.
    """
    libro, comprobantes, conf = _preparar(doc, contab, incluir_observados)
    mod = drivers.obtener(driver)
    params: dict[str, Any] = {}
    if drivers.contrato.necesita_asiento(mod):
        venta = libro.es_venta
        corr = {s: 1 for s in asi.sub_diarios_presentes(comprobantes, conf, venta)}
        corr.update(correlativos or {})
        params = {"contab": conf, "correlativos": corr}
    exp = gen.generar(libro, comprobantes, driver, incluir_errores=incluir_observados, **params)

    salida: dict[str, Any] = {
        "driver": driver, "formato": exp.formato, "archivo": exp.nombre,
        "filas": exp.n_filas, "resumen": exp.resumen,
    }
    if exp.txt:
        salida["texto"] = exp.txt.decode("utf-8", errors="replace")
        salida["zip_base64"] = base64.b64encode(exp.zip).decode()
        salida["archivo_zip"] = exp.nombre_zip
    else:
        contenido = exp.contenido
        salida["content_type"] = exp.content_type
        if (exp.content_type or "").startswith("text/"):
            salida["texto"] = contenido.decode("utf-8-sig", errors="replace")
        salida["contenido_base64"] = base64.b64encode(contenido).decode()
    return salida


def adaptar_pcge(lineas: list[dict]) -> dict:
    """Aplica las equivalencias del PCGE 2026. Sin la tabla oficial cargada no toca nada
    y lo dice: en este proyecto ninguna regla contable se escribe de memoria."""
    salida, informe = pcge.adaptar(lineas)
    return {"asiento": salida, "informe": informe.a_dict()}
