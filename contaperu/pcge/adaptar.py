"""Adaptación al Plan Contable General Empresarial 2026.

**La tabla está vacía, y no es una tarea pendiente: es el estado correcto hoy.** Este proyecto
nace en 2026 y trabaja con el PCGE 2026 desde el primer asiento — no hay plan anterior del que
traducir, y nadie va a traer aquí una cuenta del PCGE 2019. Este módulo lee las equivalencias de
`pcge2026.json` y no tiene ninguna regla escrita en el código: mientras el archivo no traiga
mapeos, `adaptar()` devuelve las líneas intactas y dice que no hizo nada.

Lo que sí hace falta es el **riel**, y por eso el módulo existe: el día que una modificatoria
sustituya cuentas, el cambio será un archivo de datos y no una versión del programa.

El listón para llenarlo es serio. Este repositorio es público y lo puede usar cualquiera para su
contabilidad real: una equivalencia mal puesta —netear una cuenta que no correspondía— produce
estados financieros incorrectos en empresas que no tienen forma de saberlo. Las reglas entran
**con la cita del artículo de la resolución al lado de cada mapeo** —`cargar()` se niega a leer un
mapeo sin ella—, no de memoria ni por analogía con otro plan.

**Esto no es el catálogo.** Los nombres oficiales de las cuentas y su existencia viven en
`catalogo.py`, que sí trae dato: 1615 cuentas de la norma. Son dos cosas distintas en el mismo
paquete.

**Por qué solo existe el modo `renombrar`.** Sustituir una cuenta por otra es inequívoco: la
misma línea, la misma cantidad, el mismo sentido, otra cuenta. El **neteo** —que una cuenta
desaparezca y su importe se reste de otra— no lo es: hay que decidir si la línea cambia de
sentido o no, y eso lo define la norma, no el sentido común. Se implementará cuando el texto
esté delante, porque escribirlo antes sería exactamente lo que este archivo dice que no se hace.

Si algún día sale una modificatoria y tienes su texto oficial delante, esa es la contribución
que hace falta aquí: el JSON con las citas, no código.

Formato de `pcge2026.json`:

    {
      "version": "2026",
      "fuente": "R.M. 002-2026-EF/30",
      "mapeos": [
        {"de": "<cuenta o prefijo>", "a": "<cuenta>", "modo": "renombrar",
         "cita": "<articulo o anexo que lo dice>", "nota": "<matiz, si lo hay>"}
      ]
    }
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Any

TABLA = pathlib.Path(__file__).with_name("pcge2026.json")

MODOS = ("renombrar",)


class TablaInvalida(ValueError):
    """La tabla del PCGE existe pero está mal formada. Mejor fallar que adaptar a medias."""


@dataclass(frozen=True)
class Mapeo:
    de: str        # cuenta o prefijo de cuenta al que se aplica
    a: str         # cuenta con la que se sustituye
    modo: str      # de momento solo "renombrar"; ver el docstring del módulo
    cita: str = ""
    nota: str = ""


@dataclass
class Informe:
    """Qué se cambió y por qué. Va junto al resultado: una adaptación silenciosa es peor
    que ninguna."""

    version: str = ""
    fuente: str = ""
    aplicados: list[dict] = field(default_factory=list)
    sin_tabla: bool = False

    @property
    def hubo_cambios(self) -> bool:
        return bool(self.aplicados)

    def a_dict(self) -> dict:
        return {
            "version": self.version, "fuente": self.fuente,
            "sin_tabla": self.sin_tabla, "cambios": len(self.aplicados),
            "aplicados": self.aplicados,
        }


def cargar(ruta: pathlib.Path | None = None) -> tuple[list[Mapeo], dict]:
    """Los mapeos de la tabla. Lista vacía mientras la norma no esté codificada."""
    p = ruta or TABLA
    if not p.exists():
        return [], {}
    datos = json.loads(p.read_text(encoding="utf-8"))
    mapeos = []
    for i, m in enumerate(datos.get("mapeos") or []):
        if not m.get("de") or not m.get("a"):
            raise TablaInvalida(f"El mapeo {i} no dice de qué cuenta a cuál.")
        if m.get("modo") not in MODOS:
            raise TablaInvalida(
                f"El mapeo {i} tiene un modo desconocido: {m.get('modo')!r}. "
                f"De momento solo existe {MODOS[0]!r}: el neteo llega con la norma.")
        if not m.get("cita"):
            raise TablaInvalida(
                f"El mapeo {i} ({m['de']} -> {m['a']}) no cita la norma que lo respalda. "
                "En este proyecto ninguna regla contable entra sin fuente."
            )
        mapeos.append(Mapeo(**{k: m.get(k, "") for k in ("de", "a", "modo", "cita", "nota")}))
    return mapeos, datos


def _aplica(cuenta: str, de: str) -> bool:
    """La cuenta cae bajo el mapeo si coincide o si empieza por el prefijo declarado."""
    return bool(cuenta) and cuenta.startswith(de)


def adaptar(lineas: list[dict[str, Any]], ruta: pathlib.Path | None = None) -> tuple[list[dict], Informe]:
    """Líneas de diario -> líneas con las cuentas del PCGE 2026 + el informe de lo que cambió.

    Mientras la tabla esté vacía devuelve las líneas **tal cual**, sin tocar nada, y el informe
    dice `sin_tabla`. Nunca inventa una equivalencia.

    Los mapeos se prueban EN ORDEN y gana el primero que case, así que lo específico va antes
    que lo general: `741101` antes que `74`.
    """
    mapeos, datos = cargar(ruta)
    informe = Informe(version=str(datos.get("version") or ""), fuente=str(datos.get("fuente") or ""),
                      sin_tabla=not mapeos)
    if not mapeos:
        return list(lineas), informe

    salida = []
    for linea in lineas:
        nueva = dict(linea)
        cuenta = str(nueva.get("cuenta") or "")
        for m in mapeos:
            if not _aplica(cuenta, m.de):
                continue
            nueva["cuenta"] = m.a
            informe.aplicados.append({
                "de": cuenta, "a": nueva["cuenta"], "modo": m.modo, "cita": m.cita,
                "glosa": nueva.get("glosa", ""),
            })
            break
        salida.append(nueva)
    return salida, informe
