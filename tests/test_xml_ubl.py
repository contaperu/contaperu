"""XML UBL 2.1 de SUNAT → Comprobante, visto desde ventas y desde compras."""
import io
import zipfile
from datetime import date
from decimal import Decimal

import pytest

from contaperu import validar
from contaperu.lectores import archivos, xml_ubl
from contaperu.modelo import Libro
from util import XML

EMISOR = "20131312955"     # RUC válido (módulo 11)
CLIENTE = "20604444447"    # RUC válido
VENTAS = Libro(ruc=EMISOR, razon_social="EMISOR DE PRUEBA S.A.C.", periodo="202601", tipo="venta")
COMPRAS = Libro(ruc=CLIENTE, razon_social="CLIENTE DE PRUEBA S.A.", periodo="202601", tipo="compra")


def leer(nombre: str) -> bytes:
    return (XML / nombre).read_bytes()


def test_factura_como_venta():
    c = xml_ubl.parsear(leer("20131312955-01-F001-123.xml"), "venta", "F001-123.xml")
    assert (c.tipo_cp, c.serie, c.numero) == ("01", "F001", "123")
    assert c.fecha_emision == date(2026, 1, 10)
    assert c.fecha_vencimiento == date(2026, 2, 10)          # la cuota manda sobre cbc:DueDate
    assert (c.contraparte_tipo_doc, c.contraparte_doc, c.contraparte_nombre) == ("6", CLIENTE, "CLIENTE DE PRUEBA S.A.")
    assert c.moneda == "PEN" and c.tipo_cambio is None
    assert (c.base_gravada, c.igv, c.exonerado, c.total) == (Decimal("1000.00"), Decimal("180.00"), Decimal("100.00"), Decimal("1280.00"))
    assert c.detraccion == {"codigo": "022", "porcentaje": "12", "monto": "153.60", "cuenta": "00-000-123456"}
    assert c.concepto.startswith("Servicio de consultor")
    assert c.datos_raw["emisor"]["doc"] == EMISOR and c.datos_raw["forma_pago"] == "Credito"
    assert c.condicion_pago == "credito"                     # la forma de pago pasa al registro
    assert c.origen == "xml" and c.confianza == Decimal("1.00") and c.archivo_nombre == "F001-123.xml"
    validar.revisar([c], VENTAS)
    assert c.observaciones == [] and c.estado == "ok"


def test_factura_como_compra_y_de_otro_ruc():
    c = xml_ubl.parsear(leer("20131312955-01-F001-123.xml"), "compra")
    assert c.contraparte_doc == EMISOR and c.contraparte_nombre == "EMISOR DE PRUEBA S.A.C."
    validar.revisar([c], COMPRAS)
    assert c.estado == "ok"
    otro = Libro(ruc="10601111115", razon_social="OTRO", periodo="202601", tipo="compra")
    validar.revisar([c], otro)
    assert [o.codigo for o in c.observaciones] == ["XML_PARA_OTRO_RUC"] and c.tiene_errores
    validar.revisar([c], Libro(ruc="10601111115", razon_social="OTRO", periodo="202601", tipo="venta"))
    assert [o.codigo for o in c.observaciones] == ["XML_DE_OTRO_RUC"]


def test_boleta_con_dni_y_latin1():
    c = xml_ubl.parsear(leer("20131312955-03-B001-55.xml"), "venta")
    assert (c.tipo_cp, c.serie, c.numero) == ("03", "B001", "55")
    assert (c.contraparte_tipo_doc, c.contraparte_doc) == ("1", "12345678")
    assert c.contraparte_nombre == "APELLIDO DE PRUEBA, ÁNGEL"   # con tilde: es lo que prueba el latin-1
    assert c.fecha_vencimiento is None and c.datos_raw["forma_pago"] == "Contado"
    assert c.condicion_pago == "contado"
    assert (c.base_gravada, c.igv, c.total) == (Decimal("100.00"), Decimal("18.00"), Decimal("118.00"))
    validar.revisar([c], VENTAS)
    assert c.estado == "ok"


