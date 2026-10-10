"""Mide cuánto tarda el motor en un mes, y publica el arnés con el que se midió.

Existe por la misma razón que ninguna regla entra sin su fuente: **una medida sin su arnés es una afirmación que
nadie puede contrastar**. La tabla que decía «3 000 filas se revisan en 0,19 s» se midió una vez en una máquina y
quedó escrita; cualquiera que quisiera comprobarla tenía que rehacer el montaje de cero y adivinar qué documento se
usó. Con esto se corre y se compara.

    python herramientas/medir.py
    python herramientas/medir.py --filas 100 1000 5000

El documento se fabrica multiplicando el golden `casos_202608.json`, que es el que trae los doce casos del motor
—venta, compra, detracción, nota, no domiciliado—, así que lo que se mide es trabajo real y no un comprobante de
juguete repetido. El tope son `MAXIMO_COMPROBANTES` filas: por encima el motor se niega, y con razón.

**Lo que NO es:** una prueba de rendimiento con umbrales. No falla si un día tarda más — de eso no se saca nada útil
en una máquina compartida. Lo que importa de estos números es la **forma**: que crezcan en línea recta. Una curva
que se dobla es una regresión cuadrática escondida, y eso sí se ve a simple vista.
"""
from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys
import time

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from contaperu import api  # noqa: E402

GOLDEN = RAIZ / "tests" / "fixtures" / "golden" / "casos_202608.json"
FILAS = (100, 1000, 3000, 5000)


def documento_de(n: int) -> dict:
    """Un mes de `n` comprobantes, con su imputación dentro, a partir de los doce casos del golden.

    La imputación va **en el documento** y no en la configuración, que es lo que el motor contesta si uno se
    equivoca: «`imputaciones` no va en la configuración: la imputación de cada documento llega en el bloque
    `imputaciones` del documento».

    Cada uno lleva su serie-número y su `id_externo` propios: sin eso el motor los contaría como duplicados y
    estaríamos midiendo el camino de un error, que es otro."""
    g = json.loads(GOLDEN.read_text(encoding="utf-8"))
    base = g["comprobantes"]
    comprobantes, imputaciones = [], {}
    for i in range(n):
        c = copy.deepcopy(base[i % len(base)])
        c["serie"], c["numero"], c["id_externo"] = "F900", f"{i + 1:08d}", f"m{i}"
        imputaciones[f"m{i}"] = {"cuenta_contable": "631101", "centro_costo": "001"}
        comprobantes.append(c)
    return {"open_accounting": g["open_accounting"], "libro": g["libro"], "comprobantes": comprobantes,
            "imputaciones": imputaciones}


def mide(f) -> tuple[float, object]:
    """Cuánto tardó y qué devolvió.

    El resultado **se asigna antes** de leer el reloj y no es un capricho: en `return perf_counter() - arranque,
    f()` Python evalúa los elementos de la tupla de izquierda a derecha, así que el tiempo se calcula ANTES de
    llamar a `f` y salen ceros. Escrito así la primera vez, y los ceros parecían una medida."""
    arranque = time.perf_counter()
    try:
        salida = f()
    except Exception as e:  # noqa: BLE001 — lo que no se pudo medir se dice, no se oculta
        salida = e
    return time.perf_counter() - arranque, salida


def main() -> int:
    p = argparse.ArgumentParser(description="Cuánto tarda el motor en un mes, con el arnés a la vista.")
    p.add_argument("--filas", type=int, nargs="*", default=list(FILAS))
    args = p.parse_args()

    print(f"\n{'Filas':>6} {'revisar':>10} {'exportar(SIRE)':>16} {'por fila':>12}")
    print(f"{'-' * 48}")
    for n in args.filas:
        doc = documento_de(n)
        t_revisar, _ = mide(lambda: api.revisar(doc))
        t_exportar, salida = mide(lambda: api.exportar(doc, driver="sire"))
        exportar = f"{t_exportar:.2f}s" if isinstance(salida, dict) else type(salida).__name__[:14]
        print(f"{n:>6} {t_revisar:>9.2f}s {exportar:>16} {t_revisar / n * 1000:>10.3f} ms")
    print("\nLo que importa es la FORMA: en línea recta está bien; una curva que se dobla es una regresión "
          "cuadrática.\nY la máquina cuenta, así que un número de aquí no se compara con uno de otra.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
