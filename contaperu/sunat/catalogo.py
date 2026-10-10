"""El catálogo de la API del SIRE, leído una vez y validado: las once operaciones, los libros y las gradas.

Mismo trato que la tabla de regímenes (`catalogos/contribuyente.py`): si falta el fichero o su fuente, el motor no
arranca. Un catálogo sin fuente es una regla sin fuente, y en este proyecto eso no entra.
"""
from __future__ import annotations

import copy
from typing import Any

from .. import _datos
from ..errores import ErrorContaperu

RUTA = "datos/sunat/sire_api.json"

# Con qué cuidado se llama cada operación, y no es una anotación: es lo que decide si quien envía puede llamarla sola.
# Una lectura no cambia nada en SUNAT; una escritura toca un mes; una declarativa DECLARA ante SUNAT.
GRADAS = ("lectura", "escritura", "declarativa")


class CatalogoDelSireInvalido(ErrorContaperu, ValueError):
    """El catálogo de la API del SIRE no se puede usar: le falta la fuente, una grada o un método."""


def _valido(tabla: dict) -> dict:
    if not str(tabla.get("actualizado_al") or "").strip():
        raise CatalogoDelSireInvalido(f"El catálogo del SIRE no dice de cuándo es ({RUTA}, `actualizado_al`). Una "
                                      "API ajena cambia, y un mapa sin fecha no se puede contrastar.")
    if not (tabla.get("fuentes") or {}):
        raise CatalogoDelSireInvalido(f"El catálogo del SIRE no cita sus manuales ({RUTA}, `fuentes`).")
    for nombre, op in (tabla.get("operaciones") or {}).items():
        if nombre.startswith("_"):
            continue
        if op.get("grada") not in GRADAS:
            raise CatalogoDelSireInvalido(
                f"La operación {nombre!r} no declara una grada de {GRADAS}: sin ella, quien envía no puede saber si "
                "puede llamarla sola o necesita un acto explícito.")
        if not str(op.get("metodo") or "").strip():
            raise CatalogoDelSireInvalido(f"La operación {nombre!r} no dice su método HTTP.")
        if not str(op.get("fuente") or "").strip():
            raise CatalogoDelSireInvalido(
                f"La operación {nombre!r} no cita el manual del que sale. Ninguna regla sin fuente, y la ruta de una "
                "API ajena es una regla: si cambia, hay que poder ir a mirar de dónde salió.")
        if not (op.get("ruta") or op.get("ruta_por_libro")):
            raise CatalogoDelSireInvalido(f"La operación {nombre!r} no dice su ruta ni su ruta por libro.")
    return tabla


def _tabla() -> dict:
    tabla = _datos.leer_json(RUTA)
    if not tabla:
        raise FileNotFoundError(f"No encuentro el catálogo de la API del SIRE ({RUTA})")
    return _valido(tabla)


_CATALOGO = _tabla()
# Las once, sin la nota del fichero. En orden de catálogo, que es el del flujo: pedir, sondear, bajar, reemplazar…
OPERACIONES: tuple[str, ...] = tuple(n for n in _CATALOGO["operaciones"] if not n.startswith("_"))
# `cod_libro` de la API: 080000 el RCE y 140000 el RVIE. **No es** el código del nombre del archivo (080400/140400),
# que vive en `drivers/sire`: confundirlos no da 404, da 500 de nginx, y se lee como si SUNAT estuviera caída.
CODIGOS_DE_LIBRO: tuple[str, ...] = tuple(c for c in _CATALOGO["libros"] if not c.startswith("_"))


def sire_api() -> dict:
    """El catálogo entero, copiado: las once operaciones, los hosts, los libros, los tickets, el TUS, los errores y
    los límites, con su `actualizado_al` y sus fuentes. Se copia porque quien lo pide puede guardarlo."""
    return copy.deepcopy(_CATALOGO)


def operaciones() -> dict[str, dict]:
    """Las once operaciones por su nombre, copiadas, cada una con su método, su grada, su ruta y su fuente."""
    return {n: copy.deepcopy(_CATALOGO["operaciones"][n]) for n in OPERACIONES}


def libros() -> dict[str, dict]:
    """Los dos libros del SIRE por su `cod_libro` de la API: el RCE (compras) y el RVIE (ventas)."""
    return {c: copy.deepcopy(_CATALOGO["libros"][c]) for c in CODIGOS_DE_LIBRO}


def cod_libro_de(registro: str) -> str:
    """El `cod_libro` de la API para un registro del estándar (`compra` o `venta`).

    Existe para que quien integra no tenga que aprenderse los números: el estándar habla de compras y ventas, y la
    API del SIRE de 080000 y 140000. La traducción vive aquí, una vez."""
    buscado = str(registro or "").strip().lower()
    for codigo, libro in _CATALOGO["libros"].items():
        if not codigo.startswith("_") and libro.get("registro") == buscado:
            return codigo
    conocidos = sorted(l["registro"] for c, l in _CATALOGO["libros"].items() if not c.startswith("_"))
    raise CatalogoDelSireInvalido(f"El SIRE no tiene libro para {registro!r}; los registros son {', '.join(conocidos)}")


def _operacion(nombre: str) -> dict[str, Any]:
    """La operación por su nombre, o un error que las enumera. No se copia: es de uso interno."""
    op = _CATALOGO["operaciones"].get(nombre) if not nombre.startswith("_") else None
    if op is None:
        raise CatalogoDelSireInvalido(
            f"El SIRE no tiene la operación {nombre!r}; las que hay son {', '.join(OPERACIONES)}")
    return op
