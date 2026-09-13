"""La detracción contrastada con la tabla del contribuyente, y su monto calculado una sola vez.

El caso que motiva la tabla: una IA lee «retención 3 %» en una factura y devuelve una detracción con
código «000». Si ese código llega al asiento, se provisiona una detracción que no existe.

El caso que motiva el monto (10-sep-2026): la pantalla enseñaba una cifra —calculada en el navegador o
leída del PDF— y a CONCAR iba otra. Ahora las dos salen de `detracciones.monto_detraccion()`.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from contaperu import asiento as asi
from contaperu.drivers import concar as driver_concar
from contaperu import detracciones, validar
from contaperu.modelo import Comprobante, Libro

CONTAB = asi.config_de(None)
CODIGOS = detracciones.codigos_de(CONTAB)
# Una tabla explícita para todo lo que depende de las tasas: no se apoya en lo que traigan los defaults.
TABLA = dict(CONTAB, detraccion_codigos={"027": "02701", "037": "03701"}, detraccion_tasas={"027": 4, "037": 12})


def comprobante(det, **k) -> Comprobante:
    base = dict(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-08-11",
                contraparte_doc="20601111111", base_gravada="100", igv="18", total="118", detraccion=det)
    base.update(k)
    return Comprobante(**base)


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
    """Cambian la que se limpia y la que recibe el monto del motor; la tasa de la buena no se toca."""
    buena = comprobante({"codigo": "027", "porcentaje": 4})
    mala = comprobante({"codigo": "000", "porcentaje": 3})
    sin = comprobante(None)

    assert detracciones.normalizar([buena, mala, sin], TABLA) == [buena, mala]
    assert mala.detraccion is None            # se limpió
    # 118 × 4 % = 4.72 → 5 soles enteros; y la tasa de la tabla, anotada para compararla.
    assert buena.detraccion == {"codigo": "027", "porcentaje": 4, "monto": "5", "tasa_tabla": "4"}
    assert sin.detraccion is None
    # Idempotente: repetirla no cambia nada, así la revalidación no reescribe filas de más.
    assert detracciones.normalizar([buena, mala, sin], TABLA) == []


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
    filas = driver_concar.filas_de_comprobante(c, dict(CONTAB, cuentas=dict(CONTAB["cuentas"], gasto="659999")),
                        (date(2026, 8, 1), date(2026, 8, 31)), "080001")
    assert len(filas) == 3 and all(f["R"] != "DR" for f in filas)


# ── El monto: una sola cifra, la que va a CONCAR ─────────────────────────────

def test_el_monto_va_en_soles_enteros():
    """Del Excel real validado en CONCAR: 4 956 × 4 % = 198.24 → 198. Y el caso que destapó el problema:
    330.40 al 12 % son 40, no los 33.65 que enseñaba la pantalla."""
    assert detracciones.monto_detraccion(comprobante({"codigo": "027", "porcentaje": 4}, total="4956"), TABLA) == \
        (Decimal("198"), Decimal("198"))
    assert detracciones.monto_detraccion(comprobante({"codigo": "037", "porcentaje": 12}, total="330.40"), TABLA)[0] == 40


def test_en_dolares_se_deposita_en_soles():
    c = comprobante({"codigo": "037", "porcentaje": 12}, total="1000", moneda="USD", tipo_cambio="3.5")
    assert detracciones.monto_detraccion(c, TABLA) == (Decimal("420"), Decimal("120.00"))
    sin_tc = comprobante({"codigo": "037", "porcentaje": 12}, total="1000", moneda="USD")
    assert detracciones.monto_detraccion(sin_tc, TABLA) == (0, 0)


def test_sin_tasa_en_el_comprobante_usa_la_de_la_tabla():
    c = comprobante({"codigo": "037"}, total="330.40")
    assert detracciones.tasa_detraccion(c, TABLA) == 12 and detracciones.monto_detraccion(c, TABLA)[0] == 40


def test_el_asiento_usa_el_mismo_monto():
    """Una sola implementación: lo que ve la persona es lo que sale en las líneas de la detracción."""
    c = comprobante({"codigo": "037", "porcentaje": 12}, total="330.40", base_gravada="280", igv="50.40")
    contab = dict(TABLA, cuentas=dict(TABLA["cuentas"], gasto="659999"))
    filas = driver_concar.filas_de_comprobante(c, contab, (date(2026, 8, 1), date(2026, 8, 31)), "080001")
    detraccion = [f for f in filas if f["R"] == "DR"]
    assert detraccion and all(f["O"] == 40 for f in detraccion)


# ── El aviso de tasa ─────────────────────────────────────────────────────────

def _codigos(c: Comprobante) -> set[str]:
    validar.validar(c, Libro(ruc="20601111112", razon_social="EMPRESA", periodo="202608", tipo="compra"))
    return {o.codigo for o in c.observaciones}


def test_avisa_si_la_tasa_no_es_la_de_la_tabla():
    """El caso que teme John: la IA lee un 10 % y el código es del 12 %."""
    c = comprobante({"codigo": "037", "porcentaje": 10}, total="330.40")
    detracciones.normalizar([c], TABLA)
    assert "DETRACCION_TASA_DISTINTA" in _codigos(c)


def test_no_avisa_si_coincide_o_si_la_tasa_sale_de_la_tabla():
    igual = comprobante({"codigo": "037", "porcentaje": 12}, total="330.40")
    de_tabla = comprobante({"codigo": "037"}, total="330.40")
    detracciones.normalizar([igual, de_tabla], TABLA)
    assert "DETRACCION_TASA_DISTINTA" not in _codigos(igual)
    assert "DETRACCION_TASA_DISTINTA" not in _codigos(de_tabla)
