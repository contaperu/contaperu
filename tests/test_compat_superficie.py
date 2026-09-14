"""La superficie pública de la 0.10, congelada: ningún nombre desaparece sin aviso durante la 1.x.

`contab-core` y quien use el motor como librería importan hoy nombres de muchos módulos. La 1.0 fija una API nueva
(`contaperu.api`), pero promete que todo lo de la 0.10 sigue resolviendo hasta la 2.0, aunque avise. Este test guarda
los nombres de cada módulo del paquete tal como estaban en la 0.10.0 (`fixtures/compat/superficie_0_10.json`) y
comprueba que cada uno se sigue pudiendo importar y leer. No compara firmas ni comportamiento: eso lo hacen
`test_compat_contab_core` y `test_caracterizacion`.

Entran los nombres públicos (sin `_` delante) que son del propio paquete —funciones, clases, constantes, instancias y
submódulos de `contaperu`— y todo lo que un módulo declara en `__all__`; no entra lo que un módulo importa de la
biblioteca estándar.

Se generó una sola vez, con el código de la v0.10.0 (rama `motor-v1`, etapa 1, 14-sep-2026), y NO se regenera: es la
promesa de la 1.x. Solo se regenera para la 2.0.

    python -c "import sys; sys.path.insert(0, 'tests'); import test_compat_superficie as t; t.regenerar()"
"""
from __future__ import annotations

import importlib
import json
import pkgutil
import types
import warnings
from pathlib import Path

import pytest

import contaperu

SUPERFICIE = Path(__file__).parent / "fixtures" / "compat" / "superficie_0_10.json"
# Los módulos que necesitan una dependencia opcional para importarse.
OPCIONALES = {"contaperu.servidor_mcp": "mcp"}
TIPOS_DE_CONSTANTE = {"builtins", "decimal", "datetime"}


def _modulos() -> list[str]:
    nombres = ["contaperu"]
    for info in pkgutil.walk_packages(contaperu.__path__, "contaperu."):
        if not any(parte.startswith("_") for parte in info.name.split(".")[1:]):
            nombres.append(info.name)
    return sorted(nombres)


def _es_del_paquete(valor) -> bool:
    if isinstance(valor, types.ModuleType):
        return valor.__name__.startswith("contaperu")
    if isinstance(valor, type) or callable(valor):
        return str(getattr(valor, "__module__", "") or "").startswith("contaperu")
    modulo_del_tipo = type(valor).__module__
    return modulo_del_tipo in TIPOS_DE_CONSTANTE or modulo_del_tipo.startswith("contaperu")


def publicos(modulo) -> list[str]:
    declarados = set(getattr(modulo, "__all__", ()) or ())
    propios = {nombre for nombre, valor in vars(modulo).items()
               if not nombre.startswith("_") and _es_del_paquete(valor)}
    return sorted(declarados | propios)


def regenerar() -> None:
    """Reescribe la superficie con el código de hoy. Ver el docstring del módulo antes de usarlo."""
    datos = {nombre: publicos(importlib.import_module(nombre)) for nombre in _modulos()}
    SUPERFICIE.parent.mkdir(parents=True, exist_ok=True)
    SUPERFICIE.write_bytes((json.dumps(datos, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def _cargar() -> dict[str, list[str]]:
    return json.loads(SUPERFICIE.read_text(encoding="utf-8")) if SUPERFICIE.exists() else {}


def test_la_superficie_de_la_0_10_esta_guardada():
    datos = _cargar()
    assert "exportar" in datos["contaperu.operaciones"] and "filas_de_comprobante" in datos["contaperu.drivers.concar"]
    assert "Comprobante" in datos["contaperu.modelo"] and "generar" in datos["contaperu.generar"]


@pytest.mark.parametrize("modulo", sorted(_cargar()))
def test_cada_nombre_de_la_0_10_sigue_resolviendo(modulo):
    if modulo in OPCIONALES:
        pytest.importorskip(OPCIONALES[modulo])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")      # en la 1.x una ruta vieja puede avisar; lo que no puede es faltar
        mod = importlib.import_module(modulo)
        faltan = [nombre for nombre in _cargar()[modulo] if not hasattr(mod, nombre)]
    assert faltan == [], f"{modulo} ya no tiene {faltan}"
