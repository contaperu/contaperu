"""La plantilla `sire` sigue los anexos oficiales (Anexo 3 RVIE / Anexo 11 RCE).

La estructura de VENTAS está contrastada contra un archivo REAL aceptado por SUNAT (RVIE de julio de
un estudio contable, 25-ago-2026): 33 campos y palote final, sin los campos 34-40 que completa la
Administración; la de COMPRAS, contra el RCE real presentado del mismo mes (27-ago-2026): 41 campos
y palote final, con los 38-41 vacíos pero presentes. Los archivos no viven en el repo —son data de
un cliente—, así que aquí se prueba la forma que se comprobó con ellos: número de campos, cabecera,
fechas DD/MM/AAAA, CRLF, nombre del archivo, signo de las notas de crédito, tipo de cambio y saneado
a ASCII.
"""
from dataclasses import replace
from decimal import Decimal

import pytest

from contaperu.pipeline import salida as g
from contaperu import api
from contaperu.pipeline import preparacion as prep
from contaperu.modelo import Comprobante
from contaperu.drivers import sire
from util import campos, cargar_golden
from util import con_imputaciones, imputar


def test_el_mismo_contenido_da_el_mismo_zip_byte_a_byte():
    """La fecha de la entrada es fija, así que el ZIP es reproducible y quien guarde su huella lo reconoce.

    Lo afirma el docstring del pipeline desde que existe el SIRE. Vivía en el test de STARSOFT, que es quien lo
    estrenó en la 2.3; cuando en la 6.0 su archivo dejó de ir comprimido, la regla se quedó sin quien la probara
    y se mudó aquí, que es el driver que comprime.
    """
    libro, comprobantes = cargar_golden("compras_202601.json")
    uno, otro = g.generar(libro, comprobantes, "sire"), g.generar(libro, comprobantes, "sire")
    assert uno.comprimido == otro.comprimido


@pytest.mark.parametrize("json_golden,n_campos,nombre", [
    ("ventas_202512.json", 33, "LE2060123456720251200140400021112.TXT"),
    ("compras_202601.json", 41, "LE2060123456720260100080400021112.TXT"),
])
def test_estructura(json_golden, n_campos, nombre):
    libro, comprobantes = cargar_golden(json_golden)
    exp = g.generar(libro, comprobantes, "sire")

    assert exp.nombre == nombre
    assert exp.nombre_comprimido == nombre[:-4] + ".zip"
    assert exp.texto.endswith(b"\r\n") and b"\n" not in exp.texto.replace(b"\r\n", b"")
    lineas = exp.texto.decode("ascii").split("\r\n")[:-1]
    assert len(lineas) == len(comprobantes)
    for linea in lineas:
        assert linea.endswith("|"), linea             # palote final, como el archivo aceptado
        f = campos(linea, palote_final=True)
        assert len(f) == n_campos, linea
        assert f[0] == "20601234567"                  # 1 RUC del generador
        assert f[1] == "EMPRESA DE PRUEBA SAC"        # 2 ID libre (se usa la razón social)
        assert f[2] == "202512" or f[2] == "202601"   # 3 periodo AAAAMM
        assert f[3] == ""                             # 4 CAR vacío
        assert len(f[4]) == 10 and f[4][2] == "/"     # 5 fecha DD/MM/AAAA
        if n_campos == 41:                            # compras: los 38-41 van vacíos pero PRESENTES
            assert f[-4:] == ["", "", "", ""]


# El número va sin ceros a la izquierda (regla de un contador, 23-ago-2026): 00001001 → 1001.
def test_ventas_primera_linea_literal():
    """La forma exacta que SUNAT aceptó: 33 campos, palote final y el vencimiento VACÍO
    (campo 6) en una factura — solo lo llevan los tipos que lo exigen."""
    libro, comprobantes = cargar_golden("ventas_202512.json")
    linea = g.lineas_de_texto(libro, comprobantes[:1], "sire")[0]
    assert linea == (
        "20601234567|EMPRESA DE PRUEBA SAC|202512||02/12/2025||01|F001|1001||6|20609999999|"
        "DISTRIBUIDORA COMERCIAL DEL NORTE SAC|0.00|25000.00|0.00|4500.00|0.00|0.00|0.00|0.00|0.00|0.00|0.00|"
        "0.00|29500.00|PEN|||||||"    # 28-33 vacíos + el palote que cierra la fila
    )


