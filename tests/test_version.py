"""La versión se escribe en un solo sitio, y estos tests lo comprueban por estructura.

Nace de un desajuste real: llegaron a convivir **tres** versiones a la vez — `0.3.0` en
`pyproject.toml`, `0.2.0` en el código y `0.1.0` en la metadata instalada—, y la del medio era la que
el servidor MCP le decía al Claude del contador al presentarse. Un número que miente sobre qué código
corre sale caro justo el día que hace falta: cuando algo falla en casa de un cliente.

No se detectó porque el único test que miraba la versión comparaba la constante **consigo misma**:
verde garantizado dijera lo que dijera.

El arreglo no es comprobar que dos copias coinciden —eso solo avisa cuando ya se separaron—, sino
que **haya una sola copia**. Por eso estos tests miran el `pyproject.toml` en vez de comparar valores.
"""
from __future__ import annotations

import pathlib
import tomllib

import contaperu

RAIZ = pathlib.Path(__file__).resolve().parents[1]


def pyproject() -> dict:
    return tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))


def test_el_empaquetado_lee_la_version_del_codigo_y_no_la_repite():
    """`pyproject.toml` no puede tener su propio número: lo saca de `contaperu/_version.py`.

    En el otro sentido no funciona. Leerla con `importlib.metadata` parece más moderno, pero en una
    instalación editable esa metadata se congela el día que se instaló: así apareció el `0.1.0`.
    """
    p = pyproject()
    assert "version" not in p["project"], "el pyproject volvió a escribir la versión a mano"
    assert p["project"]["dynamic"] == ["version"]
    assert p["tool"]["hatch"]["version"]["path"] == "contaperu/_version.py"


def test_las_dos_puertas_se_presentan_con_la_version_de_la_libreria():
    """Es lo que ve el contador en su Claude al conectar, y lo que sale con `contaperu --version`.

    Ninguna de las dos puede inventarse el número ni heredar el del SDK que usan por dentro.
    """
    from contaperu.servidor_mcp import mcp

    assert contaperu.__version__ == contaperu._version.__version__
    assert mcp._mcp_server.version == contaperu.__version__


def test_la_version_de_la_libreria_no_es_la_del_estandar_y_cada_una_vive_una_vez():
    """Dos relojes distintos: `pe-ledger` es el formato publicado y cambia poquísimo; la librería
    cambia cada vez que se corrige un asiento. `PE_LEDGER` también llegó a estar escrito dos veces
    —en `__init__.py` y en `operaciones.py`—, así que se comprueba que ahora sea el mismo objeto."""
    from contaperu import operaciones

    assert contaperu.PE_LEDGER == "0.1" and contaperu.__version__ != contaperu.PE_LEDGER
    assert operaciones.PE_LEDGER is contaperu.PE_LEDGER


def test_el_numero_esta_escrito_una_sola_vez_en_todo_el_repositorio():
    """El guardián de verdad: que nadie vuelva a teclear la versión en otro archivo.

    Se busca el literal en el código y en el empaquetado. El CHANGELOG queda fuera a propósito: ahí
    la versión se escribe a mano y así debe ser — es la bitácora, no la fuente.
    """
    literal = f'"{contaperu.__version__}"'
    donde = []
    for f in list((RAIZ / "contaperu").rglob("*.py")) + [RAIZ / "pyproject.toml"]:
        if literal in f.read_text(encoding="utf-8"):
            donde.append(str(f.relative_to(RAIZ)).replace("\\", "/"))
    assert donde == ["contaperu/_version.py"], f"la versión aparece escrita en: {donde}"
