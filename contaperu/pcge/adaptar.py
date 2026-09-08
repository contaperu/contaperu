"""Adaptación al Plan Contable General Empresarial 2026.

**La tabla está vacía a propósito.** Este módulo lee las equivalencias de `pcge2026.json` y no
tiene ninguna regla escrita en el código: mientras el archivo no traiga mapeos, `adaptar()`
devuelve las líneas intactas y dice que no hizo nada.

El motivo es serio. Este repositorio es público y lo puede usar cualquiera para su
contabilidad real: una equivalencia mal puesta —netear una cuenta que no correspondía— produce
estados financieros incorrectos en empresas que no tienen forma de saberlo. Las reglas se
publicarán **con la cita del artículo de la resolución al lado de cada mapeo**, no de memoria
ni por analogía con otro plan.

Si tienes el texto oficial y quieres ayudar, esa es hoy la contribución más útil al proyecto.

Formato de `pcge2026.json`:

    {
      "version": "2026",
      "fuente": "R.M. 002-2026-EF/30",
      "mapeos": [
        {"de": "<cuenta o prefijo>", "a": "<cuenta>", "modo": "renombrar|netear",
         "contra": "<cuenta contra la que netea, si modo=netear>",
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

MODOS = ("renombrar", "netear")


class TablaInvalida(ValueError):
    """La tabla del PCGE existe pero está mal formada. Mejor fallar que adaptar a medias."""


@dataclass(frozen=True)
class Mapeo:
    de: str
    a: str
    modo: str
    contra: str = ""
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
            raise TablaInvalida(f"El mapeo {i} tiene un modo desconocido: {m.get('modo')!r}")
        if m["modo"] == "netear" and not m.get("contra"):
            raise TablaInvalida(f"El mapeo {i} netea pero no dice contra qué cuenta.")
        if not m.get("cita"):
            raise TablaInvalida(
                f"El mapeo {i} ({m['de']} -> {m['a']}) no cita la norma que lo respalda. "
                "En este proyecto ninguna regla contable entra sin fuente."
            )
        mapeos.append(Mapeo(**{k: m.get(k, "") for k in ("de", "a", "modo", "contra", "cita", "nota")}))
    return mapeos, datos


def _aplica(cuenta: str, de: str) -> bool:
    """La cuenta cae bajo el mapeo si coincide o si empieza por el prefijo declarado."""
    return bool(cuenta) and cuenta.startswith(de)


def adaptar(lineas: list[dict[str, Any]], ruta: pathlib.Path | None = None) -> tuple[list[dict], Informe]:
    """Líneas de diario -> líneas con las cuentas del PCGE 2026 + el informe de lo que cambió.

    Mientras la tabla esté vacía devuelve las líneas **tal cual**, sin tocar nada, y el informe
    dice `sin_tabla`. Nunca inventa una equivalencia.
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
            if m.modo == "netear":
                # Netear invierte el sentido contra la cuenta destino: lo que era un ingreso
                # por separado pasa a restar del ingreso principal.
                nueva["debe_haber"] = "H" if nueva.get("debe_haber") == "D" else "D"
                nueva["cuenta"] = m.contra
            informe.aplicados.append({
                "de": cuenta, "a": nueva["cuenta"], "modo": m.modo, "cita": m.cita,
                "glosa": nueva.get("glosa", ""),
            })
            break
        salida.append(nueva)
    return salida, informe
