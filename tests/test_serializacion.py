"""Lo que el motor recibe y devuelve se puede escribir y volver a leer sin perder nada (1.0).

La API de la 1.0 habla en diccionarios, y la puerta HTTP los recibe por JSON: el libro y las líneas del asiento tienen
que ir y volver sin cambiar, y lo que no es de ellos se rechaza en vez de ignorarse. Aquí también se fijan las piezas
que la 1.0 separa sin cambiar comportamiento: el número sin ceros, la numeración en orden, la identidad del comprobante
y la clave estable de cada error.
"""
from __future__ import annotations

import json
from decimal import Decimal
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

LINEAS = json.loads((Path(__file__).parent / "fixtures" / "snapshot" / "lineas_legacy.json").read_text(encoding="utf-8"))
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


def test_un_comprobante_con_una_clave_que_no_es_suya_se_rechaza():
    """Una clave que el estándar no declara se rechaza en vez de ignorarse (4.0), que es lo que `INTEGRAR.md` promete:
    «un dato que se cuela sin error es un dato que se pierde sin aviso».

    Pasaba de verdad, y así se encontró: un `retencion_4ta` donde el campo se llama `retencion` exportaba el mes
    entero **sin la línea de retención de 4ta**, y solo se veía leyendo las celdas del Excel. Además dejaba al lector
    más laxo que el esquema publicado, que ya rechaza por su `additionalProperties: false`.

    **Y desde la 5.0 el ejemplo vale por otro motivo, que conviene dejar escrito.** El rol se renombró a `retencion`,
    así que `retencion_4ta` ya no es ni un campo ni un rol: es un nombre muerto, y el de alguien que escriba desde una
    integración vieja. Que siga fallando en voz alta es justo lo que hace falta. Lo que ya no protege es la diferencia
    de nombre —el rol y el campo se llaman igual ahora, como `detraccion`, que es campo, bloque y rol a la vez—, sino
    que el comprobante rechace cualquier clave que no sea suya, que es lo que este test fija."""
    base = {"tipo_cp": "01", "serie": "F001", "numero": "1", "total": "118"}

    with pytest.raises(ValueError, match="retencion_4ta"):
        Comprobante.de_dict({**base, "retencion_4ta": "240"})
    # Las nombra TODAS y ordenadas, no revienta en la primera, y dice adónde va lo que el motor no entiende.
    with pytest.raises(ValueError, match="aaa, zzz.*datos_originales"):
        Comprobante.de_dict({**base, "zzz": 1, "aaa": 2})
    # Una anotación `_` tampoco pasa AQUÍ: el estándar las admite en la raíz y dentro de la detracción, no en un
    # comprobante. Dejarla pasar volvería a poner el lector por delante del esquema.
    with pytest.raises(ValueError, match="_lo_mio"):
        Comprobante.de_dict({**base, "_lo_mio": "x"})

    # Y lo que sí tiene sitio declarado sigue entrando, con lo que sea dentro: es la salida que el mensaje enseña.
    c = Comprobante.de_dict({**base, "datos_originales": {"erp": {"folio": 9}}})
    assert c.datos_originales == {"erp": {"folio": 9}} and c.total == Decimal("118")


@pytest.mark.parametrize("numero,esperado", [("00028806", "28806"), ("0000", "0"), (" 12 ", "12"), ("F-001", "F-001"),
                                             ("", "")])
def test_el_numero_sin_ceros(numero, esperado):
    assert numero_sin_ceros(numero) == esperado


def test_numerar_en_orden_da_lo_mismo_que_numerar_sin_depender_de_la_identidad():
    documento = json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8"))
    comprobantes = prep.comprobantes_de(documento)
    config = prep.config_aplicada({"usa_centros_costo": False}, "concar")
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
