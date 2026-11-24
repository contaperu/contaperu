"""Lo que una herramienta con modos hace antes de trabajar: saber qué se le pide y negarse a lo que no va.

El SDK del protocolo valida los argumentos con pydantic, y eso tiene dos huecos que una familia de operaciones pisa:

- **un `enum` declarado solo en el esquema no se valida**: `que` puede llegar con un valor que no es ningún modo;
- **un argumento que la firma no conoce se descarta en silencio**, y la firma de una familia lleva los parámetros de
  todos sus modos, así que «`proveedor` con `que: anulada`» se ignoraría y el lote haría otra cosa que la pedida.

Por eso el servidor dice qué pide cada modo, con la clave `entrada_invalida`, en vez de confiar en el esquema.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence, TypeVar

from ..errores import ErrorContaperu
from .catalogo import Ficha, Herramienta

__all__ = ["EntradaInvalida", "SIN_VALOR", "operacion_del_modo", "recortar", "solo_los_de_su_modo"]

T = TypeVar("T")

# Lo que cuenta como «no se pasó». `False` está dentro porque una casilla sin marcar es lo mismo que no decirla; un
# booleano que por defecto es `True` necesita su propio centinela para poder decir que se pasó en contra.
SIN_VALOR: tuple[Any, ...] = (None, "", [], {}, False)


class EntradaInvalida(ErrorContaperu, ValueError):
    """Lo que se pidió no cuadra con la herramienta: un `que` que no es ningún modo, o un parámetro de otro."""


def operacion_del_modo(herramienta: Herramienta, que: str) -> Ficha:
    """La ficha que pide `que`, o `entrada_invalida` diciendo cuáles hay. Sin `que`, la de por defecto si la
    herramienta la tiene; una herramienta de una sola operación no necesita que se diga."""
    pedido = str(que or "").strip().lower()
    if not herramienta.tiene_modos and not pedido:
        return herramienta.principal
    ficha = herramienta.de_modo(pedido or herramienta.por_defecto)
    if ficha is None:
        raise EntradaInvalida(f"`que` es uno de: {', '.join(herramienta.modos)}.")
    return ficha


def solo_los_de_su_modo(que: str, por_modo: Mapping[str, set[str]], **valores: Any) -> None:
    """Rechaza el parámetro de OTRO modo que llegue con valor: `por_modo` dice cuáles son de cada uno."""
    propios = por_modo.get(que, set())
    sobran = sorted(p for p, v in valores.items() if v not in SIN_VALOR and p not in propios)
    if sobran:
        raise EntradaInvalida(f"Con `que: {que}` no van {', '.join(f'`{p}`' for p in sobran)}.")


def recortar(lista: Sequence[T], tope: int = 50) -> tuple[list[T], int]:
    """La lista hasta el tope y cuántos quedaron fuera. **Una lista recortada dice siempre cuánto le falta**: si no, el
    agente diría «son 50» de algo que trae ochenta."""
    return list(lista[:tope]), max(0, len(lista) - tope)
