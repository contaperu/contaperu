"""La imputación dentro del documento (1.0): que dé lo mismo que por el argumento, y que lo que no puede casarse se
rechace en la puerta.

Desde la 1.0 la imputación viaja en el bloque `imputaciones` del documento, para que un archivo guardado explique su
propio asiento. El argumento se conserva, así que lo primero que hay que probar es que **las dos vías dan lo mismo por
todas las operaciones**: una vía que ignore el bloque en silencio contabilizaría con la cuenta por defecto, sin error
y sin aviso. Ya pasó una vez con `revisar`, que llamaba a `con_imputacion` y descartaba el resultado.
"""
from __future__ import annotations

import json

import jsonschema
import pytest

from contaperu import api
from contaperu.errores import DocumentoInvalido
from test_caracterizacion import IMPUTACION_CASOS
from util import GOLDEN

# La configuración de `casos_202608.json` en la caracterización: lo general por defecto. Su imputación es la de
# siempre, con el reparto de un comprobante, porque es el único golden cuyos doce comprobantes traen `id_externo`.
CONFIG: dict = {}
OPERACIONES = ("revisar", "diagnosticar", "generar_asiento", "exportar")


def casos() -> dict:
    """El golden que trae `id_externo` en sus doce comprobantes, que es el que puede llevar imputaciones."""
    return json.loads((GOLDEN / "casos_202608.json").read_text(encoding="utf-8"))


def llamar(nombre: str, en_el_documento: bool, **kwargs):
    """La operación con la imputación por dentro del documento o por el argumento, según se pida."""
    documento, imputacion = casos(), dict(IMPUTACION_CASOS)
    if en_el_documento:
        documento = dict(documento, imputaciones=imputacion)
    else:
        kwargs["imputacion"] = imputacion
    if nombre != "revisar":
        kwargs.setdefault("driver", "concar")
    return getattr(api, nombre)(documento, configuracion=CONFIG, **kwargs)


@pytest.mark.parametrize("operacion", OPERACIONES)
def test_las_dos_vias_dan_exactamente_lo_mismo(operacion):
    """El corazón de esta parte: la imputación en el documento y la imputación en el argumento son la misma cosa.

    Se compara todo menos los bytes del archivo, que en un Excel llevan la hora dentro del zip y por tanto cambian
    entre dos llamadas seguidas. Lo que dice si el contenido es el mismo es la huella, y va aparte."""
    por_dentro = llamar(operacion, en_el_documento=True)
    por_fuera = llamar(operacion, en_el_documento=False)
    sin_bytes = {"contenido_base64", "texto"}
    assert {k: v for k, v in por_dentro.items() if k not in sin_bytes} == \
           {k: v for k, v in por_fuera.items() if k not in sin_bytes}


def test_la_huella_no_depende_de_por_donde_llego_la_imputacion():
    """Si dependiera, quien cambiara de vía vería su mes entero como «cambiado»."""
    argumento = llamar("exportar", en_el_documento=False)
    documento = llamar("exportar", en_el_documento=True)
    assert documento["_exportacion"]["huella"] == argumento["_exportacion"]["huella"]


def test_las_dos_formas_a_la_vez_se_rechazan():
    """Adivinar cuál manda sería elegir en silencio la cuenta de un comprobante."""
    doc = dict(casos(), imputaciones={"c07": {"cuenta_contable": "6321001"}})
    with pytest.raises(DocumentoInvalido, match="llega dos veces"):
        api.diagnosticar(doc, driver="concar", configuracion=CONFIG,
                         imputacion={"c07": {"cuenta_contable": "6321001"}})


def test_una_llave_que_no_es_de_ningun_comprobante_se_rechaza():
    doc = dict(casos(), imputaciones={"fila-que-no-existe": {"cuenta_contable": "6343001"}})
    with pytest.raises(DocumentoInvalido, match="documentos que no están"):
        api.diagnosticar(doc, driver="concar", configuracion=CONFIG)


def test_un_comprobante_sin_id_externo_se_rechaza_nombrandolo():
    """La llave es el `id_externo`: sin él no hay con qué casar la decisión, y el mensaje dice qué comprobante es."""
    doc = casos()
    doc["comprobantes"][0] = {k: v for k, v in doc["comprobantes"][0].items() if k != "id_externo"}
    doc["imputaciones"] = {"c02": {"cuenta_contable": "6343001"}}
    with pytest.raises(DocumentoInvalido, match="cada comprobante necesita su `id_externo`"):
        api.diagnosticar(doc, driver="concar", configuracion=CONFIG)


def test_dos_comprobantes_con_el_mismo_id_externo_se_rechazan():
    """Lo que el esquema no puede decir: con la llave repetida, la misma decisión se aplicaría a dos comprobantes."""
    doc = casos()
    doc["comprobantes"][1]["id_externo"] = doc["comprobantes"][0]["id_externo"]
    doc["imputaciones"] = {doc["comprobantes"][0]["id_externo"]: {"cuenta_contable": "6343001"}}
    with pytest.raises(DocumentoInvalido, match="comparten `id_externo`"):
        api.diagnosticar(doc, driver="concar", configuracion=CONFIG)


