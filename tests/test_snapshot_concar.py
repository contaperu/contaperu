"""El Excel de CONCAR, congelado celda a celda.

Existe para poder mover la lógica del asiento sin miedo. Las filas A..AO que produce
`asiento.asiento()` para cada caso de la tabla del README (y los que salieron de archivos reales)
quedan escritas en `fixtures/snapshot/concar_filas.json`; si un refactor cambia una sola celda —su
valor o su tipo: un `18` entero no es un `18.0`, y openpyxl los escribe distinto— este test falla.

Se congeló el 11-sep-2026, con el código de la v0.6.0, ANTES de invertir el asiento (la línea
neutral pasa a ser la fuente y CONCAR una proyección). Ese Excel lleva un año importándose en
CONCARs de producción: un refactor de arquitectura no tiene derecho a cambiarlo.

Regenerarlo es una decisión, no un trámite: solo cuando una regla contable cambia A PROPÓSITO, con
su fuente al lado, y mirando el diff del JSON celda por celda.

    python -c "import sys; sys.path.insert(0, 'tests'); import test_snapshot_concar as t; t.regenerar()"
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from contaperu import asiento as asi
from contaperu.modelo import Comprobante

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshot"
FILAS = SNAPSHOT / "concar_filas.json"
LINEAS = SNAPSHOT / "lineas_neutrales.json"
MES = (date(2026, 8, 1), date(2026, 8, 31))


def cp(**k) -> Comprobante:
    base = dict(tipo_cp="01", serie="F001", numero="00000123", fecha_emision="2026-08-11",
                fecha_vencimiento="2026-08-18", contraparte_tipo_doc="6", contraparte_doc="20607777773",
                contraparte_nombre="ELECTROMECANICA DE PRUEBA S.R.L.", moneda="PEN", base_gravada="100",
                igv="18", total="118", concepto="Grillete tipo lira 5/8 para torre de alta tension linea 2",
                cuenta_contable="631101", centro_costo="OBRA01")
    base.update(k)
    return Comprobante(**base)


RH = dict(tipo_cp="02", serie="E001", numero="7", base_gravada="0", igv="0", inafecto="2000",
          total="2000", concepto="Asesoria contable")
NC = dict(tipo_cp="07", serie="FC01", numero="9", ref_tipo_cp="01", ref_serie="F001",
          ref_numero="00000123", ref_fecha="2026-08-01")
DET = {"codigo": "037", "porcentaje": "12", "monto": "14.16", "cuenta": "00-000-123456"}
REAL = dict(serie="E001", numero="871", fecha_emision="2026-08-10", fecha_vencimiento="2026-08-27",
            contraparte_doc="20602222226", contraparte_nombre="PROVEEDOR DE PRUEBA SAC",
            base_gravada="4200", igv="756", total="4956",
            concepto="SERVICIO DE TRANSPORTE DE MATERIALES BENCE", cuenta_contable="659999",
            centro_costo="CC-64", detraccion={"codigo": "027", "porcentaje": "4"})

# (nombre, campos del comprobante, venta, configuración del RUC encima de la de fábrica)
CASOS: list[tuple[str, dict, bool, dict | None]] = [
    ("factura_pen", {}, False, None),
    ("factura_usd_con_tc", dict(moneda="USD", tipo_cambio="3.550"), False, None),
    ("factura_usd_sin_tc", dict(moneda="USD"), False, None),
    ("boleta_en_compras", dict(tipo_cp="03", serie="B001", numero="55"), False, None),
    ("honorarios_sin_retencion", RH, False, None),
    ("honorarios_con_retencion", dict(RH, retencion="160"), False, None),
    ("honorarios_usd_con_retencion", dict(RH, retencion="16", moneda="USD", tipo_cambio="3.55"), False, None),
    ("honorarios_retencion_propia", dict(RH, retencion="160"), False,
     {"cuentas": {"retencion_4ta": "401722"}}),
    ("nota_de_credito_compra", NC, False, None),
    ("nota_de_debito_compra", dict(tipo_cp="08", serie="FD01", numero="3"), False, None),
    ("igv_reducido", dict(base_gravada="100", igv="10.5", total="110.5"), False, None),
    ("inafecto", dict(base_gravada="0", igv="0", inafecto="118"), False, None),
    ("sin_vencimiento", dict(fecha_vencimiento=None), False, None),
    ("sin_concepto", dict(concepto=""), False, None),
    ("extemporaneo", dict(fecha_emision="2026-06-15"), False, None),
    ("posterior_al_periodo", dict(fecha_emision="2026-09-02", fecha_vencimiento="2026-09-10"), False, None),
    ("sin_fecha", dict(fecha_emision=None, fecha_vencimiento=None), False, None),
    ("detraccion_pen", dict(detraccion=DET), False, None),
    ("detraccion_usd", dict(detraccion=DET, moneda="USD", tipo_cambio="3.5"), False, None),
    ("detraccion_usd_sin_tc", dict(detraccion=DET, moneda="USD"), False, None),
    ("detraccion_excel_real", REAL, False, None),
    ("detraccion_codigo_sin_tasa", dict(detraccion={"codigo": "031", "porcentaje": "", "monto": "0"}), False, None),
    ("detraccion_tasa_de_tabla", dict(detraccion={"codigo": "019"}), False, None),
    ("detraccion_en_el_11", dict(detraccion=DET), False,
     {"sub_diario_detraccion": "", "detraccion_codigos": {"037": "03799"}}),
    ("detraccion_area_y_tipo_doc", REAL, False, {"detraccion_area": "9001", "detraccion_tipo_doc": "DT"}),
    ("detraccion_cuenta_propia", dict(detraccion=DET), False, {"cuentas": {"cxp_detraccion": {"PEN": "421209"}}}),
    ("nota_con_detraccion", dict(NC, detraccion={"codigo": "027", "porcentaje": "4"}), False, None),
    ("honorarios_con_detraccion", dict(RH, detraccion=DET), False, None),
    ("recibo_servicios_publicos", dict(tipo_cp="14", serie="", numero="12345"), False, None),
    ("cuenta_sin_centro", dict(cuenta_contable="603201"), False, None),
    ("centro_referencia_en_x", dict(cuenta_contable="603201"), False, {"cc_referencia_en_x": True}),
    ("centro_referencia_con_detraccion", dict(cuenta_contable="603201", detraccion={"codigo": "027", "porcentaje": 4}),
     False, {"cc_referencia_en_x": True}),
    ("sin_centros_de_costo", {}, False, {"usa_centros_costo": False}),
    ("ninguna_cuenta_lleva_centro", {}, False, {"cuentas_con_centro": []}),
    ("gasto_y_cxp_del_ruc", dict(cuenta_contable="", moneda="USD"), False,
     {"cuentas": {"gasto": "659901", "cxp": {"USD": "421203"}}}),
    ("tipo_renombrado_por_el_ruc", {}, False, {"tipos": {"01": {"concar": "FA", "sub_diario": "12"}}}),
    ("venta_factura", dict(cuenta_contable=""), True, None),
    ("venta_usd_cuentas_del_ruc", dict(cuenta_contable="", moneda="USD", tipo_cambio="3.55"), True,
     {"cuentas": {"ventas": "701201", "clientes": {"USD": "121209"}}}),
    ("venta_boleta", dict(tipo_cp="03", serie="B001", numero="9", cuenta_contable=""), True, None),
    ("venta_nota_de_credito", dict(NC, serie="FC01", numero="3", cuenta_contable=""), True, None),
    ("venta_con_detraccion", dict(detraccion=DET), True, None),
    ("venta_extemporanea", dict(fecha_emision="2026-07-20", cuenta_contable=""), True, None),
]


def contab_de(extra: dict | None) -> dict:
    return asi.config_de({"concar": extra} if extra else None)


def _celda(v):
    """[tipo, valor]: el tipo cuenta tanto como el valor (openpyxl escribe distinto un int y un float)."""
    if isinstance(v, date):
        return ["date", v.isoformat()]
    return [type(v).__name__, v]


def filas_de(caso) -> list[dict]:
    _, campos, venta, extra = caso
    return asi.asiento(cp(**campos), contab_de(extra), MES, "080001", venta=venta)


def serializar_filas(caso) -> list[dict]:
    return [{col: _celda(v) for col, v in fila.items()} for fila in filas_de(caso)]


def serializar_lineas(caso) -> list[dict]:
    _, _, _, extra = caso
    return [ln.a_dict() for ln in asi.a_lineas(filas_de(caso), contab_de(extra))]


def regenerar() -> None:
    """Reescribe los dos snapshots con el código de hoy. Ver el docstring del módulo antes de usarlo."""
    SNAPSHOT.mkdir(parents=True, exist_ok=True)
    for ruta, fn in ((FILAS, serializar_filas), (LINEAS, serializar_lineas)):
        datos = {caso[0]: fn(caso) for caso in CASOS}
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _cargar(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def test_los_casos_no_se_repiten():
    nombres = [c[0] for c in CASOS]
    assert len(nombres) == len(set(nombres))


def test_el_snapshot_cubre_todos_los_casos():
    """Un caso nuevo en CASOS sin regenerar el snapshot no puede pasar desapercibido."""
    assert set(_cargar(FILAS)) == {c[0] for c in CASOS}
    assert set(_cargar(LINEAS)) == {c[0] for c in CASOS}


@pytest.mark.parametrize("caso", CASOS, ids=[c[0] for c in CASOS])
def test_las_filas_de_concar_no_cambian_ni_una_celda(caso):
    esperado = _cargar(FILAS)[caso[0]]
    obtenido = serializar_filas(caso)
    assert len(obtenido) == len(esperado), f"{caso[0]}: {len(obtenido)} filas, se esperaban {len(esperado)}"
    for i, (fila, fila_esperada) in enumerate(zip(obtenido, esperado)):
        distintas = {col: (fila.get(col), fila_esperada.get(col))
                     for col in set(fila) | set(fila_esperada) if fila.get(col) != fila_esperada.get(col)}
        assert not distintas, f"{caso[0]}, fila {i}: celdas distintas (obtenido, esperado) {distintas}"


@pytest.mark.parametrize("caso", CASOS, ids=[c[0] for c in CASOS])
def test_las_lineas_neutrales_son_las_congeladas(caso):
    assert serializar_lineas(caso) == _cargar(LINEAS)[caso[0]]
