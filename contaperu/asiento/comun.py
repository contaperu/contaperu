"""Lo que los dos motores del asiento hacen igual, escrito una vez.

`asiento/` arma hoy dos asientos: el de un comprobante (`comprobante.py`) y el de un movimiento de tesorería
(`movimiento.py`). Nacieron con diez meses de diferencia, y el segundo se escribió mirando al primero, así que
tres cosas quedaron copiadas letra por letra. Aquí están, una vez:

- `iso` y `limpio`, dos líneas cada una, que estaban en los dos ficheros.
- `indice_de_lineas_por_id`, que es la grande: `comprobante.indice_de_lineas_dadas` y
  `movimiento.indice_de_movimientos_dados` eran **el mismo bucle** —el mismo enlace por
  `linea.documento.id_externo`, los mismos tres rechazos y el mismo tramo `desde`/`hasta`—, y lo único
  distinto era la excepción, el sustantivo de los mensajes y con qué se construye la cabecera. El docstring de
  la segunda ya lo decía: «hermana exacta» de la primera. Dos copias de un bucle con tres rechazos son dos
  sitios donde arreglar el cuarto.

**Los textos de los tres mensajes no cambian ni una letra** al unificarlos: los afirma la batería
(`test_asiento_de_tesoreria.py`, `test_driver_ple.py`), y además son lo que lee quien integra. Por eso el
sustantivo y el bloque entran como parámetro en vez de reescribirse «mejor».
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable, Iterable, Sequence

from ..modelo.accesores import campo
from .lineas import LineaDiario


def iso(fecha: date | None) -> str:
    """Una fecha como la escribe el estándar, y vacío si no la hay."""
    return fecha.isoformat() if fecha else ""


def limpio(campos: dict) -> dict:
    """Sin las claves vacías: un documento `open-accounting` no lleva ruido."""
    return {k: v for k, v in campos.items() if v not in ("", None)}


def _id_de_la_linea(linea: LineaDiario) -> str:
    return str((linea.documento or {}).get("id_externo") or "")


def indice_de_lineas_por_id(entradas: Iterable[Any], lineas: Sequence[LineaDiario], *,
                            excepcion: type[Exception], sustantivo: str, bloque: str,
                            clase: Callable[..., Any], cabecera: Callable[[Any, str], Any]) -> tuple:
    """Unas líneas que YA vienen armadas → el índice de qué tramo es de qué entrada.

    Es la vuelta de generar el asiento: allí el índice nace de producir las líneas, y aquí de reconocerlas.
    **El enlace es `linea.documento.id_externo`**, que el estándar puso en la línea justamente para esto
    ([enmienda 0009](../../estandar/enmiendas/0009-id-externo-en-la-linea.md)). No se adivina por cuenta ni por
    importe.

    Y **no se renumera nada**: el `sub_diario` y el `correlativo` salen de las propias líneas, así que el CUO
    que escriba el destino es el que puso quien las produjo. Renumerar aquí cambiaría el número de un asiento
    que ya salió.

    Tres cosas se rechazan en voz alta, porque pasarlas por alto daría un archivo incompleto que parece
    correcto: una línea sin `id_externo`, una con uno que ninguna entrada tiene, y las líneas de una misma
    entrada **no contiguas** —el índice es un tramo `desde`/`hasta`, así que un asiento partido en dos trozos
    no se puede representar—.
    """
    de_su_id: dict[str, tuple[int, Any]] = {}
    for posicion, entrada in enumerate(entradas):
        clave = str(campo(entrada, "id_externo") or "")
        if clave:
            de_su_id[clave] = (posicion, entrada)

    indice: list[Any] = []
    vistos: set[str] = set()
    i = 0
    while i < len(lineas):
        id_externo = _id_de_la_linea(lineas[i])
        if not id_externo:
            raise excepcion(
                f"la línea {i + 1} del asiento no dice de qué {sustantivo} es: le falta `documento.id_externo`, "
                f"que es el enlace con el bloque `{bloque}`")
        if id_externo not in de_su_id:
            raise excepcion(
                f"la línea {i + 1} del asiento dice ser del {sustantivo} {id_externo!r}, que no está en el documento")
        if id_externo in vistos:
            raise excepcion(
                f"las líneas del {sustantivo} {id_externo!r} no van seguidas: el índice de un asiento es un tramo, "
                f"así que un {sustantivo} partido en dos trozos no se puede representar")
        vistos.add(id_externo)
        desde = i
        while i < len(lineas) and _id_de_la_linea(lineas[i]) == id_externo:
            i += 1
        posicion, entrada = de_su_id[id_externo]
        indice.append(clase(posicion=posicion, sub_diario=lineas[desde].sub_diario,
                            correlativo=lineas[desde].correlativo, desde=desde, hasta=i,
                            cabecera=cabecera(entrada, id_externo)))
    return tuple(indice)