def test_compras_tipo_14_y_destino():
    libro, comprobantes = cargar_golden("compras_202601.json")
    recibo = comprobantes[2]
    f = campos(g.lineas_de_texto(libro, [recibo], "sire")[0], palote_final=False)
    assert f[6] == "14" and f[7] == "" and f[9] == "12345679"
    assert f[14:20] == ["1800.00", "324.00", "0.00", "0.00", "0.00", "0.00"]   # DG
    recibo.destino_igv = "DNG"
    f = campos(g.lineas_de_texto(libro, [recibo], "sire")[0], palote_final=False)
    assert f[14:20] == ["0.00", "0.00", "0.00", "0.00", "1800.00", "324.00"]


def test_nota_de_credito_en_negativo_y_referencia():
    libro, _ = cargar_golden("ventas_202512.json")
    nc = Comprobante(tipo_cp="07", serie="FC01", numero="7", fecha_emision="2025-12-20",
                     contraparte_doc="20131312955", contraparte_nombre="CLIENTE SAC",
                     base_gravada="100", igv="18", total="118",
                     ref_fecha="2025-12-02", ref_tipo_cp="01", ref_serie="F001", ref_numero="1001")
    f = campos(g.lineas_de_texto(libro, [nc], "sire")[0], palote_final=False)
    assert f[14] == "-100.00" and f[16] == "-18.00" and f[25] == "-118.00"
    assert f[28:32] == ["02/12/2025", "01", "F001", "1001"]


def test_usd_con_tipo_cambio_y_pen_sin_tc():
    libro, comprobantes = cargar_golden("ventas_202512.json")
    usd = Comprobante(tipo_cp="01", serie="F001", numero="9", fecha_emision="2025-12-21",
                      contraparte_doc="20131312955", contraparte_nombre="X", moneda="USD",
                      tipo_cambio="3.7512", base_gravada="500", igv="90", total="590")
    f = campos(g.lineas_de_texto(libro, [usd], "sire")[0], palote_final=False)
    assert f[26] == "USD" and f[27] == "3.751"
    # Y sus importes, en soles por el tipo de cambio que sale en la fila (15.9.0): el comprobante lo guarda con tres
    # decimales, así que es 500 × 3.751 y no × 3.7512.
    assert (f[14], f[16], f[25]) == ("1875.50", "337.59", "2213.09")
    f = campos(g.lineas_de_texto(libro, comprobantes[:1], "sire")[0], palote_final=False)
    assert f[26] == "PEN" and f[27] == ""           # en el SIRE: obligatorio solo si ≠ PEN


def _en_dolares(**importes) -> Comprobante:
    return Comprobante(tipo_cp="01", serie="F001", numero="9", fecha_emision="2025-12-21", contraparte_tipo_doc="6",
                       contraparte_doc="20131312955", contraparte_nombre="X", moneda="USD", **importes)


