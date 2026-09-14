"""La superficie pública de la 1.0, congelada: lo que la 1.x promete no cambiar sin que se vea.

Dos niveles (ver `contaperu/api/__init__.py`):

- **Aplicación, `contaperu.api`**: cada nombre con su firma. Cambiar o quitar una firma es la 2.0.
- **Extensión**: el modelo, el asiento, los impuestos, la validación, los catálogos, la configuración, la partida
  doble, el PCGE, los lectores, el registro y el contrato de drivers, y cada driver de serie. De estos se congelan los
  nombres: su `__all__` si lo declaran, y si no, los nombres públicos que son del paquete.

`pipeline`, `puertas`, `_datos` y `_compat` son internos y no entran.

Añadir es una versión menor, pero no pasa en silencio: un nombre nuevo hace fallar el test hasta que se regenera la
superficie, a propósito. Quitar o cambiar lo que está no se arregla regenerando en la 1.x.

    python -c "import sys; sys.path.insert(0, 'tests'); import test_superficie_publica as t; t.regenerar()"
"""
from __future__ import annotations

import importlib
import inspect
import json
import types
from pathlib import Path

SUPERFICIE = Path(__file__).parent / "fixtures" / "superficie" / "1.0.json"

APLICACION = "contaperu.api"
EXTENSION = (
    "contaperu.errores", "contaperu.modelo", "contaperu.catalogos", "contaperu.configuracion", "contaperu.igv",
    "contaperu.detracciones", "contaperu.validar", "contaperu.partida_doble", "contaperu.asiento", "contaperu.pcge",
    "contaperu.lectores", "contaperu.lectores.archivos", "contaperu.lectores.sire_txt", "contaperu.lectores.xml_ubl",
    "contaperu.drivers", "contaperu.drivers.contrato", "contaperu.drivers.concar", "contaperu.drivers.contasis",
    "contaperu.drivers.csv", "contaperu.drivers.sire",
)
TIPOS_DE_CONSTANTE = {"builtins", "decimal", "datetime"}


def _es_del_paquete(valor) -> bool:
    if isinstance(valor, types.ModuleType):
        return valor.__name__.startswith("contaperu")
    if isinstance(valor, type) or callable(valor):
        return str(getattr(valor, "__module__", "") or "").startswith("contaperu")
    modulo_del_tipo = type(valor).__module__
    return modulo_del_tipo in TIPOS_DE_CONSTANTE or modulo_del_tipo.startswith("contaperu")


def _nombres(modulo) -> list[str]:
    declarados = getattr(modulo, "__all__", None)
    if declarados is not None:
        return sorted(declarados)
    return sorted(nombre for nombre, valor in vars(modulo).items()
                  if not nombre.startswith("_") and _es_del_paquete(valor))


def _firma(valor) -> str:
    if isinstance(valor, types.ModuleType):
        return "módulo"
    if inspect.isclass(valor):
        return "clase"
    if callable(valor):
        try:
            return "función" + str(inspect.signature(valor))
        except (TypeError, ValueError):
            return "función"
    return "valor"


def superficie() -> dict[str, dict[str, str]]:
    api = importlib.import_module(APLICACION)
    salida = {APLICACION: {nombre: _firma(getattr(api, nombre)) for nombre in sorted(api.__all__)}}
    for nombre_modulo in EXTENSION:
        modulo = importlib.import_module(nombre_modulo)
        salida[nombre_modulo] = {nombre: "" for nombre in _nombres(modulo)}
    return salida


def regenerar() -> None:
    """Reescribe la superficie congelada. Solo para AÑADIR a propósito; ver el docstring del módulo."""
    SUPERFICIE.parent.mkdir(parents=True, exist_ok=True)
    SUPERFICIE.write_bytes((json.dumps(superficie(), ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def test_nada_de_la_superficie_se_quita_ni_cambia():
    congelada = json.loads(SUPERFICIE.read_text(encoding="utf-8"))
    hoy = superficie()
    quitados = {m: sorted(set(nombres) - set(hoy.get(m, {}))) for m, nombres in congelada.items()}
    cambiados = {m: sorted(n for n, firma in nombres.items() if n in hoy.get(m, {}) and hoy[m][n] != firma)
                 for m, nombres in congelada.items()}
    assert {m: q for m, q in quitados.items() if q} == {}, "quitar un nombre público es la 2.0"
    assert {m: c for m, c in cambiados.items() if c} == {}, "cambiar una firma de la api es la 2.0"


def test_lo_nuevo_entra_en_la_superficie_a_proposito():
    congelada = json.loads(SUPERFICIE.read_text(encoding="utf-8"))
    nuevos = {m: sorted(set(nombres) - set(congelada.get(m, {}))) for m, nombres in superficie().items()}
    assert {m: n for m, n in nuevos.items() if n} == {}, (
        "hay nombres públicos nuevos: si son a propósito, regenera fixtures/superficie/1.0.json")
