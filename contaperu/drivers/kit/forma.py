"""Lo que todo driver de la forma `desde_lineas` hace antes de escribir nada.

Las dos comprobaciones de abajo estaban escritas dos veces, carácter a carácter salvo el nombre del sistema, en
CONCAR y en STARSOFT; el día que entrara un tercer legacy se habrían escrito tres. No deciden nada de
contabilidad: dicen que el libro es de un tipo que ese driver sabe escribir y que le han pasado el índice que
necesita para llevar a cada fila los datos de la cabecera de su comprobante.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable


def exigir_indice(sistema: str, libro: Any, lineas: list, indice: tuple, formatos: dict) -> None:
    """Se planta antes de escribir: tipo de libro que el driver no lleva, o líneas sin su índice.

    Un driver `desde_lineas` recibe las líneas ya numeradas y cuadradas, pero una línea no guarda lo que es del
    COMPROBANTE —su glosa entera, el IGV del total, el destino de la adquisición—. Eso viaja en el índice, y sin
    él las filas saldrían incompletas en silencio, que es peor que no salir."""
    if formatos.get(libro.tipo) is None:
        raise ValueError("Tipo de libro no soportado")
    if lineas and not indice:
        raise ValueError(f"{sistema} escribe cada fila con la cabecera de su comprobante: necesita el `indice` "
                         f"del asiento")


def filas_del_indice(indice: Iterable, lineas: list, proyectar: Callable[[Any, list], Iterable[dict]]) -> list[dict]:
    """Las filas de todos los comprobantes, en el orden del índice: a cada uno, su cabecera y su tramo de líneas.

    Cómo se corta ese tramo es del núcleo (`ComprobanteDelAsiento.lineas`), no del driver; lo que el driver pone
    es `proyectar`, que traduce ese par a las filas de su formato."""
    filas: list[dict] = []
    for entrada in indice:
        filas.extend(proyectar(entrada.cabecera, entrada.lineas(lineas)))
    return filas
