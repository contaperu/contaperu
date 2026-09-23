"""El IGV se lee del comprobante; nunca se supone (John, 10-sep-2026).

La tasa puede ser 18, 10.5 o 0 y sale de la base y el IGV de cada comprobante. Estos tests vigilan
las dos cosas que eso obliga: que el recálculo no invente ninguna tasa, y que no toque el total.
"""
from decimal import Decimal as D

import pytest

from contaperu import igv
from contaperu.drivers.concar import tasa_igv_entera as tasa_igv
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
    assert igv.tasa_calculada(r["igv"], r["base_gravada"]) == D("10.5")


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


# ── La nota de crédito de descuento global y la celda «Total» (11-sep-2026) ──────────────────────────

def nc_descuento(**k):
    return cp(tipo_cp="07", base_gravada="100", igv="18", dscto_base="100", dscto_igv="18", total="118", **k)


def test_los_descuentos_no_mueven_la_base_al_recalcular():
    """Antes `_cargos` restaba el descuento y la base de una NC de descuento salía casi al doble."""
    assert igv.aplicar_igv(nc_descuento(), "18")["base_gravada"] == D("100")


def test_una_nota_entera_como_descuento_sigue_entera_al_cambiar_el_igv():
    r = igv.aplicar_igv(nc_descuento(), "10")
    assert (r["base_gravada"], r["igv"], r["dscto_base"], r["dscto_igv"]) == (D("108"), D("10"), D("108"), D("10"))


def test_sin_igv_el_descuento_se_va_con_la_base():
    r = igv.aplicar_igv(nc_descuento(), "0")
    assert (r["inafecto"], r["dscto_base"], r["dscto_igv"]) == (D("118"), 0, 0)


def test_un_descuento_parcial_que_ya_no_cabe_se_dice():
    with pytest.raises(igv.IgvImposible, match="descuento"):
        igv.aplicar_igv(cp(tipo_cp="07", base_gravada="100", igv="18", dscto_base="50", dscto_igv="9",
                           total="118"), "5")


def test_el_total_lo_absorbe_la_base_y_el_igv_se_queda():
    r = igv.aplicar_total(cp(base_gravada="100", igv="18", total="118"), "236")
    assert (r["total"], r["base_gravada"]) == (D("236"), D("218")) and "igv" not in r


def test_el_total_se_recalcula_aunque_la_ia_lo_hubiera_leido_mal():
    """Sumar la diferencia arrastraba el error: 100 + (118 − 1180) daba una base negativa."""
    assert igv.aplicar_total(cp(base_gravada="100", igv="18", total="1180"), "118")["base_gravada"] == D("100")


def test_sin_base_lo_absorbe_el_importe_sin_igv():
    r = igv.aplicar_total(cp(base_gravada="0", igv="0", inafecto="50", total="50"), "80")
    assert r == {"total": D("80"), "inafecto": D("80"), "dscto_base": 0, "dscto_igv": 0}


def test_un_total_que_no_alcanza_o_no_es_numero_se_dice():
    with pytest.raises(igv.TotalImposible, match="menor"):
        igv.aplicar_total(cp(base_gravada="100", igv="18", total="118"), "10")
    with pytest.raises(igv.TotalImposible, match="número"):
        igv.aplicar_total(cp(), "abc")
    with pytest.raises(igv.TotalImposible, match="negativo"):
        igv.aplicar_total(cp(), "-5")


def test_una_nota_entera_como_descuento_sigue_entera_al_cambiar_el_total():
    r = igv.aplicar_total(nc_descuento(), "236")
    assert (r["base_gravada"], r["dscto_base"], r["dscto_igv"]) == (D("218"), D("218"), D("18"))


def test_la_compra_se_divide_por_el_destino_de_la_adquisicion():
    """Base e IGV van enteros a una de las tres parejas del registro de compras —gravadas (DG), gravadas y no
    gravadas (DGNG), no gravadas (DNG)— y las otras dos quedan en cero. El registro de compras del SIRE y la
    plantilla de CONTASIS llevan esas seis columnas: la división vive aquí una vez."""
    pareja, cero = (D("100"), D("18")), (D("0"), D("0"))
    assert igv.por_destino(cp(base_gravada="100", igv="18")) == (pareja, cero, cero)
    assert igv.por_destino(cp(base_gravada="100", igv="18", destino_igv="dgng")) == (cero, pareja, cero)
    assert igv.por_destino(cp(base_gravada="100", igv="18", destino_igv="DNG")) == (cero, cero, pareja)


