"""El TXT del detalle del plan contable (formato 5.3), con el molde de `test_driver_ple.py`.

**Sin snapshot, y a propósito**, por lo mismo que el del SIRE y el del 5.1: los archivos reales no viven en el
repositorio. El ancla es una línea entera, carácter a carácter.

Lo contrastado (1-oct-2026, contra el 5.3 que SUNAT aceptó junto al 5.1 del mismo mes): 8 campos separados por `|`
con palote final, CRLF, una fila por cuenta y ordenadas, el periodo con día —`AAAAMMDD`, a diferencia del `AAAAMM00`
del 5.1—, el plan `01` y el guion donde va la descripción del plan.
"""
from __future__ import annotations

import base64

import pytest

from contaperu import api
from contaperu.drivers import ple_plan
from util import cargar_golden

CAMPOS = 8
# Cómo llama esta empresa de prueba a las cuentas que el golden de compras acaba tocando.
DENOMINACIONES = {"631101": "TRANSPORTE DE CARGA", "401111": "IGV CUENTA PROPIA",
                  "421201": "FACTURAS POR PAGAR M.N.", "421203": "DETRACCIONES POR PAGAR",
                  "121201": "FACTURAS POR COBRAR M.N.", "701101": "VENTA DE MERCADERIAS"}


def documento(nombre_golden: str = "compras_202601.json", cuenta: str = "631101") -> dict:
    libro, comps = cargar_golden(nombre_golden)
    crudos = []
    for n, c in enumerate(comps, 1):
        d = c.a_dict()
        d["id_externo"] = f"f{n}"
        crudos.append(d)
    return {"open_accounting": "1.0", "libro": libro.a_dict(), "comprobantes": crudos,
            "imputaciones": {f"f{n}": {"cuenta_contable": cuenta, "centro_costo": "001"}
                             for n in range(1, len(crudos) + 1)}}


def exportar(nombre_golden: str = "compras_202601.json", **kw) -> tuple[dict, list[str]]:
    r = api.exportar(documento(nombre_golden, **kw), driver="ple_plan",
                     configuracion={"denominacion_cuentas": DENOMINACIONES},
                     fecha="2026-10-01", incluir_observados=True)
    return r, base64.b64decode(r["contenido_base64"]).decode("ascii").splitlines()


def campos_de(linea: str) -> list[str]:
    assert linea.endswith("|"), linea
    return linea[:-1].split("|")


@pytest.mark.parametrize("golden,cuenta", [("compras_202601.json", "631101"), ("ventas_202512.json", "701101")])
def test_estructura(golden, cuenta):
    r, filas = exportar(golden, cuenta=cuenta)
    libro = documento(golden)["libro"]
    assert r["archivo"] == (f"LE{libro['ruc']}{libro['periodo']}00{ple_plan.LIBRO_PLAN_CONTABLE}"
                            f"{ple_plan.OPORTUNIDAD}{ple_plan.BANDERAS}.TXT")
    assert filas
    for fila in filas:
        assert len(campos_de(fila)) == CAMPOS
    bruto = base64.b64decode(r["contenido_base64"]).decode("ascii")
    assert "\r\n" in bruto and "\n" not in bruto.replace("\r\n", "")


def test_la_primera_linea_entera():
    """El ancla, carácter a carácter."""
    _, filas = exportar()
    assert filas[0] == "20260101|401111|IGV CUENTA PROPIA|01|-|||1|"


def test_una_fila_por_cuenta_distinta_y_ordenadas():
    """El 5.3 no es un diario: es el plan de cuentas que el mes usó, sin repetir y en orden."""
    _, filas = exportar()
    cuentas = [campos_de(f)[1] for f in filas]
    assert cuentas == sorted(set(cuentas)), "las cuentas van ordenadas y sin repetir"
    # Y son las del asiento, no las del catálogo entero: lo que no se usó no se declara.
    del_asiento = {l["cuenta"] for l in api.generar_asiento(documento(), driver="ple")["asiento"]}
    assert set(cuentas) == del_asiento


