"""Parser de comprobantes electrónicos de SUNAT (UBL 2.1) → `Comprobante`.

Lee desde bytes (los XML llegan en UTF-8 con o sin BOM y a veces en
ISO-8859-1) con `defusedxml`, que bloquea entidades externas y bombas XML.
Soporta las raíces `Invoice` (facturas, boletas y el RECIBO POR HONORARIOS
electrónico, que SUNAT emite con esta misma raíz y declarando `01`: se
distingue por la categoría de su retención, ver `_honorarios`), `CreditNote`
y `DebitNote`;
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
from ..errores import ErrorContaperu
from ..modelo.coerciones import fecha, monto, solo_digitos
from ..modelo.libro import Libro
from .comprobante import Comprobante

NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "sac": "urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1",
}
RAIZ_CDR = "ApplicationResponse"
RAICES = {"Invoice": None, "CreditNote": "07", "DebitNote": "08"}
# La categoría con la que SUNAT marca la retención de 4ta en un recibo por honorarios. No está en el
# Catálogo 05 —no es un tributo del IGV— y ninguna factura la emite: es la única seña del documento.
# En `_honorarios` están los archivos reales con que se midió.
CATEGORIA_RETENCION_4TA = "RET 4TA"


class XmlInvalido(ErrorContaperu, ValueError):
    """El archivo no es un comprobante electrónico que podamos leer."""


class XmlNoSoportado(XmlInvalido):
    """Es un comprobante, pero en una versión que no manejamos (UBL 2.0)."""


class EsCdr(XmlInvalido):
    """Es la constancia de recepción (CDR) de SUNAT, no un comprobante."""


def _raiz(datos: bytes) -> tuple[Element, str]:
    if not isinstance(datos, (bytes, bytearray)):
        raise TypeError("parsear() espera bytes")
    if datos.startswith(b"\xef\xbb\xbf"):
        datos = datos[3:]
    try:
        raiz = DET.fromstring(datos)
    except Exception as e:  # ParseError, DefusedXmlException…
        raise XmlInvalido(f"XML mal formado: {e}") from e
    local = raiz.tag.rsplit("}", 1)[-1]
    return raiz, local


def es_cdr(datos: bytes) -> bool:
    try:
        return _raiz(datos)[1] == RAIZ_CDR
    except XmlInvalido:
        return False


def _t(elemento: Element | None, ruta: str) -> str:
    if elemento is None:
        return ""
    hijo = elemento.find(ruta, NS)
    return (hijo.text or "").strip() if hijo is not None else ""


def _attr(elemento: Element | None, ruta: str, nombre: str) -> str:
    if elemento is None:
        return ""
    hijo = elemento.find(ruta, NS)
    return (hijo.get(nombre) or "").strip() if hijo is not None else ""


def _partir_id(texto: str) -> tuple[str, str]:
    """'F001-00000123' → ('F001', '00000123'); sin guion → serie vacía."""
    texto = texto.strip()
    if "-" in texto:
        serie, numero = texto.split("-", 1)
        return serie.strip().upper(), numero.strip()
    return "", texto


def _parte(elemento: Element | None) -> dict:
    """Emisor o adquirente: tipo y número de documento y razón social."""
    if elemento is None:
        return {"tipo_doc": "", "doc": "", "nombre": ""}
    entidad = elemento.find("cac:Party", NS)
    doc = _t(entidad, "cac:PartyTaxScheme/cbc:CompanyID")
    esquema = _attr(entidad, "cac:PartyTaxScheme/cbc:CompanyID", "schemeID")
    if not doc:
        doc = _t(entidad, "cac:PartyIdentification/cbc:ID")
        esquema = _attr(entidad, "cac:PartyIdentification/cbc:ID", "schemeID")
    if not doc:  # estilo antiguo que algunos emisores mantienen
        doc = _t(elemento, "cbc:CustomerAssignedAccountID")
        esquema = _t(elemento, "cbc:AdditionalAccountID")
    nombre = (
        _t(entidad, "cac:PartyLegalEntity/cbc:RegistrationName")
        or _t(entidad, "cac:PartyTaxScheme/cbc:RegistrationName")
        or _t(entidad, "cac:PartyName/cbc:Name")
        or _t(elemento, "cac:Party/cac:PartyLegalEntity/cbc:RegistrationName")
    )
    tipo_doc = cat.SCHEME_A_TIPO_DOC.get(esquema.upper(), esquema.upper() or "")
    if not tipo_doc:
        tipo_doc = "6" if len(solo_digitos(doc)) == 11 else ("1" if len(solo_digitos(doc)) == 8 else "0")
    return {"tipo_doc": tipo_doc, "doc": doc.strip(), "nombre": " ".join(nombre.split())}


def _honorarios(raiz: Element) -> dict | None:
    """El bruto, la retención y su tasa si este `Invoice` es un RECIBO POR HONORARIOS electrónico;
    `None` si no lo es, y entonces el lector sigue su camino de siempre.

    **El archivo miente sobre su propio tipo**, y es la razón de ser de esta función: un recibo trae
    `<cbc:InvoiceTypeCode>01</cbc:InvoiceTypeCode>`, igual que una factura, porque SUNAT lo emite
    desde el portal con la plantilla de `Invoice`. Lo que sí dice la verdad es la categoría de la
    retención de su línea, `RET 4TA`.

    Medido sobre dos recibos reales (24-oct-2026), uno de ellos la E001-186 que está anonimizada en
    `tests/fixtures/xml/`:

    - en la RAÍZ, `cac:TaxTotal/cac:TaxSubtotal` trae el BRUTO en `cbc:TaxableAmount` (2 450,00) y
      la retención en `cbc:TaxAmount` (196,00), con `cac:TaxCategory/cbc:ID` = `A` y un
      `cac:TaxScheme` **vacío** —de ahí que el tributo se acumule con la clave vacía y **no** con un
      código del Catálogo 05, que es por lo que un recibo no se puede reconocer por su tributo—;
    - en la LÍNEA está la seña, y también la tasa (`cbc:Percent`, 8,00). Ojo con su
      `cac:TaxTotal/cbc:TaxAmount`: vale 2 450,00, o sea **el bruto y no un tributo**;
    - `cac:LegalMonetaryTotal/cbc:PayableAmount` es el NETO ya retenido (2 254,00).

    Dos hechos que acotan la regla. La seña está **también en el recibo cuya retención es 0,00**,
    así que marca el documento y no el importe. Y la serie `E###` **no** sirve de seña, porque las
    facturas emitidas desde el portal de SUNAT también la llevan —hay una real en `privado/`, y un
    caso de `tests/test_xml_ubl.py` lo deja clavado—.

    La retención no se deriva de la tasa: es un importe que el documento afirma, y calcularlo sería
    justo el error que `RETENCION_TASA` existe para cazar.
    """
    marcado = any(" ".join((nodo.text or "").split()).upper() == CATEGORIA_RETENCION_4TA
                  for nodo in raiz.iterfind(".//cac:TaxCategory/cbc:ID", NS))
    if not marcado:
        return None
    subtotal = raiz.find("cac:TaxTotal/cac:TaxSubtotal", NS)
    linea = raiz.find("cac:InvoiceLine/cac:TaxTotal/cac:TaxSubtotal", NS)
    return {
        "bruto": monto(_t(subtotal, "cbc:TaxableAmount")),
        "retencion": monto(_t(subtotal, "cbc:TaxAmount")),
        "porcentaje": _t(linea, "cbc:Percent"),
        "neto_declarado": str(monto(_t(raiz, "cac:LegalMonetaryTotal/cbc:PayableAmount"))),
    }


def parsear(datos: bytes, libro: Libro, archivo_nombre: str = "") -> Comprobante:
    """Convierte un XML de SUNAT en un `Comprobante` visto desde el libro:
    en ventas la contraparte es el adquirente; en compras, el emisor."""
    raiz, local = _raiz(datos)
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
    # Un recibo por honorarios se declara `01` en su propio XML, así que el tipo que dice el archivo
    # se corrige por la seña de su retención. Solo con raíz `Invoice`: una nota de crédito de un
    # recibo ya trae su `07` por `RAICES` y no se le toca.
    honorarios = _honorarios(raiz) if local == "Invoice" else None
    if honorarios:
        tipo_cp = cat.TIPO_HONORARIOS

    emisor = _parte(raiz.find("cac:AccountingSupplierParty", NS))
    adquirente = _parte(raiz.find("cac:AccountingCustomerParty", NS))
    contraparte = adquirente if libro.es_venta else emisor

    # --- Tributos por código del Catálogo 05 ------------------------------
    acumulado: dict[str, list[Decimal]] = {}
    for subtotal in raiz.findall("cac:TaxTotal/cac:TaxSubtotal", NS):
        codigo = _t(subtotal, "cac:TaxCategory/cac:TaxScheme/cbc:ID")
        base = monto(_t(subtotal, "cbc:TaxableAmount"))
        tributo = monto(_t(subtotal, "cbc:TaxAmount"))
        suma = acumulado.setdefault(codigo, [Decimal("0.00"), Decimal("0.00")])
        suma[0] += base
        suma[1] += tributo

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
    if honorarios:
        # El `PayableAmount` de un recibo es el NETO ya retenido; la forma del motor es el BRUTO con la
        # retención aparte, porque la retención no resta del total: la reparte el asiento. Así cuadra
        # «base + IGV + no gravado» y no salta un `TOTAL_NO_CUADRA` falso, que es lo que pasaba hasta
        # la 14.1. La forma la fijaban ya cuatro sitios, y ninguno se movió:
        # `estandar/conformidad/diagnosticar.json`, `tests/test_retenciones.py`,
        # `tests/test_snapshot_concar.py` y `tests/test_asiento_concar.py`.
        total = honorarios["bruto"]

    base_gravada, igv = base_de(cat.TRIBUTO_IGV), tributo_de(cat.TRIBUTO_IGV)
    if not acumulado and totales is not None:
        # XML sin subtotales por tributo: lo mejor que se puede hacer
        igv = monto(_t(raiz, "cac:TaxTotal/cbc:TaxAmount"))
        base_gravada = monto(_t(totales, "cbc:LineExtensionAmount"))
    inafecto = base_de(cat.TRIBUTO_INAFECTO)
    if honorarios:
        # En un recibo no hay nada gravado y el bruto entero es inafecto. Los ceros se ponen a mano
        # porque hoy salían cero **por casualidad**: el tributo del recibo cae con la clave vacía, así
        # que `base_de(TRIBUTO_IGV)` no lo encuentra. Una casualidad no es una regla.
        base_gravada = igv = Decimal("0.00")
        inafecto = honorarios["bruto"]

    # --- Descuento global (campos 16 y 18 del SIRE) --------------------------
    # La base y el IGV que da el XML (TaxableAmount, TaxAmount) ya son NETOS del descuento, y así se guardan.
    # Un AllowanceCharge de documento con ChargeIndicator=false no se suma ni se resta: se anota y decide UNA
    # cosa, en qué columnas del SIRE va una NOTA DE CRÉDITO DE VENTAS cuyo descuento es todo su importe. Es el
    # caso contrastado con la propuesta de SUNAT (la FC01-45, 26-ago-2026): la registró entera en los campos 16
    # y 18. En lo demás —facturas, notas de débito, compras (el RCE no tiene esas columnas), notas parciales—
    # no hay fuente que diga otra cosa y el descuento queda en cero. El motivo de la nota NO lo decide: la
    # E001-233 real es «04 Descuento global» sin AllowanceCharge y SUNAT la tiene en base e IGV (11-sep-2026).
    # Tampoco se filtra por AllowanceChargeReasonCode mientras no haya un XML real que lo respalde; queda
    # anotado en `datos_originales["descuentos_globales"]` para poder hacerlo.
    descuentos = [{"codigo": _t(cargo, "cbc:AllowanceChargeReasonCode"), "importe": str(monto(_t(cargo, "cbc:Amount")))}
                  for cargo in raiz.findall("cac:AllowanceCharge", NS)
                  if (_t(cargo, "cbc:ChargeIndicator") or "").strip().lower() == "false"]
    suma_descuentos = sum((Decimal(descuento["importe"]) for descuento in descuentos), Decimal("0.00"))
    dscto_base = dscto_igv = Decimal("0.00")
    if (tipo_cp in ("07", "87") and libro.es_venta and base_gravada > 0
            and abs(suma_descuentos - base_gravada) <= Decimal("0.05")):
        # Entera: los importes exactos de la nota —ni el del AllowanceCharge ni un IGV derivado por tasa—,
        # así el campo 15 del SIRE queda en cero y nunca cambia de signo.
        dscto_base, dscto_igv = base_gravada, igv

    # --- Formas de pago, detracción, retención ------------------------------
    cuotas: list[dict] = []
    monto_pendiente: str | None = None
    forma_pago = ""
    detraccion: dict | None = None
    # El bloque crudo del término de pago, que vale para las DOS retenciones según el tipo de
    # comprobante (ver más abajo). Se llama así y no `retencion` porque en este archivo ese nombre
    # ya es el del campo y el del rol.
    bloque_retencion: dict | None = None
    for termino in raiz.findall("cac:PaymentTerms", NS):
        ident = _t(termino, "cbc:ID")
        medio = _t(termino, "cbc:PaymentMeansID")
        if ident == "FormaPago":
            if medio.lower().startswith("cuota"):
                # Hasta la 12.2 de aquí solo salía la fecha, y el importe —que la RS 000193-2020/SUNAT obliga a
                # consignar— se tiraba. Sin él no hay pago esperado contra el que conciliar (enmienda 0030).
                vence = fecha(_t(termino, "cbc:PaymentDueDate") or None)
                if vence:
                    cuotas.append({"numero": medio, "fecha": vence,
                                   "importe": str(monto(_t(termino, "cbc:Amount")))})
            elif medio:
                forma_pago = medio
                # El `cbc:Amount` del término de crédito es el MONTO NETO PENDIENTE DE PAGO, que no es el total:
                # la norma lo define sin las retenciones ni las detracciones. Solo se guarda si el documento lo
                # trae: ausente no es cero.
                if medio.strip().lower().startswith(("credito", "crédito")):
                    declarado = _t(termino, "cbc:Amount")
                    monto_pendiente = str(monto(declarado)) if declarado else None
        elif ident == "Detraccion":
            detraccion = {
                "codigo": medio,
                "porcentaje": _t(termino, "cbc:PaymentPercent"),
                "monto": str(monto(_t(termino, "cbc:Amount"))),
            }
        elif ident == "Retencion":
            bloque_retencion = {"porcentaje": _t(termino, "cbc:PaymentPercent"),
                                "monto": str(monto(_t(termino, "cbc:Amount")))}
    if detraccion is not None:
        cuenta = ""
        for medio_pago in raiz.findall("cac:PaymentMeans", NS):
            if _t(medio_pago, "cbc:ID") == "Detraccion":
                cuenta = _t(medio_pago, "cac:PayeeFinancialAccount/cbc:ID")
        if cuenta:
            detraccion["cuenta"] = cuenta
    # Solo lo que dice el XML. **El colapso de las cuotas ya no está aquí**: lo hace `Comprobante`, para que un
    # documento dictado por un ERP con sus cuotas traiga el mismo vencimiento que uno leído de un XML (12.5).
    vencimiento = fecha(_t(raiz, "cbc:DueDate") or None)
    # La condición de pago pasa al registro (`Comprobante.condicion_pago`); `datos_originales.forma_pago` sigue
    # guardando el texto tal como vino. Una factura con cuotas es a crédito aunque no lo diga en letras.
    forma_normalizada = forma_pago.strip().lower()
    condicion_pago = "credito" if cuotas or forma_normalizada.startswith(("credito", "crédito")) else ("contado" if forma_normalizada == "contado" else "")

    # --- Documento modificado (notas) ----------------------------------------
    ref_serie = ref_numero = ref_tipo = ""
    motivo: dict | None = None
    if local in ("CreditNote", "DebitNote"):
        ref = raiz.find("cac:BillingReference/cac:InvoiceDocumentReference", NS)
        if ref is not None:
            ref_serie, ref_numero = _partir_id(_t(ref, "cbc:ID"))
            ref_tipo = _t(ref, "cbc:DocumentTypeCode")[:2]
        discrepancia = raiz.find("cac:DiscrepancyResponse", NS)
        if discrepancia is not None:
            motivo = {
                "referencia": _t(discrepancia, "cbc:ReferenceID"),
                "codigo": _t(discrepancia, "cbc:ResponseCode"),
                "descripcion": _t(discrepancia, "cbc:Description"),
            }
            if not ref_numero and motivo["referencia"]:
                ref_serie, ref_numero = _partir_id(motivo["referencia"])

    # --- Concepto: la primera línea ------------------------------------------
    etiqueta_linea = {"Invoice": "cac:InvoiceLine", "CreditNote": "cac:CreditNoteLine", "DebitNote": "cac:DebitNoteLine"}[local]
    concepto = _t(raiz, f"{etiqueta_linea}/cac:Item/cbc:Description")[:100]

    datos_originales = {
        "ubl": version,
        "raiz": local,
        "emisor": emisor,
        "adquirente": adquirente,
        "forma_pago": forma_pago,
        # Queda redundante desde la 12.2 —`comprobante.cuotas` trae lo mismo con su importe— y se mantiene durante
        # toda la 12.x para no romper a quien lo esté leyendo. Su retiro se decide en la 13.0.
        "cuotas": [c["fecha"].isoformat() for c in cuotas],
        "tributos": {k: [str(v[0]), str(v[1])] for k, v in acumulado.items()},
        "gratuitas": str(base_de(cat.TRIBUTO_GRATUITO)),
        "anticipo": str(anticipo),
        "tax_inclusive": _t(totales, "cbc:TaxInclusiveAmount"),
        # Tal como viene del papel, sin interpretar. Su destino es `retencion_igv` o
        # `retencion_4ta` según el tipo de comprobante, y aquí queda el crudo para auditoría.
        "retencion": bloque_retencion,
        "motivo_nota": motivo,
        # Lo que se sobrescribe al leer un recibo no se pierde: el neto que declara el documento, su
        # tasa, y las dos cifras de las que salen `total`, `inafecto` y `retencion_4ta`.
        **({"honorarios": {clave: str(valor) for clave, valor in honorarios.items()}}
           if honorarios else {}),
        **({"descuentos_globales": descuentos} if descuentos else {}),
    }
    return Comprobante(
        tipo_cp=tipo_cp,
        serie=serie,
        numero=numero,
        fecha_emision=fecha(_t(raiz, "cbc:IssueDate") or None),
        fecha_vencimiento=vencimiento,
        condicion_pago=condicion_pago,
        cuotas=cuotas,
        monto_pendiente=monto_pendiente,
        contraparte_tipo_doc=contraparte["tipo_doc"] or "6",
        contraparte_doc=contraparte["doc"],
        contraparte_nombre=contraparte["nombre"],
        moneda=_t(raiz, "cbc:DocumentCurrencyCode") or "PEN",
        base_gravada=base_gravada,
        igv=igv,
        dscto_base=dscto_base,
        dscto_igv=dscto_igv,
        exonerado=base_de(cat.TRIBUTO_EXONERADO),
        inafecto=inafecto,
        exportacion=base_de(cat.TRIBUTO_EXPORTACION),
        isc=tributo_de(cat.TRIBUTO_ISC),
        base_ivap=base_de(cat.TRIBUTO_IVAP),
        ivap=tributo_de(cat.TRIBUTO_IVAP),
        icbper=tributo_de(cat.TRIBUTO_ICBPER),
        otros=tributo_de(cat.TRIBUTO_OTROS),
        total=total,
        # **Un término de pago, dos tributos, y lo decide el TIPO DE COMPROBANTE** (4.0).
        # `PaymentTerms Retencion` es la renta de 4ta en un recibo por honorarios y el Régimen
        # de Retenciones del IGV en una factura. Hasta la 3.3 el segundo caso **se leía y se
        # tiraba** —llegaba hasta aquí y se cambiaba por un cero—, así que el dato existía en el
        # XML, sobrevivía en `datos_originales` y no había campo donde ponerlo. Esa es la
        # ausencia que la enmienda 0005 vino a cerrar, y el caso real que la destrabó: una
        # aplicación volcando el 3 % del IGV en la columna de la 4ta porque no tenía otra.
        #
        # La de 4ta entra en el asiento; la del IGV **en ninguno** (no es un hecho del
        # comprobante sino del pago), y viaja para quien lleve la tesorería.
        # En los dos recibos reales medidos el único `PaymentTerms` es `FormaPago`: la 4ta llega por
        # `cac:TaxTotal` y no por el término de pago. La vía del término se queda detrás, para un recibo
        # que sí declare su `02` —si SUNAT lo arregla algún día— y la traiga ahí.
        retencion_4ta=(honorarios["retencion"] if honorarios else
                       monto(bloque_retencion.get("monto"))
                       if (bloque_retencion and tipo_cp == cat.TIPO_HONORARIOS) else monto(0)),
        retencion_igv=bloque_retencion if (bloque_retencion and tipo_cp != cat.TIPO_HONORARIOS) else None,
        # Por qué se emitió la nota. Lo lee este mismo lector desde la 1.x en `cac:DiscrepancyResponse/cbc:ResponseCode`
        # —es el mismo catálogo que cita el SIRE, el 09 o el 10 según el tipo— y hasta la 3.5.0 se quedaba solo en
        # `datos_originales["motivo_nota"]`, donde nadie lo miraba. Ahí sigue con su `referencia` y su `descripcion`,
        # que no tienen campo propio: quitarlo perdería datos sin avisar.
        tipo_nota=(motivo or {}).get("codigo", ""),
        ref_tipo_cp=ref_tipo,
        ref_serie=ref_serie,
        ref_numero=ref_numero,
        detraccion=detraccion,
        concepto=concepto,
        origen="xml",
        confianza=Decimal("1.00"),
        archivo_nombre=archivo_nombre,
        datos_originales=datos_originales,
    )
