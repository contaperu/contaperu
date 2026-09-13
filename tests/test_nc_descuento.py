"""La nota de crédito de descuento global: una sola forma de guardarla (11-sep-2026).

Regla de John: base = neto, IGV aparte, total = base + IGV. La misma nota llegaba distinta por cada
puerta —del XML con la base Y el descuento (contada dos veces en el TXT del SIRE), de la propuesta de SUNAT
con la base en cero (asiento sin IGV, «Inafecto» en pantalla)— y las dos se bloqueaban con TOTAL_NO_CUADRA.
Ahora la base y el IGV son siempre netos y los descuentos dicen qué parte informa el SIRE en sus campos 16
y 18 (estandar/LEEME.md, open-accounting 0.2).

Fuente: la exportación real de agosto. En sus diez filas el campo 26 es la suma con signo de los campos 14 a
25, y SUNAT registró la FC01-45 entera en 16 y 18 y la E001-233 (motivo «descuento global», sin
AllowanceCharge) en 15 y 17. Los archivos reales no viven en el repo: son de un cliente.
"""
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from contaperu import asiento as concar
from contaperu.drivers import concar as driver_concar
from contaperu import comparar_sire, validar
from contaperu import generar as g
from contaperu.lectores import sire_txt, xml_ubl
from contaperu.modelo import Comprobante, Libro
from test_sire_txt import FACTURA, NOTA, VENTAS, texto
from test_xml_ubl import NC_CON_DESCUENTO
from util import campos, cargar_golden
from util import con_imputaciones, imputar

COMPRAS = Libro(ruc=VENTAS.ruc, razon_social=VENTAS.razon_social, periodo=VENTAS.periodo, tipo="compra")

FIXTURES = Path(__file__).parent / "fixtures" / "xml"
MES = (date(2026, 8, 1), date(2026, 8, 31))
LA_NOTA = (D("9985.36"), D("1797.36"), D("9985.36"), D("1797.36"), D("11782.72"))


def importes(c):
    return (c.base_gravada, c.igv, c.dscto_base, c.dscto_igv, c.total)


def del_xml():
    return xml_ubl.parsear(NC_CON_DESCUENTO.encode("utf-8"), VENTAS)


def de_la_propuesta():
    return sire_txt.parsear(texto(NOTA), VENTAS)[0]


def linea(c, libro=VENTAS):
    return campos(g.lineas_de_texto(libro, [c], "sire")[0], palote_final=False)


def codigos(c, libro=VENTAS):
    validar.validar(c, libro)
    return {o.codigo for o in c.observaciones}


# ── La nota de descuento ─────────────────────────────────────────────────────

def test_por_las_dos_puertas_es_la_misma_nota():
    assert importes(del_xml()) == LA_NOTA
    assert importes(de_la_propuesta()) == LA_NOTA


def test_valida_sin_bloquearse():
    for c in (del_xml(), de_la_propuesta()):
        cods = codigos(c)
        assert not cods & {"TOTAL_NO_CUADRA", "IGV_NO_CUADRA", "DSCTO_MAYOR_QUE_BASE"}, cods


def test_el_txt_la_escribe_como_sunat_y_una_sola_vez():
    for c in (del_xml(), de_la_propuesta()):
        f = linea(c)
        assert f[14:18] == ["0.00", "-9985.36", "0.00", "-1797.36"] and f[25] == "-11782.72"


def test_ida_y_vuelta_contra_la_fila_de_sunat():
    r = comparar_sire.comparar([linea(de_la_propuesta())], [NOTA.split("|")])
    assert r["diferencias"] == [] and r["solo_en_sunat"] == [] and r["solo_nuestros"] == []


def test_el_asiento_revierte_tambien_el_igv():
    """Leída de la propuesta la nota tenía IGV 0, y el asiento mandaba todo el total a la 70."""
    c = de_la_propuesta()
    imputar(c, cuenta_contable="701111", centro_costo="OBRA01")
    config = con_imputaciones(concar.config_de(None))
    filas = driver_concar.filas_de_comprobante(c, config, MES, "050001", es_venta=True)
    assert sorted(D(str(f["O"])) for f in filas) == [D("1797.36"), D("9985.36"), D("11782.72")]


