"""El vocabulario del estándar en catálogos publicados: una sola fuente, y lo que degrada y lo que no.

Hasta la 1.0 los roles y los tipos de libro vivían **dos veces** —enum en el esquema y tupla en el código— y ningún
test comparaba las copias: podían separarse sin que nadie se enterara. Ahora hay una sola fuente,
`estandar/catalogos.json`, y estos tests la atan al código y al esquema.
"""
from __future__ import annotations

import json

import pytest

from contaperu import api, vocabulario
from contaperu.asiento.motor import ROLES
from contaperu.modelo import TIPOS_LIBRO

# Los valores de la 1.0, escritos a mano. Si alguien añade uno, este test se pone rojo y hay que decidirlo a
# propósito: abrir el catálogo no era para que crezcan (John, 18-sep-2026), sino para que un hecho nuevo pueda
# traer los suyos sin subir la versión del estándar.
ROLES_DE_LA_1_0 = ("principal", "igv", "retencion_4ta", "tercero", "detraccion_tercero", "detraccion")
CLASES_DE_LA_1_0 = ("activo", "pasivo", "patrimonio", "ingreso", "gasto")
TIPOS_DE_LIBRO_DE_LA_1_0 = ("venta", "compra")


def test_los_valores_de_la_1_0_no_cambian():
    assert vocabulario.ROLES == ROLES_DE_LA_1_0
    assert vocabulario.CLASES == CLASES_DE_LA_1_0
    assert vocabulario.TIPOS_LIBRO == TIPOS_DE_LIBRO_DE_LA_1_0


def test_el_codigo_y_el_catalogo_son_lo_mismo():
    """El hueco que este cambio cierra: `ROLES` y `TIPOS_LIBRO` estaban escritos en el código y otra vez como enum
    del esquema, sin nada que los comparara. Ahora salen del catálogo, así que no pueden separarse."""
    assert ROLES is vocabulario.ROLES
    assert TIPOS_LIBRO is vocabulario.TIPOS_LIBRO


def test_cada_catalogo_trae_su_fuente_y_su_version():
    """Ninguno entra sin las dos cosas: se versionan aparte del documento, así que hay que poder decir cuál se leyó."""
    for nombre in ("roles", "clases", "tipos_de_libro"):
        assert vocabulario.FUENTES[nombre].strip()
        assert vocabulario.VERSIONES[nombre].strip()


def test_cada_valor_esta_descrito():
    """Un catálogo publicado sin decir qué significa cada valor obliga a preguntar, que es lo que viene a evitar."""
    for tabla in vocabulario.catalogos().values():
        assert tabla["codigos"] and all(texto.strip() for texto in tabla["codigos"].values())


def test_el_esquema_ya_no_los_enumera():
    """Es el cambio de fondo: el día que entre un hecho nuevo, sus roles no cuestan una versión del estándar."""
    esquema = api.esquema_open_accounting()
    assert "enum" not in esquema["$defs"]["linea"]["properties"]["rol"]
    assert "enum" not in esquema["$defs"]["libro"]["properties"]["tipo"]
    # Y el catálogo se cita en la descripción, para que quien lea el esquema sepa dónde están los valores.
    assert "catalogos.json" in esquema["$defs"]["linea"]["properties"]["rol"]["description"]


def test_la_api_los_sirve_con_su_fuente():
    servidos = api.catalogos_del_estandar()
    assert set(servidos) == {"roles", "clases", "tipos_de_libro"}
    assert list(servidos["roles"]["codigos"]) == list(ROLES_DE_LA_1_0)
    assert servidos["clases"]["fuente"] == vocabulario.FUENTES["clases"]


def test_van_aparte_de_los_de_sunat():
    """Los de SUNAT se copian de la norma; estos se gobiernan. Mezclarlos borraría esa frontera — y además
    `tests/test_catalogos.py` exige que el archivo de SUNAT tenga exactamente sus tres tablas."""
    assert set(api.catalogos_sunat()) & set(api.catalogos_del_estandar()) == set()


# ── La degradación, que no es igual para los dos ───────────────────────────────────────────────────────────────

def test_un_rol_desconocido_no_rompe_la_linea():
    """La regla que hace escalable el estándar: quien recibe contabiliza con `clase`, `debe_haber` e `importe` aunque
    no conozca el rol. Un rol nuevo —la percepción, el anticipo— entra sin romper a ningún ERP ya integrado."""
    from contaperu.asiento.lineas import LineaDiario

    linea = LineaDiario.de_dict({"cuenta": "421201", "debe_haber": "H", "importe": "100.00",
                                 "clase": "pasivo", "rol": "percepcion"})
    assert linea.rol == "percepcion" and linea.clase == "pasivo"
    doc = {"open_accounting": api.OPEN_ACCOUNTING,
           "libro": {"ruc": "20601234567", "periodo": "202601", "tipo": "compra"},
           "asiento": [linea.a_dict()]}
    import jsonschema
    assert list(jsonschema.Draft202012Validator(api.esquema_open_accounting()).iter_errors(doc)) == []


def test_un_tipo_de_libro_desconocido_si_rompe_y_es_a_proposito():
    """`libro.tipo` no degrada como el rol: quien recibe un registro que no conoce no puede adivinar qué hacer con
    él. Abrir el catálogo significa que crece sin subir versión, no que valga cualquier cosa."""
    from contaperu.modelo import Libro

    with pytest.raises(ValueError, match="Tipo de libro inválido"):
        Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202601", tipo="banco")


def test_el_destino_que_no_declara_un_libro_lo_rechaza_limpio():
    """La otra mitad de esa degradación: no la hace el documento, la hace el driver, diciendo qué libros lleva."""
    from contaperu.drivers import asiento_neutral, formato_de, sire

    assert set(sire.FORMATOS) == set(TIPOS_DE_LIBRO_DE_LA_1_0)
    assert formato_de("asiento_neutral", "compra") == "asiento_neutral_json"
    assert asiento_neutral.FORMATOS.get("banco") is None


def test_el_catalogo_viaja_donde_el_esquema():
    """Vive junto al esquema para citarse por la URL del tag del estándar, y por tanto necesita su propia línea de
    `force-include`: si falta, la rueda instalada no lo encuentra y el motor no arranca."""
    from pathlib import Path

    from contaperu import _datos

    assert json.loads(_datos.del_estandar(_datos.CATALOGOS_DEL_ESTANDAR).decode("utf-8"))
    pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert '"estandar/catalogos.json"' in pyproject