def test_el_periodo_lleva_dia_a_diferencia_del_5_1():
    """`AAAAMMDD` aquí y `AAAAMM00` en el 5.1. Es el despiste fácil, porque los dos salen del mismo mes."""
    _, filas = exportar()
    assert {campos_de(f)[0] for f in filas} == {"20260101"}
    _, del_diario = api.exportar(documento(), driver="ple", fecha="2026-10-01"), None
    diario = base64.b64decode(api.exportar(documento(), driver="ple", fecha="2026-10-01")
                              ["contenido_base64"]).decode("ascii").splitlines()
    assert diario[0].split("|")[0] == "20260100"


def test_el_plan_y_su_descripcion():
    """El plan va con su código de la tabla 17, y su descripción con el guion: SUNAT solo la pide si el código es
    `99`, un plan que su tabla no lista."""
    _, filas = exportar()
    for fila in filas:
        c = campos_de(fila)
        assert c[3] == ple_plan.PLAN_DE_CUENTAS == "01"
        assert c[4] == ple_plan.SIN_DESCRIPCION_DEL_PLAN == "-"


def test_la_cuenta_corporativa_va_vacia():
    """Los campos 6 y 7 son para quien consolida con un plan corporativo distinto. El motor no tiene ese dato."""
    _, filas = exportar()
    for fila in filas:
        assert campos_de(fila)[5] == "" and campos_de(fila)[6] == ""


def test_una_cuenta_sin_denominacion_para_la_exportacion():
    """**El test que justifica todo este driver.** El motor conoce el nombre de la divisionaria del PCGE —`101` es
    «Caja»— y no el de la cuenta de la empresa. Escribir el del PCGE sería declararle a SUNAT una denominación que el
    contribuyente no usa, que es la misma clase de invento que una sigla puesta a dedo.

    Así que falta una y no sale el archivo: sale la lista de cuentas que hay que completar."""
    from contaperu.asiento.faltas import SinDenominacion
    doc = documento()
    sin_una = {k: v for k, v in DENOMINACIONES.items() if k != "401111"}
    with pytest.raises(SinDenominacion) as e:
        api.exportar(doc, driver="ple_plan", configuracion={"denominacion_cuentas": sin_una},
                     fecha="2026-10-01", incluir_observados=True)
    assert e.value.cuentas == ["401111"]
    assert e.value.clave == "sin_denominacion"


def test_el_diagnostico_dice_que_cuentas_faltan_y_a_quien_pedirselas():
    """La lista con la que un portal filtra la tabla donde el contador las completa — como la de
    `sin_codigo_detraccion`."""
    r = api.diagnosticar(documento(), driver="ple_plan",
                         configuracion={"denominacion_cuentas": {"631101": "TRANSPORTE DE CARGA"}})
    assert r["listo_para_exportar"] is False
    assert r["faltantes"]["sin_denominacion"] == ["401111", "421201"]
    motivos = {m["motivo"]: m for m in r["que_falta"]}
    assert motivos["sin_denominacion"]["pedir_a"] == "contador"


def test_el_5_1_no_pide_denominacion():
    """El otro lado: el Libro Diario no la lleva en sus líneas, así que no la exige. Si la exigiera, un mes se
    quedaría sin poder declararse por un dato que su formato ni siquiera tiene."""
    from contaperu.drivers import contrato, ple
    assert "denominacion" not in contrato.exige(ple)
    assert api.exportar(documento(), driver="ple", fecha="2026-10-01")["archivo"]


def test_el_mapa_declara_las_mismas_columnas_que_el_driver_escribe():
    _, filas = exportar()
    plan = api.campos_del_ple()["libros"]["plan_contable"]
    assert len(plan["campos"]) == len(campos_de(filas[0])) == ple_plan.CAMPOS
    assert plan["codigo"] == ple_plan.LIBRO_PLAN_CONTABLE
