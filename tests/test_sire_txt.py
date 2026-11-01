"""Importar la propuesta del SIRE (el TXT que SUNAT entrega al exportar un periodo).

Los dos formatos que entran comparten el orden de los campos informados: la
EXPORTACIÓN (con cabecera y las columnas que completa la Administración) y el de
REEMPLAZAR PROPUESTA (33 campos y palote final, el que genera este mismo portal).
El orden se verificó columna a columna contra una exportación real (26-ago-2026).
"""
import io
import zipfile
from decimal import Decimal

import pytest

from contaperu import catalogos
from contaperu.lectores import archivos, sire_txt
from contaperu.modelo import Libro

CABECERA = ("Ruc|Razon Social|Periodo|CAR SUNAT|Fecha de emisión|Fecha Vcto/Pago|Tipo CP/Doc.|Serie del CDP|"
            "Nro CP o Doc. Nro Inicial (Rango)|Nro Final (Rango)|Tipo Doc Identidad|Nro Doc Identidad|"
            "Apellidos Nombres/ Razón Social|Valor Facturado Exportación|BI Gravada|Dscto BI|IGV / IPM|"
            "Dscto IGV / IPM|Mto Exonerado|Mto Inafecto|ISC|BI Grav IVAP|IVAP|ICBPER|Otros Tributos|Total CP|"
            "Moneda|Tipo Cambio|Fecha Emisión Doc Modificado|Tipo CP Modificado|Serie CP Modificado|"
            "Nro CP Modificado|ID Proyecto Operadores Atribución|Tipo de Nota|Est. Comp|Valor FOB Embarcado|"
            "Valor OP Gratuitas|Tipo Operación|DAM / CP|CLU")
# Una factura y una nota de crédito expresada como DESCUENTO, como las trae SUNAT.
FACTURA = ("20601111111|MI EMPRESA SAC|202608|2060111111101E0010000001032|01/08/2026||01|E001|1032||6|20606666668|"
           "DISTRIBUIDORA ELECTRICA DE PRUEBA S.A.|0|205256.14|0|36946.11|0|0|0|0|0|0|0|0|242202.25|PEN|1.000|||||||1|0|0|1001||")
NOTA = ("20601111111|MI EMPRESA SAC|202608||20/08/2026||07|FC01|45||6|20622222222|CLIENTE SAC|"
        "0|0|-9985.36|0|-1797.36|0|0|0|0|0|0|0|-11782.72|PEN|1.000|31/07/2026|01|F001|257||09|1|0|0|1001||")
VENTAS = Libro(ruc="20601111111", razon_social="MI EMPRESA SAC", periodo="202608", tipo="venta")


def texto(*filas, con_cabecera=True):
    return ("\n".join(([CABECERA] if con_cabecera else []) + list(filas))).encode("utf-8")


def test_reconoce_la_propuesta_con_y_sin_cabecera():
    assert sire_txt.es_sire(texto(FACTURA))
    assert sire_txt.es_sire(texto(FACTURA, con_cabecera=False))
    assert not sire_txt.es_sire(b"cualquier cosa\nque no sea del SIRE")
    assert not sire_txt.es_sire("<?xml version='1.0'?><Invoice/>".encode("utf-8"))


