"""El estándar `open-accounting` y su esquema.

El test que más vale de este archivo es `test_el_esquema_cubre_el_modelo_entero`: si alguien
añade un campo al `Comprobante` y se olvida del esquema, el estándar y el código dejan de decir
lo mismo — que es exactamente la clase de deriva que hace inútil a un formato de intercambio.
"""
from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from contaperu import OPEN_ACCOUNTING
from contaperu.modelo import Comprobante, Libro

from util import GOLDEN

ESQUEMA = Path(__file__).resolve().parents[1] / "estandar" / "open-accounting.schema.json"


@pytest.fixture(scope="module")
def esquema() -> dict:
    return json.loads(ESQUEMA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validador(esquema) -> Draft202012Validator:
    Draft202012Validator.check_schema(esquema)
    return Draft202012Validator(esquema)


def documento(**extra) -> dict:
    base = {
        "open_accounting": OPEN_ACCOUNTING,
        "libro": {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC",
                  "periodo": "202601", "tipo": "compra"},
        "comprobantes": [],
    }
    base.update(extra)
    return base


def test_el_esquema_es_valido(validador):
    assert validador.schema["title"] == "open-accounting"


def test_el_esquema_cubre_el_modelo_entero(esquema):
    """Uno a uno con las dataclasses: ni un campo de más ni uno de menos."""
    for nombre, cls in (("comprobante", Comprobante), ("libro", Libro)):
        del_modelo = {f.name for f in fields(cls)}
        del_esquema = set(esquema["$defs"][nombre]["properties"])
        assert del_modelo == del_esquema, (
            f"{nombre}: falta en el esquema {sorted(del_modelo - del_esquema)}, "
            f"sobra {sorted(del_esquema - del_modelo)}"
        )


@pytest.mark.parametrize("archivo", ["compras_202601.json", "ventas_202512.json"])
def test_los_golden_validan(validador, archivo):
    datos = json.loads((GOLDEN / archivo).read_text(encoding="utf-8"))
    doc = dict({"open_accounting": OPEN_ACCOUNTING}, **datos)
    assert list(validador.iter_errors(doc)) == []


def test_lo_que_produce_el_modelo_valida(validador):
    """Un comprobante serializado con `a_dict()` tiene que caber en el estándar."""
    c = Comprobante(tipo_cp="01", serie="F001", numero="123", fecha_emision="2026-01-10",
                    contraparte_doc="20601111111", contraparte_nombre="PROVEEDOR DE PRUEBA SAC",
                    base_gravada="100", igv="18", total="118",
                    detraccion={"codigo": "027", "porcentaje": 4},
                    condicion_pago="credito", id_externo="fila-123")
    doc = documento(comprobantes=[c.a_dict()])
    assert list(validador.iter_errors(doc)) == []


def test_las_claves_con_guion_bajo_son_anotaciones(validador):
    assert list(validador.iter_errors(documento(_nota="lo que sea"))) == []


def test_se_rechaza_lo_que_no_es_del_estandar(validador):
    """`additionalProperties: false` es a propósito: un campo mal escrito se detecta al
    validar, no meses después cuando alguien note que nunca llegó."""
    malos = [
        documento(comprobantes=[{"tipo_cp": "01", "fecha_emision": "2026-01-10", "total": "1",
                                 "inventado": "x"}]),
        documento(libro={"ruc": "123", "periodo": "202601", "tipo": "compra"}),          # RUC corto
        documento(libro={"ruc": "20601111111", "periodo": "202613", "tipo": "compra"}),  # mes 13
        documento(libro={"ruc": "20601111111", "periodo": "202601", "tipo": "otro"}),
        documento(comprobantes=[{"tipo_cp": "01", "fecha_emision": "10/01/2026", "total": "1"}]),
        documento(comprobantes=[{"tipo_cp": "01", "fecha_emision": "2026-01-10", "total": "-5"}]),
        documento(comprobantes=[{"tipo_cp": "01", "fecha_emision": "2026-01-10", "total": "1",
                                 "condicion_pago": "a 30 dias"}]),                      # ni contado ni credito
    ]
    for doc in malos:
        assert list(validador.iter_errors(doc)), doc


def test_la_version_del_estandar_no_es_la_de_la_libreria(esquema):
    """Se versionan por separado a propósito: la librería puede corregir un driver sin
    que el formato de intercambio cambie."""
    import contaperu

    assert esquema["properties"]["open_accounting"]["const"] == OPEN_ACCOUNTING
    assert contaperu.__version__ != OPEN_ACCOUNTING


def test_la_condicion_de_pago_se_normaliza_y_lo_demas_se_rechaza():
    """Como la escribe una persona («Crédito») se normaliza; lo que no es ninguna de las dos se rechaza al
    construir el comprobante, igual que un `origen` desconocido: mejor fallar que inventar."""
    assert Comprobante(condicion_pago=" Crédito ").condicion_pago == "credito"
    assert Comprobante(condicion_pago="CONTADO").condicion_pago == "contado"
    assert Comprobante().condicion_pago == ""
    with pytest.raises(ValueError, match="condicion_pago"):
        Comprobante(condicion_pago="a 30 dias")


def test_las_decisiones_contables_no_son_del_documento(esquema):
    """Las cuentas viven en la aplicación y llegan aparte, en la imputación (John, 12-sep-2026). Desde open-accounting
    0.3 el comprobante tampoco lleva la cuenta ni el centro, y un documento que todavía los trae se rechaza: perder su
    cuenta en silencio sería peor que no aceptarlo."""
    propiedades = esquema["$defs"]["comprobante"]["properties"]
    assert not {"cuenta_contable", "centro_costo", "cuenta_tercero", "imputaciones", "imputacion",
                "reparto"} & set(propiedades)
    with pytest.raises(ValueError, match="imputación"):
        Comprobante.de_dict({"tipo_cp": "01", "cuenta_contable": "659999"})
    assert Comprobante.de_dict({"tipo_cp": "01", "cuenta_contable": "", "centro_costo": None}).tipo_cp == "01"
