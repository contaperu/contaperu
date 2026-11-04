"""Los catálogos del registro de compras de no domiciliados (15.6.0) y el convenio que le toca a un país.

Las seis tablas salen del Anexo 01 de la RS 040-2022 —la norma del SIRE—, transcritas del PDF de SUNAT con su texto y
no de memoria. Estos casos fijan lo que una transcripción podría torcer sin que nada fallara: cuántas filas tiene cada
tabla, los códigos que el registro real usa y las siete correcciones de cómo el PDF deja algunos nombres. Un código
publicado no se puede cambiar de significado después, así que el que los vigila es esto y no la memoria de nadie.
"""
from __future__ import annotations

import pathlib
from datetime import date

import pytest

from contaperu import api, catalogos

# Cuántas filas trae cada tabla en el anexo. Una fila perdida al transcribir —o una partida en dos— cambia el número.
FILAS = {"paises": 273, "vinculos_economicos": 13, "convenios_doble_imposicion": 10, "tipos_renta": 44,
         "modalidades_servicio": 3, "exoneraciones_no_domiciliado": 6}


def test_cada_tabla_tiene_las_filas_del_anexo():
    tablas = {"paises": catalogos.PAISES, "vinculos_economicos": catalogos.VINCULOS_ECONOMICOS,
              "convenios_doble_imposicion": catalogos.CONVENIOS_DOBLE_IMPOSICION, "tipos_renta": catalogos.TIPOS_RENTA,
              "modalidades_servicio": catalogos.MODALIDADES_SERVICIO,
              "exoneraciones_no_domiciliado": catalogos.EXONERACIONES_NO_DOMICILIADO}
    assert {nombre: len(tabla) for nombre, tabla in tablas.items()} == FILAS
    # Los códigos van completos y con su ancho: el país en cuatro dígitos; vínculo, convenio y renta en dos, empezando
    # por el 00; modalidad y exoneración en uno.
    assert all(len(c) == 4 and c.isdigit() for c in catalogos.PAISES)
    assert list(catalogos.VINCULOS_ECONOMICOS) == [f"{n:02d}" for n in range(13)]
    assert list(catalogos.CONVENIOS_DOBLE_IMPOSICION) == [f"{n:02d}" for n in range(10)]
    assert list(catalogos.TIPOS_RENTA) == [f"{n:02d}" for n in range(44)]
    assert list(catalogos.MODALIDADES_SERVICIO) == ["1", "2", "3"]
    assert list(catalogos.EXONERACIONES_NO_DOMICILIADO) == ["1", "2", "3", "4", "5", "6"]
    assert all(d.strip() for t in tablas.values() for d in t.values())


def test_los_paises_que_importan_tienen_su_codigo():
    """Los de los convenios, el de Estados Unidos —el del ejemplo del motor— y el del Perú."""
    esperados = {"9249": "ESTADOS UNIDOS", "9589": "PERU", "9211": "CHILE", "9149": "CANADA", "9105": "BRASIL",
                 "9493": "MEXICO", "9190": "COREA (SUR), REPUBLICA DE", "9767": "SUIZA", "9607": "PORTUGAL",
                 "9399": "JAPON", "9097": "BOLIVIA", "9169": "COLOMBIA", "9239": "ECUADOR"}
    assert {c: catalogos.PAISES[c] for c in esperados} == esperados
    assert catalogos.PAIS_PERU == "9589"


def test_las_siete_correcciones_del_pdf():
    """Tres nombres el PDF de SUNAT los trae con un «?» donde va una letra —su codificación—, y cuatro salen con las
    palabras pegadas al extraerlos. Se corrigieron a mano, cotejando con la vista del propio PDF, y la fuente lo dice."""
    assert catalogos.PAISES["9245"] == "ESPAÑA"
    assert catalogos.PAISES["9028"] == "ASCENCIÓN"
    assert catalogos.PAISES["9147"] == "CAMPIONE D'ITALIA"
    assert catalogos.PAISES["9002"] == "COTE D'IVOIRE"
    assert catalogos.PAISES["9010"] == "UNITED STATES MINOR OUTLYING ISLANDS"
    assert catalogos.PAISES["9218"] == "TAIWAN (FORMOSA)"
    assert catalogos.PAISES["9897"] == "ZONA NEUTRAL (PALESTINA)"
    assert not [d for d in catalogos.PAISES.values() if "?" in d]
    assert "Siete nombres se corrigieron" in catalogos.FUENTES["paises"]


