"""La `clase` de cada línea del asiento: de dónde sale, y qué pasa cuando la cuenta no tiene ninguna.

Es lo que hace que una línea suelta se entienda sin mirar `libro.tipo`. Hasta la 1.0 los roles `principal` y `tercero`
solo significaban algo con el libro delante —en una compra `principal` es el gasto y en una venta el ingreso—, y la
línea que recibe un ERP de fuera es justo eso: una línea suelta.

**El caso que fija la regla** es la compra de mercadería: el primer borrador de la 1.0 decía que la clase se deducía
del rol y del libro, y con esa regla una factura imputada a `201101` habría salido como `gasto` cuando es un
**activo**. Por eso la clase sale del primer dígito de la cuenta, que es el elemento del PCGE.
"""
from __future__ import annotations

import pytest

from contaperu import api, pcge
from contaperu.asiento import faltas
from contaperu.asiento.motor import ROLES

LIBRO = {"ruc": "20601234567", "periodo": "202601", "tipo": "compra"}
COMPRA = {"tipo_cp": "01", "serie": "F001", "numero": "500", "fecha_emision": "2026-01-10",
          "contraparte_tipo_doc": "6", "contraparte_doc": "20131312955",
          "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC", "moneda": "PEN",
          "base_gravada": "5000.00", "igv": "900.00", "total": "5900.00",
          "destino_igv": "DG", "id_externo": "c1"}
SIN_CENTROS = {"usa_centros_costo": False}


def documento(cuenta: str, **comprobante) -> dict:
    return {"open_accounting": api.OPEN_ACCOUNTING, "libro": dict(LIBRO),
            "comprobantes": [dict(COMPRA, **comprobante)],
            "imputaciones": {"c1": {"cuenta_contable": cuenta}}}


def asiento(cuenta: str, **comprobante) -> list[dict]:
    return api.generar_asiento(documento(cuenta, **comprobante), driver="asiento_neutral",
                               configuracion=SIN_CENTROS)["asiento"]


# ── La tabla de elementos ─────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cuenta,clase", [
    ("101101", "activo"),      # 1 · disponible y exigible
    ("201101", "activo"),      # 2 · realizable — mercaderías: el caso que tumbó la regla anterior
    ("333101", "activo"),      # 3 · inmovilizado — activo fijo
    ("421201", "pasivo"),      # 4 · pasivo
    ("501101", "patrimonio"),  # 5 · patrimonio neto
    ("634301", "gasto"),       # 6 · gastos por naturaleza
    ("701101", "ingreso"),     # 7 · ingresos
    ("941101", "gasto"),       # 9 · costos por función: quien imputa por destino sigue gastando
])
def test_cada_elemento_del_pcge_da_su_clase(cuenta, clase):
    assert pcge.clase_de(cuenta) == clase


@pytest.mark.parametrize("cuenta", ["891101", "012345", "", "X1", "  "])
def test_los_elementos_8_y_0_y_lo_que_no_es_cuenta_no_tienen_clase(cuenta):
    """No se fuerzan: el 8 son saldos intermediarios y el 0 cuentas de orden, de cierre y de control. Las cinco
    clases siguen siendo cinco, que es lo que las hace universales."""
    assert pcge.clase_de(cuenta) == ""


# ── Lo que sale en el asiento ─────────────────────────────────────────────────────────────────────────────────

def test_una_compra_de_mercaderia_es_activo_y_no_gasto():
    """El caso diario que tumba la regla vieja: el rol es `principal` y la línea es un activo."""
    principal = next(ln for ln in asiento("201101") if ln["rol"] == "principal")
    assert (principal["clase"], principal["debe_haber"]) == ("activo", "D")


def test_una_compra_de_servicio_si_es_gasto():
    principal = next(ln for ln in asiento("634301") if ln["rol"] == "principal")
    assert principal["clase"] == "gasto"


def test_el_igv_de_compras_es_pasivo_al_debe():
    """`401111` es elemento 4, así que su clase es `pasivo`. Con `debe_haber: D` la línea dice exactamente lo que
    pasa —reduce un tributo por pagar, que es el crédito fiscal—; llamarla `activo` al debe afirmaría otra cosa. Lo
    que el ERP de fuera necesita saber ya viaja igual: el rol dice que es impuesto."""
    igv = next(ln for ln in asiento("634301") if ln["rol"] == "igv")
    assert (igv["cuenta"], igv["clase"], igv["debe_haber"]) == ("401111", "pasivo", "D")


