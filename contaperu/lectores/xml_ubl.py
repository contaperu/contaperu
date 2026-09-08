"""Parser de comprobantes electrónicos de SUNAT (UBL 2.1) → `Comprobante`.

Lee desde bytes (los XML llegan en UTF-8 con o sin BOM y a veces en
ISO-8859-1) con `defusedxml`, que bloquea entidades externas y bombas XML.
Soporta las raíces `Invoice` (facturas y boletas), `CreditNote` y `DebitNote`;
detecta el CDR (`ApplicationResponse`) para que quien llame lo ignore, y
rechaza UBL 2.0 con un mensaje claro (sus totales viven en
`sac:AdditionalMonetaryTotal`, otro mundo).

Fuente de las rutas: Guía de elaboración de documentos XML de SUNAT (factura,
NC y ND, UBL 2.1). Lo que el XML no trae (fecha del documento modificado en
las notas, tipo de cambio) queda vacío para que lo complete el usuario.
"""
from __future__ import annotations

from decimal import Decimal
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as DET

from .. import catalogos as cat
from ..modelo import Comprobante, fecha, monto, solo_digitos

NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
}
RAIZ_CDR = "ApplicationResponse"
RAICES = {"Invoice": None, "CreditNote": "07", "DebitNote": "08"}


class XmlInvalido(ValueError):
    """El archivo no es un comprobante electrónico que podamos leer."""


class XmlNoSoportado(XmlInvalido):
    """Es un comprobante, pero en una versión que no manejamos (UBL 2.0)."""


class EsCdr(XmlInvalido):
    """Es la constancia de recepción (CDR) de SUNAT, no un comprobante."""


def _raiz(data: bytes) -> tuple[Element, str]:
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("parsear() espera bytes")
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        raiz = DET.fromstring(data)
    except Exception as e:  # ParseError, DefusedXmlException…
        raise XmlInvalido(f"XML mal formado: {e}") from e
    local = raiz.tag.rsplit("}", 1)[-1]
    return raiz, local


def es_cdr(data: bytes) -> bool:
    try:
        return _raiz(data)[1] == RAIZ_CDR
    except XmlInvalido:
        return False


def _t(el: Element | None, ruta: str) -> str:
    if el is None:
        return ""
    hijo = el.find(ruta, NS)
    return (hijo.text or "").strip() if hijo is not None else ""


def _attr(el: Element | None, ruta: str, nombre: str) -> str:
    if el is None:
        return ""
    hijo = el.find(ruta, NS)
    return (hijo.get(nombre) or "").strip() if hijo is not None else ""


def _partir_id(texto: str) -> tuple[str, str]:
    """'F001-00000123' → ('F001', '00000123'); sin guion → serie vacía."""
    texto = texto.strip()
    if "-" in texto:
        serie, numero = texto.split("-", 1)
        return serie.strip().upper(), numero.strip()
    return "", texto


def _parte(el: Element | None) -> dict:
    """Emisor o adquirente: tipo y número de documento y razón social."""
    if el is None:
        return {"tipo_doc": "", "doc": "", "nombre": ""}
    party = el.find("cac:Party", NS)
    doc = _t(party, "cac:PartyTaxScheme/cbc:CompanyID")
    scheme = _attr(party, "cac:PartyTaxScheme/cbc:CompanyID", "schemeID")
    if not doc:
        doc = _t(party, "cac:PartyIdentification/cbc:ID")
        scheme = _attr(party, "cac:PartyIdentification/cbc:ID", "schemeID")
    if not doc:  # estilo antiguo que algunos emisores mantienen
        doc = _t(el, "cbc:CustomerAssignedAccountID")
        scheme = _t(el, "cbc:AdditionalAccountID")
    nombre = (
        _t(party, "cac:PartyLegalEntity/cbc:RegistrationName")
        or _t(party, "cac:PartyTaxScheme/cbc:RegistrationName")
        or _t(party, "cac:PartyName/cbc:Name")
        or _t(el, "cac:Party/cac:PartyLegalEntity/cbc:RegistrationName")
    )
    tipo_doc = cat.SCHEME_A_TIPO_DOC.get(scheme.upper(), scheme.upper() or "")
    if not tipo_doc:
        tipo_doc = "6" if len(solo_digitos(doc)) == 11 else ("1" if len(solo_digitos(doc)) == 8 else "0")
    return {"tipo_doc": tipo_doc, "doc": doc.strip(), "nombre": " ".join(nombre.split())}