def test_la_propuesta_en_un_zip_desmedido_no_se_abre():
    """La propuesta puede venir dentro de su ZIP, y se lee con los mismos topes que cualquier ZIP (`comprobantes/_zip.py`):
    un TXT que se infla miles de veces no se descomprime."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("propuesta.txt", texto(FACTURA) + b"\n" * 2_000_000)
    with pytest.raises(sire_txt.SireInvalido, match="comprime"):
        sire_txt.leer_lineas(buf.getvalue())
    assert not sire_txt.es_sire(buf.getvalue())


def test_lee_una_factura_con_su_glosa():
    c = sire_txt.parsear(texto(FACTURA), VENTAS)[0]
    assert (c.tipo_cp, c.serie, c.numero) == ("01", "E001", "1032")
    assert c.base_gravada == Decimal("205256.14") and c.igv == Decimal("36946.11")
    assert c.total == Decimal("242202.25") and c.moneda == "PEN"
    assert c.contraparte_doc == "20606666668"
    # La propuesta no trae el concepto y no se inventa: la celda se queda vacía y el
    # Excel de CONCAR pone el nombre de la contraparte por su cuenta.
    assert c.concepto == ""
    assert c.origen == "sire" and c.confianza == Decimal("1.00")
    # SUNAT exporta 1.000 en soles; el registro solo pide el T.C. si no es PEN, y la
    # plantilla lo escribe vacío: guardarlo se contradiria con lo que generamos.
    assert c.tipo_cambio is None
    assert c.datos_originales["sire"][8] == "1032"      # queda la fila cruda para rastrear


def test_la_nota_de_credito_conserva_los_campos_de_descuento():
    """Si SUNAT la tiene como descuento (16 y 18), vuelve a salir igual: ida y vuelta."""
    c = sire_txt.parsear(texto(NOTA), VENTAS)[0]
    assert c.dscto_base == Decimal("9985.36") and c.dscto_igv == Decimal("1797.36")
    # Base e IGV netos (15 + 16, 17 + 18): la nota ES su descuento, no un comprobante en cero.
    assert c.base_gravada == Decimal("9985.36") and c.igv == Decimal("1797.36")
    assert (c.ref_tipo_cp, c.ref_serie, c.ref_numero) == ("01", "F001", "257")
    assert str(c.ref_fecha) == "2026-07-31"


def test_el_motivo_de_la_nota_y_el_estado_entran_desde_la_exportacion():
    """Las dos columnas que completa la Administración y que el lector ignoraba hasta la 3.5.0. Estaban en este
    mismo fixture desde que se escribió —el `09` y el `1` del final de `NOTA`— y se descartaban."""
    nota = sire_txt.parsear(texto(NOTA), VENTAS)[0]
    assert nota.tipo_nota == "09"        # Catálogo 09: disminución en el valor
    assert nota.estado_sunat == "1"
    factura = sire_txt.parsear(texto(FACTURA), VENTAS)[0]
    assert factura.tipo_nota == ""       # no es una nota: no tiene motivo
    assert factura.estado_sunat == "1"


def test_el_estado_de_sunat_se_transporta_tal_cual():
    """**El motor no traduce ese campo, y este test es lo que lo impide.** La norma no publica su tabla de valores y
    lo declara «alfanumérico» en ventas, así que cualquier normalización —un `upper()`, un `zfill`, un mapa a la
    palabra «anulado»— sería decidir algo sin fuente. Si alguien la añade, esto se pone rojo."""
    campos = NOTA.split("|")
    for valor in ("2", "a1", "A1", "9"):
        fila = "|".join(campos[:34] + [valor] + campos[35:])
        assert sire_txt.parsear(texto(fila), VENTAS)[0].estado_sunat == valor


def test_el_motivo_de_la_nota_de_un_digito_se_completa_a_dos():
    """Los dos catálogos son de dos dígitos, así que quien escriba «9» quiere decir «09». Lo hace el modelo, y solo
    si es dígito: la columna del RCE se declara alfanumérica y no se le impone un formato que la norma no pide."""
    campos = NOTA.split("|")
    assert sire_txt.parsear(texto("|".join(campos[:33] + ["9"] + campos[34:])), VENTAS)[0].tipo_nota == "09"


def test_el_formato_de_reemplazo_no_trae_las_dos_ultimas_y_entra_igual():
    """El archivo que genera este mismo motor son 33 campos y palote, sin las columnas de la Administración. Que
    entre sin ellas es lo que hace segura la ida y vuelta: sale, se sube a SUNAT y puede volver."""
    fila = "|".join(NOTA.split("|")[:33]) + "|"
    c = sire_txt.parsear(texto(fila, con_cabecera=False), VENTAS)[0]
    assert (c.tipo_nota, c.estado_sunat) == ("", "")
    assert c.total == Decimal("11782.72")     # y el resto del comprobante entra completo


def test_compras_trae_el_motivo_y_el_estado_en_sus_propias_columnas():
    """**Sus números NO son los de ventas**, y por eso cada registro tiene su mapa: el Anexo 8 de la RS 040-2022
    (§8.4) pone el motivo en el campo 39 y el estado en el 40, con la marca de detracción en el 38 —que se lee desde
    la 4.1, ver más abajo— y las inconsistencias en el 41. En ventas son el 34 y el 35."""
    compras = Libro(ruc="20601111111", razon_social="MI EMPRESA SAC", periodo="202608", tipo="compra")
    campos = [""] * 41
    campos[0:4] = ["20601111111", "MI EMPRESA SAC", "202608", ""]
    campos[4], campos[6], campos[7], campos[9] = "05/08/2026", "07", "FC01", "9"
    campos[11], campos[12], campos[13] = "6", "20608888889", "PROVEEDOR SAC"
    campos[14], campos[15], campos[24] = "100.00", "18.00", "118.00"   # DG: base, IGV y total
    campos[25] = "PEN"
    campos[27], campos[28], campos[29], campos[31] = "31/07/2026", "01", "F001", "77"
    campos[38], campos[39], campos[40] = "04", "2", "algo"            # motivo, estado, inconsistencias
    c = sire_txt.parsear(texto("|".join(campos), con_cabecera=False), compras)[0]
    assert c.tipo_nota == "04"            # Catálogo 09: descuento global
    assert c.estado_sunat == "2"
    # Y la columna de al lado sigue sin leerse: las inconsistencias (41) son la opinión de la Administración.
    assert c.total == Decimal("118.00") and c.ref_numero == "77"


def _compra(**campos_extra) -> list[str]:
    """Una fila mínima del RCE, para no repetir el andamio en cada caso."""
    campos = [""] * 41
    campos[0:3] = ["20601111111", "MI EMPRESA SAC", "202608"]
    campos[4], campos[6], campos[7], campos[9] = "10/08/2026", "01", "F001", "501"
    campos[11], campos[12], campos[13] = "6", "20608888889", "PROVEEDOR SAC"
    campos[14], campos[15], campos[24] = "4200.00", "756.00", "4956.00"
    campos[25] = "PEN"
    for i, v in campos_extra.items():
        campos[int(i[1:])] = v
    return campos


COMPRAS = Libro(ruc="20601111111", razon_social="MI EMPRESA SAC", periodo="202608", tipo="compra")


def test_compras_lee_la_marca_de_detraccion_que_sunat_afirma():
    """El campo 38 del Anexo 8: SUNAT escribe una `D` en las filas sujetas al SPOT. Es lo ÚNICO que la propuesta dice
    del SPOT —afirma QUE hay detracción y no dice CUÁL—, así que entra como anotación y el bloque sale **sin código**:
    inventarlo escribiría una tasa falsa en el asiento. En un RCE real de un mes venía en 221 de 3018 filas."""
    c = sire_txt.parsear(texto("|".join(_compra(c37="D")), con_cabecera=False), COMPRAS)[0]
    assert c.detraccion == {"_marca_sire": "D"}
    assert not c.detraccion.get("codigo") and not c.detraccion.get("monto")


def test_sin_la_marca_el_comprobante_no_trae_detraccion():
    """La columna vacía es el caso de las 2797 filas restantes: no se inventa un bloque que no está."""
    assert not sire_txt.parsear(texto("|".join(_compra()), con_cabecera=False), COMPRAS)[0].detraccion
    # Y una letra que el anexo no declara tampoco marca nada: se compara con la que SUNAT escribe, no «no vacío».
    assert not sire_txt.parsear(texto("|".join(_compra(c37="X")), con_cabecera=False), COMPRAS)[0].detraccion


def test_en_ventas_no_hay_marca_de_detraccion_porque_el_rvie_no_la_tiene():
    """Ninguna de las 40 columnas del RVIE es la detracción, así que una venta nunca sale marcada. Si algún día el
    anexo de ventas la trajera, este test es el que avisa de que hay que decidirlo."""
    assert all(campo["nombre"] != "marca de detracción" for campo in catalogos.columnas_del_sire(True))
    assert not sire_txt.parsear(texto(FACTURA), VENTAS)[0].detraccion


def test_el_tipo_de_cambio_solo_se_guarda_si_no_es_soles():
    dolares = FACTURA.replace("|PEN|1.000|", "|USD|3.755|", 1)
    assert sire_txt.parsear(texto(dolares), VENTAS)[0].tipo_cambio == Decimal("3.755")


def test_el_formato_de_reemplazo_tambien_entra():
    """El archivo que genera el portal (33 campos + palote) se puede volver a subir."""
    fila = "|".join(FACTURA.split("|")[:33]) + "|"
    c = sire_txt.parsear(texto(fila, con_cabecera=False), VENTAS)[0]
    assert (c.serie, c.numero, c.total) == ("E001", "1032", Decimal("242202.25"))


def test_no_se_carga_lo_que_es_de_otro_ruc_u_otro_periodo():
    otro_ruc = FACTURA.replace("20601111111|MI EMPRESA", "20111111111|OTRA EMPRESA", 1)
    with pytest.raises(sire_txt.SireInvalido, match="RUC"):
        sire_txt.parsear(texto(otro_ruc), VENTAS)
    with pytest.raises(sire_txt.SireInvalido, match="periodo"):
        sire_txt.parsear(texto(FACTURA.replace("|202608|", "|202607|", 1)), VENTAS)


def test_compras_reparte_las_seis_columnas_segun_el_destino():
    compras = Libro(ruc="20601111111", razon_social="MI EMPRESA SAC", periodo="202608", tipo="compra")
    # Anexo 11: 9 = año DUA, 10 = número; 15-20 = BI/IGV de DG, DGNG y DNG
    fila = ("20601111111|MI EMPRESA SAC|202608||05/08/2026||01|F001||123||6|20608888889|PROVEEDOR SAC|"
            "0|0|0|0|101.00|18.18|0|0|0|0|119.18|PEN||||||||||")
    c = sire_txt.parsear(texto(fila, con_cabecera=False), compras)[0]
    assert c.destino_igv == "DNG"                       # el importe vino en la tercera pareja
    assert c.base_gravada == Decimal("101.00") and c.igv == Decimal("18.18")
    assert c.numero == "123" and c.total == Decimal("119.18")


def test_compras_lee_el_valor_de_las_adquisiciones_no_gravadas():
    """El campo 21 del RCE, que es el ÚNICO sitio donde una compra informa lo no gravado.

    En el RVIE hay dos columnas (exonerado e inafecto); en el RCE hay una sola y el archivo no dice cuál de
    los dos es, así que va a `valor_no_gravado` y nadie inventa el desglose. En el enero real de un
    contribuyente esta columna la usaban **460 de 1116 compras**, el 41 % del mes.
    """
    compras = Libro(ruc="20601111111", razon_social="MI EMPRESA SAC", periodo="202608", tipo="compra")
    # Las seis parejas base/IGV en cero y el importe solo en la 21 (índice 20).
    fila = ("20601111111|MI EMPRESA SAC|202608||05/08/2026||01|E001||151||6|20608888889|PROVEEDOR SAC|"
            "0|0|0|0|0|0|150.00|0|0|0|150.00|PEN||||||||||")
    c = sire_txt.parsear(texto(fila, con_cabecera=False), compras)[0]
    assert c.valor_no_gravado == Decimal("150.00")
    assert c.adquisiciones_no_gravadas == Decimal("150.00")
    # Y el desglose se queda vacío a propósito: el archivo no dice si es exonerado o inafecto.
    assert c.exonerado == 0 and c.inafecto == 0 and c.base_gravada == 0 and c.igv == 0


def test_el_campo_21_en_cero_no_declara_nada():
    """Una compra gravada trae la columna 21 como «0», y eso NO es declarar que lo no gravado es cero.

    La diferencia importa desde la 3.5.1: un cero declarado gana sobre `exonerado + inafecto` en
    `adquisiciones_no_gravadas`, así que se llevaría por delante el desglose que alguien escriba luego en la
    pantalla. `None` significa «no lo declaro, mira el desglose».
    """
    compras = Libro(ruc="20601111111", razon_social="MI EMPRESA SAC", periodo="202608", tipo="compra")
    fila = ("20601111111|MI EMPRESA SAC|202608||05/08/2026||01|F001||123||6|20608888889|PROVEEDOR SAC|"
            "100.00|18.00|0|0|0|0|0.00|0|0|0|118.00|PEN||||||||||")
    c = sire_txt.parsear(texto(fila, con_cabecera=False), compras)[0]
    assert c.valor_no_gravado is None
    assert c.adquisiciones_no_gravadas == Decimal("0")


def test_otros_conceptos_en_negativo_es_un_descuento():
    """El campo 24 del RCE («otros conceptos, tributos y cargos») es un NETO CON SIGNO.

    Caso real, una factura de grifo: 96.00 no gravado y −13.40 aquí, total 82.60. `monto()` devuelve el valor
    absoluto —el signo no es parte del dato— así que el motor sumaba 109.40 y avisaba «no cuadra» por un
    comprobante correcto; y el TXT que generaba escribía +13.40 donde SUNAT tiene −13.40.
    """
    compras = Libro(ruc="20601111111", razon_social="MI EMPRESA SAC", periodo="202608", tipo="compra")
    fila = ("20601111111|MI EMPRESA SAC|202608||05/08/2026||01|FA04||440774||6|20608888889|GRIFO SAC|"
            "0|0|0|0|0|0|96.00|0|0|-13.40|82.60|PEN||||||||||")
    c = sire_txt.parsear(texto(fila, con_cabecera=False), compras)[0]
    assert c.otros == 0 and c.dscto_otros == Decimal("13.40")
    assert c.valor_no_gravado == Decimal("96.00") and c.total == Decimal("82.60")

    # Y vuelve al archivo tal como vino: el registro solo tiene una columna, así que sale el neto con signo.
    from contaperu.drivers.sire import txt as driver
    assert driver.linea(c, compras, driver.OPCIONES).split("|")[23] == "-13.40"


def test_en_una_nota_de_credito_el_negativo_NO_es_un_descuento():
    """En una nota TODOS los campos vienen negativos porque lo es la operación entera, y ese signo lo pone el
    driver al escribir. Tomarlo por descuento invertiría la nota.

    Por eso la condición es **signo contrario al del total**, y no «negativo» a secas. Comprobado en un RCE
    real de 1116 filas: sus dos notas de crédito traen esta columna en 0.00 y las seis facturas con descuento
    la traen contraria al total.
    """
    compras = Libro(ruc="20601111111", razon_social="MI EMPRESA SAC", periodo="202608", tipo="compra")
    fila = ("20601111111|MI EMPRESA SAC|202608||05/08/2026||07|FC01||97||6|20608888889|PROVEEDOR SAC|"
            "-100.00|-18.00|0|0|0|0|0|0|0|-5.00|-123.00|PEN|||01|F001||77||||")
    c = sire_txt.parsear(texto(fila, con_cabecera=False), compras)[0]
    assert c.otros == Decimal("5.00") and c.dscto_otros == 0    # el signo es de la operación, no un descuento
    assert c.total == Decimal("123.00") and c.base_gravada == Decimal("100.00")


def test_el_txt_del_sire_deja_de_ser_un_archivo_auxiliar():
    """Antes caía con los .xsl y .css: el proceso decía 'no había ningún comprobante'."""
    lote = archivos.expandir("propuesta.txt", texto(FACTURA))
    assert lote.entradas[0].es_sire and not lote.entradas[0].es_auxiliar
    res = archivos.convertir_xml(lote, VENTAS)
    assert len(res.comprobantes) == 1 and not res.ignorados
    # Un .txt que NO es del SIRE se sigue ignorando (los que acompañan a un XML)
    otro = archivos.expandir("leeme.txt", b"notas del contador")
    assert archivos.convertir_xml(otro, VENTAS).ignorados == ["leeme.txt"]


def test_entra_tal_cual_lo_entrega_sunat_dentro_del_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("LE206011111112026080014040001EXP2.txt", texto(FACTURA, NOTA).decode("utf-8"))
    lote = archivos.expandir("propuesta.zip", buf.getvalue())
    res = archivos.convertir_xml(lote, VENTAS)
    assert len(res.comprobantes) == 2


# ── Lo DECLARADO (01-nov-2026) ───────────────────────────────────────────────────────────────────────────────────
# El registro que se generó en SOL, bajado con `registro_pedir`. La forma es la del archivo real —los rótulos, que son
# de SUNAT y no de nadie— y los datos son inventados: el ZIP traía dos TXT y una carpeta vacía, en este orden.
CABECERA_DEL_REGISTRO = (
    "RUC|Apellidos y Nombres o Razón social|Periodo|CAR SUNAT|Fecha de emisión|Fecha Vcto/Pago|Tipo CP/Doc.|"
    "Serie del CDP|Año|Nro CP o Doc. Nro Inicial (Rango)|Nro Final (Rango)|Tipo Doc Identidad|Nro Doc Identidad|"
    "Apellidos Nombres/ Razón Social|BI Gravado DG|IGV / IPM DG|BI Gravado DGNG|IGV / IPM DGNG|BI Gravado DNG|"
    "IGV / IPM DNG|Valor Adq. NG|ISC|ICBPER|Otros Trib/ Cargos|Total CP|Moneda|Tipo de Cambio|"
    "Fecha Emisión Doc Modificado|Tipo CP Modificado|Serie CP Modificado|COD. DAM O DSI|Nro CP Modificado|"
    "Clasif de Bss y Sss|ID Proyecto Operadores/Partícipes|PorcPart|IMB|CAR Orig/ Ind E o I|Detracción|Tipo de Nota|"
    "Est. Comp.|Incal|" + "|".join(f"CLU{i}" for i in range(1, 40)))
CABECERA_NO_DOMICILIADOS = (
    "Periodo|CAR SUNAT|Fecha de emisión|Tipo CP/Doc.|Serie del CP|Nro CP o Doc.|Val. Adquisiciones|Otros |Total CP |"
    "Tipo CP CF|Serie CP CF|Año|Nro CP o Doc. CF|Monto Ret.|Moneda|Tipo de Cambio|País|"
    "Apellidos Nombres/ Razón Social del sujeto No Dom.|Domicilio|ID sujeto No Dom.|ID beneficiario|"
    "Apellidos Nombres/ Razón Social del beneficiario|País beneficiario|Vínculo|Rta. Bta.|Deduc./Costo|Rta. Neta|Tasa|"
    "Impto.|Convenio|Exon.|Tipo Rta|Mod. Serv.|Art. 76|CAR Orig.|" + "|".join(f"CLU{i}" for i in range(1, 11)))
# Una compra a un proveedor del exterior, con la forma del archivo real: el periodo delante, y país y renta detrás.
# Son los 35 campos informados; la exportación añade las 10 columnas libres y el que se presenta, uno vacío y palote.
CAMPOS_NO_DOMICILIADO = ["202608", "", "12/08/2026", "91", "E001", "7", "100.00", "0.00", "100.00", "00", "", "",
                         "", "0.00", "USD", "3.750", "9249", "PROVEEDOR DEL EXTERIOR", "UNA CALLE DEL EXTERIOR",
                         "X0000001", "", "", "", "00", "0.00", "0.00", "0.00", "0.00", "0.00", "00", "", "01", "1", "",
                         ""]
NO_DOMICILIADO = "|".join(CAMPOS_NO_DOMICILIADO + [""] * 10)
REGISTRO = "LE20601111111202608000804000011112.txt"
DE_NO_DOMICILIADOS = "LE20601111111202608000805000011112.txt"


def _declarado(*entradas: tuple[str, str]) -> bytes:
    """El ZIP de lo declarado, con sus entradas en el orden que se le diga — y la carpeta vacía que trae el real."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nombre, contenido in entradas:
            z.writestr(nombre, contenido)
        z.writestr("LE20601111111080400011112/", "")
    return buf.getvalue()


