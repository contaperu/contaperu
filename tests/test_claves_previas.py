"""Hito 0.1: lo ya anotado en otros periodos del mismo RUC entra por las tres puertas y detiene el duplicado, como lo
detendría SUNAT (error 452). Hito 0.0: la identidad con que se compara —en ventas, sin el cliente—.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from contaperu import api
from contaperu.pipeline import preparacion
from contaperu.puertas import cli
from util import GOLDEN, imputando

# Desde la 3.0 la cuenta es del comprobante: los documentos de estas pruebas la traen con `imputando`.
CONFIG = {"usa_centros_costo": False}


def _golden(nombre: str) -> dict:
    return imputando(json.loads((GOLDEN / nombre).read_text(encoding="utf-8")), "659999")


def _previa(c: dict, **cambios) -> list[str]:
    """La clave de un comprobante como la guardaría quien la persiste, con el número lleno de ceros."""
    clave = {"tipo_cp": c["tipo_cp"], "serie": c["serie"], "numero": "0000" + c["numero"].lstrip("0"),
             "contraparte_doc": c.get("contraparte_doc", "")}
    clave.update(cambios)
    return [clave["tipo_cp"], clave["serie"], clave["numero"], clave["contraparte_doc"]]


def _codigos(documento: dict, posicion: int = 0) -> list[str]:
    return [o["codigo"] for o in documento["comprobantes"][posicion]["observaciones"]]


def test_por_la_api_el_comprobante_ya_anotado_bloquea_y_se_pide_al_contador():
    documento = _golden("compras_202601.json")
    previa = _previa(documento["comprobantes"][0])
    revisado = api.revisar(documento, claves_previas=[previa])
    assert "DUPLICADO_PERIODO_ANTERIOR" in _codigos(revisado) and revisado["comprobantes"][0]["estado"] == "duplicada"
    assert "DUPLICADO_PERIODO_ANTERIOR" not in _codigos(revisado, 1)
    diagnostico = api.diagnosticar(documento, driver="concar", configuracion=CONFIG, claves_previas=[previa])
    [falta] = [f for f in diagnostico["que_falta"] if f["motivo"] == "DUPLICADO_PERIODO_ANTERIOR"]
    assert falta["pedir_a"] == "contador" and not diagnostico["listo_para_exportar"]
    with pytest.raises(api.DocumentoInvalido, match="observaciones que bloquean"):
        api.exportar(documento, driver="concar", configuracion=CONFIG, claves_previas=[previa])


def test_sin_claves_previas_todo_sale_igual():
    documento = _golden("compras_202601.json")
    con = api.exportar(documento, driver="csv", configuracion=CONFIG, claves_previas=[])
    assert con == api.exportar(documento, driver="csv", configuracion=CONFIG)


def test_por_el_mcp():
    pytest.importorskip("mcp")
    from contaperu.puertas.servidor_mcp import mcp

    documento = _golden("compras_202601.json")
    argumentos = {"documento": documento, "driver": "concar", "configuracion": CONFIG,
                  "claves_previas": [_previa(documento["comprobantes"][0])]}
    diagnostico = json.loads(asyncio.run(mcp.call_tool("diagnosticar", argumentos)).content[0].text)
    assert "DUPLICADO_PERIODO_ANTERIOR" in [f["motivo"] for f in diagnostico["que_falta"]]
    revisado = json.loads(asyncio.run(mcp.call_tool("validar_comprobantes", {
        "documento": documento, "claves_previas": argumentos["claves_previas"]})).content[0].text)
    assert "DUPLICADO_PERIODO_ANTERIOR" in _codigos(revisado)


def test_por_la_terminal(tmp_path, capsys):
    documento = _golden("compras_202601.json")
    rutas = {nombre: tmp_path / f"{nombre}.json" for nombre in ("documento", "config", "previas")}
    rutas["documento"].write_text(json.dumps(documento), encoding="utf-8")
    rutas["config"].write_text(json.dumps(CONFIG), encoding="utf-8")
    rutas["previas"].write_text(json.dumps([_previa(documento["comprobantes"][0])]), encoding="utf-8")
    comun = ["--config", str(rutas["config"]), "--claves-previas", str(rutas["previas"])]
    assert cli.main(["diagnosticar", str(rutas["documento"]), *comun]) == 1
    assert "DUPLICADO_PERIODO_ANTERIOR" in capsys.readouterr().out
    assert cli.main(["desde-json", str(rutas["documento"]), "--driver", "csv", "--salida", str(tmp_path / "s"),
                     *comun]) == 1
    assert "observaciones que bloquean" in capsys.readouterr().err and not (tmp_path / "s").exists()


def test_por_encima_del_tope_o_mal_escritas_se_rechazan(monkeypatch):
    documento = _golden("compras_202601.json")
    assert api.MAXIMO_CLAVES_PREVIAS == 50000
    monkeypatch.setattr(preparacion, "MAXIMO_CLAVES_PREVIAS", 1)
    with pytest.raises(api.DocumentoInvalido, match="el tope es 1"):
        api.revisar(documento, claves_previas=[["01", "F001", "1", ""], ["01", "F001", "2", ""]])
    for malas in ("01-F001-1", [["01", "F001"]], [{"tipo_cp": "01"}]):
        with pytest.raises(api.DocumentoInvalido, match="clave"):
            api.revisar(documento, claves_previas=malas)


def test_en_ventas_el_cliente_no_cuenta_y_en_compras_el_proveedor_si():
    ventas = _golden("ventas_202512.json")
    otro_cliente = _previa(ventas["comprobantes"][0], contraparte_doc="20131312955")
    assert "DUPLICADO_PERIODO_ANTERIOR" in _codigos(api.revisar(ventas, claves_previas=[otro_cliente]))
    compras = _golden("compras_202601.json")
    otro_proveedor = _previa(compras["comprobantes"][0], contraparte_doc="20131312955")
    assert "DUPLICADO_PERIODO_ANTERIOR" not in _codigos(api.revisar(compras, claves_previas=[otro_proveedor]))
