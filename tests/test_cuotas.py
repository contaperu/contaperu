"""Las cuotas de una factura al crédito y su `monto_pendiente` (12.2, enmienda 0030).

La RS 000193-2020/SUNAT obliga a declarar, al crédito, el monto neto pendiente de pago y **la fecha y el monto de
cada cuota**. Hasta la 12.2 el lector veía las fechas, las colapsaba en `fecha_vencimiento` y **tiraba todos los
importes**: una factura a tres cuotas y una a una sola, con el mismo vencimiento final, eran indistinguibles para
quien leyera el documento del motor.

Lo que estos casos fijan es eso y su contrario: que el importe llegue, y que **nada de lo que ya salía se mueva**
—`fecha_vencimiento` sigue siendo la mayor de las cuotas y ningún asiento cambia—. Y la parte que más importa para
lo que viene: **el monto pendiente no es el total** y **nulo no es cero**, porque el motor no lo deduce.

El fixture `20131312955-01-F001-123.xml` ya traía su cuota con importe desde que existe: el dato estaba delante y
se descartaba al leer.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest

from contaperu import api, asiento, modelo
from contaperu.lectores import xml_ubl
from contaperu.modelo import CERO, Comprobante, Libro
from util import XML

AL_CREDITO = "20131312955-01-F001-123.xml"   # una cuota de 1280.00 que vence el 2026-02-10
AL_CONTADO = "20131312955-01-F001-124.xml"
VENTAS = Libro(ruc="20131312955", razon_social="EMISOR DE PRUEBA S.A.C.", periodo="202601", tipo="venta")

LIBRO = {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608", "tipo": "venta"}
FACTURA = {"tipo_cp": "01", "serie": "F001", "numero": "123", "fecha_emision": "2026-08-11",
           "contraparte_tipo_doc": "6", "contraparte_doc": "20602222226", "contraparte_nombre": "CLIENTE SAC",
           "moneda": "PEN", "base_gravada": "100", "igv": "18", "total": "118", "concepto": "SERVICIO"}

# El bloque de una cuota en el XML, tal como lo escribe un emisor peruano.
_CUOTA = re.compile(r" *<cac:PaymentTerms>\s*<cbc:ID>FormaPago</cbc:ID>\s*"
                    r"<cbc:PaymentMeansID>Cuota001</cbc:PaymentMeansID>.*?</cac:PaymentTerms>", re.DOTALL)


def leido(nombre: str) -> Comprobante:
    return xml_ubl.parsear((XML / nombre).read_bytes(), VENTAS, nombre)


def con_cuotas(*cuotas: tuple[str, str, str]) -> Comprobante:
    """La factura al crédito del fixture, con sus cuotas cambiadas por las que se le pidan (`numero`, fecha, importe).

    Sin ninguna, deja la factura al crédito **sin cuotas**, que es un caso legítimo: la norma admite un pago único
    aplazado."""
    texto = (XML / AL_CREDITO).read_text(encoding="utf-8")
    bloques = "\n".join(
        "  <cac:PaymentTerms>\n"
        "    <cbc:ID>FormaPago</cbc:ID>\n"
        f"    <cbc:PaymentMeansID>Cuota{numero}</cbc:PaymentMeansID>\n"
        f'    <cbc:Amount currencyID="PEN">{importe}</cbc:Amount>\n'
        f"    <cbc:PaymentDueDate>{vence}</cbc:PaymentDueDate>\n"
        "  </cac:PaymentTerms>"
        for numero, vence, importe in cuotas)
    nuevo = _CUOTA.sub(lambda _: bloques, texto)
    assert nuevo != texto, "el fixture dejó de traer su cuota: este ayudante hay que rehacerlo"
    return xml_ubl.parsear(nuevo.encode("utf-8"), VENTAS, AL_CREDITO)


def documento(**extra) -> dict:
    return {"open_accounting": "3.2", "libro": dict(LIBRO), "comprobantes": [dict(FACTURA, **extra)]}


# --- lo que el XML declara y ahora llega -------------------------------------------------------------------------

def test_una_factura_al_credito_trae_su_cuota_con_fecha_e_importe():
    """El caso que estaba delante y se descartaba: el fixture declara su cuota con `cbc:Amount` desde siempre."""
    c = leido(AL_CREDITO)
    assert c.cuotas == [{"numero": "001", "fecha": "2026-02-10", "importe": "1280.00"}]
    assert c.monto_pendiente == Decimal("1280.00")
    assert c.condicion_pago == "credito"


def test_tres_cuotas_dejan_de_ser_indistinguibles_de_una_sola():
    """La regresión que esto cierra. Las dos facturas vencen el mismo día y hasta la 12.2 daban el mismo documento."""
    tres = con_cuotas(("001", "2026-02-10", "400.00"), ("002", "2026-03-10", "400.00"),
                      ("003", "2026-04-10", "480.00"))
    una = con_cuotas(("001", "2026-04-10", "1280.00"))
    assert tres.fecha_vencimiento == una.fecha_vencimiento == date(2026, 4, 10)
    assert [q["importe"] for q in tres.cuotas] == ["400.00", "400.00", "480.00"]
    assert len(tres.cuotas) == 3 and len(una.cuotas) == 1
    assert tres.cuotas != una.cuotas


def test_el_vencimiento_sigue_siendo_la_mayor_de_las_cuotas_y_en_su_orden():
    """Nada de lo que ya salía se mueve: el colapso se conserva, y las cuotas van **en el orden del documento**,
    que no tiene que ser el de sus fechas."""
    c = con_cuotas(("002", "2026-05-10", "500.00"), ("001", "2026-03-10", "780.00"))
    assert [q["numero"] for q in c.cuotas] == ["002", "001"]
    assert c.fecha_vencimiento == date(2026, 5, 10)


def test_al_contado_no_hay_cuotas_y_el_monto_pendiente_es_NULO_y_no_cero():
    """La distinción que decide si esto sirve: ausente es «el documento no lo dice», no «no queda nada por cobrar»."""
    c = leido(AL_CONTADO)
    assert c.cuotas == [] and c.condicion_pago == "contado"
    assert c.monto_pendiente is None
    assert c.monto_pendiente is not CERO and c.monto_pendiente != CERO


def test_al_credito_sin_cuotas_el_pago_unico_aplazado_sigue_siendo_credito():
    """La norma admite un pago único en fecha posterior: hay monto pendiente y no hay cuotas."""
    c = con_cuotas()
    assert c.cuotas == [] and c.condicion_pago == "credito"
    assert c.monto_pendiente == Decimal("1280.00")


def test_el_motor_no_deduce_el_monto_pendiente_del_total():
    """Lo declara el emisor. Si el término de crédito no trae su importe, el campo queda nulo **aunque el total
    esté**: una resta no es un hecho del papel, y la norma lo define sin las retenciones ni las detracciones —así
    que restar la detracción del total daría un número que nadie declaró—."""
    texto = (XML / AL_CREDITO).read_text(encoding="utf-8")
    sin_importe = re.sub(r"(<cbc:PaymentMeansID>Credito</cbc:PaymentMeansID>)\s*<cbc:Amount[^>]*>[^<]*</cbc:Amount>",
                         r"\1", texto)
    assert sin_importe != texto
    c = xml_ubl.parsear(sin_importe.encode("utf-8"), VENTAS, AL_CREDITO)
    assert c.monto_pendiente is None
    assert c.total == Decimal("1280.00") and c.detraccion["monto"] == "153.60"


def test_el_monto_pendiente_no_es_el_total():
    """Y por eso vale: con detracción, lo que la contraparte transfiere no es el total del comprobante. El fixture
    no lo demuestra —declara los dos iguales— así que se prueba con el dato que la norma describe."""
    c = Comprobante(**dict(FACTURA, monto_pendiente="100.00"))
    assert c.total == Decimal("118.00") and c.monto_pendiente == Decimal("100.00")


# --- lo que el modelo no admite ----------------------------------------------------------------------------------

@pytest.mark.parametrize("cuota, falta", [
    ({"numero": "001", "importe": "10.00"}, "fecha"),
    ({"numero": "001", "fecha": "2026-03-10"}, "importe"),
    ({"numero": "001"}, "fecha"),
])
def test_una_cuota_sin_fecha_o_sin_importe_no_es_una_cuota(cuota: dict, falta: str):
    """Los dos que el esquema declara obligatorios. Una cuota que no dice cuándo vence ni por cuánto no sirve para
    nada de lo que las cuotas existen."""
    with pytest.raises(ValueError, match=falta):
        Comprobante(**dict(FACTURA, cuotas=[cuota]))


def test_una_cuota_con_fecha_vacia_tampoco():
    """Vacío pasa la comprobación de presencia y no dice cuándo vence: por eso hay dos comprobaciones y no una."""
    with pytest.raises(ValueError, match="cuándo vence"):
        Comprobante(**dict(FACTURA, cuotas=[{"fecha": "", "importe": "10.00"}]))


def test_una_clave_que_no_es_de_una_cuota_se_rechaza_y_se_nombra():
    """La misma regla que `Comprobante.de_dict`: el lector no puede ser más laxo que el esquema publicado, que ya
    rechaza por su `additionalProperties: false`. Y se nombran TODAS, no la primera."""
    with pytest.raises(ValueError, match="moneda, tasa"):
        Comprobante(**dict(FACTURA, cuotas=[{"fecha": "2026-03-10", "importe": "10.00",
                                             "tasa": "1", "moneda": "PEN"}]))


def test_una_cuota_que_no_es_un_objeto_se_rechaza():
    with pytest.raises(ValueError, match="objeto"):
        Comprobante(**dict(FACTURA, cuotas=["2026-03-10"]))


def test_el_numero_de_la_cuota_son_sus_digitos_y_el_prefijo_es_la_etiqueta():
    """`Cuota001` del XML es `001`: el prefijo nombra el campo, no el dato. Y si el documento no lo da, vacío."""
    c = Comprobante(**dict(FACTURA, cuotas=[{"numero": "Cuota007", "fecha": "2026-03-10", "importe": "10.00"},
                                            {"fecha": "2026-04-10", "importe": "10.00"}]))
    assert [q["numero"] for q in c.cuotas] == ["007", ""]


# --- la ida y la vuelta, que es donde se pierden los campos nuevos -----------------------------------------------

def test_las_cuotas_sobreviven_la_ida_y_la_vuelta():
    """El hueco por el que se han colado dos regresiones: el campo y el archivo se prueban por separado y nadie
    comprueba el viaje completo."""
    c = leido(AL_CREDITO)
    vuelta = Comprobante.de_dict(c.a_dict())
    assert vuelta.cuotas == c.cuotas and vuelta.monto_pendiente == c.monto_pendiente
    assert vuelta.a_dict() == c.a_dict()


def test_el_estandar_valida_un_documento_con_cuotas():
    jsonschema = pytest.importorskip("jsonschema")  # noqa: F841 — el extra `schema`
    doc = documento(condicion_pago="credito", monto_pendiente="100.00",
                    cuotas=[{"numero": "001", "fecha": "2026-09-10", "importe": "100.00"}])
    assert api.verificar_documento(doc)["conforme"] is True


@pytest.mark.parametrize("cuota", [
    {"numero": "001", "importe": "100.00"},                      # sin fecha
    {"numero": "001", "fecha": "2026-09-10"},                    # sin importe
    {"numero": "uno", "fecha": "2026-09-10", "importe": "100.00"},   # el número no son dígitos
    {"numero": "001", "fecha": "10/09/2026", "importe": "100.00"},   # la fecha no es AAAA-MM-DD
    {"fecha": "2026-09-10", "importe": "100.00", "tasa": "1"},       # una clave que no es suya
])
def test_el_estandar_rechaza_una_cuota_mal_formada(cuota: dict):
    pytest.importorskip("jsonschema")
    assert api.verificar_documento(documento(cuotas=[cuota]))["conforme"] is False


def test_el_documento_del_estandar_escribe_las_cuotas_y_las_OMITE_cuando_no_hay():
    """`como_comprobante` deja fuera lo vacío, y la lista vacía entra en eso: un comprobante al contado no declara
    cuotas, y escribir `"cuotas": []` diría «no tiene ninguna» donde lo cierto es «el documento no habla de eso»."""
    con = asiento.cabecera_de(leido(AL_CREDITO)).como_comprobante()
    sin = asiento.cabecera_de(leido(AL_CONTADO)).como_comprobante()
    assert con["cuotas"] == [{"numero": "001", "fecha": "2026-02-10", "importe": "1280.00"}]
    assert con["monto_pendiente"] == "1280.00"
    assert "cuotas" not in sin and "monto_pendiente" not in sin


# --- y lo que NO cambia ------------------------------------------------------------------------------------------

def test_las_cuotas_no_cambian_ningun_asiento():
    """Un vencimiento no mueve una cuenta. La huella es del asiento, y dos facturas que solo se diferencian en sus
    cuotas tienen que dar la misma: si esto se rompiera, los cuatro snapshots de celdas se moverían."""
    from test_diagnosticar import FACTURA as COMPRA, doc
    from util import por_la_fachada

    generar = por_la_fachada(api.generar_asiento)
    sin = generar(doc(dict(COMPRA)), driver="csv")
    con = generar(doc(dict(COMPRA, condicion_pago="credito", monto_pendiente="4000.00",
                           cuotas=[{"numero": "001", "fecha": "2026-09-10", "importe": "2000.00"},
                                   {"numero": "002", "fecha": "2026-10-10", "importe": "2956.00"}])),
                  driver="csv")
    assert sin["asiento"] == con["asiento"]
    assert asiento.huella(sin["asiento"]) == asiento.huella(con["asiento"])


def test_los_dos_campos_son_hechos_del_documento():
    """Y no del sistema ni de la revisión: los declara el papel, así que una puerta de entrada los acepta de quien
    dicta una factura. `tests/test_campos.py` hace cumplir que los tres tramos cubran el comprobante entero."""
    assert {"cuotas", "monto_pendiente"} <= set(modelo.CAMPOS_DEL_DOCUMENTO)
    assert not {"cuotas", "monto_pendiente"} & set(modelo.CAMPOS_DEL_SISTEMA)


def test_datos_originales_sigue_trayendo_las_fechas_y_queda_redundante():
    """Se mantiene durante toda la 12.x para no romper a quien lo esté leyendo, con menos información que el campo
    —solo las fechas—. Su retiro se decide en la 13.0."""
    c = leido(AL_CREDITO)
    assert c.datos_originales["cuotas"] == ["2026-02-10"]
    assert [q["fecha"] for q in c.cuotas] == c.datos_originales["cuotas"]
