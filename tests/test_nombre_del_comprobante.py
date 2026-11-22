"""Cómo se nombra un comprobante, cómo se lee de vuelta un nombre y qué comprobantes dice un rechazo (15.16.0).

Tres cosas que una aplicación hacía por su cuenta: copiaba el formato de `etiqueta` byte a byte, armaba a mano los
nombres que aceptan sus lotes y no podía saber por HTTP cuáles comprobantes había rechazado el motor. Las pruebas
llaman al código de verdad: el nombre sale de `errores_de` y del rechazo, y las partes se comparan con la clave del
propio comprobante, no con una cuenta rehecha aquí.
"""
from __future__ import annotations

import json

import pytest

from contaperu import api
from contaperu.modelo import Comprobante
from util import GOLDEN, imputando

COMPRA = dict(tipo_cp="01", serie="f001", numero="0000123", contraparte_doc="20602222226")


def _golden() -> dict:
    return imputando(json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8")), "659999")


# --- el nombre -------------------------------------------------------------------------------------------------

def test_el_nombre_es_el_que_ya_daba_errores_de():
    """Es el mismo formato, no uno parecido: una respuesta pública lo llevaba y una aplicación lo copiaba."""
    observado = Comprobante(**COMPRA, total="0")       # sin fecha: FECHA_FALTA, que es un error
    from contaperu.tributos import validar
    from contaperu.modelo import Libro
    validar.validar(observado, Libro(ruc="20601234567", razon_social="X", periodo="202601", tipo="compra"))
    assert observado.tiene_errores
    assert api.errores_de([observado])[0]["comprobante"] == api.nombre_del_comprobante(observado) == "01 F001-0000123"


def test_el_nombre_con_el_documento_delante():
    c = Comprobante(**COMPRA)
    assert api.nombre_del_comprobante(c, con_contraparte=True) == "20602222226 01 F001-0000123"
    # Sin documento no se inventa uno.
    assert api.nombre_del_comprobante(Comprobante(tipo_cp="03", serie="B001", numero="9"), con_contraparte=True) \
        == "03 B001-9"


def test_un_diccionario_se_nombra_igual_que_su_comprobante_y_sin_inventar_el_tipo():
    """Una fila de un ERP no es un `Comprobante`, y no tiene por qué serlo para tener nombre. Y sin tipo, sin tipo:
    el `01` de fábrica del constructor no puede colarse en el nombre de alguien que no lo dijo."""
    fila = {**COMPRA, "tipo_cp": "1", "total": "118.00"}
    assert api.nombre_del_comprobante(fila) == api.nombre_del_comprobante(Comprobante(**COMPRA)) == "01 F001-0000123"
    assert api.nombre_del_comprobante({"serie": "F001", "numero": "7"}) == "F001-7"
    with pytest.raises(ValueError):
        api.nombre_del_comprobante("01 F001-7")


# --- el nombre, leído de vuelta ------------------------------------------------------------------------------

@pytest.mark.parametrize("texto,partes", [
    ("F001-0123", {"tipo_cp": "", "serie": "F001", "numero": "123", "contraparte_doc": ""}),
    ("01 F001-123", {"tipo_cp": "01", "serie": "F001", "numero": "123", "contraparte_doc": ""}),
    ("20602222226 F001-123", {"tipo_cp": "", "serie": "F001", "numero": "123", "contraparte_doc": "20602222226"}),
    ("20602222226 01 F001-0123", {"tipo_cp": "01", "serie": "F001", "numero": "123",
                                  "contraparte_doc": "20602222226"}),
    # Lo que escribe una persona: minúsculas, espacios de más, el tipo sin su cero y el número todo en ceros.
    ("  e001 - 0000 ", {"tipo_cp": "", "serie": "E001", "numero": "0", "contraparte_doc": ""}),
    ("7 fc01-00009", {"tipo_cp": "07", "serie": "FC01", "numero": "9", "contraparte_doc": ""}),
])
def test_lee_lo_que_escribe_una_persona_o_un_erp(texto, partes):
    assert api.leer_nombre_del_comprobante(texto) == partes


def test_las_partes_son_la_clave_del_motor_y_no_una_copia_de_su_regla():
    """El vigilante compara con `Comprobante.clave`, que es lo que decide un duplicado: si la lectura normalizara
    distinto —los ceros, las mayúsculas, el cero del tipo—, un nombre bien escrito no casaría con su comprobante."""
    for campos in (COMPRA, dict(tipo_cp="3", serie="b001", numero="000", contraparte_doc="1234-5678"),
                   dict(tipo_cp="14", serie="0001", numero="0045", contraparte_doc=" 20131312955 ")):
        c = Comprobante(**campos)
        leido = api.leer_nombre_del_comprobante(api.nombre_del_comprobante(c, con_contraparte=True))
        assert tuple(leido.values()) == c.clave, campos


def test_cada_comprobante_del_golden_se_lee_de_vuelta_con_su_clave():
    for nombre in ("compras_202601.json", "ventas_202512.json", "casos_202608.json"):
        documento = json.loads((GOLDEN / nombre).read_text(encoding="utf-8"))
        for c in (Comprobante.de_dict(d) for d in documento["comprobantes"]):
            if not (c.serie and c.numero):
                continue                     # sin serie no hay nombre que leer: ver el caso de abajo
            leido = api.leer_nombre_del_comprobante(api.nombre_del_comprobante(c, con_contraparte=True))
            assert tuple(leido.values()) == c.clave


@pytest.mark.parametrize("texto,dice", [
    ("", "vacío"),
    ("123", "guion"),                        # ¿el 123 de qué serie? Casaría con cualquiera
    ("F001", "guion"),
    ("F001-1-2", "más de un guion"),         # no se sabe dónde acaba la serie
    ("-123", "la serie"),
    ("F001-", "el número"),
    ("FT F001-1", "ni un documento"),        # una sigla de CONCAR no es la Tabla 10
    ("20602222226 FT F001-1", "sigla"),
    ("20602222226 123 F001-1", "Tabla 10"),
    ("a b c F001-1", "a lo sumo tres"),
])
def test_lo_que_no_entiende_lo_dice_y_no_adivina(texto, dice):
    with pytest.raises(ValueError, match=dice):
        api.leer_nombre_del_comprobante(texto)


def test_un_documento_sin_serie_se_nombra_pero_no_se_lee_de_vuelta():
    """Es la asimetría honesta: `serie_y_numero` nombra por su número un documento sin serie, y ese número a secas
    casaría con cualquier comprobante que se numere igual. Se pide por su `id_externo`."""
    c = Comprobante(tipo_cp="14", serie="", numero="12345679")
    assert api.nombre_del_comprobante(c) == "14 12345679"
    with pytest.raises(ValueError, match="id_externo"):
        api.leer_nombre_del_comprobante(api.nombre_del_comprobante(c))


# --- el rechazo dice cuáles -----------------------------------------------------------------------------------

def test_el_rechazo_dice_cuales_comprobantes_y_se_casan_con_los_del_documento():
    documento = _golden()
    with pytest.raises(api.SinCentro) as negado:
        api.exportar(documento, driver="concar", configuracion={})
    problema = api.problema(negado.value)
    assert problema["clave"] == "sin_centro"
    por_id = {c["id_externo"]: Comprobante.de_dict(c) for c in documento["comprobantes"]}
    assert [c["id_externo"] for c in problema["comprobantes"]] == [c.id_externo for c in negado.value.comprobantes]
    assert len(problema["comprobantes"]) == 3
    for dicho in problema["comprobantes"]:
        suyo = por_id[dicho["id_externo"]]
        assert dicho["comprobante"] == api.nombre_del_comprobante(suyo)
        assert tuple(dicho["partes"].values()) == suyo.clave
        assert list(dicho["partes"]) == ["tipo_cp", "serie", "numero", "contraparte_doc"]
    # Los que tienen serie y número se leen de vuelta desde su nombre y su documento.
    con_serie = [d for d in problema["comprobantes"] if d["partes"]["serie"]]
    assert con_serie
    for dicho in con_serie:
        nombre = f'{dicho["partes"]["contraparte_doc"]} {dicho["comprobante"]}'
        assert api.leer_nombre_del_comprobante(nombre) == dicho["partes"]


def test_lo_que_no_es_de_un_comprobante_no_trae_la_lista():
    """Una sigla que falta no es de ningún comprobante: una lista vacía diría «ninguno» donde la verdad es «no es
    cosa de un comprobante». Y un error que no es del motor no enseña nada."""
    assert "comprobantes" not in api.problema(api.SinSigla(["13"]))
    assert "comprobantes" not in api.problema(api.SinCuenta([]))
    assert "comprobantes" not in api.problema(ValueError("algo"))
    assert "comprobantes" not in api.problema(RuntimeError("interno"))


def test_no_cabe_dice_cada_comprobante_una_vez():
    c = Comprobante(**COMPRA, id_externo="x1")
    problema = api.problema(api.NoCabe({"moneda": [c], "largo": [c]}))
    assert [d["id_externo"] for d in problema["comprobantes"]] == ["x1"]