def test_en_dolares_el_registro_lleva_soles_y_el_total_es_la_suma_de_sus_columnas():
    """**En el RVIE y el RCE los importes van en la moneda de la contabilidad** (15.9.0), que es la de la tercera
    bandera del nombre: soles. Hasta la 15.8.0 salían los dólares tal cual y el comprobante quedaba declarado dividido
    por su tipo de cambio.

    Y el total no se convierte aparte: es la suma de las columnas, como lo escribe SUNAT. Con estos importes la
    diferencia se ve —118.01 × 3.333 = 393.33, y 333.33 + 59.99 = 393.32—, y una fila que no suma se puede rechazar."""
    libro, _ = cargar_golden("ventas_202512.json")
    usd = _en_dolares(tipo_cambio="3.333", base_gravada="100.01", igv="18.00", total="118.01")
    f = campos(g.lineas_de_texto(libro, [usd], "sire")[0], palote_final=False)
    assert (f[14], f[16], f[25], f[26], f[27]) == ("333.33", "59.99", "393.32", "USD", "3.333")
    # El comprobante no cambia: se convierte lo que se escribe, no lo que se guardó.
    assert usd.total == Decimal("118.01")

    nota = replace(usd, tipo_cp="07", serie="FC01", ref_tipo_cp="01", ref_serie="F001", ref_numero="9",
                   ref_fecha=usd.fecha_emision)
    f = campos(g.lineas_de_texto(libro, [nota], "sire")[0], palote_final=False)
    assert (f[14], f[16], f[25]) == ("-333.33", "-59.99", "-393.32"), "la nota, con su signo y la misma suma"


def test_una_compra_en_dolares_lleva_en_soles_hasta_lo_no_gravado_y_los_otros():
    libro, _ = cargar_golden("compras_202601.json")
    usd = _en_dolares(tipo_cambio="3.500", base_gravada="1000", igv="180", valor_no_gravado="100", dscto_otros="10",
                      total="1270")
    f = campos(g.lineas_de_texto(libro, [usd], "sire")[0], palote_final=False)
    assert f[14:24] == ["3500.00", "630.00", "0.00", "0.00", "0.00", "0.00", "350.00", "0.00", "0.00", "-35.00"]
    assert (f[24], f[25], f[26]) == ("4445.00", "USD", "3.500")
    # Y su total también es la suma de sus columnas: 333.33 + 59.99 = 393.32, aunque 118.01 × 3.333 sea 393.33.
    con_redondeo = _en_dolares(tipo_cambio="3.333", base_gravada="100.01", igv="18.00", total="118.01")
    f = campos(g.lineas_de_texto(libro, [con_redondeo], "sire")[0], palote_final=False)
    assert (f[14], f[15], f[24]) == ("333.33", "59.99", "393.32")


def test_en_dolares_sin_tipo_de_cambio_sale_como_esta():
    """No llega aquí sin pedirlo: `validar` lo para con `TC_FALTA`. Con `--incluir-errores` sale tal cual, con el tipo de
    cambio vacío, en vez de inventarle uno o de reventar a mitad del archivo."""
    libro, _ = cargar_golden("ventas_202512.json")
    f = campos(g.lineas_de_texto(libro, [_en_dolares(base_gravada="100", igv="18", total="118")], "sire")[0],
               palote_final=False)
    assert (f[14], f[16], f[25], f[27]) == ("100.00", "18.00", "118.00", "")


def test_en_soles_el_tipo_de_cambio_NO_sale_aunque_el_comprobante_lo_traiga():
    """El TXT que se presenta a SUNAT no puede moverse porque una aplicación anote el T.C. del día.

    Desde el 22-sep-2026 hay integradores que lo rellenan también en soles —STARSOFT lo escribe en todas sus
    filas—, así que el comprobante en PEN puede llegar con T.C. Aquí no sale: lo corta `kit.texto.formatear_cambio`
    por moneda, antes de mirar el valor, y el driver fija `tc_pen=""`. Hasta hoy solo se probaba el PEN SIN T.C.,
    que es el caso que ya no representa lo que llega.
    """
    libro, _ = cargar_golden("ventas_202512.json")
    base = dict(tipo_cp="01", serie="F001", fecha_emision="2025-12-21", contraparte_doc="20131312955",
                contraparte_nombre="X", moneda="PEN", base_gravada="100", igv="18", total="118")
    sin_tc = Comprobante(numero="11", **base)
    con_tc = Comprobante(numero="12", tipo_cambio="3.751", **base)

    linea_sin = campos(g.lineas_de_texto(libro, [sin_tc], "sire")[0], palote_final=False)
    linea_con = campos(g.lineas_de_texto(libro, [con_tc], "sire")[0], palote_final=False)
    assert linea_con[27] == "" == linea_sin[27], "el T.C. en soles no puede llegar al TXT del SIRE"
    # Y la línea entera es la misma salvo el número (campo 9): nada más se mueve por llevar el T.C.
    assert linea_con[:8] + linea_con[9:] == linea_sin[:8] + linea_sin[9:]


