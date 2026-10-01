"""Cómo se llama el archivo que produce un driver (2.1).

Una sola regla, escrita una vez: **`SISTEMA_LIBRO_PERIODO_RUC` + la extensión del driver**. El sistema delante y el
RUC al final es lo que pidió John el 21-sep-2026, y sale de cómo se busca un archivo cuando se llevan 30-80
contribuyentes: por sistema y por mes, no por número de RUC.

Hasta la 2.0 cada driver repetía su propia `f-string` y convivían tres convenciones —`CONCAR_<RUC>_<PERIODO>_COMPRAS`,
`asiento_<RUC>_<PERIODO>_compra` en minúscula y singular, y la del SIRE—. El día que entra un driver nuevo, su nombre
sale de aquí y no hay nada que decidir.

**Los libros electrónicos no pasan por esa regla, porque su nombre lo impone SUNAT** y además el motor lo lee. Pero
tampoco lo escribe cada uno por su cuenta: desde la 4.2 lo arma `nombre_de_libro_electronico`, que es de donde salen
el del SIRE y el del Libro Diario del PLE.
"""
from __future__ import annotations

from ...modelo import Libro
from .opciones import Opciones, OpcionesArchivo


def nombre_de_archivo(sistema: str, libro: Libro, opciones: Opciones | OpcionesArchivo) -> str:
    """`SISTEMA_LIBRO_PERIODO_RUC` + la extensión: `STARSOFT_COMPRAS_202507_20601234567.csv`.

    `sistema` es el `NOMBRE` del driver, que se pone en mayúscula. La extensión sale de sus opciones y **nunca se
    omite**: el ZIP del SIRE se arma cortando por el último punto (`pipeline/salida.py`), y un nombre sin extensión
    dejaría el TXT de dentro sin la suya.
    """
    return (f"{sistema.upper()}_{'VENTAS' if libro.es_venta else 'COMPRAS'}"
            f"_{libro.periodo}_{libro.ruc}{opciones.extension}")


def nombre_de_libro_electronico(libro: Libro, codigo: str, oportunidad: str, banderas: str,
                                opciones: Opciones | OpcionesArchivo, dia: str = "00") -> str:
    """El nombre que SUNAT impone a un libro electrónico: `LE` + RUC + periodo + día + código del libro +
    oportunidad + cuatro banderas + extensión.

    `LE20601234567202601000801000211 12.TXT` sin el espacio: RUC de once, periodo `AAAAMM`, día `00` cuando el libro
    es del periodo entero, **código de SEIS dígitos**, dos de oportunidad y cuatro banderas —operativa, contenido,
    moneda y origen—.

    Vive aquí desde la 4.2, cuando apareció el segundo libro electrónico. Antes era una `f-string` dentro del driver
    del SIRE, con una nota que decía que era «el ÚNICO driver que no usa el kit»; dejó de ser único y la regla no
    puede estar escrita dos veces, porque **un nombre mal formado lo rechaza SUNAT y el error parece suyo y no
    nuestro**. Y porque el propio motor lee ese nombre: `comparar_sire.registro_de()` deduce si un archivo es de
    ventas o de compras buscando su código EN EL NOMBRE, «más fiable que contar campos».

    **Ojo con los códigos: los del SIRE no son los del PLE.** El SIRE usa `140400` y `080400`; los registros del PLE
    son `140100` y `080100`, y su Libro Diario, `050100`. Cada driver trae los suyos.
    """
    return f"LE{libro.ruc}{libro.periodo}{dia}{codigo}{oportunidad}{banderas}{opciones.extension}"
