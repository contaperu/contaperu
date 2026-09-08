"""La detracción contrastada con la tabla del contribuyente.

El caso que motiva todo esto: una IA lee «retención 3 %» en una factura y devuelve una
detracción con código «000». Si ese código llega al asiento, se provisiona una detracción que
no existe.
"""
from __future__ import annotations

from contaperu import asiento as asi
from contaperu import detracciones
from contaperu.modelo import Comprobante

CONTAB = asi.config_de(None)
CODIGOS = detracciones.codigos_de(CONTAB)


def comprobante(det) -> Comprobante:
    return Comprobante(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-08-11",
                       contraparte_doc="20601111111", base_gravada="100", igv="18",
                       total="118", detraccion=det)


def test_el_codigo_de_la_tabla_se_conserva():
    assert detracciones.normalizar_una({"codigo": "027", "porcentaje": 4}, CODIGOS) == \
        {"codigo": "027", "porcentaje": 4}


def test_el_codigo_corto_se_completa_a_tres_digitos():
    assert detracciones.normalizar_una({"codigo": "27"}, CODIGOS) == {"codigo": "027"}


def test_el_codigo_que_no_esta_en_la_tabla_queda_en_blanco():
    """«000» es lo que devuelve una IA que confundió la retención del IGV con una detracción."""
    for malo in ({"codigo": "000"}, {"codigo": ""}, {"codigo": "999"}, {"porcentaje": 3}, None, "027"):
        assert detracciones.normalizar_una(malo, CODIGOS) is None


def test_normalizar_devuelve_solo_lo_que_cambio():
    buena = comprobante({"codigo": "027", "porcentaje": 4})
    mala = comprobante({"codigo": "000", "porcentaje": 3})
    sin = comprobante(None)

    cambiados = detracciones.normalizar([buena, mala, sin], CONTAB)

    assert cambiados == [mala]
    assert mala.detraccion is None            # se limpió
    assert buena.detraccion == {"codigo": "027", "porcentaje": 4}   # se respetó
    assert sin.detraccion is None


def test_sin_detracciones_no_hace_nada():
    assert detracciones.normalizar([comprobante(None)], CONTAB) == []


def test_la_tabla_sale_de_la_configuracion_del_contribuyente():
    """Quien no reconozca un código no lo tiene: la tabla es suya, no del motor."""
    propia = asi.config_de({"detraccion_codigos": {"037": "03701"}})
    assert detracciones.normalizar_una({"codigo": "037"}, detracciones.codigos_de(propia))
    vacia = detracciones.codigos_de({})
    assert detracciones.normalizar_una({"codigo": "027"}, vacia) is None


def test_una_detraccion_limpiada_no_llega_al_asiento():
    """La consecuencia real de la regla: sin código válido no hay líneas de detracción."""
    c = comprobante({"codigo": "000", "porcentaje": 3})
    detracciones.normalizar([c], CONTAB)
    filas = asi.asiento(c, dict(CONTAB, cuentas=dict(CONTAB["cuentas"], gasto="659999")),
                        (__import__("datetime").date(2026, 8, 1), __import__("datetime").date(2026, 8, 31)),
                        "080001")
    assert len(filas) == 3 and all(f["R"] != "DT" for f in filas)