def parsear(data: bytes, tipo_libro: str, archivo_nombre: str = "") -> Comprobante:
    """Convierte un XML de SUNAT en un `Comprobante` visto desde el libro:
    en ventas la contraparte es el adquirente; en compras, el emisor."""
    raiz, local = _raiz(data)
    if local == RAIZ_CDR:
        raise EsCdr("Es el CDR (constancia de recepción), no un comprobante")
    if local not in RAICES:
        raise XmlInvalido(f"Raíz XML no reconocida: <{local}>")
    version = _t(raiz, "cbc:UBLVersionID")
    if version.startswith("2.0"):
        raise XmlNoSoportado("Comprobante en UBL 2.0 (anterior a 2018): no se soporta, pide el PDF")

    serie, numero = _partir_id(_t(raiz, "cbc:ID"))
    if not numero:
        raise XmlInvalido("El XML no trae cbc:ID (serie-número)")
    tipo_cp = RAICES[local] or (_t(raiz, "cbc:InvoiceTypeCode") or "01")[:2]

    emisor = _parte(raiz.find("cac:AccountingSupplierParty", NS))
    adquirente = _parte(raiz.find("cac:AccountingCustomerParty", NS))
    contraparte = adquirente if tipo_libro == "venta" else emisor

    # --- Tributos por código del Catálogo 05 ------------------------------
    acumulado: dict[str, list[Decimal]] = {}
    for ts in raiz.findall("cac:TaxTotal/cac:TaxSubtotal", NS):
        codigo = _t(ts, "cac:TaxCategory/cac:TaxScheme/cbc:ID")
        base = monto(_t(ts, "cbc:TaxableAmount"))
        tributo = monto(_t(ts, "cbc:TaxAmount"))
        acc = acumulado.setdefault(codigo, [Decimal("0.00"), Decimal("0.00")])
        acc[0] += base
        acc[1] += tributo

    def base_de(codigo: str) -> Decimal:
        return acumulado.get(codigo, [Decimal("0.00"), Decimal("0.00")])[0]

    def tributo_de(codigo: str) -> Decimal:
        return acumulado.get(codigo, [Decimal("0.00"), Decimal("0.00")])[1]

    # --- Totales -----------------------------------------------------------
    totales = raiz.find("cac:LegalMonetaryTotal", NS)
    if totales is None:
        totales = raiz.find("cac:RequestedMonetaryTotal", NS)  # nota de débito
    total = monto(_t(totales, "cbc:PayableAmount"))
    anticipo = monto(_t(totales, "cbc:PrepaidAmount"))

    base_gravada, igv = base_de(cat.TRIBUTO_IGV), tributo_de(cat.TRIBUTO_IGV)
    if not acumulado and totales is not None:
        # XML sin subtotales por tributo: lo mejor que se puede hacer
        igv = monto(_t(raiz, "cac:TaxTotal/cbc:TaxAmount"))
        base_gravada = monto(_t(totales, "cbc:LineExtensionAmount"))

    # --- Descuento global (campos 16 y 18 del SIRE) --------------------------
    # `AllowanceCharge` con `ChargeIndicator=false` a nivel de documento es un
    # DESCUENTO global, y el registro tiene columnas propias para él ("Dscto BI" y
    # "Dscto IGV"): no es lo mismo que una base más pequeña. Se vio contrastando
    # agosto contra la propuesta de SUNAT (26-ago-2026): dos notas de crédito del
    # mismo mes caían en columnas distintas. Sin esto, los dos campos del modelo
    # existían y nadie los llenaba nunca.
    dscto_base = Decimal("0.00")
    for ac in raiz.findall("cac:AllowanceCharge", NS):
        if (_t(ac, "cbc:ChargeIndicator") or "").strip().lower() == "false":
            dscto_base += monto(_t(ac, "cbc:Amount"))
    # El IGV del descuento no viene desglosado: se deriva con la tasa del propio
    # comprobante (si no hay base gravada, no hay tasa que derivar y queda en cero).
    dscto_igv = Decimal("0.00")
    if dscto_base and base_gravada:
        dscto_igv = (dscto_base * igv / base_gravada).quantize(Decimal("0.01"))

    # --- Formas de pago, detracción, retención ------------------------------
    cuotas: list = []
    forma_pago = ""
    detraccion: dict | None = None
    retencion: dict | None = None
    for pt in raiz.findall("cac:PaymentTerms", NS):
        ident = _t(pt, "cbc:ID")
        medio = _t(pt, "cbc:PaymentMeansID")
        if ident == "FormaPago":
            if medio.lower().startswith("cuota"):
                f = fecha(_t(pt, "cbc:PaymentDueDate") or None)
                if f:
                    cuotas.append(f)
            elif medio:
                forma_pago = medio
        elif ident == "Detraccion":
            detraccion = {
                "codigo": medio,
                "porcentaje": _t(pt, "cbc:PaymentPercent"),
                "monto": str(monto(_t(pt, "cbc:Amount"))),
            }
        elif ident == "Retencion":
            retencion = {"porcentaje": _t(pt, "cbc:PaymentPercent"), "monto": str(monto(_t(pt, "cbc:Amount")))}
    if detraccion is not None:
        cuenta = ""
        for pm in raiz.findall("cac:PaymentMeans", NS):
            if _t(pm, "cbc:ID") == "Detraccion":
                cuenta = _t(pm, "cac:PayeeFinancialAccount/cbc:ID")
        if cuenta:
            detraccion["cuenta"] = cuenta
    vencimiento = max(cuotas) if cuotas else fecha(_t(raiz, "cbc:DueDate") or None)

    # --- Documento modificado (notas) ----------------------------------------
    ref_serie = ref_numero = ref_tipo = ""
    motivo: dict | None = None
    if local in ("CreditNote", "DebitNote"):
        ref = raiz.find("cac:BillingReference/cac:InvoiceDocumentReference", NS)
        if ref is not None:
            ref_serie, ref_numero = _partir_id(_t(ref, "cbc:ID"))
            ref_tipo = _t(ref, "cbc:DocumentTypeCode")[:2]
        disc = raiz.find("cac:DiscrepancyResponse", NS)
        if disc is not None:
            motivo = {
                "referencia": _t(disc, "cbc:ReferenceID"),
                "codigo": _t(disc, "cbc:ResponseCode"),
                "descripcion": _t(disc, "cbc:Description"),
            }
            if not ref_numero and motivo["referencia"]:
                ref_serie, ref_numero = _partir_id(motivo["referencia"])

    # --- Concepto: la primera línea ------------------------------------------
    linea_tag = {"Invoice": "cac:InvoiceLine", "CreditNote": "cac:CreditNoteLine", "DebitNote": "cac:DebitNoteLine"}[local]
    concepto = _t(raiz, f"{linea_tag}/cac:Item/cbc:Description")[:100]

    datos_raw = {
        "ubl": version,
        "raiz": local,
        "emisor": emisor,
        "adquirente": adquirente,
        "forma_pago": forma_pago,
        "cuotas": [c.isoformat() for c in cuotas],
        "tributos": {k: [str(v[0]), str(v[1])] for k, v in acumulado.items()},
        "gratuitas": str(base_de(cat.TRIBUTO_GRATUITO)),
        "anticipo": str(anticipo),
        "tax_inclusive": _t(totales, "cbc:TaxInclusiveAmount"),
        "retencion": retencion,
        "motivo_nota": motivo,
    }
    return Comprobante(
        tipo_cp=tipo_cp,
        serie=serie,
        numero=numero,
        fecha_emision=fecha(_t(raiz, "cbc:IssueDate") or None),
        fecha_vencimiento=vencimiento,
        contraparte_tipo_doc=contraparte["tipo_doc"] or "6",
        contraparte_doc=contraparte["doc"],
        contraparte_nombre=contraparte["nombre"],
        moneda=_t(raiz, "cbc:DocumentCurrencyCode") or "PEN",
        base_gravada=base_gravada,
        igv=igv,
        dscto_base=dscto_base,
        dscto_igv=dscto_igv,
        exonerado=base_de(cat.TRIBUTO_EXONERADO),
        inafecto=base_de(cat.TRIBUTO_INAFECTO),
        exportacion=base_de(cat.TRIBUTO_EXPORTACION),
        isc=tributo_de(cat.TRIBUTO_ISC),
        base_ivap=base_de(cat.TRIBUTO_IVAP),
        ivap=tributo_de(cat.TRIBUTO_IVAP),
        icbper=tributo_de(cat.TRIBUTO_ICBPER),
        otros=tributo_de(cat.TRIBUTO_OTROS),
        total=total,
        # `PaymentTerms Retencion` del XML es el RÉGIMEN DE RETENCIONES DEL IGV (3 %)
        # de las facturas y NO entra en ningún asiento (se ignora). La retención de 4ta
        # solo existe en el recibo por honorarios, y ahí sí parte el asiento.
        retencion=monto(retencion.get("monto")) if (retencion and tipo_cp == "02") else monto(0),
        ref_tipo_cp=ref_tipo,
        ref_serie=ref_serie,
        ref_numero=ref_numero,
        detraccion=detraccion,
        concepto=concepto,
        origen="xml",
        confianza=Decimal("1.00"),
        archivo_nombre=archivo_nombre,
        datos_raw=datos_raw,
    )
