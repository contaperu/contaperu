"""La plantilla `sire` sigue los anexos oficiales (Anexo 3 RVIE / Anexo 11 RCE).

La estructura de VENTAS está contrastada contra un archivo REAL aceptado por SUNAT
(RVIE de julio de un estudio contable, 25-ago-2026): 33 campos y palote final, sin los campos
34-40 que completa la Administración. El archivo no vive en el repo —es data de un
cliente—, así que aquí se prueba la forma que se comprobó con él: número de campos,
cabecera, fechas DD/MM/AAAA, CRLF, nombre del archivo, signo de las notas de crédito,
tipo de cambio y saneado a ASCII.
"""
from decimal import Decimal

import pytest

from contaperu import generar as g
from contaperu.modelo import Comprobante
from contaperu.drivers import sire
from util import campos, cargar_golden
from util import con_imputaciones, imputar


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
    f = campos(g.lineas_de_texto(libro, comprobantes[:1], "sire")[0], palote_final=False)
    assert f[26] == "PEN" and f[27] == ""           # en el SIRE: obligatorio solo si ≠ PEN


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


def test_los_vacios_del_final_de_COMPRAS_son_una_opcion_no_codigo():
    """Si el RCE devuelve el 453 —como pasó en ventas—, se apaga con una opción.

    Ventas ya pasó por esto: la nota del Anexo 3 decía que los 34-40 "los completa la
    Administración" y hubo que dejar de mandarlos. La del Anexo 11 dice lo contrario
    ("deberán mostrarse vacíos"), así que van; pero no está comprobado contra un RCE
    aceptado, y el arreglo no puede pedir tocar la plantilla.
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
    from datetime import date

    from contaperu import asiento as concar

    libro = cargar_golden("compras_202601.json")[0]

    def c(**k):
        base = dict(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-01-10",
                    contraparte_tipo_doc="6", contraparte_doc="20604444447", contraparte_nombre="PROVEEDOR",
                    base_gravada="100", igv="18", total="118")
        base.update(k)
        return Comprobante(**base)

    cs = [c(), c(tipo_cp="02", serie="E001", numero="9", base_gravada="0", igv="0", inafecto="500", total="500"), c(numero="2")]
    exp = g.generar(libro, cs, "sire")
    assert exp.comprobantes == 2 and exp.resumen["fuera_del_registro"] == 1
    assert b"E001" not in exp.texto and exp.texto.count(b"\r\n") == 2
    # El Excel de CONCAR sí se lo lleva (mismo mes, misma revisión)
    for x in cs:
        imputar(x, cuenta_contable="631101", centro_costo="OBRA01")   # la 631101 lleva centro y CONCAR lo exige (0.8)
    exc = g.generar(libro, cs, "concar", config=con_imputaciones(concar.config_de(None)),
                    correlativos={"11": 1, "15": 1})
    assert exc.comprobantes == 3 and exc.resumen["fuera_del_registro"] == 0