def test_nota_de_credito():
    c = xml_ubl.parsear(leer("20131312955-07-FC01-7.xml"), "venta")
    assert (c.tipo_cp, c.serie, c.numero) == ("07", "FC01", "7")
    assert (c.ref_tipo_cp, c.ref_serie, c.ref_numero, c.ref_fecha) == ("01", "F001", "123", None)
    assert c.datos_raw["motivo_nota"]["codigo"] == "01"
    assert (c.base_gravada, c.igv, c.total) == (Decimal("200.00"), Decimal("36.00"), Decimal("236.00"))
    validar.revisar([c], VENTAS)
    assert [o.codigo for o in c.observaciones] == ["NOTA_SIN_FECHA_REF"]   # el XML no trae la fecha del doc modificado
    c.ref_fecha = date(2026, 1, 10)
    validar.revisar([c], VENTAS)
    assert c.estado == "ok"


def test_factura_usd_con_icbper():
    c = xml_ubl.parsear(leer("20131312955-01-F001-124.xml"), "venta")
    assert c.moneda == "USD" and c.icbper == Decimal("0.50") and c.total == Decimal("590.50")
    validar.revisar([c], VENTAS)
    assert [o.codigo for o in c.observaciones] == ["TC_FALTA"]
    c.tipo_cambio = Decimal("3.75")
    validar.revisar([c], VENTAS)
    assert c.estado == "ok"


def test_ubl20_y_cdr_se_rechazan_con_claridad():
    with pytest.raises(xml_ubl.XmlNoSoportado, match="UBL 2.0"):
        xml_ubl.parsear(leer("ubl20-antiguo.xml"), "venta")
    with pytest.raises(xml_ubl.EsCdr):
        xml_ubl.parsear(leer("R-20131312955-01-F001-123.xml"), "venta")
    assert xml_ubl.es_cdr(leer("R-20131312955-01-F001-123.xml"))
    assert not xml_ubl.es_cdr(leer("20131312955-03-B001-55.xml"))
    with pytest.raises(xml_ubl.XmlInvalido):
        xml_ubl.parsear(b"<html>no</html>", "venta")
    with pytest.raises(xml_ubl.XmlInvalido):
        xml_ubl.parsear(b"\xef\xbb\xbf<Invoice xmlns='urn:oasis:names:specification:ubl:schema:xsd:Invoice-2'><x/></Invoice", "venta")


def test_zip_con_cdr_anidado_y_tope():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in ("20131312955-01-F001-123.xml", "20131312955-03-B001-55.xml", "R-20131312955-01-F001-123.xml"):
            z.writestr(f"enero/{n}", leer(n))
        z.writestr("__MACOSX/._basura.xml", b"x")
        z.writestr("otro.zip", b"PK\x03\x04")
        z.writestr("foto.jpg", b"\xff\xd8\xff")
        z.writestr("factura2.1.xsl", b"<?xml version='1.0'?><xsl:stylesheet/>")   # hoja de estilos del facturador
        z.writestr("ebxml21.css", b"body{}")
    lote = archivos.expandir("lote.zip", buf.getvalue())
    assert [e.nombre for e in lote.entradas] == [
        "lote.zip/20131312955-01-F001-123.xml", "lote.zip/20131312955-03-B001-55.xml",
        "lote.zip/R-20131312955-01-F001-123.xml", "lote.zip/foto.jpg", "lote.zip/factura2.1.xsl", "lote.zip/ebxml21.css",
    ]
    assert lote.errores == [{"archivo": "lote.zip/otro.zip", "motivo": "ZIP dentro de un ZIP: descomprímelo antes de subirlo"}]
    res = archivos.convertir_xml(lote, VENTAS)
    assert [c.numero for c in res.comprobantes] == ["123", "55"]
    assert res.ignorados == ["lote.zip/R-20131312955-01-F001-123.xml", "lote.zip/factura2.1.xsl", "lote.zip/ebxml21.css"]
    assert [e.nombre for e in res.pendientes_ia] == ["lote.zip/foto.jpg"]
    # tope
    lote2 = archivos.Lote()
    for i in range(3):
        archivos.expandir(f"a{i}.xml", b"<x/>", tope=2, lote=lote2)
    assert len(lote2.entradas) == 2 and lote2.errores[0]["motivo"].startswith("Supera el tope")
    assert archivos.expandir("roto.zip", b"PK\x03\x04basura").errores[0]["motivo"].startswith("El ZIP")


