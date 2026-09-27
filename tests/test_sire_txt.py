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
    """La propuesta puede venir dentro de su ZIP, y se lee con los mismos topes que cualquier ZIP (`lectores/_zip.py`):
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
    (§8.4) pone el motivo en el campo 39 y el estado en el 40, con la marca de detracción en el 38 —que no se lee— y
    las inconsistencias en el 41. En ventas son el 34 y el 35."""
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
    # Y no se ha leído la columna de al lado: la marca de detracción (38) y las inconsistencias (41) se ignoran.
    assert c.total == Decimal("118.00") and c.ref_numero == "77"


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
