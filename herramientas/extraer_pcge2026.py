"""Saca el catálogo de cuentas del PDF del PCGE 2026 y lo deja en `contaperu/pcge/catalogo2026.json`.

No es parte del paquete: es la herramienta con la que se generó el dato, y vive aquí para que
cualquiera pueda **rehacerlo y auditarlo** cuando salga una modificatoria, en vez de tener que
confiar en un JSON que apareció de la nada.

    pip install pdfplumber
    python herramientas/extraer_pcge2026.py ruta/al/pcge-2026.pdf

El PDF NO entra al repositorio: es de la web del Consejo Normativo de Contabilidad y pesa 2 MB. Lo
que entra es el extracto —código, nombre y la página donde aparece—, que es lo que hace cualquier
software contable con un plan de cuentas. La página por cuenta no es adorno: permite discutir un
nombre sin volver a abrir el PDF.

Lo que hay que saber del formato para entender el parseo:

- El catálogo es el Capítulo II. Cada línea es `<código> <nombre>`, con el código de 2 a 5 dígitos.
- **Un nombre largo se parte en dos líneas**, y la segunda no lleva código: `6093 Costos vinculados
  con las compras de materiales, suministros y` / `repuestos`. Sin unirlas, esa cuenta entra
  truncada y la siguiente se pierde.
- El corte de página cae en medio del catálogo, así que la continuación puede estar en la página
  siguiente. Por eso se recorre TODO como un solo flujo de líneas.
- La última línea de cada página es su número impreso, que es el que se cita (no el del PDF, que va
  desfasado por la portada y el índice).
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "contaperu" / "pcge" / "catalogo2026.json"

# Un código de cuenta del PCGE: entre 2 y 5 dígitos. El primero es el elemento (1-9).
CODIGO = re.compile(r"^(\d{2,5})\s+(\S.*)$")
# Líneas que son estructura del documento, no cuentas.
RUIDO = re.compile(r"^(ELEMENTO\s+\d|CAP[IÍ]TULO|CUADRO DE|CAT[ÁA]LOGO|CUENTAS DE|\d+)\s*$", re.I)
FUENTE = ("Plan Contable General Empresarial 2026 (PCGE 2026), Consejo Normativo de Contabilidad. "
          "Capítulo II — Clasificación y catálogo de cuentas.")


def es_del_indice(linea: str) -> bool:
    """El índice usa guía de puntos («10 EFECTIVO ....... 45») y también empieza por código.

    Sin esto se cuela entero: 77 cuentas madre en vez de 72, con el nombre lleno de puntos y la
    página en 0. Pasó en el primer intento.
    """
    return ".." in linea


def paginas_del_catalogo(paginas: list[str]) -> tuple[int, int]:
    """El catálogo se reconoce por DENSIDAD, no por un número de página escrito a mano.

    Una página de catálogo es una lista de códigos y poco más; el índice tiene guía de puntos y
    la prosa casi no tiene códigos. Buscarlo por contenido es lo que hace que esto siga valiendo
    cuando salga una modificatoria y todo se desplace.
    """
    def densidad(t: str) -> int:
        return sum(1 for l in t.split("\n")
                   if CODIGO.match(l.strip()) and not es_del_indice(l))

    ini = next(i for i, t in enumerate(paginas)
               if densidad(t) >= 15 and re.search(r"^10\s+EFECTIVO", t, re.M | re.I))
    fin = next((i for i in range(ini + 1, len(paginas)) if densidad(paginas[i]) < 5), len(paginas))
    return ini, fin


def numero_impreso(pagina: str, anterior: int) -> int:
    ultima = [l for l in pagina.split("\n") if l.strip()][-1:]
    if ultima and ultima[0].strip().isdigit():
        return int(ultima[0].strip())
    return anterior


def cuentas_madre_partidas(lineas: list[str]) -> dict[int, tuple[str, str]]:
    """Las cuentas madre de nombre muy largo traen el CÓDIGO EN SU PROPIA LÍNEA, en medio:

        TRIBUTOS, CONTRAPRESTACIONES Y APORTES AL SISTEMA PÚBLICO DE
        40
        PENSIONES Y DE SALUD POR PAGAR

    Es una celda de tabla con el número centrado en vertical, y al extraer el texto sale así. Sin
    tratarlo aparte se pierden las cinco cuentas madre más largas —14, 40, 44, 66 y 76—, que es
    justo lo que pasó en el segundo intento: 67 de 72.

    Devuelve {índice de la línea del código: (código, nombre)} para que quien recorre sepa también
    qué líneas ya están consumidas y no las tome por otra cosa.
    """
    out: dict[int, tuple[str, str]] = {}
    for i, l in enumerate(lineas):
        if not re.fullmatch(r"\d{2,5}", l) or i == 0 or i + 1 >= len(lineas):
            continue
        antes, despues = lineas[i - 1], lineas[i + 1]
        if CODIGO.match(antes) or CODIGO.match(despues) or not antes or not despues:
            continue
        out[i] = (l, f"{antes} {despues}".strip())
    return out


def extraer(paginas: list[str]) -> dict[str, dict]:
    ini, fin = paginas_del_catalogo(paginas)
    cuentas: dict[str, dict] = {}
    impresa = 0
    # Fuera del bucle de páginas A PROPÓSITO: hay nombres cuya segunda línea cae ya en la página
    # siguiente, y reiniciarlo en cada página los dejaba truncados.
    ultimo: str | None = None       # el código cuya línea puede continuar abajo
    for i in range(ini, fin):
        impresa = numero_impreso(paginas[i], impresa)
        lineas = [l.strip() for l in paginas[i].split("\n") if l.strip()]
        # El número impreso es la última línea; fuera, o se confunde con una cuenta partida.
        if lineas and lineas[-1].isdigit():
            lineas = lineas[:-1]

        partidas = cuentas_madre_partidas(lineas)
        consumidas = {j for k in partidas for j in (k - 1, k, k + 1)}
        for k, (cod, nom) in partidas.items():
            cuentas.setdefault(cod, {"nombre": nom, "pagina": impresa})

        for j, l in enumerate(lineas):
            if j in consumidas:
                ultimo = None
                continue
            if RUIDO.match(l) or es_del_indice(l):
                ultimo = None           # tras una cabecera no hay continuación que valga
                continue
            m = CODIGO.match(l)
            if m:
                cod, nom = m.group(1), m.group(2).strip()
                # Un código repetido es una referencia posterior: gana la primera aparición,
                # que es la del catálogo.
                cuentas.setdefault(cod, {"nombre": nom, "pagina": impresa})
                ultimo = cod
                continue
            # No empieza por código: es la segunda línea de un nombre largo.
            if ultimo and len(l) < 90 and not l[0].isdigit():
                cuentas[ultimo]["nombre"] = (cuentas[ultimo]["nombre"] + " " + l).strip()
            ultimo = None
    return cuentas


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[3], file=sys.stderr)
        return 2
    try:
        import pdfplumber
    except ImportError:
        print("Falta pdfplumber:  pip install pdfplumber", file=sys.stderr)
        return 2

    with pdfplumber.open(argv[1]) as pdf:
        paginas = [p.extract_text() or "" for p in pdf.pages]

    cuentas = extraer(paginas)
    por_largo: dict[int, int] = {}
    for c in cuentas:
        por_largo[len(c)] = por_largo.get(len(c), 0) + 1

    DESTINO.write_text(json.dumps({
        "version": "2026",
        "fuente": FUENTE,
        "nota": ("Extraído del PDF oficial con herramientas/extraer_pcge2026.py. `pagina` es el número "
                 "IMPRESO en el documento, para poder citar la cuenta sin abrirlo. Una cuenta que no "
                 "está aquí no es un error: cada empresa abre sus propias divisionarias."),
        "cuentas": dict(sorted(cuentas.items())),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"{DESTINO.relative_to(RAIZ)}: {len(cuentas)} cuentas "
          f"({' · '.join(f'{n} de {d} dígitos' for d, n in sorted(por_largo.items()))})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
