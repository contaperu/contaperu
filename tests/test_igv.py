"""El IGV se lee del comprobante; nunca se supone (John, 10-sep-2026).

La tasa puede ser 18, 10.5 o 0 y sale de la base y el IGV de cada comprobante. Estos tests vigilan
las dos cosas que eso obliga: que el recálculo no invente ninguna tasa, y que no toque el total.
"""
from decimal import Decimal as D

import pytest

from contaperu import igv
from contaperu.asiento import tasa_igv
from contaperu.modelo import Comprobante


def cp(**k):
    base = dict(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-08-11", moneda="PEN",
                contraparte_tipo_doc="6", contraparte_doc="20607777773", contraparte_nombre="PROVEEDOR SAC",
                base_gravada="0", igv="0", total="118")
    base.update(k)
    return Comprobante(**base)


def test_escribir_el_igv_de_un_inafecto_lo_vuelve_afecto_sin_tocar_el_total():
    r = igv.aplicar_igv(cp(inafecto="118", total="118"), "18")
    assert (r["base_gravada"], r["igv"], r["inafecto"], r["exonerado"]) == (D("100"), D("18"), 0, 0)


def test_la_tasa_no_esta_escrita_en_ninguna_parte():
    """Un comprobante al 10.5 % se recalcula igual que uno al 18: nadie le impone el 18."""
    r = igv.aplicar_igv(cp(inafecto="110.50", total="110.50"), "10.50")
    assert r["base_gravada"] == D("100.00")
    assert igv.tasa(r["igv"], r["base_gravada"]) == D("10.5")


def test_quitar_el_igv_lo_manda_a_inafecto():
    r = igv.aplicar_igv(cp(base_gravada="100", igv="18", total="118"), "0")
    assert (r["base_gravada"], r["igv"], r["inafecto"]) == (0, 0, D("118"))


def test_cambiar_el_igv_de_un_mixto_deja_el_exonerado_donde_estaba():
    r = igv.aplicar_igv(cp(base_gravada="100", igv="18", exonerado="50", total="168"), "10")
    assert (r["base_gravada"], r["igv"], r["exonerado"]) == (D("108"), D("10"), D("50"))


def test_los_otros_cargos_se_quedan_fuera_de_la_base():
    """ICBPER y otros cargos forman el total pero no son base: la fórmula es la de `validar.py`."""
    r = igv.aplicar_igv(cp(inafecto="120", icbper="0.50", otros="1.50", total="122"), "18")
    assert r["base_gravada"] == D("102")


def test_un_igv_imposible_no_se_reparte():
    for malo in ("150", "-1", "abc"):
        with pytest.raises(igv.IgvImposible):
            igv.aplicar_igv(cp(inafecto="100", total="100"), malo)


def test_la_columna_ao_es_la_tasa_del_comprobante_redondeada_a_entero():
    """CONCAR solo admite enteros (John): se redondea la tasa del comprobante, sin respaldo ni atajos."""
    assert tasa_igv(D("18"), D("100")) == 18
    assert tasa_igv(D("10.5"), D("100")) == 11
    assert tasa_igv(D("0"), D("100")) == ""
    assert tasa_igv(D("18"), D("0")) == ""       # sin base no hay tasa que leer, y no se inventa