def test_lo_declarado_se_lee_como_la_exportacion_y_sus_columnas_libres_se_ignoran():
    """El registro generado llega en el formato de la EXPORTACIÓN: cabecera, las 41 columnas de siempre y 39 de libre
    utilización. Un mes real de 1 326 compras se leyó entero sin un cambio en el lector (01-nov-2026), y esto lo fija:
    lo que pone la persona en una CLU no se lee como un dato del comprobante."""
    fila = _compra() + ["algo puesto a mano"] + [""] * 38
    assert len(fila) == 80 and len(CABECERA_DEL_REGISTRO.split("|")) == 80
    assert len(CABECERA_NO_DOMICILIADOS.split("|")) == len(NO_DOMICILIADO.split("|")) == 45
    contenido = (CABECERA_DEL_REGISTRO + "\n" + "|".join(fila)).encode("utf-8")
    assert sire_txt.es_sire(contenido)
    c = sire_txt.parsear(contenido, COMPRAS)[0]
    assert (c.tipo_cp, c.serie, c.numero, c.contraparte_doc) == ("01", "F001", "501", "20608888889")
    assert c.base_gravada == Decimal("4200.00") and c.igv == Decimal("756.00") and c.total == Decimal("4956.00")
    assert c.datos_originales["sire"][41] == "algo puesto a mano"     # viaja en la fila cruda, y nada más