def test_por_el_argumento_no_se_exige_el_id_a_todos():
    """La única asimetría entre las dos vías, y es a propósito: por el argumento se puede imputar 3 de 10 y que los
    otros 7 no traigan id. Exigirlo ahí sería cambiar en silencio lo que ya funciona."""
    doc = casos()
    con_id = doc["comprobantes"][0]["id_externo"]
    doc["comprobantes"][1] = {k: v for k, v in doc["comprobantes"][1].items() if k != "id_externo"}
    api.diagnosticar(doc, driver="concar", configuracion=CONFIG,
                     imputacion={con_id: {"cuenta_contable": "6343001"}})


def test_imputaciones_sigue_prohibida_en_la_configuracion():
    """Son dos sitios distintos: la configuración es del entorno y la imputación es de cada comprobante."""
    assert api.errores_de_configuracion({"imputaciones": {}}) == [
        "`imputaciones` no va en la configuración: la imputación de cada documento llega en el bloque "
        "`imputaciones` del documento o en el argumento `imputacion`"]


# ── El esquema ────────────────────────────────────────────────────────────────────────────────────────────────

BASE = {"libro": {"ruc": "20601234567", "periodo": "202601", "tipo": "compra"}}
COMPROBANTE = {"tipo_cp": "01", "fecha_emision": "2026-01-15", "total": "118.00"}


def documento(**kw) -> dict:
    return dict(BASE, open_accounting=api.OPEN_ACCOUNTING, **kw)


@pytest.mark.parametrize("descripcion,doc,valido", [
    ("sin imputaciones no se pide id_externo", documento(comprobantes=[COMPROBANTE]), True),
    ("con imputaciones y con id_externo",
     documento(comprobantes=[dict(COMPROBANTE, id_externo="c1")], imputaciones={"c1": {"cuenta_contable": "6"}}), True),
    ("con imputaciones y sin id_externo",
     documento(comprobantes=[COMPROBANTE], imputaciones={"c1": {}}), False),
    ("con imputaciones y id_externo vacío",
     documento(comprobantes=[dict(COMPROBANTE, id_externo="")], imputaciones={"c1": {}}), False),
    ("imputaciones vacías no disparan la condición",
     documento(comprobantes=[COMPROBANTE], imputaciones={}), True),
    ("una clave inventada dentro de la imputación",
     documento(comprobantes=[dict(COMPROBANTE, id_externo="c1")], imputaciones={"c1": {"cuenta": "6"}}), False),
    ("una llave vacía en imputaciones",
     documento(comprobantes=[dict(COMPROBANTE, id_externo="c1")], imputaciones={"": {}}), False),
    ("el reparto con su importe", documento(comprobantes=[dict(COMPROBANTE, id_externo="c1")],
     imputaciones={"c1": {"reparto": [{"importe": "100.00", "cuenta_contable": "636301"}]}}), True),
])
def test_el_esquema_exige_el_id_externo_solo_cuando_hay_imputaciones(descripcion, doc, valido):
    errores = list(jsonschema.Draft202012Validator(api.esquema_open_accounting()).iter_errors(doc))
    assert (errores == []) is valido, f"{descripcion}: {[e.message for e in errores]}"


# ── El enlace de la línea ─────────────────────────────────────────────────────────────────────────────────────

def test_cada_linea_lleva_el_id_externo_de_su_comprobante():
    """El enlace exacto entre la línea, el comprobante y su imputación, sin depender de la serie y el número."""
    asiento = llamar("generar_asiento", en_el_documento=True)["asiento"]
    ids = {ln["documento"].get("id_externo") for ln in asiento if ln.get("documento")}
    assert ids and "" not in ids, "toda línea de un comprobante con id lo lleva en su bloque documento"
    comprobantes = {c["id_externo"] for c in casos()["comprobantes"]}
    assert ids <= comprobantes, "el id de una línea es el de un comprobante del documento"


def test_el_id_de_la_linea_no_entra_en_la_huella():
    """Es un puntero al sistema que produjo el comprobante, no contenido contable — y sobre todo: al reexportar tras
    un «deshacer» la aplicación recrea sus filas con ids nuevos, así que con el id dentro el aviso de lote repetido se
    apagaría justo en el caso para el que la huella existe."""
    from contaperu.asiento import huella

    original = llamar("generar_asiento", en_el_documento=True)["asiento"]
    otros_ids = [dict(ln, documento=dict(ln["documento"], id_externo="otro")) if ln.get("documento") else ln
                 for ln in original]
    assert huella(otros_ids) == huella(original)
    # Y la prueba de que el filtro por rutas hace algo: cambiar la serie-número del mismo bloque SÍ la mueve.
    otra_serie = [dict(ln, documento=dict(ln["documento"], serie_numero="X999-1")) if ln.get("documento") else ln
                  for ln in original]
    assert huella(otra_serie) != huella(original)
