"""Genera `contaperu/api/openconta.json`, el contrato OpenConta de la puerta HTTP, desde la tabla de operaciones.

    python herramientas/generar_openconta.py              # lo reescribe
    python herramientas/generar_openconta.py --comprobar  # falla si el versionado no está al día

Se regenera cuando cambia una operación, un esquema de `contaperu/api/esquemas/`, el esquema del estándar o la versión
del motor. El contrato no se edita a mano: lo que diga tiene que salir del código.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from contaperu.api import openconta  # noqa: E402

VERSIONADO = RAIZ / "contaperu" / "api" / "openconta.json"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    nuevo = openconta.texto().encode("utf-8")
    if "--comprobar" in argv:
        if not VERSIONADO.is_file() or VERSIONADO.read_bytes() != nuevo:
            print("contaperu/api/openconta.json no está al día: python herramientas/generar_openconta.py",
                  file=sys.stderr)
            return 1
        print("contaperu/api/openconta.json está al día")
        return 0
    VERSIONADO.write_bytes(nuevo)
    print(f"escrito {VERSIONADO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