def test_saneado_ascii():
    libro, _ = cargar_golden("ventas_202512.json")
    c = Comprobante(tipo_cp="01", serie="F001", numero="10", fecha_emision="2025-12-21",
                    contraparte_doc="20131312955", contraparte_nombre="PEÑA & CÍA S.A.C. | Lima/Perú",
                    base_gravada="100", igv="18", total="118")
    exp = g.generar(libro, [c], "sire")
    assert "PENA & CIA S.A.C. Lima-Peru" in exp.texto.decode("ascii")
    assert exp.texto.isascii()


def test_rvie_vacios_es_opcion():
    """Si SUNAT algún día pide los 34-40 presentes, es una opción, no código."""
    libro, comprobantes = cargar_golden("ventas_202512.json")
    op = sire.OPCIONES.con(rvie_vacios=7)
    f = campos(g.lineas_de_texto(libro, comprobantes[:1], "sire", op)[0], palote_final=True)
    assert len(f) == 40


def test_importes_siempre_positivos_en_el_modelo():
    c = Comprobante(tipo_cp="07", serie="FC01", numero="1", fecha_emision="2025-12-20", base_gravada="-100", total="-118")
    assert c.base_gravada == Decimal("100.00") and c.total == Decimal("118.00")


@pytest.mark.parametrize("json_golden", ["ventas_202512.json", "compras_202601.json"])
def test_el_motivo_de_la_nota_y_el_estado_de_sunat_no_entran_en_el_txt(json_golden):
    """**Convierte un comentario en una promesa ejecutable.** Los dos campos son de los que «completa la
    Administración», y la norma dice lo mismo de ellos en los dos registros: en ventas, que el campo «no es considerado
    para la construcción del archivo de texto»; en compras, que los campos 38 al 41 «deberán mostrarse vacíos». Vacíos
    quiere decir vacíos.

    Sin este test, dentro de un año alguien «completa» las columnas que faltaban y se lleva el error 453 de estructura
    en producción, que es exactamente lo que ya pasó en ventas cuando se mandaban los campos 34-40."""
    libro, comprobantes = cargar_golden(json_golden)
    sin_ellos = g.generar(libro, comprobantes, "sire").texto
    for c in comprobantes:
        c.tipo_nota, c.estado_sunat = "09", "2"
    con_ellos = g.generar(libro, comprobantes, "sire").texto
    assert con_ellos == sin_ellos           # byte a byte: el archivo no se enteró


def test_los_vacios_del_final_de_COMPRAS_son_una_opcion_no_codigo():
    """Si el RCE devuelve el 453 —como pasó en ventas—, se apaga con una opción.

    Ventas ya pasó por esto: la nota del Anexo 3 decía que los 34-40 "los completa la
    Administración" y hubo que dejar de mandarlos. La del Anexo 11 dice lo contrario
    ("deberán mostrarse vacíos"), así que van, y así salió idéntico al RCE real presentado
    (27-ago-2026); pero si SUNAT cambia de idea, el arreglo no puede pedir tocar el driver.
    """
    libro, comprobantes = cargar_golden("compras_202601.json")
    largo = campos(g.lineas_de_texto(libro, comprobantes[:1], "sire")[0], palote_final=True)
    corto = campos(g.lineas_de_texto(libro, comprobantes[:1], "sire", sire.OPCIONES.con(rce_vacios=0))[0], palote_final=True)
    assert len(largo) == 41 and len(corto) == 37
    assert corto == largo[:37]        # lo informado no cambia: solo se van los de SUNAT


