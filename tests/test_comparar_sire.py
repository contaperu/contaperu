"""El comparador: lo que generamos vs lo que SUNAT tiene en el SIRE.

La herramienta nació del contraste manual que encontró el fallo de estructura del
25-ago-2026 (40 campos en vez de 33) antes de subir nada. Estos casos fijan lo que
debe IGNORAR —para que no ahogue el informe en ruido— y lo que sí tiene que cantar.
"""
from contaperu import comparar_sire as cs

# Una fila del reemplazo: 33 campos informados (el CAR, campo 4, va vacío).
NUESTRA = ("20601111111|MI EMPRESA SAC|202607||01/07/2026||01|F001|246||6|20611111119|CLIENTE SAC|"
           "0.00|145406.84|0.00|26173.23|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|171580.07|PEN|||||||").split("|")
# La misma, tal como la exporta SUNAT: con CAR, importes sin decimales, TC 1.000 en soles
# y las columnas que completa la Administración al final.
SUYA = ("20601111111|MI EMPRESA SAC|202607|2060111111101F0010000000246|01/07/2026||01|F001|246||6|20611111119|"
        "CLIENTE SAC|0|145406.84|0|26173.23|0|0|0|0|0|0|0|0|171580.07|PEN|1.000|||||||1|0|0|1001||").split("|")


def test_no_canta_lo_que_es_formato_de_la_exportacion():
    """CAR lleno, `0` frente a `0.00` y el TC en soles NO son diferencias reales."""
    r = cs.comparar([NUESTRA], [SUYA])
    assert r["diferencias"] == [] and len(r["comunes"]) == 1
    assert not r["solo_en_sunat"] and not r["solo_nuestros"]


def test_canta_un_importe_distinto_con_el_nombre_del_campo():
    otra = list(NUESTRA)
    otra[16] = "26173.00"                       # campo 17: IGV
    r = cs.comparar([otra], [SUYA])
    assert len(r["diferencias"]) == 1
    d = r["diferencias"][0]
    assert (d["campo"], d["nombre"], d["comprobante"]) == (17, "IGV", "01-F001-246")


def test_los_que_faltan_y_los_que_sobran():
    otra = list(NUESTRA)
    otra[8] = "999"                             # un comprobante que SUNAT no tiene
    r = cs.comparar([otra], [SUYA])
    assert r["solo_nuestros"] == [("01", "F001", "999")]
    assert r["solo_en_sunat"] == [("01", "F001", "246")]
    assert "FALTA en lo nuestro: 01-F001-246" in cs.informe(r)


def test_el_numero_con_ceros_a_la_izquierda_es_el_mismo_comprobante():
    otra = list(NUESTRA)
    otra[8] = "0000246"
    assert cs.comparar([otra], [SUYA])["diferencias"] == []


def test_lee_txt_o_zip_y_salta_la_cabecera_de_la_exportacion(tmp_path):
    import zipfile
    cabecera = "Ruc|Razon Social|Periodo|CAR SUNAT|Fecha de emisión"
    txt = tmp_path / "export.txt"
    txt.write_text(cabecera + "\n" + "|".join(SUYA), encoding="utf-8")
    assert len(cs.leer(txt)) == 1                      # la cabecera no cuenta como comprobante

    z = tmp_path / "nuestro.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("LE20601111111202607.TXT", "|".join(NUESTRA) + "\r\n")
    assert cs.leer(z)[0][7] == "F001"                  # lee el TXT de dentro del ZIP


# --- compras (Anexo 11) ------------------------------------------------------
# Los desplazamientos frente a ventas: 9 = año de la DUA, 10 = número, 15-20 = las tres
# parejas base/IGV según el destino, 27 = tipo de cambio.
COMPRA_NUESTRA = ("20601111111|MI EMPRESA SAC|202607||05/07/2026||01|F001||123||6|20608888889|PROVEEDOR SAC|"
                  "101.00|18.18|0.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|119.18|PEN||||||||||||").split("|")
COMPRA_SUYA = ("20601111111|MI EMPRESA SAC|202607|2060111111101F0010000000123|05/07/2026||01|F001||123||6|"
               "20608888889|PROVEEDOR SAC|101.00|18.18|0|0|0|0|0|0|0|0|119.18|PEN|1.000|||||||||||").split("|")


def test_compras_se_alinea_por_el_campo_10_no_por_el_9():
    """En compras el 9 es el año de la DUA: buscar ahí el número no encuentra nada."""
    r = cs.comparar([COMPRA_NUESTRA], [COMPRA_SUYA], cs.COMPRAS)
    assert r["comunes"] == [("01", "F001", "123", "20608888889")] and r["diferencias"] == []
    assert r["registro"] == "compra" and "Registro de compras" in cs.informe(r)


def test_compras_canta_el_igv_con_el_nombre_del_anexo_11():
    otra = list(COMPRA_NUESTRA)
    otra[15] = "18.00"                          # campo 16: IGV de la adquisición gravada
    d = cs.comparar([otra], [COMPRA_SUYA], cs.COMPRAS)["diferencias"][0]
    assert (d["campo"], d["nombre"]) == (16, "IGV DG")


def test_el_registro_se_deduce_del_nombre_del_archivo():
    assert cs.registro_de(["LE20601111111202607001404000211.txt"]).tipo == "venta"
    assert cs.registro_de(["x/LE206011111112026070008040002.zip"]).tipo == "compra"
    assert cs.registro_de(["cualquiera.txt"], "compra").tipo == "compra"
    # Mezclar los dos registros, o un nombre que no lo dice, no se adivina: se pregunta
    for rutas in (["a1404.txt", "b0804.txt"], ["propuesta.txt"]):
        try:
            cs.registro_de(rutas)
            raise AssertionError("debía negarse a adivinar")
        except ValueError as e:
            assert "--registro" in str(e)


def test_en_compras_dos_proveedores_comparten_la_misma_serie_numero():
    """El caso real de julio de un estudio contable: 8 de sus 623 compras chocan por tipo-serie-número.

    `01-E001-149` es a la vez de Supermarket Kusi (S/ 2 940) y de Kana Quispe (S/ 54). Sin
    el RUC en la clave, un diccionario se queda con UNA de las dos y la otra desaparece del
    contraste sin decir nada.
    """
    def fila(doc, total):
        f = list(COMPRA_SUYA)
        f[7], f[9], f[12], f[24] = "E001", "149", doc, total
        f[14], f[15] = total, "0.00"
        return f
    kusi, kana = fila("10603333336", "2940.00"), fila("10602222221", "54.00")
    r = cs.comparar([kusi, kana], [kusi, kana], cs.COMPRAS)
    assert len(r["comunes"]) == 2 and r["diferencias"] == []
    # En ventas la clave se queda en la terna a propósito: ahí el emisor eres tú
    assert len(cs.clave(kusi, cs.VENTAS)) == 3 and len(cs.clave(kusi, cs.COMPRAS)) == 4


def test_el_informe_avisa_cuando_solo_cambia_el_proveedor():
    """Efecto de meter el RUC en la clave: un RUC mal escrito sale como falta + sobra.
    Que se diga, para que no parezcan dos problemas cuando es uno."""
    otro = list(COMPRA_NUESTRA)
    otro[12] = "20111111111"                    # el mismo comprobante con otro proveedor
    inf = cs.informe(cs.comparar([otro], [COMPRA_SUYA], cs.COMPRAS))
    assert "FALTA en lo nuestro" in inf and "SOBRA" in inf
    assert "01-F001-123 está en los dos con distinto proveedor: revisa el RUC" in inf
