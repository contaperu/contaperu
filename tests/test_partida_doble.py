"""La partida doble como regla, no como suma informativa."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from contaperu import asiento as asi
from contaperu import api
from contaperu.pipeline import preparacion as prep
from contaperu import partida_doble
from contaperu.drivers import concar as driver_concar
from contaperu.modelo import Comprobante, Libro
from util import comprobante, con_imputaciones

CONTAB = con_imputaciones(prep.config_aplicada(None, "concar"))
MES = (date(2026, 8, 1), date(2026, 8, 31))


def ln(sentido, importe, cuenta="659999"):
    return {"cuenta": cuenta, "debe_haber": sentido, "importe": importe}


def test_cuadra_lo_que_cuadra():
    r = partida_doble.cuadra([ln("D", "100.00"), ln("D", "18.00"), ln("H", "118.00")])
    assert r.cuadra and r.debe == Decimal("118.00") == r.haber
    assert r.diferencia == Decimal("0.00") and r.lineas == 3


def test_no_cuadra_por_un_centimo():
    """Sin tolerancia: un céntimo de diferencia es un asiento mal armado, no un redondeo."""
    r = partida_doble.cuadra([ln("D", "100.00"), ln("H", "99.99")])
    assert not r.cuadra and r.diferencia == Decimal("0.01")


def test_una_linea_sin_debe_ni_haber_descuadra():
    r = partida_doble.cuadra([ln("D", "10.00"), ln("H", "10.00"), ln("", "10.00")])
    assert not r.cuadra and r.sin_sentido == 1


def test_exigir_levanta_descuadre_con_el_detalle():
    with pytest.raises(partida_doble.Descuadre) as e:
        partida_doble.exigir([ln("D", "10.00"), ln("H", "7.00")])
    assert e.value.resultado.diferencia == Decimal("3.00")
    assert "3.00" in str(e.value)


def test_acepta_lineas_de_diario_y_diccionarios():
    linea = asi.LineaDiario(cuenta="401111", debe_haber="D", importe="18.00")
    assert partida_doble.cuadra([linea, ln("H", "18.00")]).cuadra


def test_el_asiento_real_siempre_cuadra():
    """Compras con IGV, recibo por honorarios con retención, nota de crédito y factura con
    detracción: los cuatro asientos que arma el motor cierran solos."""
    def cp(**k):
        base = dict(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-08-11",
                    contraparte_doc="20601111111", contraparte_nombre="PROVEEDOR DE PRUEBA SAC",
                    base_gravada="100", igv="18", total="118",
                    cuenta_contable="659999", centro_costo="CC-01")
        base.update(k)
        return comprobante(**base)

    casos = {
        "factura": cp(),
        "honorarios": cp(tipo_cp="02", base_gravada="1000", igv="0", total="1000", retencion="80"),
        "nota de credito": cp(tipo_cp="07", ref_tipo_cp="01", ref_serie="F001", ref_numero="1"),
        "con detraccion": cp(base_gravada="4200", igv="756", total="4956",
                             detraccion={"codigo": "027", "porcentaje": "4"}),
        "en dolares": cp(moneda="USD", tipo_cambio="3.5"),
    }
    for nombre, c in casos.items():
        filas = driver_concar.filas_de_comprobante(c, CONTAB, MES, "080001")
        r = partida_doble.cuadra(driver_concar.a_lineas(filas, CONTAB))
        assert r.cuadra, f"{nombre} no cuadra: {r.a_dict()}"


def test_el_driver_se_niega_a_escribir_un_asiento_descuadrado(monkeypatch):
    """La red de seguridad de verdad: si el asiento no cierra, no se escribe el archivo."""
    libro = Libro(ruc="20601111111", razon_social="EMPRESA DE PRUEBA SAC",
                  periodo="202608", tipo="compra")
    c = comprobante(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-08-11",
                    contraparte_doc="20601111111", base_gravada="100", igv="18", total="118",
                    cuenta_contable="659999", centro_costo="OBRA01")   # con centro: este test es del descuadre

    # Desde la 0.7 el driver cuadra las líneas neutrales —de ellas salen las filas—, así que es
    # ahí donde se rompe el espejo de la última línea.
    original = asi.motor.lineas_del_comprobante

    def asiento_roto(*a, **k):
        lineas = original(*a, **k)
        lineas[-1].importe = "999.00"
        return lineas

    monkeypatch.setattr(driver_concar.xlsx, "lineas_del_comprobante", asiento_roto)
    with pytest.raises(partida_doble.Descuadre):
        driver_concar.construir(libro, [c], CONTAB, {"11": 1})
