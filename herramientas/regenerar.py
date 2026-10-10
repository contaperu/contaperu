"""Una sola puerta para las ocho de `regenerar()` que la batería tiene repartidas.

Ocho ficheros de test traen cada uno su `regenerar()`, y cada uno se invoca con el mismo conjuro largo:

    python -c "import sys; sys.path.insert(0, 'tests'); import test_snapshot_concar as t; t.regenerar()"

Teclearlo de memoria es cómo se regenera el que no era. Esto hace lo mismo, por nombre:

    python herramientas/regenerar.py --que                 # qué hay, y qué vigila cada uno
    python herramientas/regenerar.py snapshot_concar
    python herramientas/regenerar.py capas superficie      # varios de una vez

**Lo que no hace es decidir por ti.** Regenerar una foto congelada es decir «esto cambió a propósito», así que
después hay que **leer el diff** y contarlo en el commit. Y hay uno que ni siquiera se puede regenerar para quitar:
la superficie pública solo admite AÑADIR, porque quitar un nombre público es una mayor y su fixture se edita a mano
con el motivo escrito al lado.
"""
from __future__ import annotations

import argparse
import importlib
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tests"))

# Qué vigila cada una, para que `--que` sirva de algo y no sea una lista de nombres.
PUERTAS = {
    "capas": ("test_capas", "qué módulos no peruanos importan uno peruano"),
    "caracterizacion": ("test_caracterizacion", "lo que la fachada responde, documento a documento"),
    "formato_xlsx": ("test_formato_xlsx", "el formato de las celdas del Excel"),
    "mcp": ("test_servidor_mcp", "lo que el agente ve: descripciones, esquemas y anotaciones"),
    "snapshot_concar": ("test_snapshot_concar", "el Excel de CONCAR validado, celda a celda (52 casos)"),
    "snapshot_contasis": ("test_snapshot_contasis", "el registro que CONTASIS importó"),
    "snapshot_del_documento": ("test_snapshot_del_documento", "el documento del estándar que sale de un mes"),
    "superficie": ("test_superficie_publica", "los nombres públicos — SOLO para añadir: quitar es una mayor"),
}


def main() -> int:
    p = argparse.ArgumentParser(description="Regenera una foto congelada de la batería, por su nombre.")
    p.add_argument("puertas", nargs="*", help="cuáles regenerar; vacío no hace nada, a propósito")
    p.add_argument("--que", action="store_true", help="enumera las que hay y qué vigila cada una")
    args = p.parse_args()

    if args.que or not args.puertas:
        print("\nLo que se puede regenerar, y qué vigila cada uno:\n")
        for nombre, (modulo, vigila) in PUERTAS.items():
            print(f"  {nombre:24s} {vigila}")
            print(f"  {'':24s} ({modulo}.py)")
        print("\nRegenerar es decir «esto cambió a propósito»: lee el diff y cuéntalo en el commit.\n")
        return 0

    desconocidas = [n for n in args.puertas if n not in PUERTAS]
    if desconocidas:
        print(f"No sé regenerar {', '.join(desconocidas)}. Las que hay: {', '.join(PUERTAS)}")
        return 2

    for nombre in args.puertas:
        modulo, _ = PUERTAS[nombre]
        importlib.import_module(modulo).regenerar()
        print(f"  regenerado: {nombre} ({modulo}.py)")
    print("\nAhora `git diff`, y que el cambio sea el que esperabas.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
