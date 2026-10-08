"""Del diccionario del estándar al libro y los comprobantes del modelo, y de vuelta.

Es la frontera del motor: aquí entra lo que escribió otro —un ERP, una aplicación, el lector de un XML— y sale
tipado. Por eso **lo desconocido se rechaza en vez de ignorarse**: un dato que se cuela sin error es un dato que
se pierde sin aviso, y los topes de abajo están para que un error de quien llama se diga en vez de quedarse
pensando.
"""
from __future__ import annotations

from typing import Any

from ...asiento.lineas import LineaDiario
from ..._version import OPEN_ACCOUNTING
from ...errores import DocumentoInvalido
from ...modelo import Comprobante, Libro, serie_y_numero


# Tope de seguridad. Un mes de una PYME son decenas o cientos de comprobantes; muchos miles en
# una sola llamada es casi siempre un error de quien llama, y conviene decirlo en vez de
# quedarse pensando.
MAXIMO_COMPROBANTES = 5000

# --- conversión entre el estándar y el modelo --------------------------------------

def version_del_documento(doc: dict) -> None:
    """Un documento que se declara de una versión anterior se rechaza diciendo qué cambió.

    La 1.0 no acepta la 0.3 (John, 18-sep-2026: «como todavía ningún ERP no lo usa, puedes hacer la limpieza para que
    esté bien»). Leer las dos habría costado dos caminos en el lector y una regla de cuál gana, para una
    compatibilidad que nadie necesitaba. Un documento sin la clave no se rechaza: es lo que hace quien construye el
    documento con el motor, que la estampa él."""
    declarada = str(doc.get("open_accounting") or "").strip()
    if declarada and declarada != OPEN_ACCOUNTING:
        raise DocumentoInvalido(
            f"Este documento se declara `open_accounting` {declarada} y el motor habla la {OPEN_ACCOUNTING}. "
            "De la 0.3 a la 1.0 cambian tres cosas: la imputación va dentro del documento, en el bloque "
            "`imputaciones` llaveado por `id_externo`; cada línea del asiento lleva su `clase`; y `rol` y "
            "`libro.tipo` se validan contra el catálogo publicado del estándar. La guía, paso a paso, está en "
            "`estandar/MIGRAR-A-1.0.md`.")


def libro_de(doc: dict) -> Libro:
    version_del_documento(doc)
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


def lineas_de(doc: dict) -> list[LineaDiario] | None:
    """Las líneas del bloque `asiento` del documento, o `None` si no lo trae (5.2).

    Hermano de `comprobantes_de`, y hacía falta: había lectores para el libro, los comprobantes y las imputaciones,
    y el bloque `asiento` **solo se escribía**. El esquema del estándar lo admite de entrada desde la 1.0 —su
    descripción dice «líneas de diario ya armadas»— y el motor no sabía leerlo, así que **no podía releer su propio
    documento**: lo que devolvía `generar_asiento` no entraba por `exportar`.

    Quien lo trae manda sobre el motor: con este bloque el asiento **no se rearma**, se usa. Los `comprobantes`
    siguen haciendo falta —de su cabecera salen hechos que ninguna línea guarda, como el vencimiento— y es
    exactamente lo que el driver `asiento_contable` ya escribe en su archivo: los dos bloques, para que el documento
    se baste.

    `LineaDiario.de_dict` hace la validación: sin cuenta, sin sentido, sin importe o **sin clase** no pasa, un
    sentido que no es D ni H no pasa, y una clase que contradice su cuenta tampoco. Una clave que la línea no
    declara se rechaza en vez de perderse."""
    crudas = doc.get("asiento")
    if crudas is None:
        return None
    if not isinstance(crudas, list):
        raise DocumentoInvalido("`asiento` tiene que ser una lista de líneas de diario.")
    try:
        return [LineaDiario.de_dict(l) for l in crudas]
    except (ValueError, TypeError) as e:
        raise DocumentoInvalido(f"Una línea del asiento no se pudo leer: {e}") from None


def documento(libro: Libro, comprobantes: list[Comprobante] | None = None,
              lineas: list[dict] | None = None, **extra) -> dict:
    """Arma un documento `open-accounting` con lo que se le dé."""
    doc: dict[str, Any] = {
        "open_accounting": OPEN_ACCOUNTING,
        "libro": {"ruc": libro.ruc, "razon_social": libro.razon_social,
                  "periodo": libro.periodo, "tipo": libro.tipo},
    }
    if comprobantes is not None:
        doc["comprobantes"] = [c.a_dict() for c in comprobantes]
    if lineas is not None:
        doc["asiento"] = lineas
    doc.update(extra)
    return doc


def serie_numero(c: Comprobante) -> str:
    return serie_y_numero(c.serie, c.numero)


