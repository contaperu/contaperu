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