def test_el_igv_de_ventas_es_la_misma_cuenta_y_la_misma_clase_al_haber():
    """Las dos líneas de IGV solo se distinguen por el sentido: el crédito reduce el tributo por pagar y el débito
    lo aumenta."""
    doc = documento("701101")
    doc["libro"]["tipo"] = "venta"
    lineas = api.generar_asiento(doc, driver="asiento_neutral", configuracion=SIN_CENTROS)["asiento"]
    igv = next(ln for ln in lineas if ln["rol"] == "igv")
    assert (igv["cuenta"], igv["clase"], igv["debe_haber"]) == ("401111", "pasivo", "H")


def test_ninguna_linea_sale_sin_clase():
    """`a_dict()` omite lo vacío, así que una línea sin clase produciría un documento inválido en silencio."""
    for ln in asiento("634301"):
        assert ln.get("clase"), ln


def test_todos_los_roles_tienen_clase_en_un_asiento_completo():
    """El asiento de un recibo por honorarios con retención y el de una compra con detracción cubren los seis roles."""
    vistos = {}
    for cuenta, extra in [("634301", {"detraccion": {"codigo": "037", "porcentaje": "12"}}),
                          ("632101", {"tipo_cp": "02", "base_gravada": "0", "igv": "0",
                                      "inafecto": "3000.00", "total": "3000.00", "retencion": "240.00"})]:
        for ln in asiento(cuenta, **extra):
            vistos[ln["rol"]] = ln["clase"]
    assert set(vistos) == set(ROLES), f"faltan roles por cubrir: {set(ROLES) - set(vistos)}"
    assert all(vistos.values()), vistos


# ── Todas las cuentas del asiento, no solo la de la base ──────────────────────────────────────────────────────

# Las del asiento que SÍ son configuración: la de la base la trae cada comprobante en su imputación (3.0),
# y por eso estos casos la escriben en `base["cuenta_contable"]`.
CUENTAS_DE_PRUEBA = {"igv": "401111", "retencion_4ta": "401721"}


def aplicada(**general) -> dict:
    """La configuración aplicada como la recibe el motor, con las imputaciones de prueba dentro."""
    from contaperu.pipeline import preparacion as prep
    from util import con_imputaciones, en_secciones
    return con_imputaciones(prep.config_aplicada(en_secciones({"usa_centros_costo": False, **general}, "concar"),
                                                 "concar"))


@pytest.mark.parametrize("descripcion,campos,es_venta", [
    ("factura de compra con IGV", {}, False),
    ("factura con detracción", {"detraccion": {"codigo": "027", "porcentaje": "4"}}, False),
    ("boleta de compra, que no da crédito fiscal y no lleva línea de IGV",
     {"tipo_cp": "03", "base_gravada": "0", "igv": "0", "inafecto": "118.00"}, False),
    ("recibo por honorarios con retención de 4ta",
     {"tipo_cp": "02", "base_gravada": "0", "igv": "0", "inafecto": "3000.00", "total": "3000.00",
      "retencion": "240.00"}, False),
    ("recibo por honorarios sin retención, que es lo normal con suspensión",
     {"tipo_cp": "02", "base_gravada": "0", "igv": "0", "inafecto": "3000.00", "total": "3000.00"}, False),
    ("nota de crédito, que invierte los sentidos", {"tipo_cp": "07", "ref_tipo_cp": "01", "ref_serie": "F001",
                                                    "ref_numero": "500"}, False),
    ("una venta", {}, True),
    ("una factura en dólares", {"moneda": "USD", "tipo_cambio": "3.750"}, False),
])
def test_las_cuentas_que_el_diagnostico_mira_son_las_que_el_asiento_usa(descripcion, campos, es_venta):
    """El test que sostiene la duplicación, y la razón por la que existe.

    Las faltas se calculan **antes** de armar el asiento, así que `resolucion.cuentas_del_asiento` repite las
    condiciones de `motor.lineas_del_comprobante` —hay línea de IGV solo si hay IGV, de retención solo en un recibo
    con retención, de detracción solo si la hay—. No se puede llamar al motor desde ahí porque él importa esto, de
    modo que lo que impide que las dos listas se separen es este test. Si se separan, vuelve el defecto de la 1.0:
    una cuenta sin clase en la del tercero o la del IGV pasaba el diagnóstico y salía en un documento inválido."""
    from datetime import date

    from contaperu.asiento import lineas_del_comprobante
    from contaperu.asiento import resolucion
    from util import comprobante

    base = {"tipo_cp": "01", "serie": "F001", "numero": "500", "fecha_emision": date(2026, 1, 10),
            "contraparte_tipo_doc": "6", "contraparte_doc": "20131312955",
            "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC", "moneda": "PEN", "base_gravada": "100.00",
            "igv": "18.00", "total": "118.00", "destino_igv": "" if es_venta else "DG",
            "cuenta_contable": "701101" if es_venta else "634301"}
    c = comprobante(**{**base, **campos})
    config = aplicada(cuentas=CUENTAS_DE_PRUEBA)
    del_asiento = {ln.cuenta for ln in lineas_del_comprobante(c, config, (date(2026, 1, 1), date(2026, 1, 31)),
                                                              "000001", es_venta=es_venta)}
    assert set(resolucion.cuentas_del_asiento(c, config, es_venta)) == del_asiento, descripcion


