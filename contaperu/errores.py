"""La base de todas las excepciones del motor.

Quien use el motor puede atrapar `ErrorContaperu` y leer `clave`, un nombre estable por clase («sin_cuenta»,
«configuracion_invalida», «xml_invalido»): es lo que la puerta HTTP pone en su respuesta de error y lo que una
aplicación compara, en vez del texto, que puede mejorar de una versión a otra.

Las excepciones de siempre conservan sus bases (`ValueError`, la de su familia): atraparlas como en la 0.x sigue
funcionando. Una clase que no declara su `clave` recibe la de su nombre en minúsculas y separada por guiones bajos.
"""
from __future__ import annotations

import re


def _serpiente(nombre: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", nombre).lower()


class ErrorContaperu(Exception):
    """Algo que el motor se niega a hacer, con su motivo. `clave` lo nombra de forma estable."""

    clave: str = "error_contaperu"

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if "clave" not in cls.__dict__:
            cls.clave = _serpiente(cls.__name__)


class DocumentoInvalido(ErrorContaperu, ValueError):
    """El documento no cumple el estándar lo bastante como para poder trabajar con él."""


class ErroresBloqueantes(ErrorContaperu):
    """Quedan comprobantes con observaciones de nivel `error` y no se pidió exportarlos igual. `errores` los lista."""

    def __init__(self, errores: list[dict]):
        super().__init__(f"{len(errores)} comprobante(s) con errores que bloquean la exportación")
        self.errores = errores
