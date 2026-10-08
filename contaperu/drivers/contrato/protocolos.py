"""La forma de un driver, tipada: lo que un comprobador estático puede verificar sin ejecutar nada.

Son `Protocol`, no clases base: un driver es un **módulo**, no una instancia, y nadie hereda de aquí. Sirven
para que un editor avise antes de que lo haga el examen.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ...modelo import Comprobante, Libro
from ..kit import Opciones

if TYPE_CHECKING:
    from ...asiento.indice import ComprobanteDelAsiento
    from ...asiento.lineas import LineaDiario

class Driver(Protocol):
    NOMBRE: str
    FORMATOS: dict[str, str]
    OPCIONES: Opciones

    def nombre(self, libro: Libro, opciones: Opciones = ...) -> str: ...


class DriverRegistroTexto(Driver, Protocol):
    def linea(self, c: Comprobante, libro: Libro, idx: int, opciones: Opciones = ...) -> str: ...


class DriverRegistroArchivo(Driver, Protocol):
    CONTENT_TYPE: str
    EXIGE: frozenset[str]     # opcional; subconjunto de EXIGE_POSIBLES_REGISTRO
    CUENTAS_POR_DEFECTO: dict     # opcional; las cuentas de su sistema, enteras: contrapartida + plan (compras/ventas)

    def desde_comprobantes(self, libro: Libro, comprobantes: list[Comprobante], config: dict,
                           opciones: Opciones = ...) -> tuple[bytes, dict]: ...


class DriverAsientoLineas(Driver, Protocol):
    CONTENT_TYPE: str
    EXIGE: frozenset[str]     # opcional; subconjunto de EXIGE_POSIBLES_ASIENTO
    CUENTAS_POR_DEFECTO: dict     # opcional; las cuentas de su sistema, enteras: contrapartida + plan (compras/ventas)

    def desde_lineas(self, libro: Libro, lineas: list[LineaDiario], config: dict, opciones: Opciones = ..., *,
                     indice: tuple[ComprobanteDelAsiento, ...] = ...) -> tuple[bytes, dict]: ...