def test_una_cuenta_sin_clase_que_no_es_la_de_la_base_tambien_se_dice_antes_de_exportar():
    """El defecto que esto cierra: la cuenta del tercero y la del IGV vienen de la imputación y de la configuración,
    no de la base, así que el guardián de la 1.0 no las miraba. El diagnóstico decía `listo_para_exportar: true` y el
    archivo que se entregaba al otro ERP salía con una línea **sin `clase`**: un documento que el propio esquema del
    estándar rechaza, y sin un solo aviso."""
    doc = documento("634301")
    doc["imputaciones"]["c1"]["cuenta_tercero"] = "011101"          # elemento 0: cuentas de orden
    d = api.diagnosticar(doc, driver="asiento_neutral", configuracion=SIN_CENTROS)
    assert d["listo_para_exportar"] is False
    assert d["faltantes"]["sin_clase"] == ["F001-500"]

    con_igv_raro = dict(SIN_CENTROS, cuentas={"igv": "891101"})     # elemento 8: saldos intermediarios
    d2 = api.diagnosticar(documento("634301"), driver="asiento_neutral", configuracion=con_igv_raro)
    assert d2["faltantes"]["sin_clase"] == ["F001-500"]


def test_ninguna_linea_puede_salir_sin_clase_aunque_el_diagnostico_se_despiste():
    """El último guardián, dentro de la fábrica de líneas, y se prueba llamándola directamente: por la fachada salta
    antes la falta, así que un test por ahí no diría nada de esto.

    Hace falta porque `a_dict()` omite lo vacío: una línea sin clase no sale «vacía», sale **sin el campo**, y eso es
    un documento que el propio esquema del estándar rechaza. Si algún día `cuentas_del_asiento` se queda corta otra
    vez, el motor se planta con su motivo en vez de emitir un archivo inválido."""
    from datetime import date

    from contaperu.asiento import lineas_del_comprobante
    from util import comprobante

    c = comprobante(tipo_cp="01", serie="F001", numero="500", fecha_emision=date(2026, 1, 10),
                    contraparte_doc="20131312955", moneda="PEN", base_gravada="100.00", igv="18.00",
                    total="118.00", destino_igv="DG", cuenta_contable="891101")
    with pytest.raises(faltas.SinClase, match="sin clase contable"):
        lineas_del_comprobante(c, aplicada(cuentas=CUENTAS_DE_PRUEBA), (date(2026, 1, 1), date(2026, 1, 31)), "000001")


# ── La falta ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_una_cuenta_de_elemento_8_no_genera_asiento_y_lo_dice():
    with pytest.raises(faltas.SinClase, match="sin clase contable"):
        asiento("891101")


def test_el_diagnostico_cuenta_la_cuenta_sin_clase_y_se_la_pide_al_contador():
    """Como cualquier otra falta: con su motivo, su cuenta y a quién pedírsela — la eligió el contador."""
    from contaperu.pipeline import diagnostico as diag

    d = api.diagnosticar(documento("891101"), driver="asiento_neutral", configuracion=SIN_CENTROS)
    assert d["listo_para_exportar"] is False
    assert d["faltantes"]["sin_clase"] == ["F001-500"]
    assert any("clase" in motivo for motivo in d["por_que_no"]), d["por_que_no"]
    assert diag.PEDIR_A["sin_clase"] == diag.CONTADOR


def test_la_falta_esta_en_la_tabla_una_sola_vez():
    """Clave, requisito, excepción, texto, a quién pedirla y título: la misma fila alimenta el diagnóstico y la CLI."""
    fila = next(f for f in faltas.FALTAS if f.clave == "sin_clase")
    assert fila.excepcion is faltas.SinClase and fila.requisito == "cuenta_contable"
    assert fila.texto and fila.titulo


# ── La huella ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_la_clase_no_entra_en_la_huella():
    """Se deriva de `cuenta`, que sí entra, así que no aporta información: excluirla no puede hacer que dos asientos
    distintos compartan huella. **Solo es cierto mientras el motor rechace una clase que contradiga su cuenta.**"""
    from contaperu.asiento import huella

    original = asiento("634301")
    mentida = [dict(ln, clase="ingreso") for ln in original]
    assert huella(mentida) == huella(original)
