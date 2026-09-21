"""Las capas del motor, comprobadas por dependencia y no por buena voluntad (1.0).

`test_frontera.py` vigila que el núcleo no salga a la red, no mire el reloj y no importe una puerta. Esto va más lejos:
cada módulo del paquete pertenece a una capa, y una capa solo importa de las que están debajo.

    base     _version, _obsoleto, _datos, errores: hojas sin dependencias del paquete
    nucleo   modelo, catálogos, configuración, IGV, detracciones, validación, partida doble, asiento, PCGE, lectores
    drivers  el contrato, el kit común y cada driver
    pipeline la preparación y la orquestación de un mes
    api      la fachada estable
    puertas  CLI, MCP y HTTP: solo hablan con la api
    compat   las rutas de la 0.x, que pueden importar cualquier cosa y nadie las importa

Además, aquí se hacen visibles dos cosas que la hoja de ruta pedía antes de mover código:

- **El núcleo y los drivers no abren archivos** (hito 0.5): lo que viaja con el paquete lo lee `_datos`.
- **El acoplamiento con lo peruano** (hito J0): qué módulos importan hoy uno peruano queda congelado en
  `fixtures/capas/acoplamiento_pe.json`, y un acoplamiento nuevo no entra sin verse. No mueve código.

    python -c "import sys; sys.path.insert(0, 'tests'); import test_capas as t; t.regenerar()"
"""
from __future__ import annotations

import ast
import json
import pathlib
import subprocess
import sys

import pytest

PAQUETE = pathlib.Path(__file__).resolve().parents[1] / "contaperu"
RAIZ = PAQUETE.parent
ACOPLAMIENTO = pathlib.Path(__file__).parent / "fixtures" / "capas" / "acoplamiento_pe.json"


def _nombre(archivo: pathlib.Path) -> str:
    partes = list(archivo.relative_to(RAIZ).with_suffix("").parts)
    if partes[-1] == "__init__":
        partes = partes[:-1]
    return ".".join(partes)


MODULOS: dict[str, pathlib.Path] = {_nombre(f): f for f in sorted(PAQUETE.rglob("*.py"))}

# Prefijo de módulo → capa. Gana el prefijo más largo.
CAPAS = {
    "contaperu": "paquete",
    "contaperu._version": "base", "contaperu._obsoleto": "base", "contaperu._datos": "base",
    "contaperu.errores": "base",
    "contaperu.modelo": "nucleo", "contaperu.catalogos": "nucleo", "contaperu.configuracion": "nucleo",
    # El vocabulario del estándar (roles, clases, tipos de libro), que lee su catálogo publicado por `_datos`.
    # Núcleo como su hermano `catalogos`, y no «peruano»: los cinco valores de `clase` son universales.
    "contaperu.vocabulario": "nucleo",
    "contaperu.igv": "nucleo", "contaperu.detracciones": "nucleo", "contaperu.validar": "nucleo",
    "contaperu.partida_doble": "nucleo", "contaperu.asiento": "nucleo", "contaperu.pcge": "nucleo",
    "contaperu.lectores": "nucleo", "contaperu.comparar_sire": "nucleo",
    "contaperu.drivers": "drivers",
    "contaperu.pipeline": "pipeline",
    "contaperu.api": "api",
    "contaperu.puertas": "puertas",
}
_DEBAJO = ["base", "nucleo", "drivers", "pipeline", "api"]
PUEDE = {
    "base": {"base"},
    "nucleo": {"base", "nucleo"},
    "drivers": {"base", "nucleo", "drivers"},
    "pipeline": {"base", "nucleo", "drivers", "pipeline"},
    "api": {"base", "nucleo", "drivers", "pipeline", "api"},
    "puertas": {"base", "api", "puertas"},
}

# Lo que todavía importa una capa que no le toca, con su motivo. Vacía desde que las puertas hablan solo con la api
# (etapa 3 de la 1.0): una excepción nueva entra aquí con su motivo, a la vista.
TOLERADAS: dict[tuple[str, str], str] = {}


def capa(modulo: str) -> str:
    partes = modulo.split(".")
    for largo in range(len(partes), 0, -1):
        prefijo = ".".join(partes[:largo])
        if prefijo in CAPAS:
            return CAPAS[prefijo]
    raise KeyError(f"{modulo} no tiene capa: añádelo a CAPAS")