def test_el_resumen_cuenta_el_igv_de_la_nota():
    exp = g.generar(VENTAS, [de_la_propuesta()], "sire")
    assert exp.resumen["igv"] == "-1797.36" and exp.resumen["total"] == "-11782.72"


def test_un_descuento_mayor_que_la_base_de_la_nota_es_error():
    nc = de_la_propuesta()
    nc.dscto_base = D("20000.00")
    assert "DSCTO_MAYOR_QUE_BASE" in codigos(nc)


def test_la_propuesta_con_un_descuento_en_positivo_no_se_lee():
    """SUNAT escribe los campos 16 y 18 en negativo: uno en positivo se leería mal, así que se rechaza."""
    mala = NOTA.replace("|0|0|-9985.36|0|-1797.36|", "|0|0|9985.36|0|1797.36|", 1)
    assert mala != NOTA
    with pytest.raises(sire_txt.SireInvalido, match="positivo"):
        sire_txt.parsear(texto(mala), VENTAS)


# ── Lo que no es una nota de descuento no cambia ─────────────────────────────

def test_una_nc_normal_sigue_en_base_e_igv():
    c = xml_ubl.parsear((FIXTURES / "20131312955-07-FC01-7.xml").read_bytes(), VENTAS)
    assert (c.dscto_base, c.dscto_igv) == (0, 0)
    assert linea(c)[14:18] == ["-200.00", "0.00", "-36.00", "0.00"]


def test_una_factura_con_descuento_de_la_propuesta_vuelve_igual():
    """La base neta es 15 + 16 también en una factura: 1000 − 100 = 900, y al escribirla vuelve 1000 / −100."""
    fila = FACTURA.replace("|0|205256.14|0|36946.11|0|0|0|0|0|0|0|0|242202.25|",
                           "|0|1000.00|-100.00|162.00|0|0|0|0|0|0|0|0|1062.00|", 1)
    assert fila != FACTURA
    c = sire_txt.parsear(texto(fila), VENTAS)[0]
    assert importes(c) == (D("900.00"), D("162.00"), D("100.00"), D("0.00"), D("1062.00"))
    assert "TOTAL_NO_CUADRA" not in codigos(c)
    assert linea(c)[14:18] == ["1000.00", "-100.00", "162.00", "0.00"]


def test_una_nota_de_debito_escribe_la_base_con_su_descuento():
    nd = Comprobante(tipo_cp="08", serie="FD01", numero="3", fecha_emision="2026-08-20",
                     contraparte_doc="20622222222", contraparte_nombre="CLIENTE SAC",
                     base_gravada="100", igv="18", dscto_base="10", total="118",
                     ref_fecha="2026-07-31", ref_tipo_cp="01", ref_serie="F001", ref_numero="257")
    assert linea(nd)[14:18] == ["110.00", "-10.00", "18.00", "0.00"]


def test_xml_el_descuento_solo_decide_en_una_nc_de_ventas_entera():
    factura = xml_ubl.parsear(NC_CON_DESCUENTO.replace("CreditNote", "Invoice").encode("utf-8"), VENTAS)
    assert factura.tipo_cp == "01" and (factura.dscto_base, factura.dscto_igv) == (0, 0)
    assert factura.base_gravada == D("9985.36") and "TOTAL_NO_CUADRA" not in codigos(factura)
    compra = xml_ubl.parsear(NC_CON_DESCUENTO.encode("utf-8"), COMPRAS)
    assert (compra.dscto_base, compra.dscto_igv) == (0, 0)
    parcial = xml_ubl.parsear(NC_CON_DESCUENTO.replace(">9985.36</cbc:Amount>", ">5000.00</cbc:Amount>")
                              .encode("utf-8"), VENTAS)
    assert (parcial.dscto_base, parcial.dscto_igv) == (0, 0)
    assert parcial.datos_originales["descuentos_globales"] == [{"codigo": "", "importe": "5000.00"}]


def _suma(f):
    return sum((D(v) for v in f[13:25] if v), D("0"))


def test_el_total_es_la_suma_con_signo_de_los_campos():
    """Lo que se vio en la exportación real de SUNAT, como propiedad de todo lo que escribimos."""
    libro, comprobantes = cargar_golden("ventas_202512.json")
    for c in comprobantes + [del_xml(), de_la_propuesta()]:
        f = linea(c, libro)
        assert _suma(f) == D(f[25]), (c.serie, c.numero, f[13:26])