def test_ordenar():
    a = xml_ubl.parsear(leer("20131312955-01-F001-124.xml"), "venta")   # 20/01
    b = xml_ubl.parsear(leer("20131312955-01-F001-123.xml"), "venta")   # 10/01
    c = xml_ubl.parsear(leer("20131312955-03-B001-55.xml"), "venta")    # 12/01
    assert [x.numero for x in archivos.ordenar([a, b, c])] == ["123", "55", "124"]


# ── Descuento global: campos 16 y 18 del SIRE (26-ago-2026) ──────────────────
# Salió contrastando agosto con la propuesta de SUNAT: dos notas de crédito del
# mismo mes caían en columnas distintas según lo que trae su XML.
NC_CON_DESCUENTO = """<?xml version="1.0" encoding="UTF-8"?>
<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>FC01-45</cbc:ID>
  <cbc:IssueDate>2026-08-20</cbc:IssueDate>
  <cbc:DocumentCurrencyCode>PEN</cbc:DocumentCurrencyCode>
  <cac:DiscrepancyResponse><cbc:ReferenceID>F001-257</cbc:ReferenceID><cbc:ResponseCode>09</cbc:ResponseCode></cac:DiscrepancyResponse>
  <cac:BillingReference><cac:InvoiceDocumentReference><cbc:ID>F001-257</cbc:ID>
    <cbc:DocumentTypeCode>01</cbc:DocumentTypeCode></cac:InvoiceDocumentReference></cac:BillingReference>
  <cac:AccountingSupplierParty><cac:Party><cac:PartyIdentification><cbc:ID schemeID="6">20601111111</cbc:ID></cac:PartyIdentification>
    <cac:PartyLegalEntity><cbc:RegistrationName>MI EMPRESA</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party></cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty><cac:Party><cac:PartyIdentification><cbc:ID schemeID="6">20622222222</cbc:ID></cac:PartyIdentification>
    <cac:PartyLegalEntity><cbc:RegistrationName>CLIENTE SAC</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party></cac:AccountingCustomerParty>
  <cac:AllowanceCharge><cbc:ChargeIndicator>false</cbc:ChargeIndicator>
    <cbc:Amount currencyID="PEN">9985.36</cbc:Amount></cac:AllowanceCharge>
  <cac:TaxTotal><cbc:TaxAmount currencyID="PEN">1797.36</cbc:TaxAmount>
    <cac:TaxSubtotal><cbc:TaxableAmount currencyID="PEN">9985.36</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="PEN">1797.36</cbc:TaxAmount>
      <cac:TaxCategory><cac:TaxScheme><cbc:ID>1000</cbc:ID></cac:TaxScheme></cac:TaxCategory></cac:TaxSubtotal></cac:TaxTotal>
  <cac:LegalMonetaryTotal><cbc:PayableAmount currencyID="PEN">11782.72</cbc:PayableAmount></cac:LegalMonetaryTotal>
</CreditNote>"""


def test_descuento_global_va_a_sus_propias_columnas():
    """La base y el IGV son los netos del XML, y la NC va ENTERA como descuento (campos 16 y 18)."""
    c = xml_ubl.parsear(NC_CON_DESCUENTO.encode("utf-8"), "venta")
    assert (c.base_gravada, c.igv) == (Decimal("9985.36"), Decimal("1797.36"))
    assert (c.dscto_base, c.dscto_igv) == (c.base_gravada, c.igv)      # los importes exactos de la nota


def test_sin_descuento_los_dos_campos_quedan_en_cero():
    """La NC normal (importe como línea gravada) sigue yendo a base e IGV."""
    c = xml_ubl.parsear(NC_CON_DESCUENTO.replace("false", "true").encode("utf-8"), "venta")
    assert c.dscto_base == Decimal("0.00") and c.dscto_igv == Decimal("0.00")
    assert c.base_gravada == Decimal("9985.36")


def test_sin_forma_de_pago_la_condicion_queda_vacia():
    """Vacío no es contado: es que el documento no lo dice. La nota de crédito de prueba no la trae."""
    c = xml_ubl.parsear(leer("20131312955-07-FC01-7.xml"), "venta", "FC01-7.xml")
    assert c.datos_raw["forma_pago"] == "" and c.condicion_pago == ""
