"""Leer lo que SUNAT responde cuando rechaza, con su trampa — y decir si lo que llegó significa «esto ya se hizo».

La trampa está escrita en el catálogo y vale su peso: **el 422 llega como `{cod, msg, errors:[{cod, msg}]}` y el
código que importa vive DENTRO de `errors`**; el `cod` de arriba es casi siempre «422» a secas. Mirar solo el de
arriba hace que el 1024 no se reconozca nunca — y el 1024 es la única idempotencia que la API ofrece.
"""
from __future__ import annotations

from typing import Any

from ..errores import ErrorContaperu
from .catalogo import _CATALOGO

_ERRORES = _CATALOGO["errores"]
# «Esto ya se hizo»: no es un fallo, es SUNAT diciendo que la operación ya entró. Hoy son tres —1024 por nombre de
# archivo, 1008 el registro ya en preliminar, 1009 el registro ya generado—, y son lo que permite reintentar sin
# miedo a duplicar.
IDEMPOTENTES: frozenset[str] = frozenset(_ERRORES["idempotentes"])
# Lo que el propio manual manda repetir.
REINTENTABLES: frozenset[str] = frozenset(_ERRORES["reintentables"])


class SireRechaza(ErrorContaperu, ValueError):
    """SUNAT rechazó la petición y dijo por qué.

    `codigo` es el que importa —el de dentro de `errors`, no el «422» de arriba—, `idempotente` dice si significa
    «esto ya se hizo» y `reintentable` si el manual manda repetir."""

    def __init__(self, codigo: str, mensaje: str, *, operacion: str = "", codigos: tuple[str, ...] = ()) -> None:
        super().__init__(f"{operacion + ': ' if operacion else ''}[{codigo}] {mensaje}")
        self.codigo = codigo
        self.mensaje = mensaje
        self.operacion = operacion
        # Todos los que llegaron, en orden: el de arriba primero. Quien quiera verlos enteros los tiene.
        self.codigos = codigos
        self.idempotente = codigo in IDEMPOTENTES
        self.reintentable = codigo in REINTENTABLES


def clasificar_error(cod: Any, *, mensaje: str = "", errores: list[dict] | None = None,
                     operacion: str = "") -> SireRechaza:
    """El rechazo de SUNAT, con el código que de verdad importa.

    Recibe el `cod` de arriba y la lista `errors` tal como llegan, y devuelve un `SireRechaza` sin lanzarlo: quien
    envía decide si lo lanza, lo reintenta o lo trata como «ya estaba hecho».

    **El orden de preferencia es el de la trampa**: se mira primero si alguno de los códigos de `errors` está en la
    tabla del catálogo; si ninguno está, se prefiere **el primer código interno** sobre el «422» genérico de arriba,
    porque el interno es el que el contador puede buscar en el manual. Un 422 a secas no dice nada.
    """
    candidatos = [str(cod or "").strip()]
    candidatos += [str((e or {}).get("cod") or "").strip() for e in (errores or [])]
    candidatos = [c for c in candidatos if c]
    conocidos = IDEMPOTENTES | REINTENTABLES | frozenset(_ERRORES["frecuentes"])
    elegido = next((c for c in candidatos if c in conocidos), "")
    if not elegido:
        internos = [c for c in candidatos[1:] if c]
        elegido = internos[0] if internos else (candidatos[0] if candidatos else "")
    texto = str(mensaje or "").strip() or _texto_de(elegido) or "SUNAT rechazó la petición"
    return SireRechaza(elegido, texto, operacion=operacion, codigos=tuple(candidatos))


def _texto_de(codigo: str) -> str:
    """Lo que el catálogo dice de ese código, si lo trae. Sirve cuando SUNAT no manda mensaje."""
    for grupo in ("idempotentes", "reintentables", "frecuentes"):
        if codigo in _ERRORES[grupo]:
            return str(_ERRORES[grupo][codigo])
    return ""