def test_las_tablas_dicen_lo_que_dice_el_anexo():
    assert catalogos.CONVENIOS_DOBLE_IMPOSICION["00"] == "NINGUNO"
    assert catalogos.CONVENIOS_DOBLE_IMPOSICION["03"] == "COMUNIDAD ANDINA DE NACIONES (CAN)"
    assert catalogos.CONVENIOS_DOBLE_IMPOSICION["09"] == "OTROS"
    assert catalogos.VINCULOS_ECONOMICOS["00"] == "Sin vinculación."
    assert catalogos.VINCULOS_ECONOMICOS["06"].endswith("Reglamento de la LIR, art. 24, numeral 6")
    assert catalogos.TIPOS_RENTA["00"] == "Bienes"
    assert catalogos.TIPOS_RENTA["01"] == "Arrendamiento de predios — LIR art. 9° a)"
    # El de los servicios digitales, que es el de las suscripciones del exterior: el caso más común de un estudio.
    assert catalogos.TIPOS_RENTA["18"].startswith("Las obtenidas por servicios digitales")
    assert catalogos.TIPOS_RENTA["18"].endswith("LIR art. 9° i)")
    assert catalogos.TIPOS_RENTA["19"].endswith("LIR art. 9° j)")
    # La última columna, el código de la OCDE, no se transcribe: ningún «07 - 21» al final de una descripción.
    assert not [d for d in catalogos.TIPOS_RENTA.values() if d.rstrip().endswith(("07 - 21", " 13", " 8"))]
    assert catalogos.MODALIDADES_SERVICIO["3"] == "SERVICIO PRESTADO EXCLUSIVAMENTE EN EL EXTRANJERO"
    # Cada fuente cita la norma del SIRE y SU tabla: el número del PLE —35, 27, 25, 31, 32, 33— era otro.
    for nombre, tabla in (("paises", 16), ("vinculos_economicos", 17), ("convenios_doble_imposicion", 18),
                          ("tipos_renta", 19), ("modalidades_servicio", 20), ("exoneraciones_no_domiciliado", 21)):
        assert "RS 040-2022" in catalogos.FUENTES[nombre] and f"Tabla {tabla}" in catalogos.FUENTES[nombre], nombre


def test_los_catalogos_salen_por_la_fachada():
    sunat = api.catalogos_sunat()
    assert sunat["paises"] == catalogos.PAISES
    assert sunat["tipos_renta"] == catalogos.TIPOS_RENTA
    assert sunat["convenios_por_pais"] == catalogos.CONVENIOS_POR_PAIS
    assert sunat["fuentes"]["convenios_por_pais"] == catalogos.FUENTE_CONVENIOS


# ── El convenio que le toca a un país ─────────────────────────────────────────────────────────────────────────────

def test_cada_convenio_por_pais_apunta_a_un_codigo_que_existe():
    for pais, convenio in catalogos.CONVENIOS_POR_PAIS.items():
        assert pais in catalogos.PAISES
        assert convenio["convenio"] == "" or convenio["convenio"] in catalogos.CONVENIOS_DOBLE_IMPOSICION
        assert date.fromisoformat(convenio["desde"])
    # Los tres de la CAN comparten código; Japón es el único con convenio y sin código.
    assert {p for p, c in catalogos.CONVENIOS_POR_PAIS.items() if c["convenio"] == "03"} == {"9097", "9169", "9239"}
    assert [p for p, c in catalogos.CONVENIOS_POR_PAIS.items() if not c["convenio"]] == ["9399"]


