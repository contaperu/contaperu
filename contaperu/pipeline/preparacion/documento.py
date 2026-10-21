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
from ... import aplicaciones, tesoreria
from ...tesoreria import Movimiento


# Tope de seguridad. Un mes de una PYME son decenas o cientos de comprobantes; muchos miles en
# una sola llamada es casi siempre un error de quien llama, y conviene decirlo en vez de
# quedarse pensando.
MAXIMO_COMPROBANTES = 5000

# Y el de los movimientos, que es otro orden de magnitud: un mes de una cuenta bancaria activa son cientos de
# líneas y varias cuentas en el mismo documento las multiplican, así que el tope es más alto que el de los
# comprobantes. Lo que no cambia es por qué existe: un número absurdo es casi siempre un error de quien llama.
MAXIMO_MOVIMIENTOS = 20000

# Y el de las aplicaciones, que son las más numerosas de las tres: un pago que cancela diez facturas son diez, y un
# mes puede traer las de varios meses anteriores. Por eso dobla el de los movimientos. El motivo es el mismo.
MAXIMO_APLICACIONES = 40000

# --- conversión entre el estándar y el modelo --------------------------------------

def version_del_documento(doc: dict) -> None:
    """Un documento de otra MAYOR del estándar se rechaza diciendo qué cambió; de otra menor, se lee.

    **Una mayor no lee la anterior**, y es la misma decisión las tres veces que ha pasado. La 1.0 no aceptó la
    0.3 (John, 18-sep-2026: «como todavía ningún ERP no lo usa, puedes hacer la limpieza para que esté bien»), la
    2.0 no acepta la 1.0 y la 3.0 no acepta la 2.0: leer dos cuesta dos caminos en el lector y una regla de cuál
    gana.

    **Una MENOR sí se lee, y hasta la 12.0 no se leía.** Esta comparación era de igualdad exacta, así que la
    primera menor del estándar habría rechazado todos los documentos de su mayor — y una menor es **aditiva por
    definición** (`estandar/LEEME.md`, «Versionado»): lo que trae son bloques y campos opcionales, de modo que un
    documento 3.0 es un 3.1 sin usar lo nuevo. No se había visto porque el estándar solo había tenido mayores:
    0.3, 1.0, 2.0, 3.0. La 3.1 es la primera menor, y la encontró.

    Hacia adelante también se lee: un documento de una menor MAYOR que la nuestra puede traer una clave que no
    conocemos, y entonces falla donde toca —en su bloque, con el nombre de la clave— en vez de con un número de
    versión que no le dice a nadie qué arreglar.

    Un documento sin la clave no se rechaza: es lo que hace quien construye el documento con el motor."""
    declarada = str(doc.get("open_accounting") or "").strip()
    if declarada and declarada.split(".")[0] != OPEN_ACCOUNTING.split(".")[0]:
        raise DocumentoInvalido(
            f"Este documento se declara `open_accounting` {declarada} y el motor habla la {OPEN_ACCOUNTING}. "
            "Cada mayor del estándar retira algo y no lee la anterior: la 2.0 quitó de la línea el `rol`, "
            "`documento.tipo`, `referencia.tipo` y `detraccion.estado` —ninguno hacía falta, porque se derivan de "
            "lo que la línea ya trae—, la 3.0 fundió `constancias[]` dentro de `movimientos[]`, que es la "
            "entrada única de tesorería, y la 4.0 renombró `retencion` a `retencion_4ta` porque el Perú tiene dos "
            "retenciones y ese nombre servía para las dos. La guía de cada salto, paso a paso, está en "
            "`estandar/MIGRAR-A-2.0.md`, `estandar/MIGRAR-A-3.0.md` y `estandar/MIGRAR-A-4.0.md`.")


def libro_de(doc: dict) -> Libro:
    version_del_documento(doc)
    datos = doc.get("libro")
    if not isinstance(datos, dict):
        raise DocumentoInvalido("Falta el bloque `libro`: sin RUC, periodo y tipo no hay contabilidad.")
    try:
        # `Libro.de_dict` y no cuatro `.get()` aquí: hasta la 7.0 este fichero repetía el filtro a mano, así que la
        # estrictez podía estar en un sitio y no en el otro — y estuvo, porque el que ignoraba lo desconocido era
        # este. Un solo sitio decide qué claves son del libro.
        return Libro.de_dict(datos)
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


