"""El Excel de CONCAR, congelado celda a celda.

Existe para poder mover la lógica del asiento sin miedo. Las filas A..AO que produce
`drivers.concar.filas_de_comprobante()` para cada caso de la tabla del README (y los que salieron de archivos reales)
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
from contaperu.drivers import concar as driver_concar
from contaperu.modelo import Comprobante

SNAPSHOT = Path(__file__).parent / "fixtures" / "snapshot"
FILAS = SNAPSHOT / "concar_filas.json"
LINEAS = SNAPSHOT / "lineas_neutrales.json"
MES = (date(2026, 8, 1), date(2026, 8, 31))


def cp(**k) -> Comprobante:
    base = dict(tipo_cp="01", serie="F001", numero="00000123", fecha_emision="2026-08-11",
                fecha_vencimiento="2026-08-18", contraparte_tipo_doc="6", contraparte_doc="20607777773",
                contraparte_nombre="ELECTROMECANICA DE PRUEBA S.R.L.", moneda="PEN", base_gravada="100",
                igv="18", total="118", concepto="Grillete tipo lira 5/8 para torre de alta tension linea 2")
    base.update(k)
    return Comprobante(**base)


# La cuenta y el centro que escribe cada caso ya no son del comprobante (open-accounting 0.3): van en su imputación, por
# `id_externo`, fundidos con la que el caso ya traiga —la del caso manda campo a campo, y un reparto va solo—.
CUENTA_DEL_CASO = {"cuenta_contable": "631101", "centro_costo": "OBRA01"}


def armar(caso) -> tuple[Comprobante, dict, bool]:
    _, campos, es_venta, extra = caso
    campos = {**CUENTA_DEL_CASO, **campos}
    legado = {k: v for k in CUENTA_DEL_CASO if (v := campos.pop(k))}
    campos.setdefault("id_externo", "f1")
    extra = dict(extra or {})
    imputaciones = dict(extra.get("imputaciones") or {})
    propia = dict(imputaciones.get(campos["id_externo"]) or {})
    if not propia.get("reparto"):
        propia = {**legado, **propia}
    if propia:
        imputaciones[campos["id_externo"]] = propia
        extra["imputaciones"] = imputaciones
    return cp(**campos), contab_de(extra), es_venta


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
    ("centro_referencia_en_x", dict(cuenta_contable="603201"), False, {"centro_como_referencia": True}),
    ("centro_referencia_con_detraccion", dict(cuenta_contable="603201", detraccion={"codigo": "027", "porcentaje": 4}),
     False, {"centro_como_referencia": True}),
    ("sin_centros_de_costo", {}, False, {"usa_centros_costo": False}),
    ("ninguna_cuenta_lleva_centro", {}, False, {"cuentas_con_centro": []}),
    ("gasto_y_cxp_del_ruc", dict(cuenta_contable="", moneda="USD"), False,
     {"cuentas": {"gasto": "659901", "cxp": {"USD": "421203"}}}),
    # La imputación de un documento llega aparte, en la configuración y por `id_externo` (John, 12-sep-2026: las
    # cuentas viven en la aplicación). La cuenta del total que decide manda sobre la del RUC, también en la línea
    # que le descuenta la detracción al proveedor; la de la detracción sigue siendo la suya.
    ("cuenta_tercero_de_la_imputacion", dict(id_externo="f1"), False,
     {"imputaciones": {"f1": {"cuenta_tercero": "469901"}}}),
    ("cuenta_tercero_con_detraccion", dict(id_externo="f1", detraccion=DET), False,
     {"imputaciones": {"f1": {"cuenta_tercero": "469901"}}}),
    ("venta_cuenta_tercero_de_la_imputacion", dict(cuenta_contable="", id_externo="f1"), True,
     {"imputaciones": {"f1": {"cuenta_tercero": "121209"}}}),
    # Campo a campo: la cuenta de la imputación manda sobre la de legado, y el centro que no trae sale del legado.
    ("la_imputacion_manda_campo_a_campo", dict(id_externo="f1"), False,
     {"imputaciones": {"f1": {"cuenta_contable": "659999"}}}),
    # El reparto de la base entre cuentas y centros: una línea de gasto o ingreso por parte, con su centro donde la
    # cuenta lo lleva; el doble anexo del tercero, solo si todas las partes comparten centro.
    ("reparto_dos_cuentas", dict(cuenta_contable="", centro_costo="", id_externo="f1"), False,
     {"imputaciones": {"f1": {"reparto": [
         {"importe": "60", "cuenta_contable": "636301", "centro_costo": "SISTEMAS"},
         {"importe": "40", "cuenta_contable": "632201", "centro_costo": "DESARROLLO"}]}}}),
    ("reparto_boleta_con_igv_al_gasto", dict(tipo_cp="03", serie="B001", numero="55", cuenta_contable="",
                                             centro_costo="", id_externo="f1"), False,
     {"imputaciones": {"f1": {"reparto": [
         {"importe": "100", "cuenta_contable": "631101", "centro_costo": "OBRA01"},
         {"importe": "18", "cuenta_contable": "659999"}]}}}),
    ("reparto_mismo_centro_doble_anexo", dict(cuenta_contable="", centro_costo="", id_externo="f1"), False,
     {"centro_en_anexo_del_tercero": True, "imputaciones": {"f1": {"reparto": [
         {"importe": "60", "cuenta_contable": "631101", "centro_costo": "OBRA01"},
         {"importe": "40", "cuenta_contable": "632201", "centro_costo": "OBRA01"}]}}}),
    ("venta_reparto", dict(cuenta_contable="", centro_costo="", id_externo="f1"), True,
     {"imputaciones": {"f1": {"reparto": [
         {"importe": "70", "cuenta_contable": "701101"}, {"importe": "30", "cuenta_contable": "704101"}]}}}),
    ("tipo_renombrado_por_el_ruc", {}, False, {"tipos": {"01": {"sigla": "FA", "sub_diario": "12"}}}),
    ("venta_factura", dict(cuenta_contable=""), True, None),
    ("venta_usd_cuentas_del_ruc", dict(cuenta_contable="", moneda="USD", tipo_cambio="3.55"), True,
     {"cuentas": {"ventas": "701201", "clientes": {"USD": "121209"}}}),
    ("venta_boleta", dict(tipo_cp="03", serie="B001", numero="9", cuenta_contable=""), True, None),
    ("venta_nota_de_credito", dict(NC, serie="FC01", numero="3", cuenta_contable=""), True, None),
    ("venta_con_detraccion", dict(detraccion=DET), True, None),
    ("venta_extemporanea", dict(fecha_emision="2026-07-20", cuenta_contable=""), True, None),
]


def contab_de(extra: dict | None) -> dict:
    return asi.config_aplicada(extra)


def _celda(v):
    """[tipo, valor]: el tipo cuenta tanto como el valor (openpyxl escribe distinto un int y un float)."""
    if isinstance(v, date):
        return ["date", v.isoformat()]
    return [type(v).__name__, v]


def filas_de(caso) -> list[dict]:
    c, config, es_venta = armar(caso)
    return driver_concar.filas_de_comprobante(c, config, MES, "080001", es_venta=es_venta)


def serializar_filas(caso) -> list[dict]:
    return [{col: _celda(v) for col, v in fila.items()} for fila in filas_de(caso)]


def serializar_lineas(caso) -> list[dict]:
    """Las líneas neutrales que arma el motor. Se congelaron primero desde las columnas de CONCAR
    (v0.6) y se regeneraron UNA vez al invertir el asiento (0.7), con un diff revisado que solo
    añadía `rol`, `tipo_cp` y el código SUNAT de la detracción, dejaba la glosa sin cortar y la tasa
    del IGV como texto exacto. Ningún importe, cuenta ni sentido cambió."""
    c, config, es_venta = armar(caso)
    return [ln.a_dict() for ln in asi.lineas_del_comprobante(c, config, MES, "080001", es_venta=es_venta)]


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