@pytest.mark.parametrize("pais, fecha, convenio", [
    ("9211", "2026-09-10", "02"),            # Chile
    ("9149", date(2026, 9, 10), "01"),       # Canadá, con la fecha como `date`
    ("9169", "2026-09-10", "03"),            # Colombia, por la Decisión 578
    ("9105", "2026-09-10", "04"),            # Brasil
    ("9190", "2026-09-10", "06"),            # Corea del Sur
    ("9249", "2026-09-10", "00"),            # Estados Unidos: sin convenio
    ("9105", "2009-12-31", "00"),            # Brasil, un día antes de aplicarse
    ("9105", "2010-01-01", "04"),            # … y el día en que se aplica
    ("9211", None, "02"),                    # sin fecha se responde como si ya rigiera
])
def test_el_convenio_sugerido(pais, fecha, convenio):
    sugerido = catalogos.convenio_sugerido(pais, fecha)
    assert sugerido["convenio"] == convenio
    assert sugerido["motivo"].strip()


def test_japon_tiene_convenio_pero_no_codigo_y_no_se_inventa():
    sugerido = catalogos.convenio_sugerido("9399", "2026-09-10")
    assert sugerido["convenio"] == ""
    assert "Japón" in sugerido["instrumento"]
    assert "no le da código" in sugerido["motivo"]


def test_el_peru_y_un_pais_que_no_existe_no_tienen_sugerencia():
    """Un no domiciliado reside fuera: el 9589 en su país es un error de captura, y el motor lo dice en vez de sugerir
    «ninguno», que lo daría por bueno."""
    assert catalogos.convenio_sugerido("9589", "2026-09-10")["convenio"] == ""
    assert "Perú" in catalogos.convenio_sugerido("9589")["motivo"]
    assert catalogos.convenio_sugerido("1234")["convenio"] == ""
    assert catalogos.convenio_sugerido("")["convenio"] == ""


# ── El registro real ──────────────────────────────────────────────────────────────────────────────────────────────

# El TXT 080500 que SUNAT aceptó en setiembre de 2026, en `tests/fixtures/privado/sire/`. Es de un contribuyente real y
# está fuera de Git: si no está, el caso se salta. De él solo se leen códigos de catálogo, y los mensajes no muestran
# ningún dato.
PRIVADO = pathlib.Path(__file__).parent / "fixtures" / "privado" / "sire"


def _registro_real() -> list[list[str]]:
    archivos = sorted(PRIVADO.glob("LE*080500*.txt")) if PRIVADO.is_dir() else []
    if not archivos:
        pytest.skip("sin el registro de no domiciliados real en tests/fixtures/privado/sire (fuera de Git)")
    return [linea.split("|") for linea in archivos[0].read_text(encoding="utf-8").splitlines() if linea.strip()]


def test_los_codigos_del_registro_real_estan_en_los_catalogos():
    filas = _registro_real()
    columnas = {"paises": 16, "vinculos_economicos": 23, "convenios_doble_imposicion": 29, "tipos_renta": 31,
                "modalidades_servicio": 32, "exoneraciones_no_domiciliado": 30}
    tablas = {"paises": catalogos.PAISES, "vinculos_economicos": catalogos.VINCULOS_ECONOMICOS,
              "convenios_doble_imposicion": catalogos.CONVENIOS_DOBLE_IMPOSICION, "tipos_renta": catalogos.TIPOS_RENTA,
              "modalidades_servicio": catalogos.MODALIDADES_SERVICIO,
              "exoneraciones_no_domiciliado": catalogos.EXONERACIONES_NO_DOMICILIADO}
    for nombre, indice in columnas.items():
        fuera = {f[indice] for f in filas if f[indice] and f[indice] not in tablas[nombre]}
        assert not fuera, f"{nombre}: {len(fuera)} código(s) del registro real que el catálogo no tiene"
