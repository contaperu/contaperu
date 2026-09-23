"""Hito B6: la guía para integrar el motor en un ERP (`INTEGRAR.md`) funciona tal como está escrita.

Sus bloques de Python se ejecutan en orden, su petición HTTP de ejemplo valida contra OpenConta y responde por la puerta,
y cada comando que nombra existe. Una guía que deja de funcionar es peor que no tener guía.
"""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

RAIZ = Path(__file__).resolve().parents[1]
GUIA = (RAIZ / "INTEGRAR.md").read_text(encoding="utf-8")


def _bloques(lenguaje: str) -> list[str]:
    return re.findall(rf"```{lenguaje}\n(.*?)```", GUIA, flags=re.S)


def _peticiones() -> list[dict]:
    return [json.loads(bloque) for bloque in _bloques("json") if '"documento"' in bloque]


def test_los_ejemplos_de_python_se_ejecutan_en_orden(monkeypatch, capsys):
    monkeypatch.chdir(RAIZ)
    bloques = _bloques("python")
    assert len(bloques) >= 3
    espacio: dict = {}
    for numero, bloque in enumerate(bloques, 1):
        exec(compile(bloque, f"INTEGRAR.md, bloque {numero}", "exec"), espacio)
    salida = capsys.readouterr().out
    assert "concar" in salida.lower() and "sin_centro" in salida


def test_la_peticion_http_de_ejemplo_valida_contra_openconta_y_responde():
    contrato = json.loads((RAIZ / "contaperu" / "api" / "openconta.json").read_text(encoding="utf-8"))
    peticiones = _peticiones()
    assert peticiones
    for peticion in peticiones:
        Draft202012Validator({**contrato, "$ref": "#/components/schemas/diagnosticar_entrada"}).validate(peticion)
    pytest.importorskip("starlette")
    pytest.importorskip("httpx")
    from starlette.testclient import TestClient

    from contaperu.puertas import servidor_http

    cliente = TestClient(servidor_http.crear_app(), base_url="http://localhost:8080")
    for peticion in peticiones:
        respuesta = cliente.post("/v1/diagnosticar", json=peticion)
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["listo_para_exportar"] is True


def test_cada_comando_que_nombra_existe():
    import tomllib

    from contaperu.puertas import cli

    scripts = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    subcomandos = {"generar", "desde-json", "diagnosticar", "configuracion", "comparar", "verificar-documento"}
    for bloque in _bloques("bash"):
        for linea in bloque.splitlines():
            partes = shlex.split(linea) if linea.strip() else []
            if not partes or not partes[0].startswith("contaperu"):
                continue
            assert partes[0] in scripts, partes[0]
            if partes[0] == "contaperu":
                assert partes[1] in subcomandos, linea
    assert "--claves-previas" in (RAIZ / "contaperu" / "puertas" / "cli.py").read_text(encoding="utf-8")
    assert callable(cli.main)