def _recorrer(nodo: ast.AST, en_funcion: bool = False):
    for hijo in ast.iter_child_nodes(nodo):
        yield hijo, en_funcion
        yield from _recorrer(hijo, en_funcion or isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef)))


def importaciones(modulo: str) -> set[str]:
    """Los módulos del paquete que `modulo` importa, resolviendo los imports relativos y los submódulos que se importan
    por su nombre (`from . import concar`)."""
    archivo = MODULOS[modulo]
    paquete = modulo if archivo.name == "__init__.py" else modulo.rpartition(".")[0]
    salida: set[str] = set()
    for nodo, _ in _recorrer(ast.parse(archivo.read_text(encoding="utf-8"))):
        destinos: list[str] = []
        if isinstance(nodo, ast.Import):
            destinos = [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                partes = paquete.split(".")
                base = partes[:len(partes) - (nodo.level - 1)]
                origen = ".".join(base + ([nodo.module] if nodo.module else []))
            else:
                origen = nodo.module or ""
            destinos = [origen] + [f"{origen}.{alias.name}" for alias in nodo.names]
        for destino in destinos:
            if destino.split(".")[0] != "contaperu":
                continue
            while destino and destino not in MODULOS:
                destino = destino.rpartition(".")[0]
            # La raíz del paquete es perezosa y solo trae `_version`: pedirle un nombre no es depender de otra capa.
            if destino and destino not in (modulo, "contaperu"):
                salida.add(destino)
    return salida


def test_cada_modulo_tiene_capa():
    assert [m for m in MODULOS if not _tiene_capa(m)] == []


def _tiene_capa(modulo: str) -> bool:
    try:
        capa(modulo)
        return True
    except KeyError:
        return False


def test_cada_modulo_importa_solo_su_capa_o_las_de_abajo():
    culpables = {}
    for modulo in MODULOS:
        propia = capa(modulo)
        if propia in ("paquete", "compat"):
            continue
        malas = sorted(d for d in importaciones(modulo)
                       if capa(d) not in PUEDE[propia] and (modulo, d) not in TOLERADAS)
        if malas:
            culpables[modulo] = malas
    assert culpables == {}, f"importan una capa que no les toca: {culpables}"


def test_las_toleradas_siguen_existiendo():
    """Una excepción que ya no hace falta se quita de la lista, para que no tape una nueva."""
    sobran = [par for par in TOLERADAS if par[1] not in importaciones(par[0])]
    assert sobran == []


def test_las_puertas_hablan_solo_con_la_api():
    """Una puerta traduce un protocolo: si importara el núcleo o el pipeline, dejaría de haber una api entre ellas y el
    motor, y el mismo documento podría salir distinto según por dónde llega."""
    culpables = {m: sorted(d for d in importaciones(m) if capa(d) not in ("base", "api", "puertas"))
                 for m in MODULOS if capa(m) == "puertas"}
    assert {m: d for m, d in culpables.items() if d} == {}


def test_los_drivers_no_saben_por_que_puerta_llego_el_documento():
    culpables = {m: sorted(d for d in importaciones(m) if capa(d) in ("pipeline", "api", "puertas"))
                 for m in MODULOS if capa(m) == "drivers"}
    assert {m: d for m, d in culpables.items() if d} == {}


def test_nadie_importa_las_rutas_viejas():
    """`_compat` es de las rutas de la 0.x: el motor no depende de ellas, solo las publica."""
    culpables = {m: sorted(d for d in importaciones(m) if capa(d) == "compat")
                 for m in MODULOS if capa(m) not in ("compat", "paquete")}
    assert {m: d for m, d in culpables.items() if d} == {}


def test_importar_el_modelo_no_carga_los_drivers_ni_la_fachada():
    """El paquete es perezoso: quien solo necesita el modelo no paga los drivers, la fachada ni openpyxl."""
    codigo = ("import json, sys; import contaperu.modelo; "
              "print(json.dumps(sorted(m for m in sys.modules if m.startswith(('contaperu', 'openpyxl')))))")
    salida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, cwd=RAIZ, check=True)
    cargados = set(json.loads(salida.stdout))
    assert not cargados & {"contaperu.drivers", "contaperu.api", "contaperu.pipeline", "openpyxl"}, sorted(cargados)


_LECTURAS = {"read_text", "read_bytes", "write_text", "write_bytes"}


