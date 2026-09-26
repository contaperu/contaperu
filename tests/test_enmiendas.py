"""Las enmiendas del estándar: que existan, que estén bien formadas y que las `final` citen un test que corre.

Es el criterio de salida del hito E1 vuelto ejecutable. Sin esto, un estándar que promete no romper hasta la 2.0
tendría el mecanismo escrito y nada que lo obligue: una enmienda `final` podría citar un test que ya no existe, o un
nombre reservado del LEEME podría no tener su enmienda y nadie se enteraría.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ENMIENDAS = RAIZ / "estandar" / "enmiendas"
LEEME_ESTANDAR = RAIZ / "estandar" / "LEEME.md"

ESTADOS = {"borrador", "con caso real", "aceptada", "final", "reservada", "rechazada", "reemplazada"}
SECCIONES = ("## Motivación", "## Fuente", "## Especificación")
CABECERA = ("**Estado**", "**Compatibilidad**", "**Nivel**", "**Versión**", "**Test**")

# Los nombres reservados en el LEEME, que es el texto normativo. Cada uno tiene que tener su enmienda: es lo que
# impide que un nombre quede tomado en un sitio y libre en el otro.
# `medio_pago` salió de aquí el 25-sep-2026: entró en el estándar (enmienda 0004, `final`), y un nombre que
# ya existe no está reservado. Es el test diciendo la verdad sobre lo que hay, que es para lo que está.
RESERVADOS = ("id_en_destino", "dimensiones", "estado", "retencion_igv", "percepcion", "no_domiciliado")


def archivos() -> list[Path]:
    return sorted(p for p in ENMIENDAS.glob("*.md") if p.name != "LEEME.md")


def campo(texto: str, nombre: str) -> str:
    """El valor de una fila de la tabla de cabecera: `| **Estado** | reservada |`."""
    fila = re.search(rf"^\|\s*\*\*{nombre}\*\*\s*\|(.*)\|\s*$", texto, re.MULTILINE)
    return fila.group(1).strip() if fila else ""


def test_hay_enmiendas_y_el_indice_las_lista_todas():
    """El LEEME de las enmiendas es el índice: una que no esté ahí no la encuentra nadie."""
    indice = (ENMIENDAS / "LEEME.md").read_text(encoding="utf-8")
    assert archivos(), "no hay ninguna enmienda en estandar/enmiendas/"
    sin_listar = [p.name for p in archivos() if p.name not in indice]
    assert sin_listar == [], f"enmiendas que el índice no lista: {sin_listar}"


@pytest.mark.parametrize("ruta", archivos(), ids=lambda p: p.stem)
def test_cada_enmienda_esta_bien_formada(ruta: Path):
    texto = ruta.read_text(encoding="utf-8")
    numero = ruta.name[:4]
    assert re.match(r"^# \d{4} · .+", texto), "la primera línea es `# NNNN · título`"
    assert texto.startswith(f"# {numero} ·"), "el número del título y el del archivo son el mismo"
    for fila in CABECERA:
        assert campo(texto, fila.strip("*")), f"falta {fila} en la tabla de cabecera"
    for seccion in SECCIONES:
        assert seccion in texto, f"falta la sección {seccion}"
    assert campo(texto, "Estado") in ESTADOS, f"estado desconocido: {campo(texto, 'Estado')!r}"


@pytest.mark.parametrize("ruta", archivos(), ids=lambda p: p.stem)
def test_una_enmienda_final_cita_un_test_que_existe(ruta: Path):
    """Una `final` sin test es una promesa sin nada que la sostenga; es justo lo que este hito venía a evitar."""
    texto = ruta.read_text(encoding="utf-8")
    if campo(texto, "Estado") != "final":
        pytest.skip("solo las `final` tienen que citar un test")
    citado = campo(texto, "Test")
    assert citado not in ("", "—"), "una enmienda `final` cita el test que la sostiene"
    for referencia in re.findall(r"`?(tests/[\w./]+\.py)(?:::(\w+))?`?", citado):
        archivo, funcion = referencia
        ruta_test = RAIZ / archivo
        assert ruta_test.is_file(), f"el test citado no existe: {archivo}"
        if funcion:
            assert f"def {funcion}(" in ruta_test.read_text(encoding="utf-8"), \
                f"{archivo} no tiene la función {funcion}"


@pytest.mark.parametrize("reservado", RESERVADOS)
def test_cada_nombre_reservado_del_leeme_tiene_su_enmienda(reservado: str):
    """El LEEME reserva nombres y las enmiendas guardan su porqué: si uno aparece solo en el LEEME, el día que entre
    nadie sabrá qué se esperaba de él."""
    assert reservado in LEEME_ESTANDAR.read_text(encoding="utf-8"), \
        f"{reservado} ya no está reservado en el LEEME: su enmienda tiene que decir en qué versión entró"
    reservadas = [p.read_text(encoding="utf-8") for p in archivos()
                  if campo(p.read_text(encoding="utf-8"), "Estado") == "reservada"]
    assert any(f"`{reservado}`" in t or f"`linea.{reservado}`" in t for t in reservadas), \
        f"ningún archivo de enmienda reservada nombra {reservado}"
