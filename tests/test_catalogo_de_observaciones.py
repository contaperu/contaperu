"""El catálogo público de observaciones, contrastado con las llamadas de `validar.py` (15.16.0).

El catálogo dice el nivel de cada código, y el nivel de verdad lo decide la llamada que lo emite. Si el vigilante
copiara la tabla no vigilaría nada; por eso lee `validar.py` como lo lee `test_diagnosticar.py` —`error(...)`,
`aviso(...)` y `.observar(...)` con el código como primera constante— y, donde el nivel es una variable, lo pregunta
validando un comprobante de verdad.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from contaperu import api
from contaperu.comprobantes.comprobante import ORIGENES, CodigoDeObservacion
from contaperu.modelo import Comprobante, Libro
from contaperu.pipeline import diagnostico as diag
from contaperu.tributos import observaciones, validar

COMPRAS = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202601", tipo="compra")


def _llamadas_de_validar() -> dict[str, set[str]]:
    """Cada código que `validar.py` emite, con el nivel de cada llamada: el literal, o `?` si es una variable."""
    niveles: dict[str, set[str]] = {}
    for n in ast.walk(ast.parse(pathlib.Path(validar.__file__).read_text(encoding="utf-8"))):
        if not (isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[0].value, str)):
            continue
        f = n.func
        if isinstance(f, ast.Name) and f.id in ("error", "aviso"):
            niveles.setdefault(n.args[0].value, set()).add(f.id)
        elif isinstance(f, ast.Attribute) and f.attr == "observar" and len(n.args) > 1:
            nivel = n.args[1]
            niveles.setdefault(n.args[0].value, set()).add(
                nivel.value if isinstance(nivel, ast.Constant) else "?")
    return niveles


LLAMADAS = _llamadas_de_validar()


def test_el_catalogo_tiene_exactamente_los_codigos_que_emite_validar():
    assert LLAMADAS, "no se encontró ningún código en validar.py: el vigilante no está mirando"
    faltan = sorted(set(LLAMADAS) - set(observaciones.CATALOGO))
    sobran = sorted(set(observaciones.CATALOGO) - set(LLAMADAS))
    assert faltan == [], f"códigos que se emiten sin estar en el catálogo: {faltan}"
    assert sobran == [], f"códigos del catálogo que nadie emite: {sobran}"


@pytest.mark.parametrize("codigo", sorted(LLAMADAS))
def test_el_nivel_del_catalogo_es_el_de_su_llamada(codigo):
    """Un código con el nivel en una variable tiene que decir en el catálogo dónde cambia; uno con el nivel literal,
    ese nivel y ningún cambio por origen."""
    entrada = observaciones.CATALOGO[codigo]
    literales = LLAMADAS[codigo] - {"?"}
    assert len(literales) <= 1, f"{codigo} se emite con dos niveles literales: {sorted(literales)}"
    if "?" in LLAMADAS[codigo]:
        assert entrada.nivel_por_origen, f"{codigo} cambia de nivel según el comprobante y el catálogo no lo dice"
    else:
        assert entrada.nivel_por_origen == {}
        assert {entrada.nivel} == literales


def _descuadrado(origen: str, **cambios) -> Comprobante:
    campos = dict(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-01-10", contraparte_doc="20602222226",
                  contraparte_nombre="PROVEEDOR SAC", base_gravada="100.00", igv="15.00", total="115.00",
                  origen=origen)
    return Comprobante(**{**campos, **cambios})


@pytest.mark.parametrize("codigo,cambios", [
    ("IGV_NO_CUADRA", {}),
    ("TOTAL_NO_CUADRA", {"igv": "18.00", "total": "200.00"}),
])
@pytest.mark.parametrize("origen", ORIGENES)
def test_donde_el_nivel_es_una_variable_el_catalogo_dice_el_de_cada_origen(codigo, cambios, origen):
    """Se valida un comprobante de verdad, de cada origen, y el nivel que sale es el que el catálogo promete."""
    c = _descuadrado(origen, **cambios)
    validar.validar(c, COMPRAS)
    salio = {o.codigo: o.nivel for o in c.observaciones}
    assert codigo in salio, salio
    assert salio[codigo] == observaciones.CATALOGO[codigo].nivel_para(origen)


def test_pedir_a_sale_del_catalogo_y_dice_lo_que_decia():
    """`PEDIR_A` ya no escribe los códigos de la validación: los lee de aquí, y el T.C. sigue siendo del sistema."""
    for codigo, entrada in observaciones.CATALOGO.items():
        assert diag.PEDIR_A[codigo] == entrada.pedir_a
    assert diag.PEDIR_A["TC_FALTA"] == diag.SISTEMA
    assert {e.pedir_a for e in observaciones.CATALOGO.values()} == {diag.CONTADOR, diag.SISTEMA}
    # `proveedor` sigue reservado: el motor no puede afirmar que lo que falta esté en su papel.
    assert diag.PROVEEDOR not in {e.pedir_a for e in observaciones.CATALOGO.values()}


def test_el_catalogo_publico_es_la_tabla_entera_por_codigo():
    publico = api.catalogo_de_observaciones()
    assert list(publico) == sorted(observaciones.CATALOGO)
    for codigo, dicho in publico.items():
        entrada = observaciones.CATALOGO[codigo]
        assert dicho == {"nivel": entrada.nivel, "nivel_por_origen": entrada.nivel_por_origen,
                         "pedir_a": entrada.pedir_a, "texto": entrada.texto}
        assert dicho["nivel"] in ("error", "aviso") and dicho["texto"].strip()
        assert set(dicho["nivel_por_origen"]) <= set(ORIGENES)
    # Devolver una copia: quien la toque no cambia la tabla del motor.
    publico["IGV_NO_CUADRA"]["nivel_por_origen"]["sire"] = "error"
    assert api.catalogo_de_observaciones()["IGV_NO_CUADRA"]["nivel_por_origen"] == {"sire": "aviso"}


def test_la_forma_de_una_entrada_no_es_de_ningun_pais():
    """La adelanta la hoja de ruta (J2): la forma vive en el comprobante, que es núcleo y no peruano; la tabla que la
    llena, en `tributos`. Lo que J2 sigue esperando es partir la tabla y escribir la fuente de cada regla."""
    assert CodigoDeObservacion.__module__ == "contaperu.comprobantes.comprobante"
    assert observaciones.__name__.startswith("contaperu.tributos.")
    entrada = CodigoDeObservacion("error", "contador", "Algo.", {"sire": "aviso"})
    assert (entrada.nivel_para("sire"), entrada.nivel_para("xml")) == ("aviso", "error")