def test_dentro_del_zip_de_lo_declarado_se_lee_el_registro_aunque_vaya_segundo():
    """El ZIP trae dos TXT y el lector tomaba **el primero de la lista**. En el real el registro iba primero, por suerte:
    con el de no domiciliados delante, `parsear` habría leído ese y fallado en la primera fila."""
    registro = CABECERA_DEL_REGISTRO + "\n" + "|".join(_compra() + [""] * 39)
    no_dom = CABECERA_NO_DOMICILIADOS + "\n" + NO_DOMICILIADO
    zip_ = _declarado((DE_NO_DOMICILIADOS, no_dom), (REGISTRO, registro))
    assert sire_txt.es_sire(zip_)
    assert [c.numero for c in sire_txt.parsear(zip_, COMPRAS)] == ["501"]


def test_el_registro_de_no_domiciliados_se_dice_en_vez_de_callarse():
    """El de no domiciliados tiene su propio formato —el periodo delante, país, renta y retención detrás— y el motor
    todavía no lo lee. Hasta la 15.1 caía con las hojas de estilo, como un acompañante, y sus filas se perdían sin un
    error: en el mes real eran diez. Ahora va a `no_leidos`, con sus filas contadas, **y no a errores**: el registro de
    al lado se leyó bien, y un integrador que pare con cualquier error dejaría de enseñar lo declarado entero."""
    registro = CABECERA_DEL_REGISTRO + "\n" + "|".join(_compra() + [""] * 39)
    otro = CAMPOS_NO_DOMICILIADO[:5] + ["8"] + CAMPOS_NO_DOMICILIADO[6:]
    no_dom = CABECERA_NO_DOMICILIADOS + "\n" + NO_DOMICILIADO + "\n" + "|".join(otro + [""] * 10)
    lote = archivos.expandir("declarado.zip", _declarado((REGISTRO, registro), (DE_NO_DOMICILIADOS, no_dom)))
    res = archivos.convertir_xml(lote, COMPRAS)
    assert len(res.comprobantes) == 1 and res.errores == [] and res.ignorados == []
    assert res.no_leidos == [{"archivo": f"declarado.zip/{DE_NO_DOMICILIADOS}", "codigo": "080500", "filas": 2,
                              "motivo": "Es el registro de compras de no domiciliados del SIRE: tiene su propio "
                                        "formato y este lector todavía no lo lee"}]


