"""Lo que comparten las puertas de red: los topes y los nombres de host por los que se dejan llamar."""
from __future__ import annotations

from typing import Iterable

# Tope del archivo que se devuelve por un protocolo. Un Excel de un mes normal pesa unas
# decenas de kilobytes; varios megas casi siempre significan que había que partir el lote.
MAXIMO_ARCHIVO = 4 * 1024 * 1024

# Tope del cuerpo de una petición. Un mes con miles de comprobantes en JSON cabe holgado.
MAXIMO_PETICION = 10 * 1024 * 1024

# Nombres por los que un servidor local se deja llamar. Se mantienen también al escuchar en 0.0.0.0, que es lo normal
# dentro de un contenedor, para que `curl localhost:8000` siga sirviendo para comprobar que está vivo.
LOCALES = ["127.0.0.1:*", "localhost:*", "[::1]:*"]


def hosts_permitidos(dominios: Iterable[str]) -> list[str]:
    """Los valores de `Host` que se aceptan: los locales y cada dominio público declarado, con o sin puerto."""
    dominios = list(dominios)
    return [*LOCALES, *dominios, *(f"{d}:*" for d in dominios)]


def origenes_permitidos(dominios: Iterable[str]) -> list[str]:
    return [f"http://{h}" for h in LOCALES] + [f"https://{d}" for d in dominios]


def peso_de_base64(*textos: str) -> int:
    """Lo que pesan en bytes unos textos en base64: el base64 abulta un tercio más que los bytes."""
    return sum(len(t) for t in textos) * 3 // 4
