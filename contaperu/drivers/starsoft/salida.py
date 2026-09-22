"""Cómo se escribe el archivo de STARSOFT Desktop: un TXT de palotes, envuelto en un ZIP.

**El formato sale del archivo de verdad** (capturas de John, 21 y 22-sep-2026): los campos separados por `|`,
**sin fila de cabecera** —ningún TXT de los vistos la lleva, y STARSOFT podría tomarla por un asiento—, sin
palote al final de la línea, y las fechas en `DD/MM/AAAA`.

Hasta la 2.2 esto escribía un CSV de puntos y coma, y era provisional: se hizo así para poder abrirlo y
revisarlo columna por columna con un contador mientras no se conocía la plantilla. Ahora se conoce.

**El orden de los campos es el de `datos.COLUMNAS`**, que es el de la hoja real y lo validó John campo a
campo. Este módulo no decide ninguno: solo los escribe.
"""
from __future__ import annotations

from typing import Any

from ...asiento.indice import ComprobanteDelAsiento
from ...asiento.lineas import LineaDiario
from ...modelo import Libro
from ..kit import Opciones, OpcionesArchivo, celdas, nombre_de_archivo
from ..kit.texto import formatear_fecha, sanear
from . import datos, proyeccion
from .datos import OPCIONES

SEPARADOR = "|"          # el del TXT real; por eso ningún campo puede llevarlo (ver `_campo`)
NUEVA_LINEA = "\r\n"     # CRLF, como el archivo que abrió el Bloc de notas
# Para sanear un campo hace falta una `Opciones`, y `OpcionesArchivo` no lo es. Con `sanear=False` la función
# hace justo lo que este formato necesita: quitar el separador y los saltos de línea, y **conservar las
# tildes y la Ñ** —la hoja real lleva «RECONSTRUCCIÓN NACIONAL SAC»—, al revés que el TXT del SIRE.
_COMO_VIENE = Opciones(sanear=False)


def nombre(libro: Libro, opciones: OpcionesArchivo = OPCIONES) -> str:
    return nombre_de_archivo(datos.NOMBRE, libro, opciones)


def _campo(valor: Any, clase: str, opciones: OpcionesArchivo) -> str:
    """Un valor de la proyección → su texto en el archivo.

    Las fechas se traducen **por la clase declarada de su columna**, no por su nombre: así la columna de fecha
    que se añada mañana sale bien sin que nadie se acuerde. Llegan en ISO, porque así viajan en el estándar.
    """
    if valor in (None, ""):
        return ""
    if clase == "fecha" and opciones.fecha:
        return formatear_fecha(celdas.fecha(str(valor), None), opciones)
    # Un `|` dentro de una razón social partiría la línea y correría todos los campos siguientes.
    return sanear(str(valor), _COMO_VIENE)


def escribir(libro: Libro, filas: list[dict[str, Any]], opciones: OpcionesArchivo = OPCIONES) -> bytes:
    """Las filas proyectadas, en el orden de las columnas de su libro. Sin cabecera: la primera línea ya es un
    asiento."""
    columnas = datos.COLUMNAS[libro.tipo]
    lineas = [SEPARADOR.join(_campo(fila.get(cabecera), clase, opciones) for _, cabecera, clase in columnas)
              for fila in filas]
    cuerpo = NUEVA_LINEA.join(lineas) + (NUEVA_LINEA if lineas else "")
    return cuerpo.encode("utf-8")


def desde_lineas(libro: Libro, lineas: list[LineaDiario], config: dict,
                 opciones: OpcionesArchivo = OPCIONES, *,
                 indice: tuple[ComprobanteDelAsiento, ...] = ()) -> tuple[bytes, dict]:
    """Las líneas neutrales del libro, ya numeradas y cuadradas por el núcleo → el archivo y lo que STARSOFT suma
    al resumen.

    Necesita el `indice`: cada fila lleva datos de la CABECERA de su comprobante —el IGV del total, el número sin
    partir y el destino de la adquisición— que ninguna línea guarda.
    """
    if FORMATOS.get(libro.tipo) is None:
        raise ValueError("Tipo de libro no soportado")
    if lineas and not indice:
        raise ValueError("STARSOFT escribe cada fila con la cabecera de su comprobante: necesita el `indice` "
                         "del asiento")
    # STARSOFT no mira el reloj y el motor tampoco: la fecha de registro es la de cada comprobante, no la de hoy.
    filas: list[dict[str, Any]] = []
    for entrada in indice:
        filas.extend(proyeccion.filas(entrada.cabecera, entrada.lineas(lineas), libro, config,
                                      entrada.cabecera.fecha_emision))
    # `sub_diarios` NO se pone aquí: lo calcula el núcleo con sus rangos (`asiento.numerar_en_orden`) y lo
    # que devuelva el driver lo PISA (`pipeline/armado.py`). Hasta la 2.0 esto devolvía la lista de
    # sub-diarios presentes y borraba el diccionario de rangos, que es lo que un ERP guarda para proponer
    # el correlativo del mes siguiente: quien lo consumiera esperando un dict se encontraba una lista.
    resumen = {"filas": len(filas)}
    return escribir(libro, filas, opciones), resumen


# Se reexporta para que `desde_lineas` compruebe el libro sin importar el módulo entero.
FORMATOS = datos.FORMATOS
