"""La CLI genera el TXT del SIRE desde XML locales, sin API ni portal."""
import json
import zipfile

from contaperu import cli
from util import GOLDEN, XML


def test_generar_desde_xml(tmp_path, capsys):
    salida = tmp_path / "salida"
    codigo = cli.main([
        "generar", "--tipo", "venta", "--ruc", "20131312955", "--razon", "EMISOR DE PRUEBA S.A.C.",
        "--periodo", "202601", "--salida", str(salida), "--json", str(tmp_path / "datos.json"),
        str(XML / "20131312955-01-F001-123.xml"), str(XML / "20131312955-03-B001-55.xml"),
        str(XML / "R-20131312955-01-F001-123.xml"), str(tmp_path / "no-existe.xml"),
    ])
    out = capsys.readouterr().out
    assert codigo == 0
    assert "1 ignorados" in out and "no-existe.xml: No existe" in out
    nombres = sorted(p.name for p in salida.iterdir())
    # "todas" = los drivers de TXT, que desde la muerte del PLE es solo el SIRE
    assert nombres == [
        "LE2013131295520260100140400021112.TXT", "LE2013131295520260100140400021112.zip",
    ]
    with zipfile.ZipFile(salida / "LE2013131295520260100140400021112.zip") as z:
        assert z.namelist() == ["LE2013131295520260100140400021112.TXT"]
    datos = json.loads((tmp_path / "datos.json").read_text(encoding="utf-8"))
    assert [c["numero"] for c in datos["comprobantes"]] == ["123", "55"]


def test_errores_bloquean_salvo_flag(tmp_path, capsys):
    args = ["generar", "--tipo", "venta", "--ruc", "20131312955", "--razon", "X", "--periodo", "202601",
            "--driver", "sire", "--salida", str(tmp_path / "s"), str(XML / "20131312955-01-F001-124.xml")]
    assert cli.main(args) == 1                      # USD sin tipo de cambio → error
    assert "TC_FALTA" in capsys.readouterr().out
    assert not (tmp_path / "s").exists()
    assert cli.main(args + ["--incluir-errores"]) == 0
    assert (tmp_path / "s" / "LE2013131295520260100140400021112.zip").exists()


def test_desde_json(tmp_path):
    assert cli.main(["desde-json", str(GOLDEN / "compras_202601.json"), "--driver", "sire", "--salida", str(tmp_path)]) == 0
    assert (tmp_path / "LE2060123456720260100080400021112.TXT").read_bytes().count(b"\r\n") == 3


def test_la_consola_de_windows_no_tumba_el_cli(monkeypatch):
    """La consola de Windows es cp1252 y el CLI imprime flechas y tildes. Que se caiga al
    IMPRIMIR, con los archivos ya escritos, seria absurdo."""
    from contaperu.cli import _consola_utf8

    class SinReconfigure:
        encoding = "cp1252"

    monkeypatch.setattr("sys.stdout", SinReconfigure())
    _consola_utf8()          # no revienta aunque el flujo no sepa reconfigurarse
