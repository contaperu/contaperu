"""`medio_pago`: con qué se pagó la operación, de punta a punta (3.3, enmienda 0004).

El campo llevaba desde el 12-sep-2026 reservado en el estándar esperando **una decisión**, no un caso: si era dato de
cada documento o un valor del contribuyente. Los dos, decidió John el 25-sep-2026 — el documento manda y la
configuración del sistema contable es el respaldo—, y este archivo es esa decisión hecha pruebas.

La otra mitad de la decisión: un código que no está en el catálogo de SUNAT **avisa y se respeta**. El medio de pago
no cambia ningún asiento ni ningún importe, así que no puede frenar el mes de nadie; y SUNAT puede añadir códigos.
"""
from __future__ import annotations

import pytest

from contaperu import api, asiento, catalogos, validar
from contaperu.drivers import contasis
from contaperu.modelo import Comprobante, Libro
from contaperu.pipeline import preparacion as prep

LIBRO = {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608", "tipo": "venta"}
FACTURA = {"tipo_cp": "01", "serie": "F001", "numero": "123", "fecha_emision": "2026-08-11",
           "contraparte_tipo_doc": "6", "contraparte_doc": "20602222226", "contraparte_nombre": "CLIENTE SAC",
           "moneda": "PEN", "base_gravada": "100", "igv": "18", "total": "118", "concepto": "SERVICIO"}


def documento(**extra) -> dict:
    return {"open_accounting": "1.0", "libro": dict(LIBRO), "comprobantes": [dict(FACTURA, **extra)]}


# --- el estándar: qué admite y qué no ----------------------------------------------------------------------------

@pytest.mark.parametrize("codigo", ["001", "003", "005", "999", ""])
def test_el_estandar_admite_un_codigo_del_catalogo_y_el_vacio(codigo: str):
    """Vacío es un valor con sentido: el documento no dice con qué se pagó."""
    assert api.verificar_documento(documento(medio_pago=codigo))["conforme"] is True


@pytest.mark.parametrize("codigo", ["3", "0001", "efectivo", "00A"])
def test_el_estandar_rechaza_lo_que_no_tiene_forma_de_codigo(codigo: str):
    """La FORMA la cuida el esquema —tres dígitos—; el significado lo cuida el catálogo, y avisa en vez de romper."""
    assert api.verificar_documento(documento(medio_pago=codigo))["conforme"] is False


def test_un_codigo_de_tres_digitos_que_SUNAT_todavia_no_tiene_valida():
    """La decisión que separa la forma del significado: `014` no existe hoy y el documento es válido igual. El día
    que SUNAT lo cree, quien ya lo usaba no tiene que cambiar nada."""
    assert api.verificar_documento(documento(medio_pago="014"))["conforme"] is True


# --- el catálogo: lo que avisa -----------------------------------------------------------------------------------

def _revisado(**extra) -> Comprobante:
    c = Comprobante(**dict(FACTURA, **extra))
    validar.validar(c, Libro(**LIBRO))
    return c


def test_un_codigo_que_no_esta_en_el_catalogo_avisa_y_se_respeta():
    """Aviso, no error: el mes sale igual. Es la decisión de John del 25-sep-2026."""
    c = _revisado(medio_pago="014")
    observacion = next(o for o in c.observaciones if o.codigo == "MEDIO_PAGO_DESCONOCIDO")
    assert observacion.nivel == "aviso"
    assert c.medio_pago == "014", "el valor se respeta: no se borra ni se sustituye"
    assert not c.tiene_errores


def test_un_codigo_del_catalogo_no_dice_nada():
    for codigo in ("001", "003", "005", "999"):
        assert [o.codigo for o in _revisado(medio_pago=codigo).observaciones] == []


def test_sin_medio_de_pago_no_hay_aviso():
    """Lo normal: el documento no lo dice, y eso no es un problema de nadie."""
    assert [o.codigo for o in _revisado().observaciones] == []


def test_el_aviso_no_bloquea_la_exportacion():
    d = api.diagnosticar(documento(medio_pago="014"), driver="sire")
    assert d["listo_para_exportar"] is True
    assert "MEDIO_PAGO_DESCONOCIDO" in [o["codigo"] for a in d["avisos"] for o in a["observaciones"]]


# --- el hecho llega al driver ------------------------------------------------------------------------------------

def test_el_medio_de_pago_llega_a_la_cabecera_del_asiento():
    """La regla de `tests/test_cabecera.py`: todo hecho del comprobante llega al driver, o el próximo descubre —como
    STARSOFT— que el dato existe en el estándar y se cae por el camino."""
    c = Comprobante(**dict(FACTURA, medio_pago="003"))
    assert asiento.cabecera_de(c).medio_pago == "003"


def test_en_CONTASIS_manda_el_documento_y_la_configuracion_es_el_respaldo():
    """Las dos mitades de la decisión, en la única columna que hoy lo escribe (AN de su registro de ventas)."""
    config = prep.config_aplicada({"contasis": {"medio_pago": "003"}}, "contasis")
    libro = Libro(**LIBRO)

    del_entorno = Comprobante(**dict(FACTURA, id_externo="f1"))
    del_documento = Comprobante(**dict(FACTURA, id_externo="f2", medio_pago="005"))
    imputacion = {"f1": {"cuenta_contable": "701101"}, "f2": {"cuenta_contable": "701101"}}
    config = {**config, "imputaciones": imputacion}

    assert contasis.fila(del_entorno, libro, config)["AN"] == "003"
    assert contasis.fila(del_documento, libro, config)["AN"] == "005"


def test_el_catalogo_y_el_campo_hablan_del_mismo_codigo():
    """Un catálogo que el validador no consultara sería decoración. `005` es tarjeta de débito, y es el que casi
    entra mal en el motor."""
    assert catalogos.MEDIOS_PAGO["005"] == "Tarjeta de débito"
    assert _revisado(medio_pago="005").observaciones == []
