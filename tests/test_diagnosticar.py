"""`diagnosticar`: todo lo que hay que mirar de un mes antes de exportarlo, sin lanzar nada.

Un caso por cada cosa que puede faltar. La regla que se prueba en todos: la respuesta describe, no
corrige ni inventa —un comprobante sin cuenta sale por su serie-número y nada más—.
"""
from __future__ import annotations

import json

import pytest

from contaperu import api
from contaperu.pipeline import diagnostico as diag
from util import GOLDEN, por_la_fachada

LIBRO = {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608", "tipo": "compra"}
FACTURA = {"tipo_cp": "01", "serie": "E001", "numero": "871", "fecha_emision": "2026-08-10",
           "fecha_vencimiento": "2026-08-27", "contraparte_doc": "20602222226",
           "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC", "base_gravada": "4200", "igv": "756",
           "total": "4956", "concepto": "SERVICIO DE TRANSPORTE", "cuenta_contable": "659999",
           "centro_costo": "CC-64"}


# Las facturas de estas pruebas escriben su cuenta y su centro: llegan como su imputación (open-accounting 0.3).
diagnosticar = por_la_fachada(api.diagnosticar)
exportar = por_la_fachada(api.exportar)


def doc(*comprobantes: dict, **libro) -> dict:
    return {"open_accounting": "1.0", "libro": dict(LIBRO, **libro), "comprobantes": list(comprobantes)}


def test_un_mes_limpio_esta_listo_y_dice_que_saldria():
    d = diagnosticar(doc(FACTURA, dict(FACTURA, numero="872", total="118", base_gravada="100", igv="18")), driver="concar")
    assert d["listo_para_exportar"] is True and d["por_que_no"] == []
    assert d["saldrian"] == ["E001-871", "E001-872"]
    assert d["totales"] == {"comprobantes": 2, "saldrian": 2, "excluidos": 0, "fuera_del_destino": 0,
                            "con_error": 0, "con_aviso": 0}
    assert d["sub_diarios"] == {"11": {"etiqueta": "Compras", "comprobantes": 2, "empieza_en": 1}}
    assert d["resumen_por_contraparte"]["20602222226"] == {
        "nombre": "PROVEEDOR DE PRUEBA SAC", "comprobantes": 2, "total": "5074.00", "moneda": "PEN",
        "por_moneda": {"PEN": "5074.00"}}
    for clave in ("sin_cuenta", "sin_centro", "sin_sigla", "sin_codigo_de_moneda"):
        assert d["faltantes"][clave] == []
    # Sin correlativos dados, lo dice —arrancaría en 1— pero no es motivo para no estar listo.
    assert d["faltantes"]["sin_correlativo"] == ["11"]


def test_los_errores_bloquean_y_van_por_serie_numero():
    d = diagnosticar(doc(FACTURA, dict(FACTURA, numero="872", igv="99")), driver="concar")    # IGV que no cuadra
    assert d["listo_para_exportar"] is False
    assert d["por_que_no"] == ["1 comprobantes con observaciones que bloquean"]
    assert [b["serie_numero"] for b in d["bloqueantes"]] == ["E001-872"]
    assert d["bloqueantes"][0]["observaciones"][0]["codigo"] == "IGV_NO_CUADRA"
    assert d["saldrian"] == ["E001-871"]                # lo que saldría con `incluir_observados`, no


def test_los_avisos_no_bloquean_pero_se_ven():
    d = diagnosticar(doc(dict(FACTURA, fecha_emision="2025-07-20")), driver="concar")    # 13 meses: fuera del plazo de anotación
    assert d["listo_para_exportar"] is True
    assert d["avisos"][0]["serie_numero"] == "E001-871"
    assert d["avisos"][0]["observaciones"][0]["codigo"] == "CREDITO_FISCAL_FUERA_DE_PLAZO"
    assert d["totales"]["con_aviso"] == 1
    # El del mes pasado se anota aquí sin más (Ley 29215, art. 2): ni aviso ni «observado».
    d = diagnosticar(doc(dict(FACTURA, fecha_emision="2026-07-20")), driver="concar")
    assert d["avisos"] == [] and d["totales"]["con_aviso"] == 0 and d["listo_para_exportar"] is True


@pytest.mark.parametrize("cambio,clave,motivo", [
    ({"cuenta_contable": ""}, "sin_cuenta", "sin cuenta contable"),
    ({"tipo_cp": "13", "serie": "", "numero": "77"}, "sin_sigla",
     "de un tipo sin sigla en el sistema de destino"),
    ({"moneda": "EUR", "tipo_cambio": "4.1"}, "sin_codigo_de_moneda",
     "en una moneda que el sistema de destino no admite"),
    ({"centro_costo": ""}, "sin_centro", "sin centro de costo en una cuenta que lo lleva"),
])
def test_cada_faltante_se_describe_sin_lanzar(cambio, clave, motivo):
    # Desde la 3.0 una fila sin cuenta falta siempre: no hay ninguna cuenta de la empresa que la supla.
    config = None
    d = diagnosticar(doc(dict(FACTURA, **cambio)), driver="concar", configuracion=config)
    assert d["listo_para_exportar"] is False and d["por_que_no"] == [f"1 {motivo}"]
    assert len(d["faltantes"][clave]) == 1
    # Y la exportación de verdad se niega por lo mismo: el diagnóstico no dice nada que ella no haga.
    with pytest.raises(Exception):
        exportar(doc(dict(FACTURA, **cambio)), driver="concar", configuracion=config)


def test_el_centro_de_costo_lo_para_el_driver_desde_la_0_8():
    """Hasta la 0.7 era la única comprobación que el diagnóstico hacía y el driver de CONCAR no: un
    Excel con la M vacía se generaba igual, y la regla del contador (06-sep-2026: obligatorio donde la
    cuenta lo lleva) la aplicaba solo el portal. Decisión de John (11-sep-2026): el driver la hace
    cumplir —la declara en `EXIGE`— y la regla vive en el motor. Lo que exportar se niega a hacer es
    exactamente lo que el diagnóstico dice, como con la cuenta.
    """
    from contaperu import asiento as asi
    sin_centro = doc(dict(FACTURA, centro_costo=""))
    d = diagnosticar(sin_centro, driver="concar")
    assert d["listo_para_exportar"] is False
    assert d["por_que_no"] == ["1 sin centro de costo en una cuenta que lo lleva"]
    assert d["faltantes"]["sin_centro"] == ["E001-871"]
    assert "centro_costo" in d["exige"]
    with pytest.raises(asi.SinCentro) as e:
        exportar(sin_centro, driver="concar")
    assert [c.numero for c in e.value.comprobantes] == ["871"]


def test_el_tipo_sin_equivalencia_no_se_confunde_con_falta_de_cuenta():
    """Un tipo sin mapa dice SU problema; no arrastra al resto de comprobaciones."""
    d = diagnosticar(doc(dict(FACTURA, tipo_cp="13", serie="", numero="77")), driver="concar")
    assert d["faltantes"]["sin_sigla"] == ["13"]
    assert d["faltantes"]["sin_cuenta"] == [] and d["sub_diarios"] == {}


def test_una_cuenta_que_no_lleva_centro_no_lo_pide():
    d = diagnosticar(doc(dict(FACTURA, cuenta_contable="603201", centro_costo="")), driver="concar")
    assert d["listo_para_exportar"] is True and d["faltantes"]["sin_centro"] == []


def test_los_correlativos_se_ensenan_antes_de_exportar():
    """Lo que un agente tiene que enseñar: desde qué número arranca cada sub-diario."""
    con_det = dict(FACTURA, numero="872", detraccion={"codigo": "027", "porcentaje": 4})
    d = diagnosticar(doc(FACTURA, con_det), driver="concar", correlativos={"11": 41})
    assert d["sub_diarios"]["11"]["empieza_en"] == 41 and d["sub_diarios"]["10"]["empieza_en"] == 1
    assert d["faltantes"]["sin_correlativo"] == ["10"]     # informa; no bloquea
    assert d["listo_para_exportar"] is True


def test_la_detraccion_espera_su_constancia_hasta_que_se_pague():
    """Las dos caras, desde la 3.2: pagada es la que tiene número de constancia Y fecha del depósito.

    La tercera factura es el caso que trajo el cambio: alguien pega el vóucher y se deja la fecha. Antes salía de
    la lista y nadie volvía a mirarla; ahora sigue pendiente, y su entrada dice que el número ya está."""
    provisional = dict(FACTURA, detraccion={"codigo": "027", "porcentaje": 4})
    pagada = dict(FACTURA, numero="872", detraccion={"codigo": "027", "porcentaje": 4, "estado": "PAGADO",
                                                     "nro_constancia": "123456789", "fecha_constancia": "2026-08-20"})
    a_medias = dict(FACTURA, numero="873", detraccion={"codigo": "027", "porcentaje": 4,
                                                       "nro_constancia": "123456789"})
    d = diagnosticar(doc(provisional, pagada, a_medias), driver="concar")
    assert [p["serie_numero"] for p in d["detracciones_pendientes"]] == ["E001-871", "E001-873"]
    assert d["detracciones_pendientes"][0] == {"serie_numero": "E001-871", "codigo": "027", "monto": "198",
                                               "nro_constancia": "", "fecha_constancia": ""}
    assert d["detracciones_pendientes"][1]["nro_constancia"] == "123456789"
    assert d["detracciones_pendientes"][1]["fecha_constancia"] == ""
    assert d["detracciones_pagadas"] == [{"serie_numero": "E001-872", "codigo": "027", "monto": "198",
                                          "nro_constancia": "123456789", "fecha_constancia": "2026-08-20"}]
    # Las dos listas tienen la MISMA forma: quien pinta las dos no aprende dos formas.
    assert set(d["detracciones_pendientes"][0]) == set(d["detracciones_pagadas"][0])
    # Un código que el contribuyente no reconoce se descarta antes (normalizar): ni pendiente ni pagada.
    d2 = diagnosticar(doc(dict(FACTURA, detraccion={"codigo": "000", "porcentaje": 3})), driver="concar")
    assert d2["detracciones_pendientes"] == [] and d2["detracciones_pagadas"] == []
    # Y el `estado` que declare el documento es informativo: PAGADO sin constancia sigue saliendo pendiente.
    solo_lo_dice = dict(FACTURA, detraccion={"codigo": "027", "porcentaje": 4, "estado": "PAGADO"})
    d3 = diagnosticar(doc(solo_lo_dice), driver="concar")
    assert [p["serie_numero"] for p in d3["detracciones_pendientes"]] == ["E001-871"]
    assert d3["detracciones_pagadas"] == []


def test_los_excluidos_y_lo_que_el_destino_no_lleva_se_cuentan_aparte():
    rh = dict(FACTURA, tipo_cp="02", numero="7", base_gravada="0", igv="0", inafecto="4956")
    d = diagnosticar(doc(FACTURA, dict(FACTURA, numero="872", excluida=True), rh), driver="sire")
    assert d["totales"]["excluidos"] == 1 and d["totales"]["fuera_del_destino"] == 1
    assert d["saldrian"] == ["E001-871"]
    # El SIRE es un registro tributario: no pide cuentas ni sub-diarios.
    assert d["faltantes"] == {} and d["sub_diarios"] == {}


def test_una_nota_de_credito_resta_en_el_resumen_por_contraparte():
    nc = dict(FACTURA, tipo_cp="07", serie="FC01", numero="9", total="118", base_gravada="100", igv="18",
              ref_tipo_cp="01", ref_serie="E001", ref_numero="871", ref_fecha="2026-08-10")
    d = diagnosticar(doc(FACTURA, nc), driver="concar")
    assert d["resumen_por_contraparte"]["20602222226"]["total"] == "4838.00"


def test_un_mes_vacio_no_esta_listo():
    d = diagnosticar(doc(), driver="concar")
    assert d["listo_para_exportar"] is False and d["por_que_no"] == ["no hay comprobantes que exportar"]


def test_el_golden_de_compras_se_diagnostica_con_la_cuenta_de_cada_comprobante():
    """El golden viene de SUNAT y no imputa nada, así que las tres facturas están sin cuenta. Hasta la 3.0 la
    ponía la configuración —`cuentas.gasto`, y CONCAR traía la suya—, y entonces un mes al que nadie le había
    escrito una cuenta pasaba a «listo para exportar» imputado a un comodín."""
    from util import imputando

    datos = json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8"))
    sin = diagnosticar(datos, driver="concar", configuracion={"usa_centros_costo": False})
    assert sin["listo_para_exportar"] is False and len(sin["faltantes"]["sin_cuenta"]) == 3
    con = diagnosticar(imputando(datos, "659999"), driver="concar", configuracion={"usa_centros_costo": False})
    assert con["listo_para_exportar"] is True and len(con["saldrian"]) == 3


def test_solo_un_documento_que_no_es_documento_lanza():
    with pytest.raises(api.DocumentoInvalido, match="Falta el bloque"):
        diagnosticar({"comprobantes": []}, driver="concar")


# ── Para ese destino, y a quién pedírselo (0.8.0) ──────────────────────────────

def test_el_csv_no_bloquea_por_centro_ni_por_moneda():
    """Lo que deja un mes «no listo» depende del destino: el CSV escribe la moneda en ISO y el centro que
    haya, así que ni EUR ni una M vacía lo paran. `faltantes` lo sigue diciendo, informando."""
    d = diagnosticar(doc(dict(FACTURA, centro_costo="", moneda="EUR", tipo_cambio="4.1")), driver="csv")
    assert d["exige"] == ["cuenta_contable", "tipo_cp"]
    assert d["listo_para_exportar"] is True and d["por_que_no"] == [] and d["que_falta"] == []
    assert d["faltantes"]["sin_codigo_de_moneda"] == ["EUR"] and d["faltantes"]["sin_centro"] == ["E001-871"]
    # Y la exportación de verdad sale: el diagnóstico no dice nada que ella no haga.
    assert exportar(doc(dict(FACTURA, centro_costo="", moneda="EUR", tipo_cambio="4.1")), driver="csv")["archivo"].endswith(".csv")


def test_lo_que_falta_dice_a_quien_pedirselo():
    """Un agente redacta la pregunta a quien toca: al contador lo que se ve en el documento o en el
    plan de cuentas; al sistema, la configuración del destino."""
    d = diagnosticar(doc(dict(FACTURA, igv="99", total="4299"),                    # el IGV no es el 18 %
                            dict(FACTURA, numero="872", cuenta_contable=""),
                            dict(FACTURA, numero="873", cuenta_contable=""),
                            dict(FACTURA, tipo_cp="13", serie="", numero="77")), driver="concar")   # sin sigla
    assert [(q["motivo"], q["comprobantes"], q["pedir_a"]) for q in d["que_falta"]] == [
        ("IGV_NO_CUADRA", ["E001-871"], "contador"),
        ("sin_sigla", ["77"], "sistema"),
        ("sin_cuenta", ["E001-872", "E001-873"], "contador"),
    ]
    assert d["que_falta"][1]["texto"].endswith(": 13")
    assert all(q["texto"] for q in d["que_falta"])


def test_la_tabla_pedir_a_cubre_todos_los_codigos_de_validar():
    """Si alguien añade una observación sin decir a quién se le pide, este test lo dice."""
    import ast
    import pathlib

    import contaperu.validar as validar
    codigos = set()
    for n in ast.walk(ast.parse(pathlib.Path(validar.__file__).read_text(encoding="utf-8"))):
        if isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            f = n.func
            if (isinstance(f, ast.Name) and f.id in ("error", "aviso")) or (isinstance(f, ast.Attribute) and f.attr == "observar"):
                codigos.add(n.args[0].value)
    assert codigos, "no se encontró ningún código en validar.py"
    faltan = sorted(codigos - set(diag.PEDIR_A))
    assert faltan == [], f"códigos sin pedir_a: {faltan}"
    assert set(diag.PEDIR_A.values()) <= {diag.CONTADOR, diag.SISTEMA, diag.PROVEEDOR}
    # `proveedor` está reservado: el motor no puede afirmar que lo que falta esté en el papel.
    assert diag.PROVEEDOR not in diag.PEDIR_A.values()
    for clave in ("sin_cuenta", "sin_centro", "sin_sigla", "sin_codigo_de_moneda"):
        assert clave in diag.PEDIR_A


def test_una_sola_tabla_de_faltas():
    """Clave, requisito, excepción, texto, a quién pedirla y título viven en `asiento.FALTAS`, en el orden de la
    comprobación. Cada excepción hereda de `NoExportable` y lleva la clave de su fila; la CLI atrapa solo esa base."""
    from contaperu import asiento as asi
    from contaperu.drivers import concar, contrato

    assert [f.clave for f in asi.FALTAS] == ["sin_sigla", "sin_codigo_de_moneda", "reparto_no_admitido",
                                            "sin_cuenta", "sin_clase", "reparto_que_no_cuadra", "sin_centro",
                                            "sin_correlativo", "no_cabe"]
    for falta in asi.FALTAS:
        assert falta.texto and falta.titulo and falta.pedir_a == diag.PEDIR_A[falta.clave]
        if falta.excepcion is not None:
            assert issubclass(falta.excepcion, asi.NoExportable) and falta.excepcion.clave == falta.clave
    assert issubclass(contrato.NoCabe, asi.NoExportable) and contrato.NoCabe.clave == "no_cabe"
    assert issubclass(concar.CorrelativoDesborda, asi.NoExportable)
    assert not issubclass(asi.RepartoNoCuadra, asi.SinCuenta) and not issubclass(asi.RepartoNoAdmitido, asi.SinCuenta)


def test_lo_que_saldria_se_cuenta_igual_en_totales_y_en_la_lista():
    """Hito 0.8: `totales.saldrian` contaba los candidatos, también los que bloquean; la lista, solo los que saldrían."""
    d = diagnosticar(doc(FACTURA, dict(FACTURA, numero="872", igv="99")), driver="concar")
    assert d["saldrian"] == ["E001-871"] and d["totales"]["saldrian"] == len(d["saldrian"]) == 1


def test_el_resumen_por_contraparte_no_suma_soles_con_dolares():
    """Hito 0.8: dos monedas del mismo RUC no dan un único total."""
    usd = dict(FACTURA, numero="872", moneda="USD", tipo_cambio="3.750", total="118", base_gravada="100", igv="18")
    r = diagnosticar(doc(FACTURA, usd), driver="concar")["resumen_por_contraparte"]["20602222226"]
    assert r["por_moneda"] == {"PEN": "4956.00", "USD": "118.00"}
    assert (r["moneda"], r["total"], r["comprobantes"]) == ("PEN", "4956.00", 2)