def test_el_de_no_domiciliados_se_reconoce_por_su_nombre_o_por_su_cabecera():
    """El que se PRESENTA no trae cabecera —diez filas de 36 campos y palote, en el caso real—, así que lo delata el
    código de su nombre. Y la exportación renombrada lo delata su cabecera, que empieza por el periodo."""
    fila_presentada = "|".join(CAMPOS_NO_DOMICILIADO + [""]) + "|"
    assert len(fila_presentada.split("|")) == 37          # 36 campos y el palote, como el real
    presentado = "\r\n".join([fila_presentada] * 3).encode("utf-8")
    sin_cabecera = archivos.convertir_xml(archivos.expandir(DE_NO_DOMICILIADOS, presentado), COMPRAS)
    assert [(n["codigo"], n["filas"]) for n in sin_cabecera.no_leidos] == [("080500", 3)]
    renombrado = (CABECERA_NO_DOMICILIADOS + "\n" + NO_DOMICILIADO).encode("utf-8")
    con_cabecera = archivos.convertir_xml(archivos.expandir("no-domiciliados.txt", renombrado), COMPRAS)
    assert [(n["codigo"], n["filas"]) for n in con_cabecera.no_leidos] == [("080500", 1)]
    assert con_cabecera.ignorados == [] and con_cabecera.errores == []