def test_la_tasa_legal_es_la_que_cuadra_y_no_el_cociente():
    """Lo que declara un registro en «% IGV»: la tasa legal que cuadra con base e IGV, con la tolerancia de
    `validar`. El registro de CONTASIS validado escribe 18 aunque el IGV, redondeado ítem a ítem, dé 17.98."""
    assert igv.tasa_legal("18", "100") == D("18.00")
    assert igv.tasa_legal("9.75", "54.24") == D("18.00")        # el cociente da 17.98
    assert igv.tasa_legal("10.50", "100") == D("10.50")
    assert igv.tasa_legal("10.53", "100") == D("10.50")         # la reducida, no el cociente
    assert igv.tasa_legal("10", "100") == D("10.00")
    assert igv.tasa_legal("8", "100") == D("8.00")
    assert igv.tasa_legal("25", "100") == D("25.00")            # ninguna legal cuadra: el cociente
    assert igv.tasa_legal("0", "100") is None and igv.tasa_legal("18", "0") is None


# ── Las cuatro respuestas a «¿cuál es la tasa del IGV?» ─────────────────────────────────────────────────────────
#
# Son cuatro y las cuatro están bien: cada formato pide una cosa distinta. Lo que no había era un sitio donde se
# vieran juntas. Cada una tenía su motivo escrito en su archivo, así que para saber que difieren había que leer
# tres drivers y el núcleo — y el snapshot de CONTASIS usa casos donde coinciden, de modo que no distinguiría si
# alguien cambiara `tasa_legal` por `tasa_calculada`.

def _las_cuatro(igv_escrito: str, base: str) -> dict[str, object]:
    """Lo que escribe cada uno para el mismo comprobante, por la misma función que usa de verdad."""
    from contaperu.drivers.concar import tasa_igv_entera
    from contaperu.drivers.starsoft.proyeccion import con_dos_decimales
    from contaperu.modelo import texto_tasa

    leida = igv.tasa_calculada(igv_escrito, D(base))
    de_la_linea = "" if leida is None else texto_tasa(leida)   # la guarda es la de `asiento/motor.py`
    return {"nucleo": de_la_linea,
            "concar": tasa_igv_entera(D(igv_escrito), D(base)),
            "contasis": igv.tasa_legal(igv_escrito, base),
            "starsoft": con_dos_decimales(de_la_linea)}


def test_las_cuatro_tasas_del_igv_difieren_a_proposito():
    """El caso que las separa: 9.75 de IGV sobre 54.24 de base. El cociente da 17.98 y la tasa legal que cuadra
    dentro de la tolerancia es 18.

    - **El núcleo** escribe el cociente, sin suponer: `17.98`. Es lo que va en `linea.tasa_igv`.
    - **CONCAR** lo redondea a entero desde los importes del comprobante, porque su columna AO solo admite entero.
      No redondea la tasa de la línea: redondear dos veces puede dar otro entero.
    - **CONTASIS** declara la tasa LEGAL, porque su plantilla pide «el porcentaje del IGV» con el ejemplo `18.00`
      y el registro que validó escribe 18 aunque los importes, redondeados ítem a ítem, den 17.98.
    - **STARSOFT** se queda con la de la línea y solo le pone dos decimales: es el único que no vuelve a leer el
      comprobante.

    Si alguna deja de ser la que es, esto lo dice — y dice cuál."""
    assert _las_cuatro("9.75", "54.24") == {"nucleo": "17.98", "concar": 18,
                                            "contasis": D("18.00"), "starsoft": "17.98"}


def test_con_una_tasa_exacta_las_cuatro_coinciden_y_por_eso_no_bastan_los_snapshots():
    """18 % sobre 100: las cuatro dicen 18, cada una en su formato. Es el caso normal, y es justo el que hace que
    un snapshot no distinga una función de otra — por eso hace falta el test de arriba."""
    cuatro = _las_cuatro("18", "100")
    assert cuatro == {"nucleo": "18", "concar": 18, "contasis": D("18.00"), "starsoft": "18.00"}


def test_sin_igv_ninguna_se_inventa_una_tasa():
    """Una boleta sin crédito fiscal, una compra exonerada: no hay tasa que leer y ninguna supone el 18 %. CONCAR
    tuvo un 18 de respaldo hasta el 10-sep-2026 y se quitó por eso."""
    assert igv.tasa_calculada("0", D("100")) is None
    assert igv.tasa_legal("0", "100") is None
    assert _las_cuatro("0", "100")["concar"] == ""
