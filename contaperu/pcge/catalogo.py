"""El catálogo oficial de cuentas del PCGE 2026: código, nombre y la página que lo dice.

Es el dato que le faltaba a este proyecto. Sin él, quien registra una compra escribe `631101` y no
hay nada contra lo que contrastarlo: ni para poner el nombre en pantalla, ni para que un modelo de
lenguaje sepa si la cuenta que propone existe. Con él, las tres cosas salen gratis.

**Una cuenta que no está aquí NO es un error.** El PCGE llega hasta cinco dígitos y cada empresa
abre sus propias divisionarias debajo: `603201 Compras suministros diversos` es perfectamente
válida y no aparece en la norma. Por eso lo que se ofrece es `resolver()`, que devuelve la cuenta
exacta si existe y, si no, **su antecesora más larga** — de `603201` sale `603 Materiales
auxiliares, suministros y repuestos`, que es información útil, no un rechazo.

El dato viene de `catalogo2026.json`, generado desde el PDF oficial con
`herramientas/extraer_pcge2026.py`. El PDF no está en el repositorio; el script sí, para que
cualquiera pueda rehacerlo y auditarlo cuando salga una modificatoria.
"""
from __future__ import annotations

import unicodedata
from functools import lru_cache

from .. import _datos

# El dato viaja dentro del paquete y lo lee `_datos`: el núcleo no abre archivos (1.0, hito 0.5).
DATO = "pcge/catalogo2026.json"


@lru_cache(maxsize=1)
def cargar_catalogo() -> dict:
    """El catálogo entero: `{"version", "fuente", "nota", "cuentas": {codigo: {nombre, pagina}}}`.

    Cacheado: son 1615 cuentas y se consultan una por fila de un registro de compras.
    """
    return _datos.leer_json(DATO) or {"version": "", "fuente": "", "cuentas": {}}


def cuentas() -> dict[str, dict]:
    return cargar_catalogo().get("cuentas") or {}


def _limpio(codigo: str) -> str:
    return "".join(ch for ch in str(codigo or "") if ch.isdigit())


def existe(codigo: str) -> bool:
    """¿Está esta cuenta EXACTAMENTE en el PCGE 2026?

    Ojo al usarlo para validar: la respuesta correcta ante un `False` es un aviso, nunca un
    bloqueo. Ver `resolver()`.
    """
    return _limpio(codigo) in cuentas()


def nombre_de(codigo: str) -> str:
    """El nombre oficial, o cadena vacía si esa cuenta no está en la norma."""
    c = cuentas().get(_limpio(codigo))
    return c["nombre"] if c else ""


def resolver(codigo: str) -> dict | None:
    """La cuenta del PCGE que gobierna este código: ella misma, o su antecesora más larga.

    Devuelve `{"codigo", "nombre", "pagina", "exacta"}`, con `exacta=False` cuando lo que se
    encontró fue la madre —el caso de una divisionaria propia de la empresa—. `None` solo si ni
    siquiera el elemento de dos dígitos existe, que es un código mal escrito.
    """
    cod = _limpio(codigo)
    tabla = cuentas()
    for largo in range(len(cod), 1, -1):
        trozo = cod[:largo]
        if trozo in tabla:
            c = tabla[trozo]
            return {"codigo": trozo, "nombre": c["nombre"], "pagina": c["pagina"],
                    "exacta": trozo == cod}
    return None


def _sin_tildes(t: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", t.lower())
                   if unicodedata.category(ch) != "Mn")


def buscar(texto: str, limite: int = 20) -> list[dict]:
    """Cuentas cuyo nombre contiene el texto. Sin tildes y sin mayúsculas: quien busca «gestion»
    espera encontrar «Otros gastos de gestión»."""
    aguja = _sin_tildes(str(texto or "").strip())
    if not aguja:
        return []
    out = [{"codigo": k, "nombre": v["nombre"], "pagina": v["pagina"]}
           for k, v in sorted(cuentas().items()) if aguja in _sin_tildes(v["nombre"])]
    return out[:limite]