def imputaciones_de_movimientos_de(doc: dict, movimientos) -> dict:
    """El bloque `imputaciones_de_movimientos`, por el `id_externo` del movimiento.

    Recibe los movimientos porque una llave que no es de ninguno **se rechaza**: es la misma puerta que
    `con_imputacion` pone para los comprobantes y por el mismo motivo — una llave mal escrita dejaría ese
    movimiento sin su cuenta y sin aviso."""
    crudas = doc.get("imputaciones_de_movimientos") or {}
    try:
        return tesoreria.leer_imputaciones(crudas, movimientos)
    except (ValueError, TypeError) as e:
        raise DocumentoInvalido(f"La imputación de un movimiento no se pudo leer: {e}") from None


def aplicaciones_de(doc: dict) -> tuple:
    """El bloque `aplicaciones` del documento, que entró al estándar con la enmienda 0031.

    **No se comprueba que lo que nombran esté aquí**, y eso es el contrato y no un olvido: una factura de enero
    pagada en marzo se nombra desde el documento de marzo, y el comprobante está en el de enero. Lo que falta se
    **avisa** (`aplicaciones.sin_documento_declarado`), con el mismo trato que una cuenta bancaria sin
    identificador: lo que impide un paso posterior se dice, no se para.

    Quien rechaza lo que no entiende es `Aplicacion.de_dict`, que nombra la clave sobrante."""
    crudas = doc.get("aplicaciones") or []
    if not isinstance(crudas, list):
        raise DocumentoInvalido("`aplicaciones` tiene que ser una lista.")
    if len(crudas) > MAXIMO_APLICACIONES:
        raise DocumentoInvalido(
            f"{len(crudas)} aplicaciones en una sola llamada; el tope es {MAXIMO_APLICACIONES}. "
            "Divídelo por cuenta o por periodo.")
    try:
        return aplicaciones.leer(crudas)
    except (ValueError, TypeError) as e:
        raise DocumentoInvalido(f"Una aplicación no se pudo leer: {e}") from None


def extractos_de(doc: dict) -> dict:
    """El bloque `extractos`, por el `id` de su cuenta.

    Devuelve un diccionario y no una lista porque es como se usa —se busca el de una cuenta— y porque así el
    rechazo de dos del mismo `id` cae aquí, en la puerta, y no más adentro."""
    crudos = doc.get("extractos") or []
    if not isinstance(crudos, list):
        raise DocumentoInvalido("`extractos` tiene que ser una lista.")
    try:
        return tesoreria.por_cuenta(crudos)
    except (ValueError, TypeError) as e:
        raise DocumentoInvalido(f"Un extracto no se pudo leer: {e}") from None


def movimientos_de(doc: dict) -> list[Movimiento]:
    """El bloque `movimientos` del documento, que entró al estándar con la enmienda 0024.

    Un bloque ausente es una lista vacía y no un error, igual que `comprobantes`: la raíz del estándar solo exige
    `open_accounting` y `libro`, y un documento puede traer unos, otros, los dos o ninguno.

    Quien rechaza lo que no entiende es `Movimiento.de_dict`, que nombra la clave sobrante — y eso es a propósito:
    **un dato que se cuela sin error es un dato que se pierde sin aviso**, que es la lección de la 7.0 con el
    `libro`."""
    crudos = doc.get("movimientos") or []
    if not isinstance(crudos, list):
        raise DocumentoInvalido("`movimientos` tiene que ser una lista.")
    if len(crudos) > MAXIMO_MOVIMIENTOS:
        raise DocumentoInvalido(
            f"{len(crudos)} movimientos en una sola llamada; el tope es {MAXIMO_MOVIMIENTOS}. "
            "Divídelo por cuenta o por periodo.")
    try:
        return [Movimiento.de_dict(m) if isinstance(m, dict) else m for m in crudos]
    except (ValueError, TypeError) as e:
        raise DocumentoInvalido(f"Un movimiento no se pudo leer: {e}") from None
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