def test_un_registro_del_sire_con_una_forma_que_no_se_conoce_no_da_una_tabla_vacia():
    """El riesgo que esto vino a cerrar: el día que SUNAT cambie la forma del registro, el TXT dejaría de reconocerse,
    caería con las hojas de estilo y lo declarado saldría VACÍO, sin un error. Su nombre dice lo que es, así que se
    dice con sus filas, y quien integra decide."""
    otra_forma = b"Ruc|Periodo|Total\n20601111111|202608|4956.00\n20601111111|202608|10.00"
    res = archivos.convertir_xml(archivos.expandir(REGISTRO, otra_forma), COMPRAS)
    assert res.comprobantes == [] and res.ignorados == []
    assert [(n["codigo"], n["filas"]) for n in res.no_leidos] == [("080400", 2)]
    assert "puede que SUNAT la haya cambiado" in res.no_leidos[0]["motivo"]


def test_el_codigo_del_libro_se_busca_despues_del_ruc():
    """El código va en el nombre DETRÁS del RUC, y un RUC puede contenerlo: este lleva «140400» dentro —y el dígito
    verificador mal a propósito, para que no pueda ser de nadie—. Buscarlo en el nombre entero lo leería como el
    registro de ventas."""
    res = archivos.convertir_xml(archivos.expandir("LE20140400120202608000101000011112.txt", b"20260800|algo"),
                                 COMPRAS)
    assert [(n["codigo"], n["filas"]) for n in res.no_leidos] == [("", 1)]
    assert res.no_leidos[0]["motivo"] == "Es un libro electrónico de SUNAT que este lector no reconoce"


def test_un_txt_que_no_es_de_sunat_sigue_siendo_un_acompanante():
    """Lo de arriba no puede volver ruidoso el ZIP de un facturador: un `.txt` cualquiera —unas notas, un léeme— no
    se llama `LE` + RUC ni empieza por «Periodo|CAR SUNAT», y se sigue ignorando como siempre."""
    for nombre in ("leeme.txt", "LE-notas.txt", "LEEME20601111111.txt"):
        res = archivos.convertir_xml(archivos.expandir(nombre, b"notas del contador"), COMPRAS)
        assert res.ignorados == [nombre] and res.no_leidos == [], nombre
