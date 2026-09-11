"""`diagnosticar`: todo lo que hay que mirar de un mes antes de exportarlo, sin lanzar nada.

Un caso por cada cosa que puede faltar. La regla que se prueba en todos: la respuesta describe, no
corrige ni inventa —un comprobante sin cuenta sale por su serie-número y nada más—.
"""
from __future__ import annotations

import json

import pytest

from contaperu import operaciones as op
from util import GOLDEN

LIBRO = {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608", "tipo": "compra"}
FACTURA = {"tipo_cp": "01", "serie": "E001", "numero": "871", "fecha_emision": "2026-08-10",
           "fecha_vencimiento": "2026-08-27", "contraparte_doc": "20602222226",
           "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC", "base_gravada": "4200", "igv": "756",
           "total": "4956", "concepto": "SERVICIO DE TRANSPORTE", "cuenta_contable": "659999",
           "centro_costo": "CC-64"}


def doc(*comprobantes: dict, **libro) -> dict:
    return {"pe_ledger": "0.2", "libro": dict(LIBRO, **libro), "comprobantes": list(comprobantes)}


def test_un_mes_limpio_esta_listo_y_dice_que_saldria():
    d = op.diagnosticar(doc(FACTURA, dict(FACTURA, numero="872", total="118", base_gravada="100", igv="18")))
    assert d["listo_para_exportar"] is True and d["por_que_no"] == []
    assert d["saldrian"] == ["E001-871", "E001-872"]
    assert d["totales"] == {"comprobantes": 2, "saldrian": 2, "excluidos": 0, "fuera_del_registro": 0,
                            "con_error": 0, "con_aviso": 0}
    assert d["sub_diarios"] == {"11": {"etiqueta": "Compras", "comprobantes": 2, "empieza_en": 1}}
    assert d["resumen_por_contraparte"]["20602222226"] == {
        "nombre": "PROVEEDOR DE PRUEBA SAC", "comprobantes": 2, "total": "5074.00", "moneda": "PEN"}
    for clave in ("sin_cuenta", "sin_centro_de_costo", "tipos_sin_equivalencia", "monedas_sin_codigo"):
        assert d["faltantes"][clave] == []
    # Sin correlativos dados, lo dice —arrancaría en 1— pero no es motivo para no estar listo.
    assert d["faltantes"]["sub_diarios_sin_correlativo"] == ["11"]


def test_los_errores_bloquean_y_van_por_serie_numero():
    d = op.diagnosticar(doc(FACTURA, dict(FACTURA, numero="872", igv="99")))    # IGV que no cuadra
    assert d["listo_para_exportar"] is False
    assert d["por_que_no"] == ["1 comprobantes con observaciones que bloquean"]
    assert [b["serie_numero"] for b in d["bloqueantes"]] == ["E001-872"]
    assert d["bloqueantes"][0]["observaciones"][0]["codigo"] == "IGV_NO_CUADRA"
    assert d["saldrian"] == ["E001-871"]                # lo que saldría con `incluir_observados`, no


def test_los_avisos_no_bloquean_pero_se_ven():
    d = op.diagnosticar(doc(dict(FACTURA, fecha_emision="2026-07-20")))    # extemporáneo: aviso
    assert d["listo_para_exportar"] is True
    assert d["avisos"][0]["serie_numero"] == "E001-871"
    assert d["avisos"][0]["observaciones"][0]["codigo"] == "PERIODO_ANTERIOR"
    assert d["totales"]["con_aviso"] == 1


@pytest.mark.parametrize("cambio,clave,motivo", [
    ({"cuenta_contable": ""}, "sin_cuenta", "sin cuenta contable"),
    ({"tipo_cp": "13", "serie": "", "numero": "77"}, "tipos_sin_equivalencia",
     "de un tipo sin equivalencia en el sistema de destino"),
    ({"moneda": "EUR", "tipo_cambio": "4.1"}, "monedas_sin_codigo",
     "en una moneda que el sistema de destino no admite"),
])
def test_cada_faltante_se_describe_sin_lanzar(cambio, clave, motivo):
    d = op.diagnosticar(doc(dict(FACTURA, **cambio)))
    assert d["listo_para_exportar"] is False and d["por_que_no"] == [f"1 {motivo}"]
    assert len(d["faltantes"][clave]) == 1
    # Y la exportación de verdad se niega por lo mismo: el diagnóstico no dice nada que ella no haga.
    with pytest.raises(Exception):
        op.exportar(doc(dict(FACTURA, **cambio)), "concar")


def test_el_centro_de_costo_lo_avisa_el_diagnostico_aunque_el_driver_no_lo_pare():
    """La única comprobación que el diagnóstico hace y el driver de CONCAR no.

    `filas_sin_centro` existe desde el 06-sep-2026 con la regla del contador (obligatorio donde la
    cuenta lo lleva en la columna M) y la aplica el portal antes de exportar; el driver, no: un Excel
    con la M vacía se genera igual. Aquí el diagnóstico lo dice —es lo que un agente necesita saber
    ANTES de generar— y este test fija que hoy `exportar` sigue sin pararlo, para que el día que se
    decida que lo pare, se haga a propósito y no por accidente.
    """
    sin_centro = doc(dict(FACTURA, centro_costo=""))
    d = op.diagnosticar(sin_centro)
    assert d["listo_para_exportar"] is False
    assert d["por_que_no"] == ["1 sin centro de costo en una cuenta que lo lleva"]
    assert d["faltantes"]["sin_centro_de_costo"] == ["E001-871"]
    assert op.exportar(sin_centro, "concar")["archivo"].endswith(".xlsx")


def test_el_tipo_sin_equivalencia_no_se_confunde_con_falta_de_cuenta():
    """Un tipo sin mapa dice SU problema; no arrastra al resto de comprobaciones."""
    d = op.diagnosticar(doc(dict(FACTURA, tipo_cp="13", serie="", numero="77")))
    assert d["faltantes"]["tipos_sin_equivalencia"] == ["13"]
    assert d["faltantes"]["sin_cuenta"] == [] and d["sub_diarios"] == {}


def test_una_cuenta_que_no_lleva_centro_no_lo_pide():
    d = op.diagnosticar(doc(dict(FACTURA, cuenta_contable="603201", centro_costo="")))
    assert d["listo_para_exportar"] is True and d["faltantes"]["sin_centro_de_costo"] == []


def test_los_correlativos_se_ensenan_antes_de_exportar():
    """Lo que un agente tiene que enseñar: desde qué número arranca cada sub-diario."""
    con_det = dict(FACTURA, numero="872", detraccion={"codigo": "027", "porcentaje": 4})
    d = op.diagnosticar(doc(FACTURA, con_det), correlativos={"11": 41})
    assert d["sub_diarios"]["11"]["empieza_en"] == 41 and d["sub_diarios"]["10"]["empieza_en"] == 1
    assert d["faltantes"]["sub_diarios_sin_correlativo"] == ["10"]     # informa; no bloquea
    assert d["listo_para_exportar"] is True


def test_la_detraccion_espera_su_constancia_hasta_que_se_pague():
    provisional = dict(FACTURA, detraccion={"codigo": "027", "porcentaje": 4})
    pagada = dict(FACTURA, numero="872", detraccion={"codigo": "027", "porcentaje": 4, "estado": "PAGADO",
                                                     "nro_constancia": "123456789", "fecha_constancia": "2026-08-20"})
    d = op.diagnosticar(doc(provisional, pagada))
    assert [p["serie_numero"] for p in d["detracciones_pendientes"]] == ["E001-871"]
    assert d["detracciones_pendientes"][0] == {"serie_numero": "E001-871", "codigo": "027", "monto": "198"}
    # Un código que el contribuyente no reconoce se descarta antes (normalizar), así que no está pendiente.
    d2 = op.diagnosticar(doc(dict(FACTURA, detraccion={"codigo": "000", "porcentaje": 3})))
    assert d2["detracciones_pendientes"] == []


def test_los_excluidos_y_lo_que_el_destino_no_lleva_se_cuentan_aparte():
    rh = dict(FACTURA, tipo_cp="02", numero="7", base_gravada="0", igv="0", inafecto="4956")
    d = op.diagnosticar(doc(FACTURA, dict(FACTURA, numero="872", excluida=True), rh), driver="sire")
    assert d["totales"]["excluidos"] == 1 and d["totales"]["fuera_del_registro"] == 1
    assert d["saldrian"] == ["E001-871"]
    # El SIRE es un registro tributario: no pide cuentas ni sub-diarios.
    assert d["faltantes"] == {} and d["sub_diarios"] == {}


def test_una_nota_de_credito_resta_en_el_resumen_por_contraparte():
    nc = dict(FACTURA, tipo_cp="07", serie="FC01", numero="9", total="118", base_gravada="100", igv="18",
              ref_tipo_cp="01", ref_serie="E001", ref_numero="871", ref_fecha="2026-08-10")
    d = op.diagnosticar(doc(FACTURA, nc))
    assert d["resumen_por_contraparte"]["20602222226"]["total"] == "4838.00"


def test_un_mes_vacio_no_esta_listo():
    d = op.diagnosticar(doc())
    assert d["listo_para_exportar"] is False and d["por_que_no"] == ["no hay comprobantes que exportar"]


def test_el_golden_de_compras_se_diagnostica_con_la_cuenta_del_ruc():
    datos = json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8"))
    sin = op.diagnosticar(datos)
    assert sin["listo_para_exportar"] is False and len(sin["faltantes"]["sin_cuenta"]) == 3
    con = op.diagnosticar(datos, {"cuentas": {"gasto": "659999"}, "usa_centros_costo": False})
    assert con["listo_para_exportar"] is True and len(con["saldrian"]) == 3


def test_solo_un_documento_que_no_es_documento_lanza():
    with pytest.raises(op.DocumentoInvalido, match="Falta el bloque"):
        op.diagnosticar({"comprobantes": []})
