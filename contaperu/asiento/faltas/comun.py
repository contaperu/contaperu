"""Lo que no es de un libro ni del otro: la excepción base, la forma de una fila de la tabla, a quién se le pide y
la puerta del eje del libro.

Las cuatro cosas estaban en el mismo fichero que las faltas de un comprobante y las de un movimiento, y aquí se ven
por lo que son. `NoExportable` es el contrato de errores que una puerta atrapa y traduce, y las dos familias lo
heredan. `Falta` es la FORMA de una fila: la tabla que las reparte cuenta comprobantes, así que vive con ellos
(`faltas/comprobante.py`), pero su forma no es de ninguno de los dos. Y `LibroQueElMotorNoOrigina` no mira una fila
de nada: dice qué TIPOS DE LIBRO sabe armar el motor —tesorería incluida—, así que meterla en el bloque de uno de
los dos diría que ese «no» es solo de ese libro, y no lo es.
"""
from __future__ import annotations

from dataclasses import dataclass

from ...errores import ErrorContaperu
from ...modelo import Comprobante

# A quién se le pide. **contador**: se decide mirando el documento o el plan de cuentas. **sistema**: la configuración
# del destino o un dato público que no está en el papel. **proveedor** queda reservado (ver `operaciones.PEDIR_A`).
CONTADOR, SISTEMA, PROVEEDOR = "contador", "sistema", "proveedor"


class NoExportable(ErrorContaperu):
    """La base de todo lo que impide exportar a un destino. Quien llama atrapa esta y lee `clave` (la de su fila de
    `FALTAS`, o la propia de un driver) y `comprobantes`, vacía cuando lo que falta es un código: un tipo, una moneda,
    un sub-diario."""

    clave = ""

    def __init__(self, mensaje: str, comprobantes: list[Comprobante] | None = None):
        super().__init__(mensaje)
        self.comprobantes = list(comprobantes or [])


@dataclass(frozen=True)
class Falta:
    clave: str
    requisito: str                          # el de `contrato.exige` que la hace bloquear; '' = no bloquea por requisito
    excepcion: type[NoExportable] | None    # con la que se niega el núcleo; None = la declara otro (el driver)
    texto: str                              # detrás de un número: «3 sin cuenta contable»
    pedir_a: str
    titulo: str                             # el de la CLI


class LibroQueElMotorNoOrigina(NoExportable):
    """Un libro cuyo tipo el catálogo publica y el motor no sabe armar.

    No es una falta de un comprobante y por eso no está en `FALTAS`: es de la cabecera, y se sabe antes de mirar
    una sola fila. Nació porque el motor decidía casi todo por `libro.es_venta` y **lo que no era venta lo trataba
    como compra**: un libro nuevo del catálogo salía con el debe y el haber invertidos y la contraparte en la cuenta
    equivocada, sin un solo error. La 9.0 cambió ese eje por una tabla (`modelo.RASGOS`), que es el arreglo, y esta
    puerta **sigue haciendo falta igual**: la tabla tiene las filas que tiene, y un tipo del catálogo que no tenga
    la suya hay que pararlo aquí y decir cuáles sabe originar, no dejar que falle dentro.

    Hoy no se dispara nunca —`TIPOS_DEL_MOTOR` y el catálogo coinciden— y ése es justo el momento de ponerla: el
    día que el catálogo crezca (B13), lo que falle será esto y no una exportación que nadie revisó."""

    clave = "libro_que_el_motor_no_origina"

    def __init__(self, tipo: str, sabe: tuple[str, ...]):
        super().__init__(f"El motor no sabe armar el asiento de un libro {tipo!r}: origina {', '.join(sabe)}")
        self.tipo = tipo
        self.sabe = tuple(sabe)