def test_el_nucleo_y_los_drivers_no_abren_archivos():
    """Hito 0.5: lo que el núcleo necesita le llega en bytes o diccionarios, y lo que viaja con el paquete lo lee
    `_datos`. Un `open()` o un `Path.read_*` en el núcleo o en un driver haría depender una regla del disco."""
    culpables = []
    for modulo, archivo in MODULOS.items():
        if capa(modulo) not in ("nucleo", "drivers"):
            continue
        for nodo, _ in _recorrer(ast.parse(archivo.read_text(encoding="utf-8"))):
            if not isinstance(nodo, ast.Call):
                continue
            if isinstance(nodo.func, ast.Name) and nodo.func.id == "open":
                culpables.append(f"{modulo}:{nodo.lineno} open()")
            elif isinstance(nodo.func, ast.Attribute) and nodo.func.attr in _LECTURAS:
                culpables.append(f"{modulo}:{nodo.lineno} .{nodo.func.attr}()")
    assert culpables == []


# ── J0: el acoplamiento con lo peruano, a la vista ────────────────────────────────────────────────────────────────

# Los módulos que son contabilidad peruana por lo que IMPORTAN a otros: catálogos de SUNAT, IGV, detracciones,
# validación de SUNAT, PCGE, los lectores del UBL de SUNAT y de la propuesta del SIRE, y el driver del SIRE.
PERUANOS = ("contaperu.catalogos", "contaperu.igv", "contaperu.detracciones", "contaperu.validar", "contaperu.pcge",
            "contaperu.lectores.xml_ubl", "contaperu.lectores.sire_txt", "contaperu.comparar_sire",
            "contaperu.drivers.sire")
# Y los que lo son por lo que CONTIENEN, aunque no importen nada peruano. Separarlos es J2-J4, con un cliente real.
PERUANOS_POR_CONTENIDO = {
    "contaperu.modelo:Libro": "exige un RUC de 11 dígitos y un periodo AAAAMM de venta o compra",
    "contaperu.modelo:Comprobante": "los impuestos del Perú en campos fijos (base gravada, IGV, ISC, IVAP, ICBPER)",
    "contaperu.configuracion:CONFIGURACION_GENERAL": "las cuentas del PCGE y las tasas de detracción",
    "contaperu.asiento.configuracion:CONFIGURACION_DEL_ASIENTO": "la Tabla 10, los sub-diarios y la detracción",
}


def _peruano(modulo: str) -> bool:
    return any(modulo == p or modulo.startswith(p + ".") for p in PERUANOS)


def acoplamiento() -> dict[str, list[str]]:
    salida = {}
    for modulo in MODULOS:
        peruanos = sorted(d for d in importaciones(modulo) if _peruano(d) and not _peruano(modulo))
        if peruanos:
            salida[modulo] = peruanos
    return salida


def regenerar() -> None:
    """Reescribe el acoplamiento congelado. Solo cuando se añade o se quita un acoplamiento A PROPÓSITO."""
    ACOPLAMIENTO.parent.mkdir(parents=True, exist_ok=True)
    ACOPLAMIENTO.write_bytes((json.dumps(acoplamiento(), ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def test_el_acoplamiento_con_lo_peruano_no_crece_sin_verse():
    congelado = json.loads(ACOPLAMIENTO.read_text(encoding="utf-8"))
    hoy = acoplamiento()
    nuevos = {m: sorted(set(p) - set(congelado.get(m, []))) for m, p in hoy.items()}
    assert {m: p for m, p in nuevos.items() if p} == {}, (
        "un módulo que no es peruano empezó a importar uno que sí: si es a propósito, regenera el acoplamiento")
    assert hoy == congelado, "un acoplamiento desapareció: regenera el archivo para que la lista siga siendo la de hoy"


@pytest.mark.parametrize("ruta", sorted(PERUANOS_POR_CONTENIDO))
def test_lo_peruano_por_contenido_sigue_donde_se_dice(ruta):
    import importlib
    modulo, _, nombre = ruta.partition(":")
    assert hasattr(importlib.import_module(modulo), nombre)


def test_no_hay_assert_en_el_paquete():
    """Un `assert` desaparece con `python -O`: lo que protege un archivo no puede depender de cómo se arranca Python. Lo
    que no se cumple se dice con una excepción del motor."""
    culpables = [f"{modulo}:{nodo.lineno}" for modulo, archivo in MODULOS.items()
                 for nodo, _ in _recorrer(ast.parse(archivo.read_text(encoding="utf-8"))) if isinstance(nodo, ast.Assert)]
    assert culpables == []
