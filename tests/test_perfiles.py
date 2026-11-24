"""B10: qué publica el servidor abierto y qué solo un integrador, y las perillas con que se elige (16.0).

El criterio de salida del hito era este: **una operación de integrador no aparece en el servidor público, y la foto del
MCP lo fija**. Hoy las 18 son públicas, así que se prueba con una sintética: la tabla con una operación pasada a
integrador, por las dos puertas.
"""
from __future__ import annotations

import asyncio
import dataclasses

import pytest

from contaperu import agentes, api
from contaperu.agentes import DEL_MOTOR
from contaperu.agentes.servidor import crear_servidor
from contaperu.api import textos
from contaperu.api.tabla import PERFILES, Operacion


def nombres(servidor) -> list[str]:
    return [h.name for h in asyncio.run(servidor.list_tools())]


def con_una_de_integrador(monkeypatch) -> None:
    """La tabla de hoy con `estado_de_cuenta` pasada a integrador, como lo estaría una que armara peticiones con
    credenciales."""
    tabla = tuple(dataclasses.replace(op, perfil="integrador", por_que_integrador="necesita las credenciales del RUC")
                  if op.nombre == "estado_de_cuenta" else op for op in api.OPERACIONES)
    monkeypatch.setattr(api, "OPERACIONES", tabla)


def test_una_operacion_de_integrador_dice_por_que_y_solo_ella():
    with pytest.raises(ValueError, match="dice por qué no sale en el servidor abierto"):
        Operacion("x", "POST", "/v1/x", perfil="integrador")
    with pytest.raises(ValueError, match="solo ella lo dice"):
        Operacion("x", "POST", "/v1/x", por_que_integrador="porque sí")
    with pytest.raises(ValueError, match="no es uno de"):
        Operacion("x", "POST", "/v1/x", perfil="privado")
    assert all(op.perfil == "publico" and not op.por_que_integrador for op in api.OPERACIONES), "hoy todas son públicas"


def test_la_api_y_la_base_dicen_los_mismos_perfiles():
    """La api no puede importar la base, que está encima: los dos los escriben, y esto los ata."""
    assert agentes.PERFILES == PERFILES == ("publico", "integrador")


def test_lo_de_un_integrador_no_sale_en_el_servidor_publico(monkeypatch):
    con_una_de_integrador(monkeypatch)
    publico = nombres(crear_servidor())
    assert "estado_de_cuenta" not in publico and len(publico) == 17
    integrador = nombres(crear_servidor(perfil="integrador"))
    assert "estado_de_cuenta" in integrador and len(integrador) == 18, "el perfil integrador incluye al público"


def test_ni_por_la_puerta_http(monkeypatch):
    pytest.importorskip("starlette")
    pytest.importorskip("httpx")
    from starlette.testclient import TestClient

    from contaperu.puertas import servidor_http

    con_una_de_integrador(monkeypatch)
    publica = TestClient(servidor_http.crear_app(), base_url="http://localhost:8080")
    assert publica.post("/v1/estado_de_cuenta", json={}).status_code == 404
    assert publica.post("/v1/por_pagar", json={}).status_code != 404, "lo público sigue"
    de_integrador = TestClient(servidor_http.crear_app(perfil="integrador"), base_url="http://localhost:8080")
    assert de_integrador.post("/v1/estado_de_cuenta", json={}).status_code != 404
    with pytest.raises(ValueError, match="no es uno de"):
        servidor_http.crear_app(perfil="privado")


def test_los_grupos_siguen_el_camino_de_un_mes():
    grupos = {}
    for h in DEL_MOTOR.herramientas.values():
        grupos.setdefault(h.grupo, []).append(h.nombre)
    assert grupos == {
        "leer": ["leer_xml_ubl", "leer_propuesta_sire"],
        "validar": ["validar_comprobantes", "normalizar_detracciones", "diagnosticar"],
        "asentar": ["generar_asiento", "exportar", "validar_partida_doble"],
        "informes": ["resumen", "por_cuenta", "estado_de_cuenta", "por_pagar"],
        "tesoreria": ["validar_cuentas_bancarias", "revisar_tesoreria"],
        "pcge": ["buscar_cuenta_pcge", "adaptar_pcge2026"],
        "catalogos": ["configuracion_por_defecto", "drivers_disponibles"],
    }
    assert nombres(crear_servidor(grupos=["leer", "pcge"])) == ["leer_xml_ubl", "leer_propuesta_sire",
                                                                "buscar_cuenta_pcge", "adaptar_pcge2026"]


def test_cada_herramienta_tiene_su_titulo_y_el_cliente_lo_ve():
    assert set(textos.TITULOS) == set(textos.PARA_HERRAMIENTA), "un título por herramienta, ni uno más"
    for h in asyncio.run(crear_servidor().list_tools()):
        assert h.title == textos.TITULOS[h.name] == h.annotations.title, h.name


# --- las perillas de contaperu-mcp ---------------------------------------------------------------------------------

def arrancado(monkeypatch, *argumentos: str):
    from contaperu.puertas import servidor_mcp

    visto = {}
    monkeypatch.setattr(servidor_mcp, "servir", lambda servidor, **opciones: visto.update(servidor=servidor, **opciones))
    servidor_mcp.main(list(argumentos))
    return visto


def test_sin_perillas_sirve_el_servidor_publico_de_siempre(monkeypatch):
    from contaperu.puertas import servidor_mcp

    assert arrancado(monkeypatch)["servidor"] is servidor_mcp.mcp


def test_las_perillas_eligen_lo_que_se_publica(monkeypatch):
    assert nombres(arrancado(monkeypatch, "--grupo", "leer")["servidor"]) == ["leer_xml_ubl", "leer_propuesta_sire"]
    assert nombres(arrancado(monkeypatch, "--herramienta", "exportar", "--herramienta", "diagnosticar")["servidor"]) == [
        "diagnosticar", "exportar"], "en el orden de la tabla"
    assert len(nombres(arrancado(monkeypatch, "--solo-lectura")["servidor"])) == 18, "ninguna del motor escribe"
    con_una_de_integrador(monkeypatch)
    assert "estado_de_cuenta" in nombres(arrancado(monkeypatch, "--perfil", "integrador")["servidor"])


def test_una_perilla_que_no_existe_se_dice_al_arrancar(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        arrancado(monkeypatch, "--grupo", "bancos")
    assert "«bancos» no es un grupo" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        arrancado(monkeypatch, "--perfil", "privado")