def test_el_recibo_por_honorarios_no_va_al_registro_de_sunat():
    """Regla de contabilidad (23-ago-2026): el RH no se anota en el registro que se
    declara a SUNAT; sí en el asiento contable. El TXT lo deja fuera y lo dice en el
    resumen, para que no parezca que se perdió. (Vivía en el archivo del PLE y se
    portó aquí al morir aquel, 30-ago-2026.)"""


    libro = cargar_golden("compras_202601.json")[0]

    def c(**k):
        base = dict(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-01-10",
                    contraparte_tipo_doc="6", contraparte_doc="20604444447", contraparte_nombre="PROVEEDOR",
                    base_gravada="100", igv="18", total="118")
        base.update(k)
        return Comprobante(**base)

    cs = [c(), c(tipo_cp="02", serie="E001", numero="9", base_gravada="0", igv="0", inafecto="500", total="500"), c(numero="2")]
    exp = g.generar(libro, cs, "sire")
    assert exp.comprobantes == 2 and exp.resumen["fuera_del_destino"] == 1
    assert b"E001" not in exp.texto and exp.texto.count(b"\r\n") == 2
    # El Excel de CONCAR sí se lo lleva (mismo mes, misma revisión)
    for x in cs:
        imputar(x, cuenta_contable="631101", centro_costo="OBRA01")   # la 631101 lleva centro y CONCAR lo exige (0.8)
    exc = g.generar(libro, cs, "concar", config=con_imputaciones(prep.config_aplicada(None, "concar")),
                    correlativos={"11": 1, "15": 1})
    assert exc.comprobantes == 3 and exc.resumen["fuera_del_destino"] == 0


def test_el_no_domiciliado_va_en_su_registro_y_no_en_este():
    """El 91 y sus notas se anotan en el registro de compras de no domiciliados (080500), y este driver escribe el
    080400: una fila de otro registro aquí la rechazaría SUNAT o la contaría dos veces. Entraron a la tabla cuando se
    empezaron a leer (15.3.0), y desde entonces el TXT las deja fuera y lo dice, como al recibo por honorarios."""
    libro = cargar_golden("compras_202601.json")[0]
    comun = dict(fecha_emision="2026-01-10", contraparte_tipo_doc="0", contraparte_doc="ABCDE1234F",
                 contraparte_nombre="PROVEEDOR DEL EXTERIOR", moneda="USD", tipo_cambio="3.750", valor_no_gravado="100",
                 total="100")
    cs = [Comprobante(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-01-10", contraparte_tipo_doc="6",
                      contraparte_doc="20604444447", contraparte_nombre="PROVEEDOR", base_gravada="100", igv="18",
                      total="118"),
          Comprobante(tipo_cp="91", serie="EXT1", numero="7", **comun),
          Comprobante(tipo_cp="97", serie="EXT1", numero="8", **comun),
          Comprobante(tipo_cp="98", serie="EXT1", numero="9", **comun)]
    exp = g.generar(libro, cs, "sire")
    assert exp.comprobantes == 1 and exp.resumen["fuera_del_destino"] == 3
    assert b"EXT1" not in exp.texto and exp.texto.count(b"\r\n") == 1


def test_una_nota_que_cambiaria_de_signo_no_se_escribe_y_dice_cual():
    """Hasta la 0.10 esto era un `assert`: con `python -O` el TXT habría salido con el campo 15 en positivo."""
    from contaperu.drivers import sire
    from contaperu.modelo import Comprobante, Libro

    libro = Libro(ruc="20131312955", razon_social="EMISOR DE PRUEBA S.A.C.", periodo="202601", tipo="venta")
    nota = Comprobante(tipo_cp="07", serie="FC01", numero="1", fecha_emision="2026-01-10", contraparte_tipo_doc="6",
                       contraparte_doc="20601234567", base_gravada="100", igv="18", total="118", dscto_base="150")
    with pytest.raises(api.CampoCambiaDeSigno, match="DSCTO_MAYOR_QUE_BASE") as error:
        sire.linea(nota, libro, 1)
    assert isinstance(error.value, api.NoExportable) and error.value.comprobantes == [nota]
    assert error.value.clave == "campo_cambia_de_signo"
