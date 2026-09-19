"""La batería de conformidad del estándar (hito E2), corrida contra el propio motor.

Existe para que **un tercero pueda comprobar que lo que produce es correcto sin escribirle a nadie**. Hasta ahora
había dos piezas —`diagnosticar`, que valida un documento, y `verificar-driver`, que valida un driver— y faltaba la
tercera: un juego de casos con lo que debe salir.

Vive en `estandar/conformidad/`, se publica con el tag del estándar y se cita como se cita el esquema. Los casos de
esquema se corren **sin el motor**, con cualquier validador de draft 2020-12; los de `diagnosticar` necesitan un motor,
y este archivo los corre contra el de aquí: **si el motor no pasa su propia conformidad, no la pasa nadie.**
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

from contaperu import api
from contaperu.errores import ErrorContaperu

CONFORMIDAD = Path(__file__).resolve().parent.parent / "estandar" / "conformidad"
ESQUEMA = json.loads((CONFORMIDAD / "esquema.json").read_text(encoding="utf-8"))
DIAGNOSTICAR = json.loads((CONFORMIDAD / "diagnosticar.json").read_text(encoding="utf-8"))


def ids(casos):
    return [c["description"][:70] for c in casos]


# ── Los casos de esquema: sin el motor ────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("caso", ESQUEMA["casos"], ids=ids(ESQUEMA["casos"]))
def test_los_casos_de_esquema(caso):
    """Se corren con el validador y nada más: es lo que permite que un ERP en otro lenguaje los use tal cual."""
    validador = jsonschema.Draft202012Validator(api.esquema_open_accounting())
    errores = [e.message for e in validador.iter_errors(caso["data"])]
    if caso["valid"]:
        assert errores == [], caso["description"]
    else:
        assert errores != [], f"debería rechazarse y no se rechazó: {caso['description']}"


def test_los_casos_de_esquema_cubren_lo_que_esta_investigacion_descubrio():
    """Cada uno de estos sale de algo que se equivocó de verdad al escribir la 1.0. Si alguien los quita, el caso
    vuelve a poder romperse en silencio."""
    descripciones = " ".join(c["description"] for c in ESQUEMA["casos"]).lower()
    for imprescindible in ("detraccion: false", "imputaciones", "id_externo", "clase", "degradación",
                           "positivo", "guion bajo"):
        assert imprescindible.lower() in descripciones, f"falta el caso de: {imprescindible}"


# ── Los casos de `diagnosticar`: contra el motor ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("caso", DIAGNOSTICAR["casos"], ids=ids(DIAGNOSTICAR["casos"]))
def test_los_casos_de_diagnosticar(caso):
    espera = caso["espera"]
    if "error" in espera:
        with pytest.raises(ErrorContaperu, match=re.escape(espera["error"])):
            api.diagnosticar(caso["documento"], driver=caso["driver"], configuracion=caso["configuracion"])
        return

    d = api.diagnosticar(caso["documento"], driver=caso["driver"], configuracion=caso["configuracion"])
    if "listo_para_exportar" in espera:
        assert d["listo_para_exportar"] is espera["listo_para_exportar"], d["por_que_no"]
    if "por_que_no" in espera:
        assert d["por_que_no"] == espera["por_que_no"]
    for clave, esperado in (espera.get("faltantes") or {}).items():
        assert d["faltantes"].get(clave) == esperado, d["faltantes"]
    if espera.get("faltantes") == {}:
        assert all(v == [] for v in d["faltantes"].values()), d["faltantes"]
    for clave, quien in (espera.get("pedir_a") or {}).items():
        from contaperu.pipeline import diagnostico as diag
        assert diag.PEDIR_A[clave] == quien
    for codigo in espera.get("observaciones") or []:
        # El diagnóstico lleva las observaciones de cada comprobante; basta con que el código aparezca.
        assert codigo in json.dumps(d, ensure_ascii=False), f"no se observó {codigo}"
    if "fuera_del_destino" in espera:
        assert d["totales"]["fuera_del_destino"] == espera["fuera_del_destino"]
    if "detracciones_pendientes" in espera:
        assert len(d["detracciones_pendientes"]) == espera["detracciones_pendientes"]


def test_hay_un_caso_por_falta_que_el_motor_puede_declarar():
    """El criterio de salida del hito: que la batería no deje una falta sin caso. Las que aquí no aparecen son las que
    ningún destino de serie exige todavía, y se nombran para que se vea que es a propósito."""
    from contaperu import asiento as asi

    con_caso = {clave for c in DIAGNOSTICAR["casos"] for clave in (c["espera"].get("faltantes") or {})}
    sin_caso = {f.clave for f in asi.FALTAS} - con_caso
    assert sin_caso == {"sin_sigla", "sin_codigo_de_moneda", "reparto_no_admitido", "reparto_que_no_cuadra",
                        "sin_centro", "sin_correlativo", "no_cabe"}, sin_caso


def test_la_conformidad_viaja_con_el_estandar():
    """Se publica con el tag, así que se cita como el esquema: `.../open-accounting-1.0/estandar/conformidad/`."""
    assert (CONFORMIDAD / "esquema.json").is_file() and (CONFORMIDAD / "diagnosticar.json").is_file()
    for archivo in (ESQUEMA, DIAGNOSTICAR):
        assert archivo["_nota"].strip(), "cada archivo de conformidad dice para qué es"
