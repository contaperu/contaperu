"""Lo que el motor recibe y devuelve se puede escribir y volver a leer sin perder nada (1.0).

La API de la 1.0 habla en diccionarios, y la puerta HTTP los recibe por JSON: el libro y las líneas del asiento tienen
que ir y volver sin cambiar, y lo que no es de ellos se rechaza en vez de ignorarse. Aquí también se fijan las piezas
que la 1.0 separa sin cambiar comportamiento: el número sin ceros, la numeración en orden, la identidad del comprobante
y la clave estable de cada error.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from contaperu import asiento as asi
from contaperu import api
from contaperu.pipeline import preparacion as prep
from contaperu.asiento.lineas import LineaDiario
from contaperu.configuracion import ConfiguracionInvalida
from contaperu.errores import ErrorContaperu
from contaperu.lectores.xml_ubl import XmlInvalido
from contaperu.modelo import Comprobante, Libro, identidad_de, numero_sin_ceros
from util import GOLDEN

LINEAS = json.loads((Path(__file__).parent / "fixtures" / "snapshot" / "lineas_neutrales.json").read_text(encoding="utf-8"))
COMPRAS = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202608", tipo="compra")


def test_el_libro_va_y_vuelve():
    assert Libro.de_dict(COMPRAS.a_dict()) == COMPRAS
    assert Libro.de_dict({**COMPRAS.a_dict(), "otra": "cosa"}) == COMPRAS       # lo desconocido se ignora


def test_un_libro_incompleto_se_rechaza():
    with pytest.raises(ValueError):
        Libro.de_dict({"ruc": "20601234567"})
    with pytest.raises(ValueError):
        Libro.de_dict(["no", "es", "un", "objeto"])


@pytest.mark.parametrize("caso", sorted(LINEAS))
def test_cada_linea_del_snapshot_va_y_vuelve(caso):
    for linea in LINEAS[caso]:
        assert LineaDiario.de_dict(linea).a_dict() == linea


@pytest.mark.parametrize("linea,motivo", [
    ({"cuenta": "631101", "debe_haber": "X", "importe": "1.00", "clase": "gasto"}, "D o H"),
    ({"cuenta": "631101", "debe_haber": "D", "clase": "gasto"}, "importe"),
    ({"cuenta": "", "debe_haber": "D", "importe": "1.00", "clase": "gasto"}, "cuenta"),
    ({"cuenta": "631101", "debe_haber": "D", "importe": "1.00", "clase": "gasto", "raro": 1}, "raro"),
    # La clase, desde la 1.0: obligatoria y coherente con su cuenta. Sin las dos comprobaciones el lector era más
    # laxo que el esquema que el propio motor publica, y `clase` no podría quedar fuera de la huella.
    ({"cuenta": "631101", "debe_haber": "D", "importe": "1.00"}, "le falta: clase"),
    ({"cuenta": "631101", "debe_haber": "D", "importe": "1.00", "clase": ""}, "le falta: clase"),
    ({"cuenta": "631101", "debe_haber": "D", "importe": "1.00", "clase": "ingreso"}, "es de clase 'gasto'"),
    ({"cuenta": "201101", "debe_haber": "D", "importe": "1.00", "clase": "gasto"}, "es de clase 'activo'"),
    ({"cuenta": "891101", "debe_haber": "D", "importe": "1.00", "clase": "gasto"}, "sin clase contable"),
])
def test_una_linea_que_no_es_del_asiento_se_rechaza(linea, motivo):
    with pytest.raises(ValueError, match=motivo):
        LineaDiario.de_dict(linea)


@pytest.mark.parametrize("numero,esperado", [("00028806", "28806"), ("0000", "0"), (" 12 ", "12"), ("F-001", "F-001"),
                                             ("", "")])
def test_el_numero_sin_ceros(numero, esperado):
    assert numero_sin_ceros(numero) == esperado


def test_numerar_en_orden_da_lo_mismo_que_numerar_sin_depender_de_la_identidad():
    documento = json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8"))
    comprobantes = prep.comprobantes_de(documento)
    config = prep.config_aplicada({"cuentas": {"gasto": "659999"}, "usa_centros_costo": False}, "concar")
    en_orden, rangos = asi.numerar_en_orden(comprobantes, config, "202601", {"11": 5})
    por_id, rangos_viejos = asi.numerar(comprobantes, config, "202601", {"11": 5})
    assert en_orden == ["010005", "010006", "010007"] == [por_id[id(c)] for c in comprobantes]
    assert rangos == rangos_viejos


def test_la_identidad_del_comprobante():
    """Hito 0.0: RUC y tipo del libro, tipo, serie y número sin ceros; en compras, el proveedor; en ventas, no."""
    c = Comprobante(tipo_cp="01", serie="f001", numero="00000123", contraparte_doc="20607777773")
    assert identidad_de(COMPRAS, c) == {"ruc": "20601234567", "libro": "compra", "tipo_cp": "01", "serie": "F001",
                                        "numero": "123", "contraparte_doc": "20607777773"}
    ventas = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202608", tipo="venta")
    assert "contraparte_doc" not in identidad_de(ventas, c)


def test_cada_error_tiene_su_clave_y_conserva_sus_bases():
    assert issubclass(asi.NoExportable, ErrorContaperu) and asi.SinCuenta.clave == "sin_cuenta"
    assert asi.NoExportable.clave == ""                      # la base de las faltas no nombra ninguna
    assert issubclass(ConfiguracionInvalida, ValueError) and ConfiguracionInvalida.clave == "configuracion_invalida"
    assert issubclass(XmlInvalido, ValueError) and XmlInvalido.clave == "xml_invalido"
    assert issubclass(api.DocumentoInvalido, (ErrorContaperu, ValueError)) and api.DocumentoInvalido.clave == "documento_invalido"
